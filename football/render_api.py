from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request


RENDER_API_BASE = "https://api.render.com/v1"
DEFAULT_TIMEOUT = 12


def render_api_key() -> str:
    return str(os.getenv("OLLANA_RENDER_API_KEY") or os.getenv("RENDER_API_KEY") or "").strip()


def _request(path: str, *, timeout: int = DEFAULT_TIMEOUT):
    key = render_api_key()
    if not key:
        return None, {"ok": False, "error": "missing_token"}
    url = f"{RENDER_API_BASE}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=max(3, int(timeout or DEFAULT_TIMEOUT))) as resp:
            raw = resp.read()
        return json.loads(raw.decode("utf-8") or "{}"), {"ok": True}
    except urllib.error.HTTPError as exc:
        return None, {"ok": False, "error": f"http_{exc.code}"}
    except Exception as exc:
        return None, {"ok": False, "error": f"{exc.__class__.__name__}:{str(exc)[:120]}"}


def list_render_services(*, timeout: int = DEFAULT_TIMEOUT, limit: int = 5) -> dict:
    payload, meta = _request("/services", timeout=timeout)
    if not meta.get("ok"):
        return {
            "enabled": False,
            "reason": meta.get("error") or "request_failed",
            "services": [],
        }
    rows = []
    for row in payload or []:
        service = row.get("service") if isinstance(row, dict) else {}
        if not isinstance(service, dict):
            continue
        rows.append({
            "id": str(service.get("id") or "")[:80],
            "name": str(service.get("name") or "")[:120],
            "type": str(service.get("type") or "")[:40],
            "status": str(service.get("status") or "")[:40],
            "dashboard_url": str(service.get("dashboardUrl") or "")[:220],
            "branch": str(service.get("branch") or "")[:80],
        })
        if len(rows) >= max(1, int(limit or 5)):
            break
    return {
        "enabled": True,
        "reason": "connected" if rows else "no_services",
        "service_count": len(payload or []),
        "services": rows,
    }
