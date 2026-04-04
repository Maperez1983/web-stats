from __future__ import annotations

import json
import os
from datetime import timedelta

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.cache import add_never_cache_headers
from django.utils.timezone import now


def _build_id() -> str:
    return (
        os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("RENDER_DEPLOY_ID")
        or os.getenv("SOURCE_VERSION")
        or os.getenv("GIT_SHA")
        or ""
    ).strip() or "dev"


def pwa_manifest(request: HttpRequest) -> HttpResponse:
    """
    Manifest servido desde "/" para que la PWA tenga scope completo.
    """
    build = _build_id()
    manifest = {
        "name": "Segunda Jugada",
        "short_name": "2J",
        "description": "Segunda Jugada · 2J Football Intelligence · Tareas, sesiones y análisis.",
        # En iOS, start_url debe ser estable y preferimos entrar por login para que
        # el modo standalone no se quede en la landing si el usuario aún no tiene sesión.
        "start_url": "/login/?next=/",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#08111d",
        "theme_color": "#08111d",
        "icons": [
            {"src": f"/static/football/pwa/icons/icon-180.png?v={build}", "sizes": "180x180", "type": "image/png"},
            {"src": f"/static/football/pwa/icons/icon-192.png?v={build}", "sizes": "192x192", "type": "image/png"},
            {"src": f"/static/football/pwa/icons/icon-512.png?v={build}", "sizes": "512x512", "type": "image/png"},
        ],
    }
    response = JsonResponse(manifest)
    # Manifest: queremos que refresque rápido tras deploys.
    add_never_cache_headers(response)
    return response


def pwa_service_worker(request: HttpRequest) -> HttpResponse:
    """
    Service worker servido desde "/" para controlar toda la app (no desde /static/).
    """
    build = _build_id()
    offline_url = reverse("pwa-offline")
    # Nota: mantenemos el SW lo más conservador posible para no cachear HTML autenticado
    # de forma agresiva. Cachea estáticos y ofrece fallback offline para navegación.
    script = f"""/* web-stats service worker (build {build}) */
const BUILD = {json.dumps(build)};
const STATIC_CACHE = `webstats-static-${{BUILD}}`;
const RUNTIME_CACHE = `webstats-runtime-${{BUILD}}`;
const OFFLINE_URL = {json.dumps(offline_url)};

const STATIC_ASSETS = [
  OFFLINE_URL,
  `/static/football/css/product_system.css?v=${{BUILD}}`,
  `/static/football/css/commercial.css?v=${{BUILD}}`,
  `/static/logos/logo.png?v=${{BUILD}}`,
  `/static/football/pwa/icons/icon-192.png?v=${{BUILD}}`,
  `/static/football/pwa/icons/icon-512.png?v=${{BUILD}}`,
];

self.addEventListener('install', (event) => {{
  event.waitUntil((async () => {{
    try {{
      const cache = await caches.open(STATIC_CACHE);
      await cache.addAll(STATIC_ASSETS);
    }} catch (e) {{
      // ignore
    }}
    self.skipWaiting();
  }})());
}});

self.addEventListener('activate', (event) => {{
  event.waitUntil((async () => {{
    try {{
      const keys = await caches.keys();
      await Promise.all(keys.map((key) => {{
        if (key === STATIC_CACHE || key === RUNTIME_CACHE) return null;
        if (key.startsWith('webstats-')) return caches.delete(key);
        return null;
      }}));
    }} catch (e) {{
      // ignore
    }}
    self.clients.claim();
  }})());
}});

const isCacheableStatic = (url) => {{
  return url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/');
}};

self.addEventListener('fetch', (event) => {{
  const req = event.request;
  if (!req || req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Navegación: network-first con fallback offline.
  if (req.mode === 'navigate') {{
    event.respondWith((async () => {{
      try {{
        const resp = await fetch(req);
        // No cacheamos redirecciones a login.
        if (!resp || resp.redirected) return resp;
        const cache = await caches.open(RUNTIME_CACHE);
        cache.put(req, resp.clone()).catch(() => {{}});
        return resp;
      }} catch (e) {{
        const cached = await caches.match(req);
        return cached || caches.match(OFFLINE_URL);
      }}
    }})());
    return;
  }}

  // Estáticos: cache-first.
  if (isCacheableStatic(url)) {{
    event.respondWith((async () => {{
      const cached = await caches.match(req);
      if (cached) return cached;
      try {{
        const resp = await fetch(req);
        if (resp && resp.ok) {{
          const cache = await caches.open(STATIC_CACHE);
          cache.put(req, resp.clone()).catch(() => {{}});
        }}
        return resp;
      }} catch (e) {{
        return cached || new Response('', {{ status: 504 }});
      }}
    }})());
    return;
  }}
}});
"""
    response = HttpResponse(script, content_type="application/javascript; charset=utf-8")
    # Service worker: nunca cachear por el navegador.
    add_never_cache_headers(response)
    response["Service-Worker-Allowed"] = "/"
    return response


def pwa_offline(request: HttpRequest) -> HttpResponse:
    """
    Página simple de fallback para cuando no hay red.
    """
    html = f"""<!doctype html>
<html lang="es">
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
<title>Sin conexión · Segunda Jugada</title>
<style>
  body {{
    margin: 0;
    font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
    color: #f5f7fa;
    background: linear-gradient(180deg, #02060d 0%, #08111d 58%, #050a13 100%);
    padding: 18px;
  }}
  .card {{
    max-width: 560px;
    margin: 12vh auto 0;
    padding: 18px 18px 16px;
    border-radius: 18px;
    border: 1px solid rgba(144, 161, 185, 0.22);
    background: rgba(14, 23, 39, 0.92);
    box-shadow: 0 22px 60px rgba(0,0,0,0.35);
  }}
  h1 {{ margin: 0 0 6px; font-size: 18px; letter-spacing: .06em; text-transform: uppercase; }}
  p {{ margin: 0; color: rgba(176, 188, 205, 0.95); line-height: 1.45; }}
  .meta {{ margin-top: 12px; font-size: 12px; opacity: 0.72; }}
</style>
<div class="card">
  <h1>Sin conexión</h1>
  <p>No hay red ahora mismo. Vuelve a intentarlo cuando tengas conexión.</p>
  <p class="meta">Build: {_build_id()} · {now().strftime("%Y-%m-%d %H:%M")}</p>
</div>
"""
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    add_never_cache_headers(response)
    return response
