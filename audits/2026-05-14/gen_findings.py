#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "audits" / "2026-05-14"


@dataclass(frozen=True)
class Hit:
    file: str
    line: int
    text: str
    kind: str


def iter_text_files(*, roots: list[Path], suffixes: set[str]) -> list[Path]:
    out: list[Path] = []
    for base in roots:
        if base.is_file():
            if base.suffix in suffixes:
                out.append(base)
            continue
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in suffixes:
                out.append(p)
    return out


def scan_file(path: Path, *, patterns: list[tuple[str, re.Pattern[str]]]) -> list[Hit]:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    hits: list[Hit] = []
    rel = str(path.relative_to(ROOT))
    for idx, line in enumerate(lines, start=1):
        s = line.rstrip("\n")
        for kind, rx in patterns:
            if rx.search(s):
                hits.append(Hit(file=rel, line=idx, text=s.strip()[:400], kind=kind))
    return hits


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    patterns: list[tuple[str, re.Pattern[str]]] = [
        ("csrf_exempt", re.compile(r"\bcsrf_exempt\b")),
        ("mark_safe", re.compile(r"\bmark_safe\b")),
        ("template_safe_filter", re.compile(r"\|\s*safe\b")),
        ("subprocess_run", re.compile(r"\bsubprocess\.run\s*\(")),
        ("subprocess_popen", re.compile(r"\bsubprocess\.Popen\s*\(")),
        ("shell_true", re.compile(r"\bshell\s*=\s*True\b")),
        ("os_system", re.compile(r"\bos\.system\s*\(")),
        ("eval", re.compile(r"(^|[^A-Za-z0-9_])eval\s*\(")),
        ("exec", re.compile(r"(^|[^A-Za-z0-9_])exec\s*\(")),
        ("pickle", re.compile(r"\bpickle\.")),
        ("yaml_load", re.compile(r"\byaml\.load\s*\(")),
        ("requests_http", re.compile(r"\brequests\.(get|post|put|delete|head|options)\s*\(")),
        ("urllib_request", re.compile(r"\burllib\.request\b")),
        ("openai_api_key_env", re.compile(r"\bOPENAI_API_KEY\b")),
        ("stripe", re.compile(r"\bstripe\b", re.IGNORECASE)),
        ("private_key_block", re.compile(r"-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----")),
        ("aws_key_like", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
        ("stripe_key_like", re.compile(r"\b(sk_live_|sk_test_|rk_live_|rk_test_)[0-9A-Za-z]+\b")),
    ]

    files = iter_text_files(
        roots=[ROOT / "football", ROOT / "webstats", ROOT / "scripts"],
        suffixes={".py", ".js", ".mjs", ".html", ".sh"},
    )

    hits: list[Hit] = []
    for f in files:
        hits.extend(scan_file(f, patterns=patterns))

    payload = {
        "generated_at": "2026-05-14",
        "file_count": len(files),
        "hit_count": len(hits),
        "hits": [h.__dict__ for h in hits],
    }
    (OUT_DIR / "pattern_hits.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    by_kind: dict[str, list[Hit]] = {}
    for h in hits:
        by_kind.setdefault(h.kind, []).append(h)

    md: list[str] = []
    md.append("# Hallazgos por patrones (generado)\n")
    md.append(f"Archivos analizados: {len(files)}  \nHits totales: {len(hits)}\n")
    for kind in sorted(by_kind.keys()):
        rows = by_kind[kind]
        md.append(f"## `{kind}` ({len(rows)})\n")
        for h in rows[:120]:
            md.append(f"- `{h.file}:{h.line}` {h.text}")
        if len(rows) > 120:
            md.append(f"- … +{len(rows) - 120} más")
        md.append("")
    (OUT_DIR / "pattern_hits.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")

    # Dependency pinning (quick)
    req = ROOT / "requirements.txt"
    pinned: list[str] = []
    unpinned: list[str] = []
    if req.exists():
        for raw in req.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "==" in line or " @ " in line or line.startswith(("git+", "http://", "https://")):
                pinned.append(line)
            else:
                unpinned.append(line)
    (OUT_DIR / "deps_python_pinning.json").write_text(
        json.dumps({"pinned": pinned, "unpinned": unpinned}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"wrote {OUT_DIR / 'pattern_hits.json'}")
    print(f"wrote {OUT_DIR / 'pattern_hits.md'}")
    print(f"wrote {OUT_DIR / 'deps_python_pinning.json'}")


if __name__ == "__main__":
    main()

