#!/bin/bash
# ============================================================
# Instalador automático - Bot Viñatero
# Bot WhatsApp (Node/Baileys) + servidor Gemini (Python/RAG)
# ============================================================
set -e

REPO="https://github.com/Agro-bot2026/bot-vinatero.git"
DIR="/root/bot_whatsapp"

echo "============================================"
echo "   INSTALADOR BOT VIÑATERO"
echo "============================================"
echo ""

echo "[1/8] Instalando dependencias del sistema..."
apt update -qq
apt install -y python3 python3-venv python3-pip git curl tar nodejs npm >/dev/null 2>&1
if ! command -v pm2 >/dev/null 2>&1; then
    npm install -g pm2 >/dev/null 2>&1
fi
echo "      Listo."

echo "[2/8] Clonando el código desde GitHub..."
if [ -d "$DIR" ]; then
    echo "      ATENCION: $DIR ya existe. Respaldala y borrala antes de reinstalar."
    exit 1
fi
git clone "$REPO" "$DIR"
cd "$DIR"
echo "      Codigo descargado."

echo "[3/8] Instalando dependencias de Node (npm install)..."
npm install >/dev/null 2>&1
echo "      Node listo."

echo "[4/8] Creando entorno virtual e instalando librerias de Python (tarda)..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip >/dev/null 2>&1
./venv/bin/pip install -r requirements.txt >/dev/null 2>&1
echo "      Python listo."

echo "[5/8] Necesito tu backup de credenciales (.json, sesion WhatsApp, vectordb)."
echo "      Esta en tu Drive: Backups_VPS/Vinatero/"
echo ""
echo "      Pega el ENLACE NORMAL de Drive (el de compartir)."
echo ""
read -p "      Enlace de Drive: " ENLACE_DRIVE

if [ -z "$ENLACE_DRIVE" ]; then
    echo "      No pegaste enlace. El bot queda instalado SIN credenciales."
    echo "      Subi a mano llave.json, auth_info/ y vectordb_vid/ a $DIR."
    exit 0
fi

FILE_ID=$(echo "$ENLACE_DRIVE" | grep -oE '[-_a-zA-Z0-9]{25,}' | head -1)
if [ -z "$FILE_ID" ]; then
    echo "      No pude extraer el ID del enlace. Revisa el enlace de Drive."
    exit 1
fi
echo "      ID detectado: $FILE_ID"

echo "[6/8] Descargando credenciales desde Drive..."
DL="https://drive.google.com/uc?export=download&id=${FILE_ID}"
curl -L -c /tmp/gdrive_cookie.txt "$DL" -o /tmp/vinatero_cred.tar.gz
if file /tmp/vinatero_cred.tar.gz | grep -qi "html"; then
    CONFIRM=$(grep -oE 'confirm=[a-zA-Z0-9_-]+' /tmp/vinatero_cred.tar.gz | head -1 | cut -d= -f2)
    curl -L -b /tmp/gdrive_cookie.txt \
        "https://drive.google.com/uc?export=download&confirm=${CONFIRM}&id=${FILE_ID}" \
        -o /tmp/vinatero_cred.tar.gz
fi
rm -f /tmp/gdrive_cookie.txt
echo "      Descargado."

echo "[7/8] Extrayendo credenciales, sesion y base vectorial..."
tar xzf /tmp/vinatero_cred.tar.gz -C "$DIR"
rm -f /tmp/vinatero_cred.tar.gz
if [ ! -f "$DIR/llave.json" ]; then
    echo "      ATENCION: no encuentro llave.json tras extraer. Revisa el backup."
    exit 1
fi
echo "      Credenciales en su lugar."

echo "[8/8] Arrancando con pm2..."
cd "$DIR"
pm2 start gemini_server.py --name vinatero-gemini --interpreter "$DIR/venv/bin/python3"
echo "      Esperando que cargue el servidor Gemini (30s)..."
sleep 30
pm2 start bot_whatsapp.mjs --name vinatero-bot --interpreter node
pm2 save
echo ""
echo "============================================"
echo "   INSTALACION COMPLETA"
echo "============================================"
echo "   pm2 list                -> ver estado"
echo "   pm2 logs vinatero-bot   -> ver el QR de WhatsApp"
echo ""
echo "   IMPORTANTE 1: La primera vez puede que tengas que"
echo "   escanear el QR. Mira: pm2 logs vinatero-bot"
echo ""
echo "   IMPORTANTE 2: Volve a tu Drive y pone el archivo"
echo "   de credenciales como PRIVADO de nuevo."
echo "============================================"
