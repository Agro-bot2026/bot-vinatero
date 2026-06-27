# Bot Viñatero

Bot de WhatsApp para consultas de viticultura, basado en RAG sobre documentos técnicos de INTA y universidades, usando Vertex AI (Gemini) y un servidor Python intermedio.

**Arquitectura:** un servidor Python (`gemini_server.py`) carga los documentos, arma la base vectorial y atiende las consultas de IA. Un bot de Node (`bot_whatsapp.mjs`) se conecta a WhatsApp con Baileys y le pasa las preguntas al servidor Python.

---

## Requisitos del servidor

- **Sistema:** Ubuntu / Debian (probado en VPS)
- **Node.js:** versión 18 o superior
- **Python:** versión 3.10 o superior
- **tmux:** para mantener los procesos corriendo al cerrar la terminal
- Una **cuenta de servicio de Google Cloud** con Vertex AI habilitado (archivo `llave.json`, NO incluido en el repo)

---

## Instalación paso a paso

### 1. Clonar el repositorio

```bash
cd ~
git clone https://github.com/Agro-bot2026/bot-vinatero.git bot_whatsapp
cd bot_whatsapp
```

### 2. Instalar los programas base (si el VPS es nuevo)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nodejs npm tmux
```

> Si la versión de Node que trae apt es vieja (menor a 18), instalá una más nueva con NodeSource:
> ```bash
> curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
> sudo apt install -y nodejs
> ```

### 3. Instalar las dependencias de Node

```bash
npm install
```

Esto lee el `package.json` e instala:
- `@whiskeysockets/baileys` — conexión a WhatsApp
- `@google/generative-ai` — cliente de Gemini
- `axios` — peticiones HTTP
- `pino` — logs
- `qrcode-terminal` — mostrar el QR para vincular WhatsApp

- ### 4. Crear el entorno virtual de Python e instalar dependencias

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install google-cloud-aiplatform vertexai chromadb sentence-transformers PyPDF2 requests
```

> Las librerías `base64`, `datetime`, `io`, `json`, `os`, `re`, `socket`, `sys`, `threading` son parte de Python, no hay que instalarlas.
> `bayesian` es un módulo propio del proyecto (`bayesian.py`), ya viene en el repo.

### 5. Colocar la credencial de Google (¡el paso clave!)

El archivo `llave.json` **no está en el repositorio** por seguridad. Tenés que copiarlo a mano desde tu backup o descargarlo de Google Cloud:

```bash
# copiá tu archivo llave.json dentro de la carpeta del bot
# debe quedar en: ~/bot_whatsapp/llave.json
```

> Es la cuenta de servicio de Google Cloud con permiso de Vertex AI.
> Los scripts esperan encontrarla en la ruta `/root/bot_whatsapp/llave.json`.
> Si instalás en otra ruta (otro usuario que no sea root), revisá y ajustá esa ruta en `gemini_server.py` y en `arrancar.sh` / `start_bot.sh`.

### 6. Generar la base de datos vectorial (RAG)

La carpeta `vectordb_vid/` no viene en el repo (se regenera). Para crearla a partir de los documentos:

```bash
source venv/bin/activate
python3 crear_rag_vid.py
```

> Esto procesa todos los archivos de `documentos_vid/` y arma la base vectorial. Puede tardar varios minutos la primera vez.

---

## Arrancar el bot

Usá el script con tmux (deja cada proceso en su propia sesión y sigue corriendo aunque cierres la terminal):

```bash
chmod +x arrancar.sh
./arrancar.sh
```

Esto levanta:
1. El servidor Gemini (sesión tmux `gemini`)
2. Espera unos segundos a que cargue
3. El bot de WhatsApp (sesión tmux `botwa`)

### Vincular WhatsApp la primera vez

La primera vez hay que escanear un QR para vincular el número. Mirá la sesión del bot:

```bash
tmux attach -t botwa
```

Aparece un código QR en la terminal. Escanealo desde WhatsApp en el teléfono (Dispositivos vinculados → Vincular dispositivo).

> Para salir de la vista de tmux sin cortar el proceso: apretá `Ctrl+B` y después `D`.
>
> ---

## Comandos útiles

| Acción | Comando |
|---|---|
| Ver logs del servidor Gemini | `tmux attach -t gemini` |
| Ver logs del bot WhatsApp | `tmux attach -t botwa` |
| Salir de la vista (sin cortar) | `Ctrl+B`, luego `D` |
| Reiniciar todo | `./arrancar.sh` |
| Ver sesiones activas | `tmux ls` |

---

## Estructura del proyecto

```
bot_whatsapp/
├── bot_whatsapp.mjs       # Bot de WhatsApp (Node + Baileys)
├── gemini_server.py       # Servidor de IA (Vertex AI + RAG)
├── bayesian.py            # Módulo de perfilado bayesiano de usuarios
├── crear_rag_vid.py       # Genera la base vectorial desde los documentos
├── documentos_vid/        # Documentos técnicos (INTA, universidades)
├── arrancar.sh            # Arranque con tmux (recomendado)
├── start_bot.sh           # Arranque alternativo (una sola terminal)
├── package.json           # Dependencias de Node
├── llave.json             # ⚠️ NO incluido - tu credencial de Google
└── vectordb_vid/          # ⚠️ NO incluido - se regenera con crear_rag_vid.py
```

---

## Archivos que NO vienen en el repo

Por seguridad y peso, estos archivos quedan fuera de GitHub y los tenés que aportar vos al reinstalar:

- **`llave.json`** — credencial de Google Cloud (copiala desde tu backup)
- **`vectordb_vid/`** — base vectorial (se regenera con `crear_rag_vid.py`)
- **`auth_info/`, `.wwebjs_auth/`** — sesión de WhatsApp (se regenera escaneando el QR)
- **`node_modules/`, `venv/`** — dependencias (se regeneran con `npm install` y `pip install`)
- **`usuarios_autorizados.json`, `bayesian_data.json`** — datos de usuarios
