import subprocess
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


BASE_DIR = Path(__file__).resolve().parents[3]
SCRIPT_PATH = BASE_DIR / "scripts" / "import_from_rfef.py"


class Command(BaseCommand):
    help = "Descarga la clasificación oficial de la Federación (RFAF) y actualiza TeamStanding."

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=600,
            help="Timeout en segundos para el proceso de importación (por defecto 600).",
        )

    def handle(self, *args, **options):
        if not SCRIPT_PATH.exists():
            raise CommandError(f"No se encuentra el script: {SCRIPT_PATH}")

        timeout = options["timeout"]
        self.stdout.write(f"Ejecutando importación federación: {SCRIPT_PATH}")

        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH)],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise CommandError(
                f"Timeout al actualizar clasificación de la federación ({timeout}s)."
            ) from exc
        except Exception as exc:  # pragma: no cover
            raise CommandError(f"Error lanzando la importación: {exc}") from exc

        if result.stdout:
            self.stdout.write(result.stdout.strip())
        if result.returncode != 0:
            stderr = (result.stderr or "").strip() or "Error desconocido"
            raise CommandError(stderr)
        if result.stderr:
            self.stderr.write(result.stderr.strip())

        self.stdout.write(self.style.SUCCESS("Clasificación actualizada desde la federación."))
