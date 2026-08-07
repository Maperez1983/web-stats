"""Quita la marca "interactiva" a las tareas que no lo son.

QUÉ PASÓ. El editor guarda en la tarea el repositorio que trae la URL
(`draw_library_repository`, que sale de `?repo=`). Basta con entrar UNA vez por el botón
"🎬 Interactiva" para que ese `repo=interactive` se quede en la barra de direcciones, y a
partir de ahí TODO lo que guardes queda marcado como interactivo: tareas dibujadas a mano en
el estudio, tareas importadas de un libro... En producción salieron 141 así, y ninguna es una
tarea de vídeo.

QUÉ HACE ESTE COMANDO. Le quita la marca a las que no son interactivas de verdad. Se considera
interactiva de verdad la que tiene vídeo o la que viene de una jugada de Táctica
(`source: tactics-playbook`); todo lo demás vuelve a lo que era, y la biblioteca lo recoloca
sola en General o en Importadas según de dónde saliera.

CÓMO ESCRIBE. Con `update()`, nunca con `save()`: `save()` vuelve a derivar `task_family` del
JSON, y las tareas catalogadas a mano (que llevan el tipo en la columna y NO en el JSON)
perderían su tipo. Y toca sólo la clave `repository`: ni reconstruye la copia ligera ni roza
el lienzo.

    python3 manage.py arreglar_marca_interactiva            # sólo propone
    python3 manage.py arreglar_marca_interactiva --apply
"""
from django.core.management.base import BaseCommand

from football.library_repositories import (
    LIBRARY_REPOSITORY_CHOICES,
    LIBRARY_REPOSITORY_INTERACTIVE,
    LIBRARY_REPOSITORY_TRADITIONAL,
    is_library_session,
    library_repository_for_session,
    normalize_library_repository,
)
from football.models import SessionTask
from football.session_import_services import get_or_create_library_session_with_repository
from football.task_library_services import task_scope_for_item

# Lo único que justifica la marca: vídeo, o una jugada guardada desde Táctica.
FUENTES_INTERACTIVAS = {"tactics-playbook", "video", "video_import", "library_upload_video"}
CLAVES_REPO = ("repository", "library_repo", "library_repository")


def meta_de(dic):
    if not isinstance(dic, dict):
        return None
    meta = dic.get("meta")
    return meta if isinstance(meta, dict) else None


def marca_en_metadata(tarea):
    """¿La marca está en la METADATA de la tarea? (lo otro es la sesión, y eso no se toca aquí)"""
    for campo in ("task_layout_light", "tactical_layout"):
        meta = meta_de(getattr(tarea, campo, None))
        if not meta:
            continue
        for clave in CLAVES_REPO:
            repo = normalize_library_repository(meta.get(clave), fallback="")
            if repo in LIBRARY_REPOSITORY_CHOICES:
                return repo == LIBRARY_REPOSITORY_INTERACTIVE
    return False


def es_interactiva_de_verdad(tarea):
    meta = meta_de(getattr(tarea, "task_layout_light", None)) or {}
    if str(meta.get("source") or "").strip().lower() in FUENTES_INTERACTIVAS:
        return True
    for clave in ("video_url", "video", "video_file", "clip_url"):
        if str(meta.get(clave) or "").strip():
            return True
    return False


def sin_marca(dic):
    """Devuelve una copia del JSON sin las claves de repositorio. None si no había nada que quitar."""
    meta = meta_de(dic)
    if not meta or not any(k in meta for k in CLAVES_REPO):
        return None
    nuevo = dict(dic)
    nuevo_meta = dict(meta)
    for clave in CLAVES_REPO:
        nuevo_meta.pop(clave, None)
    nuevo["meta"] = nuevo_meta
    return nuevo


class Command(BaseCommand):
    help = 'Quita la marca "interactiva" a las tareas de biblioteca que no lo son.'

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Escribe (por defecto sólo propone).")
        parser.add_argument("--team", type=int, default=0, help="Limitar a un equipo.")

    def handle(self, *args, **options):
        aplicar = bool(options.get("apply"))
        equipo = int(options.get("team") or 0)

        qs = (
            SessionTask.objects.select_related("session__microcycle__team")
            .filter(deleted_at__isnull=True)
        )
        if equipo:
            qs = qs.filter(session__microcycle__team_id=equipo)

        a_limpiar = []
        se_quedan = []
        a_mudar = []
        for tarea in qs.iterator():
            sesion = getattr(tarea, "session", None)
            if not is_library_session(sesion):
                continue
            if marca_en_metadata(tarea):
                if es_interactiva_de_verdad(tarea):
                    se_quedan.append(tarea)
                else:
                    a_limpiar.append(tarea)
                continue
            # Sin marca propia: entonces la que la llama interactiva es LA SESIÓN que la aloja.
            # Quitarle el nombre a la sesión arrastraría todo lo que cuelgue de ella, así que a
            # estas se las muda de sesión, que es una tarea cada vez y se puede mirar antes.
            if (
                library_repository_for_session(sesion) == LIBRARY_REPOSITORY_INTERACTIVE
                and not es_interactiva_de_verdad(tarea)
            ):
                a_mudar.append(tarea)

        self.stdout.write(self.style.SUCCESS(f"\nMarcadas interactivas en su metadata: "
                                             f"{len(a_limpiar) + len(se_quedan)}"))
        self.stdout.write(f"  se les quita la marca : {len(a_limpiar)}")
        self.stdout.write(f"  se quedan (sí lo son) : {len(se_quedan)}")

        for tarea in a_limpiar[:25]:
            meta = meta_de(getattr(tarea, "task_layout_light", None)) or {}
            origen = str(meta.get("source") or "").strip() or "(sin source)"
            self.stdout.write(f'  {tarea.id:>6}  [{origen}]  {str(tarea.title or "")[:58]}')
        if len(a_limpiar) > 25:
            self.stdout.write(f"  … y {len(a_limpiar) - 25} más")

        if a_mudar:
            self.stdout.write(self.style.SUCCESS(
                f"\nAlojadas en una sesión llamada «Biblioteca interactiva»: {len(a_mudar)}"
            ))
            self.stdout.write("  (se mudan a la biblioteca normal de su equipo; la sesión no se toca)")
            for tarea in a_mudar[:25]:
                equipo = getattr(getattr(getattr(tarea, "session", None), "microcycle", None), "team", None)
                self.stdout.write(
                    f'  {tarea.id:>6}  {str(tarea.title or "")[:58]}  ({getattr(equipo, "name", "?")})'
                )

        if not aplicar:
            self.stdout.write(self.style.WARNING("\nPropuesta: nada escrito. Repite con --apply."))
            return

        mudadas = 0
        for tarea in a_mudar:
            sesion = getattr(tarea, "session", None)
            equipo = getattr(getattr(sesion, "microcycle", None), "team", None)
            if not equipo:
                continue
            try:
                destino = get_or_create_library_session_with_repository(
                    equipo, task_scope_for_item(tarea), repository=LIBRARY_REPOSITORY_TRADITIONAL
                )
            except Exception:
                self.stderr.write(f"  no se pudo resolver la biblioteca de la tarea {tarea.id}")
                continue
            if not destino or destino.id == getattr(sesion, "id", None):
                continue
            SessionTask.objects.filter(id=tarea.id).update(session=destino)
            mudadas += 1
        if a_mudar:
            self.stdout.write(self.style.SUCCESS(f"Mudadas de sesión: {mudadas}"))

        escritas = 0
        for tarea in a_limpiar:
            cambios = {}
            for campo in ("tactical_layout", "task_layout_light"):
                nuevo = sin_marca(getattr(tarea, campo, None))
                if nuevo is not None:
                    cambios[campo] = nuevo
            if not cambios:
                continue
            # update() y NO save(): save() vuelve a derivar task_family del JSON y las tareas
            # catalogadas a mano (tipo en la columna, no en el JSON) perderían su tipo.
            SessionTask.objects.filter(id=tarea.id).update(**cambios)
            escritas += 1

        self.stdout.write(self.style.SUCCESS(f"\nAplicado: {escritas} tareas recuperadas."))
        self.stdout.write("Vuelven solas a General o a Importadas, según de dónde salieran.")
