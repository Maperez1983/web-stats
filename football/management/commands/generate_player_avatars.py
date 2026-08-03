"""Genera OFFLINE el avatar de cada jugador (face-swap con su foto + peinado + color + altura).

Es un paso LOCAL: depende de insightface (+ modelo inswapper_128.onnx) que NO están en producción.
Los imports pesados son perezosos para que importar este módulo (p. ej. en `manage.py check` en
prod) no falle. El resultado se guarda en Player.avatar_generated y el resolver lo sirve en
pizarra / 11 / editor. Regenera solo si cambian las entradas (avatar_source_key).

Uso:
    python manage.py generate_player_avatars --listar               # quien esta pendiente (vale en prod)
    python manage.py generate_player_avatars --pendientes --club 1  # solo un club
    python manage.py generate_player_avatars --pendientes --equipo 3
    python manage.py generate_player_avatars --pendientes    # barre la cola
    python manage.py generate_player_avatars --all
    python manage.py generate_player_avatars --player 42 --force

El CUERPO no es siempre el mismo: cada tramo de edad tiene el suyo (ver FIGURAS), porque un nino
de ocho anos no es un adulto pequeno. Sin fecha de nacimiento no se sabe cual le toca y no se
genera nada: es preferible quedarse sin avatar a ponerle a un benjamin un cuerpo de adulto.

Config de rutas (opcional):
    AVATAR_INSWAPPER=/ruta/inswapper_128.onnx   (por defecto ~/ai-image-gen/inswapper_128.onnx)
"""
import hashlib
import io
import os

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from football.models import Player

STYLE_OVERLAYS = {"medio": "medio.png", "rizado": "rizado.png", "largo": "largo.png"}  # 'corto'/'' = pelo base
# Paleta de grado de piel 1-6 (igual que views.AVATAR_SKIN_GRADES) para el avatar SIN foto.
AVATAR_SKIN_GRADES = {
    1: (236, 205, 178), 2: (224, 176, 136), 3: (200, 144, 95),
    4: (165, 106, 60), 5: (109, 67, 40), 6: (74, 45, 26),
}


def _asset(*parts):
    from pathlib import Path
    for base in (
        Path(settings.BASE_DIR) / "football" / "static" / "football" / "images" / "coach_roster_avatars",
        Path(settings.BASE_DIR) / "static" / "football" / "images" / "coach_roster_avatars",
    ):
        p = base.joinpath(*parts)
        if p.exists():
            return str(p)
    return None


def _find_player_photo_name(player):
    """La foto del jugador NO es un campo del modelo: se guarda por convención en
    player-photos/player-<id>.<ext>. Devuelve el nombre de almacenamiento que exista, o ''."""
    from django.core.files.storage import default_storage
    pid = int(getattr(player, "id", 0) or 0)
    if not pid:
        return ""
    for ext in ("png", "jpg", "jpeg", "webp"):
        name = f"player-photos/player-{pid}.{ext}"
        try:
            if default_storage.exists(name):
                return name
        except Exception:
            pass
    return ""


# CATALOGO DE FIGURAS BASE, POR EDAD.
#
# Durante mucho tiempo hubo una sola figura, kit_home_hd.png, que es un CUERPO DE ADULTO. Ponerle
# la cara de un nino de 8 anos encima no produce "el nino": produce un adulto con su cara, que es
# otra cosa y no se le puede ensenar a su familia. Y escalar tampoco lo arregla: un nino no es un
# adulto pequeno, cambian las proporciones empezando por el tamano de la cabeza.
#
# Por eso cada tramo de edad tiene su propio cuerpo, y cada tramo tiene VARIAS variantes: si
# hubiera una sola, un equipo de veinte ninos serian veinte clones con caras distintas.
#
# Las mascaras van por convencion: masks/hair_<clave>.png y masks/skin_<clave>.png. El adulto
# conserva los nombres que ya tenia. `overlays` marca la unica figura sobre la que estan alineados
# los peinados postizos (hairstyles/*.png): en las demas el peinado solo cambia de color.
FIGURAS = (
    {"clave": "peque_a", "png": "nino_peque_a_hd.png", "desde": 0, "hasta": 9},
    {"clave": "peque_b", "png": "nino_peque_b_hd.png", "desde": 0, "hasta": 9},
    {"clave": "peque_c", "png": "nino_peque_c_hd.png", "desde": 0, "hasta": 9},
    {"clave": "medio_a", "png": "nino_medio_a_hd.png", "desde": 10, "hasta": 13},
    {"clave": "medio_b", "png": "nino_medio_b_hd.png", "desde": 10, "hasta": 13},
    {"clave": "ado_a", "png": "nino_ado_a_hd.png", "desde": 14, "hasta": 15},
    {"clave": "ado_b", "png": "nino_ado_b_hd.png", "desde": 14, "hasta": 15},
    {"clave": "adulto", "png": "kit_home_hd.png", "desde": 16, "hasta": 200,
     "hair": "hair_home.png", "skin": "skin_home.png", "overlays": True},
)


ADULTO = next(f for f in FIGURAS if f["clave"] == "adulto")


def edad_de(player, hoy=None):
    """Edad en anos a partir de la fecha de nacimiento. None si no se sabe."""
    import datetime
    fecha = getattr(player, 'birth_date', None)
    if not fecha:
        return None
    hoy = hoy or datetime.date.today()
    try:
        return hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
    except Exception:
        return None


_INSTALADAS = {}


def _figura_instalada(figura):
    """¿Estan en disco el PNG de la figura y sus dos mascaras? (se pregunta una vez por proceso)"""
    if not figura:
        return False
    clave = figura["clave"]
    if clave not in _INSTALADAS:
        _INSTALADAS[clave] = all((
            _asset("library", figura["png"]),
            _asset("masks", figura.get("hair") or f"hair_{clave}.png"),
            _asset("masks", figura.get("skin") or f"skin_{clave}.png"),
        ))
    return _INSTALADAS[clave]


def figura_para(player, solo_instaladas=True):
    """
    Que cuerpo le toca a este jugador. None si no se puede saber.

    El reparto entre variantes es por id, no al azar: tiene que ser el MISMO en cada pasada, o
    cada regeneracion le cambiaria el cuerpo al jugador.
    """
    edad = edad_de(player)
    if edad is None:
        return None
    candidatas = [f for f in FIGURAS if f["desde"] <= edad <= f["hasta"]]
    if solo_instaladas:
        candidatas = [f for f in candidatas if _figura_instalada(f)]
    if not candidatas:
        return None
    return candidatas[int(getattr(player, "id", 0) or 0) % len(candidatas)]


def figura_apta(player, edad_minima=None):
    """
    ¿Hay un cuerpo para este jugador? (si/no, motivo)

    Sin fecha de nacimiento se dice que NO: mejor quedarse sin avatar que arriesgarse a ponerle un
    cuerpo de adulto a un alevin porque falte un dato.

    `edad_minima` se mantiene por compatibilidad con la opcion --edad-minima: si se pasa, ademas
    hay que llegar a esa edad.
    """
    edad = edad_de(player)
    if edad is None:
        return False, 'sin fecha de nacimiento'
    if edad_minima and edad < int(edad_minima):
        return False, f'{edad} anos (por debajo del minimo pedido)'
    if figura_para(player) is None:
        return False, f'no hay figura instalada para {edad} anos'
    return True, ''


def avatar_pendiente(player):
    """
    ¿A este jugador le falta el avatar o lo tiene desactualizado?

    Es la regla que decide la COLA: hay material para generarlo (foto o características) y el
    avatar guardado no corresponde a ese material. Vive aquí, junto al generador, para que la
    pantalla que lo avisa y el comando que lo hace no puedan discrepar.
    """
    if player is None:
        return False
    try:
        photo_name = _find_player_photo_name(player)
    except Exception:
        return False
    hay_material = bool(
        getattr(player, "skin_grade", None)
        or (getattr(player, "hairstyle", "") or "").strip()
        or (getattr(player, "hair_color", "") or "").strip()
        or getattr(player, "height_cm", None)
        or photo_name
    )
    if not hay_material:
        return False
    # Sin cuerpo para su edad no hay nada que generar: marcarlo como pendiente seria enviar al
    # entrenador a rellenar datos que no van a producir ningun avatar.
    if not figura_apta(player)[0]:
        return False
    try:
        return _inputs_key(player, photo_name) != (getattr(player, "avatar_source_key", "") or "")
    except Exception:
        return False


def cola_avatares(queryset=None):
    """
    Reparte la plantilla en tres montones. Los dos primeros son trabajo mío; el tercero es del
    entrenador: sin foto ni características no hay nada que generar.
    """
    qs = queryset if queryset is not None else Player.objects.filter(is_active=True)
    pendientes, al_dia, sin_material = [], [], []
    for player in qs.order_by("number", "name"):
        try:
            hay_foto = bool(_find_player_photo_name(player))
        except Exception:
            hay_foto = False
        hay_material = bool(
            hay_foto
            or getattr(player, "skin_grade", None)
            or (getattr(player, "hairstyle", "") or "").strip()
            or (getattr(player, "hair_color", "") or "").strip()
            or getattr(player, "height_cm", None)
        )
        if not hay_material:
            sin_material.append(player)
        elif not figura_apta(player)[0]:
            # No es trabajo pendiente: es que no hay figura para su edad.
            sin_material.append(player)
        elif avatar_pendiente(player):
            pendientes.append(player)
        else:
            al_dia.append(player)
    return pendientes, al_dia, sin_material


def _inputs_key(player, photo_name=""):
    """Hash de las entradas del avatar. Agnóstico del almacenamiento (local o S3): usa
    name+size del fichero de foto (resuelto por convención) + características."""
    from django.core.files.storage import default_storage
    h = hashlib.sha1()
    if photo_name:
        try:
            h.update(f"{photo_name}:{default_storage.size(photo_name)}".encode())
        except Exception:
            h.update(photo_name.encode())
    else:
        h.update(b"nophoto")
    for v in (player.hairstyle, player.hair_color, player.skin_grade, player.height_cm):
        h.update(f"|{v}".encode())
    # El cuerpo cuenta como entrada: si cumple anos y pasa de benjamin a cadete, su avatar esta
    # desactualizado aunque no haya tocado ni la foto ni el pelo.
    _fig = figura_para(player)
    h.update(f"|fig:{(_fig or {}).get('clave', '')}".encode())
    return h.hexdigest()


def _read_photo_bgr(photo_name):
    """Lee la foto (local o S3) como BGR para OpenCV, vía la API de almacenamiento (no .path)."""
    import numpy as np
    import cv2
    from django.core.files.storage import default_storage
    try:
        f = default_storage.open(photo_name, "rb")
        data = f.read()
        f.close()
    except Exception:
        return None
    if not data:
        return None
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def _recolor_rgb(arr, mask01, rgb):
    """Recolorea (in place) la zona (mask 0-1) al RGB dado, conservando la luminancia (V)."""
    import colorsys
    import numpy as np
    if not rgb:
        return
    th, ts, _ = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])
    lut = np.array([colorsys.hsv_to_rgb(th, ts, v / 255.0) for v in range(256)]) * 255
    v_idx = np.max(arr[:, :, :3], axis=2).astype(np.int32).clip(0, 255)
    tint = lut[v_idx]
    mm = mask01[..., None]
    arr[:, :, :3] = arr[:, :, :3] * (1 - mm) + tint * mm


def _recolor_hair(arr, mask01, hair_hex):
    """Recolorea el pelo (mask 0-1) al hex '#rrggbb'."""
    try:
        hc = str(hair_hex).lstrip("#")
        _recolor_rgb(arr, mask01, (int(hc[0:2], 16), int(hc[2:4], 16), int(hc[4:6], 16)))
    except Exception:
        return


def _ambito(opts):
    """
    A quien alcanza el comando. Sin filtros son TODOS los jugadores activos de TODOS los clubes:
    en una plataforma con varios clubes eso es generar avatares ajenos con tu maquina.
    """
    qs = Player.objects.filter(is_active=True)
    if opts.get("equipo"):
        qs = qs.filter(team_id=opts["equipo"])
    if opts.get("club"):
        # `Team.club` es la clave real; `Team.workspace` es la relacion INVERSA de Workspace y no
        # se puede filtrar por ahi.
        qs = qs.filter(team__club_id=opts["club"])
    return qs


class Command(BaseCommand):
    help = "Genera el avatar por jugador: face-swap si tiene foto, si no sintético (piel/peinado/altura)."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Todos los jugadores activos (con foto o por características).")
        parser.add_argument("--player", type=int, default=0, help="Solo este id de jugador.")
        parser.add_argument("--force", action="store_true", help="Regenerar aunque no cambien las entradas.")
        parser.add_argument("--pendientes", action="store_true", help="Solo los que tienen el avatar pendiente (la cola).")
        parser.add_argument("--equipo", type=int, default=0, help="Limita a un equipo (id).")
        parser.add_argument("--club", type=int, default=0, help="Limita a un club/espacio de trabajo (id).")
        parser.add_argument("--edad-minima", type=int, default=0,
                            help="Salta a los menores de esta edad (por defecto no salta a nadie: cada tramo tiene su figura).")
        parser.add_argument("--listar", action="store_true", help="Enseña la cola y sale. No necesita insightface: sirve tambien en produccion.")

    def handle(self, *args, **opts):
        # --listar va PRIMERO, antes de los imports pesados: asi se puede mirar la cola en
        # produccion, donde insightface no existe.
        if opts.get("listar"):
            pendientes, al_dia, sin_material = cola_avatares(_ambito(opts))
            self.stdout.write(f"Al dia:        {len(al_dia)}")
            self.stdout.write(f"Pendientes:    {len(pendientes)}")
            for p in pendientes:
                self.stdout.write(f"   · {p.number or '-'} {p.name}")
            self.stdout.write(f"Sin material:  {len(sin_material)}  (falta foto o caracteristicas; esto no lo arregla el comando)")
            for p in sin_material:
                self.stdout.write(f"   · {p.number or '-'} {p.name}")
            return

        import cv2
        import numpy as np
        from PIL import Image
        import insightface
        from insightface.app import FaceAnalysis

        if not _figura_instalada(ADULTO):
            self.stderr.write("Falta la figura base de adulto o sus máscaras."); return
        # Ruta del modelo: env AVATAR_INSWAPPER, si no varias rutas conocidas (donde lo deja el
        # build en Render = BASE_DIR/vendor, o el venv local del Mac). Robusto aunque falte la env.
        _model_candidates = [
            os.environ.get("AVATAR_INSWAPPER") or "",
            os.path.join(str(settings.BASE_DIR), "vendor", "inswapper_128.onnx"),
            os.path.expanduser("~/ai-image-gen/inswapper_128.onnx"),
        ]
        model_path = next((p for p in _model_candidates if p and os.path.exists(p)), "")
        if not model_path:
            self.stderr.write(f"No encuentro inswapper_128.onnx (probado: {[p for p in _model_candidates if p]}). Define AVATAR_INSWAPPER."); return

        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        # det_size reducido (menos memoria; ayuda en instancias de 2 GB). Configurable por env.
        try:
            _det = int(os.environ.get("AVATAR_DET_SIZE") or 320)
        except Exception:
            _det = 320
        app.prepare(ctx_id=-1, det_size=(_det, _det))
        swapper = insightface.model_zoo.get_model(model_path, download=False, providers=["CPUExecutionProvider"])

        # Las figuras se cargan a demanda y se guardan: detectar la cara de cada cuerpo cuesta, y
        # en una plantilla de veinte niños el mismo cuerpo se repite muchas veces.
        _figuras_cargadas = {}

        def cargar_figura(figura):
            clave = figura["clave"]
            if clave in _figuras_cargadas:
                return _figuras_cargadas[clave]
            rgba = np.asarray(Image.open(_asset("library", figura["png"])).convert("RGBA"))
            bgr = rgba[:, :, :3][:, :, ::-1].copy()
            caras = app.get(bgr)
            if not caras:
                _figuras_cargadas[clave] = None
                return None
            cara = sorted(caras, key=lambda f: (f.bbox[2] - f.bbox[0]))[-1]
            pelo = np.asarray(Image.open(
                _asset("masks", figura.get("hair") or f"hair_{clave}.png")
            ).convert("L")).astype(np.float32) / 255.0
            _piel = _asset("masks", figura.get("skin") or f"skin_{clave}.png")
            piel = (np.asarray(Image.open(_piel).convert("L")).astype(np.float32) / 255.0) if _piel else None
            datos = {"bgr": bgr, "alpha": rgba[:, :, 3], "cara": cara, "pelo": pelo, "piel": piel,
                     "overlays": bool(figura.get("overlays"))}
            _figuras_cargadas[clave] = datos
            return datos

        if cargar_figura(ADULTO) is None:
            self.stderr.write("No se detecta cara en la figura base de adulto."); return

        # Figura base DEDICADA para el rapado (buzz generado nativo): el face-swap va sobre ella,
        # sin overlay ni recolor. El rapado no funciona como overlay (se pega al cráneo).
        rapado_path = _asset("library", "kit_rapado_hd.png")
        rapado_bgr = rapado_alpha = rapado_face = None
        if rapado_path:
            _r = np.asarray(Image.open(rapado_path).convert("RGBA"))
            rapado_alpha = _r[:, :, 3]
            rapado_bgr = _r[:, :, :3][:, :, ::-1].copy()
            _rf = app.get(rapado_bgr)
            if _rf:
                rapado_face = sorted(_rf, key=lambda f: (f.bbox[2] - f.bbox[0]))[-1]

        qs = _ambito(opts)
        if opts["player"]:
            qs = Player.objects.filter(id=opts["player"])
        elif opts.get("pendientes"):
            # La cola: el comando ya no decide a quien le toca, lo dice el estado de los datos.
            pendientes, _al_dia, sin_material = cola_avatares(qs)
            if not pendientes:
                self.stdout.write("No hay nada pendiente.")
                if sin_material:
                    self.stdout.write(f"({len(sin_material)} jugadores sin foto ni caracteristicas: eso hay que rellenarlo a mano.)")
                return
            qs = Player.objects.filter(id__in=[p.id for p in pendientes])
            self.stdout.write(f"Cola: {len(pendientes)} jugadores.")
        elif not opts["all"]:
            self.stderr.write("Indica --all, --pendientes, --listar o --player <id>."); return

        # Altura por PERCENTIL de la plantilla: el más bajo del equipo -> escala mínima, el más
        # alto -> máxima, anclando en p10-p90 para que un outlier no comprima al resto (la mediana
        # queda en ~1.0). Usa SIEMPRE la plantilla completa, no solo los que se regeneran ahora.
        # Nota: si cambia mucho la plantilla, relanza con --force para refrescar la escala de todos.
        # Altura por percentil DE SU EQUIPO. Antes el percentil se sacaba de TODA la tabla, no de la
        # plantilla: con alevines de 1,40 y seniors de 1,90 -y varios clubes en la misma base- los
        # anclajes p10/p90 no describian a nadie, asi que un senior salia aplastado y un nino
        # estirado. El comentario decia "la plantilla completa"; la consulta no la filtraba.
        # El techo es 1.0 y no 1.12 por una razon concreta: la figura ampliada se pega con los pies
        # abajo dentro de un lienzo del mismo tamano, asi que todo lo que pase de 1.0 se sale por
        # arriba y al mas alto de cada plantilla se le cortaba la cabeza. Encogiendo a los bajos en
        # vez de estirar a los altos se mantiene la diferencia relativa y no se pierde a nadie.
        HEIGHT_MIN_F, HEIGHT_MAX_F = 0.86, 1.0
        _percentiles = {}

        def _anclas(team_id):
            if team_id in _percentiles:
                return _percentiles[team_id]
            alturas = sorted(
                h for h in Player.objects.filter(is_active=True, team_id=team_id).values_list("height_cm", flat=True) if h
            )
            par = (alturas[int(0.10 * (len(alturas) - 1))], alturas[int(0.90 * (len(alturas) - 1))]) if len(alturas) >= 3 else (None, None)
            _percentiles[team_id] = par
            return par

        def _height_factor(player):
            h_cm = getattr(player, "height_cm", None)
            lo, hi = _anclas(getattr(player, "team_id", None))
            if not h_cm or lo is None or hi <= lo:
                return 1.0
            t = max(0.0, min(1.0, (h_cm - lo) / (hi - lo)))
            return HEIGHT_MIN_F + t * (HEIGHT_MAX_F - HEIGHT_MIN_F)

        done = skipped = failed = menores = 0
        for player in qs:
            # Porteros: la figura base es de campo -> no se les genera avatar de campo (usan su PNG GK).
            _pos = str(getattr(player, "position", "") or "").strip().lower()
            if _pos in {"por", "gk"} or "porter" in _pos or "goalkeep" in _pos:
                continue
            # Cada edad tiene su cuerpo; sin fecha de nacimiento no se sabe cual y no se toca.
            _apta, _motivo = figura_apta(player, opts.get("edad_minima") or 0)
            if not _apta:
                menores += 1
                self.stdout.write(f"· {player.id} {player.name} — sin cuerpo para su edad ({_motivo})")
                continue
            figura = figura_para(player)
            photo_name = _find_player_photo_name(player)
            has_photo = bool(photo_name)
            # Nada que personalizar y sin foto -> se deja la figura estática (resolver cae al PNG base).
            if not has_photo and not (
                player.skin_grade or player.hairstyle or player.hair_color or player.height_cm
            ):
                continue
            key = _inputs_key(player, photo_name)
            if key == player.avatar_source_key and player.avatar_generated and not opts["force"]:
                skipped += 1
                continue
            try:
                # ¿Hay cara utilizable en la foto? Si sí -> face-swap; si no -> sintético.
                sface = None
                if has_photo:
                    src = _read_photo_bgr(photo_name)
                    sfaces = app.get(src) if src is not None else []
                    if sfaces:
                        sface = sorted(sfaces, key=lambda f: (f.bbox[2] - f.bbox[0]))[-1]

                cuerpo = cargar_figura(figura)
                if cuerpo is None:
                    failed += 1
                    self.stderr.write(f"✗ {player.id} {player.name}: no se detecta cara en la figura {figura['clave']}")
                    continue
                hair_mask, skin_mask = cuerpo["pelo"], cuerpo["piel"]
                kps = cuerpo["cara"].kps

                style = (player.hairstyle or "").strip().lower()
                # El rapado tiene figura propia, pero SOLO de adulto: a un benjamin no se le puede
                # poner ese cuerpo por el peinado.
                use_rapado = style == "rapado" and rapado_face is not None and figura["clave"] == "adulto"
                b_bgr, b_alpha, b_face = (
                    (rapado_bgr, rapado_alpha, rapado_face) if use_rapado
                    else (cuerpo["bgr"], cuerpo["alpha"], cuerpo["cara"])
                )

                if sface is not None:
                    # CON foto: face-swap de su cara real sobre la figura elegida.
                    res = swapper.get(b_bgr.copy(), b_face, sface, paste_back=True)
                    arr = np.dstack([res[:, :, ::-1], b_alpha]).astype(np.float32)
                else:
                    # SIN foto (o sin cara): sintético = figura base + grado de piel del jugador.
                    arr = np.dstack([b_bgr[:, :, ::-1], b_alpha]).astype(np.float32)
                    if not use_rapado and player.skin_grade and skin_mask is not None:
                        _recolor_rgb(arr, skin_mask, AVATAR_SKIN_GRADES.get(int(player.skin_grade)))

                if use_rapado:
                    style = ""  # rapado ya resuelto por la figura dedicada; sin overlay/recolor

                if style in STYLE_OVERLAYS and not cuerpo["overlays"]:
                    # Los peinados postizos estan recortados y colocados sobre la cabeza del
                    # adulto; encima de un niño quedarian a otra escala y fuera de sitio. En esas
                    # figuras el peinado se queda en el color, que si es suyo.
                    style = ""

                if style in STYLE_OVERLAYS:
                    # borrar pelo base (cuero cabelludo con su tono de frente) + overlay del peinado
                    ex, ey = int((kps[0][0] + kps[1][0]) / 2), int((kps[0][1] + kps[1][1]) / 2)
                    scalp = np.median(arr[ey - 34:ey - 14, ex - 16:ex + 16, :3].reshape(-1, 3), axis=0) * 0.9
                    mm = cv2.GaussianBlur((hair_mask * 255).astype(np.uint8), (9, 9), 0).astype(np.float32) / 255.0
                    arr[:, :, :3] = arr[:, :, :3] * (1 - mm[..., None]) + scalp * mm[..., None]
                    ov_path = _asset("hairstyles", STYLE_OVERLAYS[style])
                    ov = np.asarray(Image.open(ov_path).convert("RGBA")).astype(np.float32)
                    oa = (ov[:, :, 3:4] / 255.0)
                    if player.hair_color:
                        _recolor_hair(ov, ov[:, :, 3] / 255.0, player.hair_color)
                    arr[:, :, :3] = arr[:, :, :3] * (1 - oa) + ov[:, :, :3] * oa
                    arr[:, :, 3] = np.maximum(arr[:, :, 3], ov[:, :, 3])
                elif player.hair_color:
                    _recolor_hair(arr, hair_mask, player.hair_color)

                # altura: escala la figura (pies abajo) según el percentil de la plantilla.
                out = Image.fromarray(arr.astype("uint8"), "RGBA")
                f = _height_factor(player)
                if abs(f - 1.0) > 0.01:
                    W, H = out.size
                    sc = out.resize((max(1, int(W * f)), max(1, int(H * f))), Image.LANCZOS)
                    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    canvas.paste(sc, ((W - sc.width) // 2, H - sc.height), sc)
                    out = canvas

                buf = io.BytesIO(); out.save(buf, "PNG")
                player.avatar_generated.save(f"player-{player.id}.png", ContentFile(buf.getvalue()), save=False)
                player.avatar_source_key = key
                player.save(update_fields=["avatar_generated", "avatar_source_key"])
                done += 1
                _src = "foto" if sface is not None else "sintético"
                _st = "rapado" if use_rapado else (style or "base")
                self.stdout.write(f"✓ {player.id} {player.name} [{_src}·{_st}·{figura['clave']}]")
            except Exception as exc:
                failed += 1
                self.stderr.write(f"✗ {player.id} {player.name}: {exc}")

        self.stdout.write(self.style.SUCCESS(f"Generados {done} · saltados {skipped} · fallidos {failed} · sin cuerpo para su edad {menores}"))
