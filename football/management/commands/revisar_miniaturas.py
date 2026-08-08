"""¿Por qué hay tarjetas de biblioteca en gris? No escribe nada.

La tarjeta pinta imagen si la tarea tiene PORTADA, MINIATURA, PDF adjunto o DIBUJO. Sin ninguna
de las cuatro sale el hueco gris. Pero hay un caso peor y más difícil de ver: que la tarea diga
que tiene miniatura y el fichero NO esté donde dice. Entonces la base de datos parece sana y la
tarjeta sale rota igual. Ya ha pasado en este proyecto dos veces: una regeneración masiva que
dejó miniaturas vacías, y ficheros subidos a S3 sin el prefijo `media/`.

Por eso este comando no se conforma con mirar la columna: ABRE el fichero de una muestra.

    python3 manage.py revisar_miniaturas
    python3 manage.py revisar_miniaturas --team 3 --muestra 60
"""
import io

from django.core.management.base import BaseCommand

from football.library_repositories import is_library_session
from football.models import SessionTask


def datos_de_url(valor):
    """Saca los bytes de un data-URL ("data:image/jpeg;base64,....") o de un base64 pelado."""
    import base64

    texto = str(valor or "").strip()
    if not texto:
        return b""
    if texto.startswith("data:"):
        _, _, texto = texto.partition(",")
    try:
        return base64.b64decode(texto, validate=False)
    except Exception:
        return b""


def es_cesped_pelado(crudo):
    """¿La miniatura es un campo vacío? Se mide lo que NO es hierba.

    Una tarea dibujada tiene conos, fichas y flechas: en la imagen eso son píxeles que no son
    verdes y píxeles claros. Un campo pelado no tiene ninguno de los dos.

    Se mide a 320px de ancho, no a 60: encogiendo más, las líneas del campo y las fichas se
    funden con la hierba y hasta una tarea llena parece vacía. Con estos números, medidos sobre
    imágenes del propio proyecto: tarea con fichas 0.057/0.036, campo vacío 0.002/0.016,
    hierba sola 0.000/0.000.
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(crudo)).convert("RGB")
        if not img.width:
            return False
        img = img.resize((320, max(1, int(img.height * 320 / img.width))))
        pixeles = list(img.getdata())
        if not pixeles:
            return False
        n = len(pixeles)
        no_verde = sum(1 for r, g, b in pixeles if not (g > r + 10 and g > b + 10))
        claros = sum(1 for r, g, b in pixeles if min(r, g, b) > 140)
        return (no_verde / n) <= 0.02 and (claros / n) <= 0.02
    except Exception:
        return False


class Command(BaseCommand):
    help = "Dice por qué hay tarjetas de biblioteca sin imagen. No escribe nada."

    def add_arguments(self, parser):
        parser.add_argument("--team", type=int, default=0, help="Limitar a un equipo.")
        parser.add_argument(
            "--muestra", type=int, default=40,
            help="Cuántos ficheros de miniatura se abren de verdad (cada uno es una llamada a S3).",
        )

    def handle(self, *args, **options):
        equipo = int(options.get("team") or 0)
        muestra = max(0, int(options.get("muestra") or 0))

        qs = (
            SessionTask.objects.select_related("session__microcycle__team")
            .filter(deleted_at__isnull=True)
            .defer("tactical_layout", "preview_data_b64", "cover_data_b64")
        )
        if equipo:
            qs = qs.filter(session__microcycle__team_id=equipo)

        def cubos_vacios():
            return {"portada": 0, "miniatura": 0, "pdf": 0, "dibujo": 0, "nada": 0}

        # Se cuentan por separado las de BIBLIOTECA (las que salen en tarjetas) y las que viven en
        # una sesión de verdad: son el mismo modelo, pero sólo las primeras se pintan como cards.
        cubos = cubos_vacios()
        cubos_sesion = cubos_vacios()
        por_equipo_sin_nada = {}
        con_portada = []
        con_miniatura = []
        sin_nada = []
        total = 0
        total_sesion = 0
        for tarea in qs.iterator():
            sesion = getattr(tarea, "session", None)
            de_biblioteca = is_library_session(sesion)
            destino = cubos if de_biblioteca else cubos_sesion
            if de_biblioteca:
                total += 1
            else:
                total_sesion += 1
            light = getattr(tarea, "task_layout_light", None)
            dibujo = bool(isinstance(light, dict) and light.get("has_canvas"))
            if getattr(tarea, "cover_present", False):
                destino["portada"] += 1
                if de_biblioteca:
                    con_portada.append(tarea.id)
            elif getattr(tarea, "task_preview_image", None):
                destino["miniatura"] += 1
                if de_biblioteca:
                    con_miniatura.append(tarea)
            elif getattr(tarea, "task_pdf", None):
                destino["pdf"] += 1
            elif dibujo:
                destino["dibujo"] += 1
            else:
                destino["nada"] += 1
                if de_biblioteca:
                    equipo = getattr(getattr(sesion, "microcycle", None), "team", None)
                    nombre = str(getattr(equipo, "name", "") or f"equipo {getattr(equipo, 'id', '?')}")
                    por_equipo_sin_nada[nombre] = por_equipo_sin_nada.get(nombre, 0) + 1
                    if len(sin_nada) < 20:
                        sin_nada.append(tarea)

        etiquetas = (
            ("portada", "portada"),
            ("miniatura", "miniatura guardada"),
            ("pdf", "PDF adjunto"),
            ("dibujo", "dibujo en el lienzo"),
            ("nada", "NADA  <-- salen en gris seguro"),
        )

        self.stdout.write(self.style.SUCCESS(f"\nTareas de BIBLIOTECA (las que salen en tarjetas): {total}"))
        self.stdout.write("\n=== qué tiene cada una para pintar la tarjeta ===")
        for clave, etiqueta in etiquetas:
            self.stdout.write(f"  {cubos[clave]:>5}  {etiqueta}")

        if total_sesion:
            self.stdout.write(self.style.SUCCESS(
                f"\nTareas metidas en sesiones de verdad: {total_sesion}"
            ))
            for clave, etiqueta in etiquetas:
                self.stdout.write(f"  {cubos_sesion[clave]:>5}  {etiqueta.replace('  <-- salen en gris seguro', '')}")

        if por_equipo_sin_nada:
            self.stdout.write("\n=== las de biblioteca SIN NADA, por equipo ===")
            for equipo, n in sorted(por_equipo_sin_nada.items(), key=lambda kv: -kv[1]):
                self.stdout.write(f"  {n:>5}  {equipo}")

        # LAS PORTADAS. Son la mayoría y la tarjeta las prefiere a todo lo demás, así que si una
        # está vacía da igual que la tarea tenga una miniatura perfecta debajo: se ve la portada.
        # No son ficheros: viven en una columna base64, que además está diferida a propósito
        # porque pesa. Se piden aparte y sólo las de la muestra.
        if con_portada and muestra:
            cuantas = min(muestra, len(con_portada))
            self.stdout.write(f"\n=== mirando {cuantas} portadas por dentro ===")
            peladas = []
            ilegibles = 0
            miradas = 0
            for tid in con_portada[:cuantas]:
                fila = SessionTask.objects.filter(id=tid).values_list("cover_data_b64", flat=True).first()
                crudo = datos_de_url(fila)
                if not crudo:
                    # Retrocompat: las portadas viejas viven dentro del JSON, no en su columna.
                    tarea_completa = SessionTask.objects.filter(id=tid).first()
                    crudo = datos_de_url(
                        tarea_completa.cover_embedded_url() if tarea_completa else ""
                    )
                if not crudo:
                    ilegibles += 1
                    continue
                miradas += 1
                if es_cesped_pelado(crudo):
                    peladas.append(tid)
            self.stdout.write(f"  {miradas:>5}  se leen")
            self.stdout.write(f"  {ilegibles:>5}  no se pueden leer")
            self.stdout.write(self.style.WARNING(
                f"  {len(peladas):>5}  son CAMPO PELADO: se ven, pero no hay nada dibujado"
            ))
            if peladas:
                self.stdout.write("  ids de las peladas:")
                self.stdout.write("  " + ", ".join(str(i) for i in peladas[:80]))

        # LA PRUEBA DE VERDAD: que el fichero esté donde la base de datos dice.
        if con_miniatura and muestra:
            self.stdout.write(f"\n=== abriendo {min(muestra, len(con_miniatura))} miniaturas de verdad ===")
            ok = 0
            vacias = 0
            cesped_pelado = 0
            peladas_ids = []
            perdidas = []
            for tarea in con_miniatura[:muestra]:
                campo = tarea.task_preview_image
                try:
                    campo.open("rb")
                    try:
                        crudo = campo.read() or b""
                    finally:
                        try:
                            campo.close()
                        except Exception:
                            pass
                    if crudo:
                        ok += 1
                        if es_cesped_pelado(crudo):
                            cesped_pelado += 1
                            peladas_ids.append(tarea.id)
                    else:
                        vacias += 1
                        perdidas.append((tarea.id, campo.name, "vacía (0 bytes)"))
                except Exception as exc:
                    perdidas.append((tarea.id, getattr(campo, "name", "?"), f"{type(exc).__name__}"))
            self.stdout.write(f"  {ok:>5}  se abren y traen datos")
            if cesped_pelado:
                self.stdout.write(self.style.WARNING(
                    f"  {cesped_pelado:>5}  ...pero son CÉSPED PELADO: se ven, y no hay nada dibujado"
                ))
            self.stdout.write(f"  {vacias:>5}  existen pero están VACÍAS")
            self.stdout.write(f"  {len(perdidas) - vacias:>5}  NO se pueden abrir  <-- la tarjeta sale rota")
            for tid, nombre, motivo in perdidas[:12]:
                self.stdout.write(f"    {tid:>6}  {motivo}  {nombre}")
            if peladas_ids:
                self.stdout.write("  ids de las peladas (para volver a dibujarlas):")
                self.stdout.write("  " + ", ".join(str(i) for i in peladas_ids[:60]))
            if not perdidas and not cesped_pelado:
                self.stdout.write(self.style.SUCCESS(
                    "  Las miniaturas están bien: si las ves en gris, el problema es al servirlas."
                ))

        if sin_nada:
            self.stdout.write("\n=== una muestra de las que no tienen nada ===")
            for tarea in sin_nada:
                equipo_nombre = getattr(
                    getattr(getattr(tarea, "session", None), "microcycle", None), "team", None
                )
                self.stdout.write(
                    f'  {tarea.id:>6}  {str(tarea.title or "")[:56]}  ({getattr(equipo_nombre, "name", "?")})'
                )

        self.stdout.write("\nEste comando no ha escrito nada.")
