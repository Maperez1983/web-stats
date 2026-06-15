from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Entrena/fine-tunea YOLO localmente con un dataset generado desde Video Studio."

    def add_arguments(self, parser):
        parser.add_argument("--data", required=True, help="Ruta data.yaml.")
        parser.add_argument("--model", default="data/video_ai/models/yolo11n.pt", help="Pesos base.")
        parser.add_argument("--epochs", type=int, default=10)
        parser.add_argument("--imgsz", type=int, default=640)
        parser.add_argument("--batch", type=int, default=4)
        parser.add_argument("--project", default="data/video_ai/train_runs")
        parser.add_argument("--name", default="football_player_mvp")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        try:
            from ultralytics import YOLO  # noqa: WPS433
        except Exception as exc:
            raise CommandError(f"Ultralytics no disponible: {exc}") from exc

        data_path = Path(str(options["data"])).expanduser().resolve()
        model_path = Path(str(options.get("model") or "data/video_ai/models/yolo11n.pt")).expanduser().resolve()
        if not data_path.exists():
            raise CommandError(f"No existe data.yaml: {data_path}")
        if not model_path.exists():
            raise CommandError(f"No existe modelo base: {model_path}")
        epochs = max(1, min(300, int(options.get("epochs") or 10)))
        imgsz = max(320, min(1280, int(options.get("imgsz") or 640)))
        batch = max(1, min(64, int(options.get("batch") or 4)))
        project = Path(str(options.get("project") or "data/video_ai/train_runs")).resolve()
        name = str(options.get("name") or "football_player_mvp").strip() or "football_player_mvp"

        self.stdout.write(f"YOLO train: model={model_path} data={data_path} epochs={epochs} imgsz={imgsz} batch={batch}")
        if bool(options.get("dry_run")):
            self.stdout.write(self.style.WARNING("dry-run: no se entrena."))
            return

        model = YOLO(str(model_path))
        result = model.train(
            data=str(data_path),
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            project=str(project),
            name=name,
            device="cpu",
            exist_ok=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Entrenamiento lanzado/completado: {result}"))
