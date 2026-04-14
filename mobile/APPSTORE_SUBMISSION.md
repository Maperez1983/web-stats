# App Store submission (iOS)

Proyecto: `mobile/ios/App/App.xcworkspace`

## Datos

- Nombre comercial (App Store Connect): **2J Football Intelligence**
- Nombre corto (icono): **2J**
- Bundle ID: `es.segundajugada.app`
- URL app (web remota): `https://app.segundajugada.es`

## Credenciales de revisión (login obligatorio)

- Usuario: `DEMO`
- Password: (la definida en producción)

## URLs obligatorias

- Privacidad: `https://app.segundajugada.es/legal/privacidad/`
- Términos: `https://app.segundajugada.es/legal/terminos/`
- Soporte: `https://app.segundajugada.es/support/`

## Pasos (Xcode)

1. Abrir `App.xcworkspace`.
2. Seleccionar `TARGETS → App → Signing & Capabilities`.
3. Activar `Automatically manage signing` y elegir tu `Team`.
4. Comprobar `Bundle Identifier` (`es.segundajugada.app`).
5. En `General`, revisar `Version` / `Build` (ej: `1.0` / `1`).
6. `Product → Archive`.
7. En `Organizer` → `Distribute App` → `App Store Connect` → `Upload`.

## Review Notes (pegar en App Store Connect)

La app requiere login.

- URL: `https://app.segundajugada.es/login/`
- Usuario: `DEMO`
- Contraseña: (la definida en producción)

Módulos a probar:
Portada, Entrenos, Partido, Jugadores, generación de PDFs.

