#!/bin/bash
cd /root/bot_whatsapp
source /root/bot_whatsapp/venv/bin/activate
export GOOGLE_APPLICATION_CREDENTIALS="/root/bot_whatsapp/llave.json"
export PATH="/root/bot_whatsapp/venv/bin:$PATH"
/root/bot_whatsapp/venv/bin/python3 gemini_server.py &
PYTHON_PID=$!
echo "Esperando servidor Gemini (PID: $PYTHON_PID)..."
sleep 45
if kill -0 $PYTHON_PID 2>/dev/null; then
    echo "✅ Servidor Python activo"
else
    echo "❌ Servidor Python se cayó"
    exit 1
fi
echo "Arrancando bot WhatsApp..."
node bot_whatsapp.mjs
