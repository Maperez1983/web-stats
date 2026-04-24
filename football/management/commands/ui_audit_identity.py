from __future__ import annotations

import pathlib
import re
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand


RE_HEX = re.compile(r"#[0-9a-fA-F]{3,8}")


class Command(BaseCommand):
    help = (
        "Audita identidad visual: detecta colores hardcode en templates/CSS y "
        "verifica que las páginas no-PDF usan `body.prod-commercial`."
    )

    def add_arguments(self, parser):
        parser.add_argument("--fail-on-issues", action="store_true", help="Devuelve exit code 1 si hay issues.")
        parser.add_argument(
            "--root",
            default="football/templates/football",
            help="Directorio de templates a auditar (default: football/templates/football).",
        )

    def handle(self, *args, **options):
        root = pathlib.Path(options["root"]).resolve()
        fail_on_issues = bool(options["fail_on_issues"])

        issues: list[str] = []
        color_counter: Counter[str] = Counter()
        file_colors: dict[str, Counter[str]] = defaultdict(Counter)

        if not root.exists():
            raise SystemExit(f"Root not found: {root}")

        template_files = sorted(root.glob("*.html"))

        non_pdf_missing_commercial: list[str] = []
        for tpl in template_files:
            name = tpl.name
            data = tpl.read_text(encoding="utf-8", errors="ignore")
            if "<body" in data and ("pdf" not in name.lower()):
                if "prod-commercial" not in data:
                    non_pdf_missing_commercial.append(name)

            for m in RE_HEX.findall(data):
                hx = m.lower()
                color_counter[hx] += 1
                file_colors[name][hx] += 1

        if non_pdf_missing_commercial:
            issues.append(
                f"Templates sin `body.prod-commercial` (no-PDF): {len(non_pdf_missing_commercial)}"
            )

        top_files = sorted(
            ((fn, sum(cnt.values())) for fn, cnt in file_colors.items()),
            key=lambda x: x[1],
            reverse=True,
        )

        self.stdout.write("UI audit (identity)")
        self.stdout.write(f"- templates scanned: {len(template_files)} ({root})")
        self.stdout.write(f"- total hardcoded hex colors: {sum(color_counter.values())}")

        if color_counter:
            self.stdout.write("- top colors:")
            for hx, n in color_counter.most_common(12):
                self.stdout.write(f"  - {hx}: {n}")

        self.stdout.write("- top templates by hardcoded colors:")
        for fn, n in top_files[:12]:
            self.stdout.write(f"  - {fn}: {n}")

        if non_pdf_missing_commercial:
            self.stdout.write("- missing prod-commercial:")
            for fn in non_pdf_missing_commercial[:40]:
                self.stdout.write(f"  - {fn}")

        if issues:
            self.stdout.write(self.style.ERROR("Issues:"))
            for it in issues:
                self.stdout.write(self.style.ERROR(f"- {it}"))
        else:
            self.stdout.write(self.style.SUCCESS("OK"))

        if issues and fail_on_issues:
            raise SystemExit(1)

