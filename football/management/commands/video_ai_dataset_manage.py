from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Gestiona dataset YOLO: filtra por calidad, separa train/val y conserva trazabilidad."

    def add_arguments(self, parser):
        parser.add_argument("--src", required=True, help="Dataset origen con manifest.json.")
        parser.add_argument("--out", required=True, help="Dataset salida train/val.")
        parser.add_argument("--val-ratio", type=float, default=0.2, help="Proporción validación.")
        parser.add_argument("--min-confidence", type=float, default=0.0, help="Filtra manifest rows con confidence menor.")
        parser.add_argument("--seed", type=int, default=13)

    def handle(self, *args, **options):
        src = Path(str(options["src"])).expanduser().resolve()
        out = Path(str(options["out"])).expanduser().resolve()
        manifest_path = src / "manifest.json"
        if not manifest_path.exists():
            raise CommandError(f"No existe manifest.json: {manifest_path}")
        rows = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise CommandError("manifest.json inválido.")
        min_conf = max(0.0, min(1.0, float(options.get("min_confidence") or 0.0)))
        val_ratio = max(0.05, min(0.5, float(options.get("val_ratio") or 0.2)))
        seed = int(options.get("seed") or 13)

        filtered = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            conf = 1.0
            meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
            if isinstance(meta.get("confidence"), dict):
                conf = float(meta["confidence"].get("avg") or conf)
            if conf < min_conf:
                continue
            img = src / str(row.get("image") or "")
            label = src / str(row.get("label") or "")
            if img.exists() and label.exists():
                filtered.append(row)

        random.Random(seed).shuffle(filtered)
        val_count = max(1, int(round(len(filtered) * val_ratio))) if len(filtered) > 1 else 0
        val_rows = filtered[:val_count]
        train_rows = filtered[val_count:]
        if not train_rows:
            train_rows, val_rows = filtered, []

        for split, split_rows in (("train", train_rows), ("val", val_rows)):
            (out / "images" / split).mkdir(parents=True, exist_ok=True)
            (out / "labels" / split).mkdir(parents=True, exist_ok=True)
            for row in split_rows:
                img = src / str(row["image"])
                label = src / str(row["label"])
                img_out = out / "images" / split / img.name
                label_out = out / "labels" / split / label.name
                shutil.copy2(img, img_out)
                shutil.copy2(label, label_out)
                row["image"] = str(img_out.relative_to(out))
                row["label"] = str(label_out.relative_to(out))
                row["split"] = split

        (out / "data.yaml").write_text(
            "\n".join([
                f"path: {out}",
                "train: images/train",
                "val: images/val" if val_rows else "val: images/train",
                "names:",
                "  0: player",
                "",
            ]),
            encoding="utf-8",
        )
        (out / "manifest.json").write_text(json.dumps(train_rows + val_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Dataset listo: train={len(train_rows)} val={len(val_rows)} out={out}"))
