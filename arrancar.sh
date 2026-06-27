#!/bin/bash
cd ~/bot_whatsapp

# Matar sesiones tmux viejas si existen
tmux kill-session -t gemini 2>/dev/null
tmux kill-session -t botwa 2>/dev/null

# Arrancar servidor Gemini
tmux new-session -d -s gemini "cd ~/bot_whatsapp && source venv/bin/activate && python3 gemini_server.py"

# Esperar que cargue los PDFs
sleep 10

# Arrancar bot WhatsApp
tmux new-session -d -s botwa "cd ~/bot_whatsapp && node bot_whatsapp.mjs"

echo "✅ Bot Viñedos arrancado!"
echo "Ver logs: tmux attach -t gemini | tmux attach -t botwa"
