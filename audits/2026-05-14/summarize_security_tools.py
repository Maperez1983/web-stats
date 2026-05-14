#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "audits" / "2026-05-14"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def summarize_bandit(path: Path) -> dict:
    obj = _load_json(path)
    results = obj.get("results") if isinstance(obj, dict) else None
    results = results if isinstance(results, list) else []
    by_sev = Counter()
    by_conf = Counter()
    by_test = Counter()
    by_file = Counter()

    for r in results:
        if not isinstance(r, dict):
            continue
        sev = str(r.get("issue_severity") or "").upper() or "UNKNOWN"
        conf = str(r.get("issue_confidence") or "").upper() or "UNKNOWN"
        test = str(r.get("test_id") or "").strip() or "?"
        filename = str(r.get("filename") or "").strip()
        by_sev[sev] += 1
        by_conf[conf] += 1
        by_test[test] += 1
        if filename:
            try:
                filename = str(Path(filename).resolve().relative_to(ROOT))
            except Exception:
                filename = filename
            by_file[filename] += 1

    return {
        "count": int(len(results)),
        "by_severity": dict(by_sev),
        "by_confidence": dict(by_conf),
        "top_tests": by_test.most_common(20),
        "top_files": by_file.most_common(20),
    }


def summarize_pip_audit(path: Path) -> dict:
    obj = _load_json(path)
    deps = obj.get("dependencies") if isinstance(obj, dict) else None
    deps = deps if isinstance(deps, list) else []

    total_vulns = 0
    per_pkg = []
    vuln_ids = Counter()

    for d in deps:
        if not isinstance(d, dict):
            continue
        name = str(d.get("name") or "").strip()
        version = str(d.get("version") or "").strip()
        vulns = d.get("vulns") if isinstance(d.get("vulns"), list) else []
        total_vulns += len(vulns)
        if vulns:
            per_pkg.append((name, version, len(vulns)))
        for v in vulns:
            if not isinstance(v, dict):
                continue
            vid = str(v.get("id") or "").strip()
            if vid:
                vuln_ids[vid] += 1

    per_pkg.sort(key=lambda t: (-t[2], t[0], t[1]))
    return {
        "packages_with_vulns": len(per_pkg),
        "total_vulns": int(total_vulns),
        "top_packages": per_pkg[:20],
        "top_vuln_ids": vuln_ids.most_common(30),
    }


def main() -> None:
    bandit_json = OUT_DIR / "bandit.json"
    pip_audit_json = OUT_DIR / "pip_audit_nodeps.json"

    summary = {
        "generated_at": "2026-05-14",
        "bandit": summarize_bandit(bandit_json) if bandit_json.exists() else None,
        "pip_audit": summarize_pip_audit(pip_audit_json) if pip_audit_json.exists() else None,
    }
    (OUT_DIR / "security_tool_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md: list[str] = []
    md.append("# Resumen de herramientas de auditoría (generado)\n")
    if summary.get("bandit"):
        b = summary["bandit"]
        md.append("## Bandit (SAST Python)\n")
        md.append(f"Total issues: **{b['count']}**\n")
        md.append(f"- Severidad: {b['by_severity']}")
        md.append(f"- Confianza: {b['by_confidence']}\n")
        md.append("Top tests:")
        for test_id, n in b["top_tests"]:
            md.append(f"- `{test_id}`: {n}")
        md.append("\nTop ficheros:")
        for fn, n in b["top_files"]:
            md.append(f"- `{fn}`: {n}")
        md.append("")
    if summary.get("pip_audit"):
        p = summary["pip_audit"]
        md.append("## pip-audit (vulnerabilidades Python)\n")
        md.append(f"Paquetes con vulnerabilidades: **{p['packages_with_vulns']}**")
        md.append(f"Vulnerabilidades totales: **{p['total_vulns']}**\n")
        md.append("Top paquetes:")
        for name, version, n in p["top_packages"]:
            md.append(f"- `{name}=={version}`: {n}")
        md.append("\nTop IDs:")
        for vid, n in p["top_vuln_ids"]:
            md.append(f"- `{vid}`: {n}")
        md.append("")

    (OUT_DIR / "security_tool_summary.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")
    print(f"wrote {OUT_DIR / 'security_tool_summary.json'}")
    print(f"wrote {OUT_DIR / 'security_tool_summary.md'}")


if __name__ == "__main__":
    main()

