from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from football.system_guard import run_system_guard


class Command(BaseCommand):
    help = (
        "Ejecuta un guardián transversal del sistema: healthcheck duro, inventario de coberturas "
        "y revisión opcional con Ollama."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-smoke",
            action="store_true",
            help="Ejecuta también los smoke commands internos (más lento).",
        )
        parser.add_argument(
            "--without-llm",
            action="store_true",
            help="Omite la revisión semántica con Ollama.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Imprime el reporte completo en JSON.",
        )
        parser.add_argument(
            "--auto-fix",
            action="store_true",
            help="Aplica autorreparaciones seguras para incidencias conocidas y vuelve a verificar.",
        )

    def handle(self, *args, **options):
        with_smoke = bool(options.get("with_smoke"))
        without_llm = bool(options.get("without_llm"))
        want_json = bool(options.get("json"))
        auto_fix = bool(options.get("auto_fix"))

        report = run_system_guard(
            run_smoke=with_smoke,
            smoke_verbosity=int(options.get("verbosity") or 1),
            run_llm=not without_llm,
            auto_fix=auto_fix,
        )

        if want_json:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return

        health = report.get("evidence", {}).get("healthcheck", {})
        self.stdout.write(f"healthcheck: {'OK' if health.get('ok') else 'WARN'}")

        for key, item in (health.get("paths") or {}).items():
            self.stdout.write(f"  path:{key}: {'OK' if item.get('ok') else 'WARN'} · {item.get('detail')}")
        for key, item in (health.get("dependencies") or {}).items():
            self.stdout.write(f"  dep:{key}: {'OK' if item.get('ok') else 'WARN'} · {item.get('detail')}")

        inventory = report.get("evidence", {}).get("module_inventory", {})
        self.stdout.write("module inventory:")
        for key, item in inventory.items():
            if item.get("kind") == "script":
                status = "OK" if item.get("exists") else "WARN"
                self.stdout.write(f"  {key}: {status} · {item.get('path')}")
            else:
                self.stdout.write(f"  {key}: OK · management command {item.get('command')}")

        issues = report.get("issues") or []
        if issues:
            self.stdout.write("issues:")
            for item in issues[:20]:
                sev = str(item.get("severity") or "warning").upper()
                auto = " · autofix" if item.get("autofix") else ""
                self.stdout.write(f"  {sev} {item.get('id')}: {item.get('message')}{auto}")

        autofix = report.get("autofix") or {}
        if autofix.get("requested"):
            self.stdout.write("autofix:")
            for item in (autofix.get("applied") or [])[:20]:
                self.stdout.write(f"  applied: {item.get('issue_id')} · {item.get('action')} · {item.get('path') or ''}")
            for item in (autofix.get("skipped") or [])[:20]:
                self.stdout.write(f"  skipped: {item.get('issue_id')} · {item.get('reason') or item.get('error') or ''}")

        smoke = report.get("evidence", {}).get("smoke", {})
        if smoke.get("requested"):
            self.stdout.write("smoke:")
            for key, item in (smoke.get("results") or {}).items():
                status = "OK" if item.get("ok") else "FAIL"
                detail = item.get("error") or item.get("exit_code") or "done"
                self.stdout.write(f"  {key}: {status} · {detail}")

        llm_review = report.get("llm_review", {})
        if llm_review.get("requested"):
            if llm_review.get("available") and isinstance(llm_review.get("review"), dict):
                review = llm_review["review"]
                self.stdout.write(f"llm review: {review.get('overall_status', 'watch')}")
                summary = str(review.get("summary") or "").strip()
                if summary:
                    self.stdout.write(f"  summary: {summary}")
                for row in (review.get("blockers") or [])[:6]:
                    self.stdout.write(f"  blocker: {row}")
                for row in (review.get("warnings") or [])[:6]:
                    self.stdout.write(f"  warning: {row}")
                for row in (review.get("autofix_candidates") or [])[:6]:
                    self.stdout.write(f"  autofix-candidate: {row}")
            else:
                self.stdout.write(f"llm review: unavailable · {llm_review.get('error') or 'no_review'}")

        if report.get("ok"):
            self.stdout.write(self.style.SUCCESS("System guard base OK"))
        else:
            self.stdout.write(self.style.WARNING("System guard con advertencias"))
