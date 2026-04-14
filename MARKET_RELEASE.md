# Market Release (App Store + Google Play)

Este documento resume lo mínimo para publicar una versión “market-ready” de 2J.

## URLs obligatorias (públicas)

- Política de privacidad: `/legal/privacidad/`
- Términos de uso: `/legal/terminos/`
- Soporte: `/support/`

## Eliminación de cuenta (requisito market)

- Pantalla “Cuenta” (in-app): `/account/`
- Acción “Eliminar cuenta” (in-app): `POST /account/delete/`

Notas:
- La eliminación desactiva el usuario (`is_active=False`) y anonimiza email/nombre. No borra datos deportivos del club.
- Para revisión: incluir un usuario demo y explicar el flujo en “Review Notes”.

## Checklist App Store

- App name, bundle id, iconos, capturas, descripción.
- URL de privacidad + soporte (las de arriba).
- Cuenta demo para revisión (usuario + contraseña) y pasos para acceder a los módulos.
- “Account deletion” accesible dentro de la app (ya cubierto).
- Crash reporting y logs (recomendado: Sentry).

## Checklist Google Play

- Data Safety form (categorías de datos).
- Política de privacidad (URL arriba).
- Cuenta demo (si el contenido está detrás de login).
- Account deletion (misma pantalla “Cuenta”).

## Valores a definir (rellenar)

- `SUPPORT_EMAIL` o `APP_SUPPORT_EMAIL`: email de soporte que aparecerá en Soporte/Legal.
- `LEGAL_UPDATED_AT`: fecha legal que se muestra en Privacidad/Términos (ej: `14/04/2026`).

