# App Privacy (App Store Connect)

Este documento sirve para completar **App Privacy** en App Store Connect para la app **2J Football Intelligence**
(`es.segundajugada.app`).

Importante: Apple exige que lo declarado en App Store Connect coincida con lo que hace realmente tu producto (incluida
la web remota cargada por la app). Si cambias el comportamiento (p. ej. añades analítica/SDKs), revisa este checklist.

## Resumen rápido (recomendación conservadora)

- **Tracking:** No.
- **Datos recogidos:** Sí (por login y uso del servicio).
- **Compartición con terceros:** Solo proveedores necesarios para operar el servicio (hosting/infra), no “venta” de datos.

## Categorías de datos (qué marcar)

Marca únicamente lo que aplique en tu caso. En esta base de código existen funcionalidades que implican:

### Contact Info

- **Email Address** (si usas email para alta/invitaciones/soporte).
  - Propósito: **App Functionality** (cuenta/gestión) y, si procede, **Customer Support**.
  - Vinculado al usuario: Sí.
  - Tracking: No.

### User Content

En el producto se suben/gestionan archivos (ejemplos en `football/models.py`):

- **Photos or Videos** (fotos de jugadores/staff, vídeos de rival/análisis).
  - Propósito: **App Functionality**.
  - Vinculado al usuario: Sí (normalmente está asociado a un club/cuenta).
  - Tracking: No.
- **Other User Content** (documentos PDF/JPG/PNG: licencias, informes, etc.).
  - Propósito: **App Functionality**.
  - Vinculado al usuario: Sí.
  - Tracking: No.

### Identifiers

- **User ID** (identificador de cuenta/usuario en el servidor).
  - Propósito: **App Functionality** (autenticación, seguridad, control de acceso).
  - Vinculado al usuario: Sí.
  - Tracking: No.

### Diagnostics (si aplica en tu despliegue)

Si guardas logs técnicos o métricas para diagnóstico (errores, device/browser, etc.):

- **Other Diagnostic Data** (o la opción equivalente).
  - Propósito: **App Functionality** (estabilidad/seguridad).
  - Vinculado al usuario: Puede ser “Sí” si el log incluye usuario; si no, “No”.
  - Tracking: No.

## Qué NO marcar (en la versión actual)

Salvo que tú lo añadas explícitamente:

- Publicidad / “Advertising”.
- “Data used to track you”.
- “Third‑party advertising”.
- Ubicación precisa.
- Datos de salud.

## Referencias internas

- URLs públicas obligatorias: `mobile/APPSTORE_SUBMISSION.md`
- Eliminación de cuenta (in‑app): `MARKET_RELEASE.md`

