#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "audits" / "2026-05-14"
MODELS = ROOT / "football" / "models.py"


def _seg(source: str, node: ast.AST) -> str:
    return (ast.get_source_segment(source, node) or "").strip()


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _call_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    src = MODELS.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(src, filename=str(MODELS))

    fields: list[dict] = []

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        model_name = node.name
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
                continue
            target = stmt.targets[0]
            if not isinstance(target, ast.Name):
                continue
            field_name = target.id
            value = stmt.value
            if not isinstance(value, ast.Call):
                continue
            callee = _call_name(value.func)
            if not callee.startswith("models."):
                continue
            field_type = callee.split(".", 1)[1]
            # Focus on data-sensitive / file / identifiers
            interesting = field_type in {
                "FileField",
                "ImageField",
                "EmailField",
                "DateField",
                "DateTimeField",
                "TextField",
                "JSONField",
            }
            if not interesting:
                continue
            kw = {k.arg: _seg(src, k.value) for k in (value.keywords or []) if k.arg}
            fields.append(
                {
                    "model": model_name,
                    "field": field_name,
                    "type": field_type,
                    "lineno": int(getattr(stmt, "lineno", 0) or 0),
                    "keywords": kw,
                }
            )

    payload = {
        "generated_at": "2026-05-14",
        "models_file": str(MODELS.relative_to(ROOT)),
        "field_count": len(fields),
        "fields": fields,
    }
    (OUT_DIR / "models_data_inventory.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Basic markdown focused on file uploads
    file_fields = [f for f in fields if f["type"] in {"FileField", "ImageField"}]
    file_fields.sort(key=lambda r: (r["model"], r["field"]))
    md: list[str] = []
    md.append("# Inventario de datos — campos (generado)\n")
    md.append(f"Total campos (subset): {len(fields)}  \nFile/Image: {len(file_fields)}\n")
    md.append("| model | field | type | upload_to | line |\n|---|---|---|---|---:|")
    for f in file_fields:
        upload_to = (f.get("keywords") or {}).get("upload_to", "")
        md.append(f"| `{f['model']}` | `{f['field']}` | `{f['type']}` | `{upload_to}` | {int(f['lineno'] or 0)} |")
    (OUT_DIR / "models_filefields.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")

    print(f"wrote {OUT_DIR / 'models_data_inventory.json'}")
    print(f"wrote {OUT_DIR / 'models_filefields.md'}")


if __name__ == "__main__":
    main()
