# App mobile (Capacitor)

Este directorio contiene el scaffold para empaquetar `https://app.segundajugada.es` como app iOS y Android.

## Requisitos

- macOS + Xcode instalado.
- Android Studio instalado (para Android).
- Node.js 18+.

## Pasos

```bash
cd mobile
npm install
npm run add:android
npm run add:ios
npm run sync:android
npm run sync:ios
npm run open:ios
```

Android:

```bash
cd mobile
npm run open:android
```

En Xcode:

- Cambia **Signing & Capabilities** (Team / Bundle Identifier).
- Revisa permisos (Network, Camera si se usa, etc.).
- Compila en dispositivo y, cuando esté estable, sube a App Store Connect.

## Notas

- La app carga el servidor remoto (`server.url`) para no duplicar despliegues.
- El modo offline (cola de acciones en vivo y borradores) se gestiona en el frontend.
