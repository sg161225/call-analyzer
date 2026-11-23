#!/usr/bin/env bash
# Starts the app and prints the link that works from your browser.
cd "$(dirname "$0")/.." || exit 1
if [ -n "${CODESPACE_NAME:-}" ]; then
  URL="https://${CODESPACE_NAME}-8501.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
else
  URL="http://localhost:8501"
fi
echo ""
echo "=================================================================="
echo "  📞 Call Analyzer is starting. Open THIS link in your browser:"
echo ""
echo "     $URL"
echo ""
echo "  (Ctrl + click it. Ignore any 'Network URL' with numbers like"
echo "   10.0.x.x below: that address only works inside the codespace.)"
echo "=================================================================="
echo ""
exec python -m streamlit run app.py --server.headless true \
  --server.enableCORS false --server.enableXsrfProtection false
