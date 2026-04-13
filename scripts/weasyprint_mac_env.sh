#!/usr/bin/env bash
set -euo pipefail

# WeasyPrint (macOS/Homebrew)
# ---------------------------
# En macOS con Homebrew en /opt/homebrew, dyld no busca automáticamente en ese prefijo.
# WeasyPrint carga librerías nativas (gobject/pango/cairo) vía dlopen, por lo que en local
# suele ser necesario exportar este path.
#
# Uso:
#   source scripts/weasyprint_mac_env.sh
#   python manage.py shell
#   # o ejecutar cualquier comando que genere PDFs

export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"

