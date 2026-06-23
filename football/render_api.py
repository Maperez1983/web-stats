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


def _normalize_env_keys(payload) -> list[str]:
    keys = []
    seen = set()
    for row in payload or []:
        env = row.get("envVar") if isinstance(row, dict) else {}
        if not isinstance(env, dict):
            continue
        key = str(env.get("key") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _normalize_deploy_summary(payload) -> dict:
    deploys = []
    for row in payload or []:
        deploy = row.get("deploy") if isinstance(row, dict) else row
        if not isinstance(deploy, dict):
            continue
        deploys.append({
            "id": str(deploy.get("id") or "")[:80],
            "status": str(deploy.get("status") or "")[:40],
            "trigger": str(deploy.get("trigger") or "")[:40],
            "created_at": str(deploy.get("createdAt") or "")[:40],
            "started_at": str(deploy.get("startedAt") or "")[:40],
            "finished_at": str(deploy.get("finishedAt") or "")[:40],
            "commit": str((deploy.get("commit") or {}).get("id") or "")[:64],
        })
    return {
        "count": len(deploys),
        "latest": deploys[0] if deploys else {},
        "items": deploys[:3],
    }


def inspect_render_service(service_id: str, *, timeout: int = DEFAULT_TIMEOUT, env_limit: int = 40, deploy_limit: int = 3) -> dict:
    service = str(service_id or "").strip()
    if not service:
        return {"enabled": False, "reason": "missing_service_id", "service": {}}
    service_payload, meta = _request(f"/services/{urllib.parse.quote(service)}", timeout=timeout)
    if not meta.get("ok"):
        return {"enabled": False, "reason": meta.get("error") or "request_failed", "service": {"id": service}}
    env_payload, env_meta = _request(f"/services/{urllib.parse.quote(service)}/env-vars", timeout=timeout)
    deploy_payload, deploy_meta = _request(f"/services/{urllib.parse.quote(service)}/deploys", timeout=timeout)
    service_obj = service_payload if isinstance(service_payload, dict) else {}
    service_details = service_obj.get("serviceDetails") if isinstance(service_obj.get("serviceDetails"), dict) else service_obj.get("serviceDetails")
    return {
        "enabled": True,
        "reason": "connected",
        "service": {
            "id": str(service_obj.get("id") or service)[:80],
            "name": str(service_obj.get("name") or "")[:120],
            "type": str(service_obj.get("type") or "")[:40],
            "branch": str(service_obj.get("branch") or "")[:80],
            "slug": str(service_obj.get("slug") or "")[:80],
            "dashboard_url": str(service_obj.get("dashboardUrl") or "")[:220],
            "suspended": str(service_obj.get("suspended") or "")[:40],
            "repo": str(service_obj.get("repo") or "")[:220],
            "root_dir": str(service_obj.get("rootDir") or "")[:120],
            "service_details_type": type(service_details).__name__,
        },
        "env": {
            "enabled": bool(env_meta.get("ok")),
            "count": len(env_payload or []) if isinstance(env_payload, list) else 0,
            "keys": _normalize_env_keys(env_payload)[:max(1, int(env_limit or 40))] if env_meta.get("ok") else [],
            "reason": env_meta.get("error") or "",
        },
        "deploys": {
            "enabled": bool(deploy_meta.get("ok")),
            "count": len(deploy_payload or []) if isinstance(deploy_payload, list) else 0,
            "summary": _normalize_deploy_summary(deploy_payload) if deploy_meta.get("ok") else {"count": 0, "latest": {}, "items": []},
            "reason": deploy_meta.get("error") or "",
        },
    }
