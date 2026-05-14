#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "audits" / "2026-05-14"


def _node_text(source: str, node: ast.AST) -> str:
    seg = ast.get_source_segment(source, node)
    return (seg or "").strip()


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


@dataclass(frozen=True)
class UrlPattern:
    route: str
    view_expr: str
    name: str
    source_file: str
    lineno: int


def extract_urlpatterns(py_path: Path) -> list[UrlPattern]:
    source = py_path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source, filename=str(py_path))

    out: list[UrlPattern] = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> Any:  # noqa: ANN401
            # We only handle direct `path(...)` calls inside urlpatterns construction.
            fn_name = ""
            if isinstance(node.func, ast.Name):
                fn_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fn_name = node.func.attr

            if fn_name == "path" and node.args:
                route = _const_str(node.args[0]) or ""
                view_expr = _node_text(source, node.args[1]) if len(node.args) >= 2 else ""
                name = ""
                for kw in node.keywords or []:
                    if kw.arg == "name":
                        name = _const_str(kw.value) or _node_text(source, kw.value)
                out.append(
                    UrlPattern(
                        route=route,
                        view_expr=view_expr,
                        name=name,
                        source_file=str(py_path.relative_to(ROOT)),
                        lineno=int(getattr(node, "lineno", 0) or 0),
                    )
                )
            self.generic_visit(node)

    Visitor().visit(tree)
    # Keep only those that look like actual url patterns (route contains '/' or is empty).
    # Avoid docstring examples.
    real = []
    for p in out:
        if p.source_file.endswith("webstats/urls.py") and "Examples:" in source:
            # Filter out docstring references: they appear as `path('', views.home...)` in comments/docstring.
            # Our AST parser won't catch comments, but it WILL catch module-level constants if present.
            pass
        if p.route == "" or "/" in p.route or p.route.startswith(".well-known/") or p.route.endswith(".js") or p.route.endswith(".webmanifest"):
            real.append(p)
    return real


def extract_view_decorators(views_py: Path) -> dict[str, dict]:
    source = views_py.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source, filename=str(views_py))
    out: dict[str, dict] = {}

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:  # noqa: ANN401
            dec = []
            for d in node.decorator_list or []:
                dec.append(_node_text(source, d))
            out[node.name] = {
                "lineno": int(getattr(node, "lineno", 0) or 0),
                "decorators": dec,
            }
            self.generic_visit(node)

    Visitor().visit(tree)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    urls_files = [
        ROOT / "webstats" / "urls.py",
        ROOT / "football" / "urls.py",
    ]

    all_patterns: list[dict] = []
    for f in urls_files:
        for p in extract_urlpatterns(f):
            all_patterns.append(
                {
                    "route": p.route,
                    "view_expr": p.view_expr,
                    "name": p.name,
                    "source_file": p.source_file,
                    "lineno": p.lineno,
                }
            )

    view_meta = extract_view_decorators(ROOT / "football" / "views.py")
    for row in all_patterns:
        view_expr = str(row.get("view_expr") or "")
        view_name = ""
        if view_expr.startswith("views."):
            view_name = view_expr.split(".", 1)[1].strip()
        row["view_name"] = view_name
        if view_name and view_name in view_meta:
            row["view_def_lineno"] = view_meta[view_name]["lineno"]
            row["decorators"] = view_meta[view_name]["decorators"]
        else:
            row["view_def_lineno"] = None
            row["decorators"] = []

    payload = {
        "generated_at": "2026-05-14",
        "urls_files": [str(p.relative_to(ROOT)) for p in urls_files],
        "pattern_count": len(all_patterns),
        "patterns": all_patterns,
    }
    (OUT_DIR / "surface_urlpatterns.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # CSRF-exempt summary (from decorators).
    csrf_rows = []
    for row in all_patterns:
        dec = row.get("decorators") or []
        if any(d.startswith("csrf_exempt") or d.endswith(".csrf_exempt") or "csrf_exempt" in d for d in dec):
            csrf_rows.append(row)
    csrf_rows.sort(key=lambda r: (str(r.get("source_file") or ""), int(r.get("lineno") or 0)))
    md = []
    md.append("# Superficie HTTP — endpoints con `csrf_exempt` (generado)\n")
    md.append(f"Total patterns: {len(all_patterns)}  \nCSRF-exempt patterns: {len(csrf_rows)}\n")
    md.append("| source | line | route | view | name | decorators |\n|---|---:|---|---|---|---|")
    for r in csrf_rows:
        md.append(
            "| {source} | {line} | `{route}` | `{view}` | `{name}` | `{decorators}` |".format(
                source=str(r.get("source_file") or ""),
                line=int(r.get("lineno") or 0),
                route=str(r.get("route") or ""),
                view=str(r.get("view_expr") or ""),
                name=str(r.get("name") or ""),
                decorators="; ".join([str(x) for x in (r.get("decorators") or [])])[:200],
            )
        )
    (OUT_DIR / "csrf_exempt_endpoints.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")

    print(f"wrote {OUT_DIR/'surface_urlpatterns.json'}")
    print(f"wrote {OUT_DIR/'csrf_exempt_endpoints.md'}")


if __name__ == '__main__':
    main()

