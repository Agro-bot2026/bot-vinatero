import os
import io
import re
import json
import base64
import socket
import threading
import PyPDF2
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/root/bot_whatsapp/llave.json'
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import texttospeech

# ============================================================
# CONFIGURACION
# ============================================================
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "llave.json"
# Vertex AI usa llave.json
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/root/bot_whatsapp/llave.json"

import requests
import sys
sys.path.insert(0, "/root/bot_whatsapp")
from bayesian import actualizar_perfil, generar_contexto_bayesiano

GOOGLE_MAPS_KEY = 'AQ.Ab8RN6JGbsuWaq4VIRqXzT9TIEaQ-CxXV08LubeApGbEZMBwPw'

OWM_KEY = '5657d871c9421f66a48e23280ad0c337'

def icono_clima(descripcion):
    desc = descripcion.lower()
    if 'tormenta' in desc or 'storm' in desc: return '⛈️'
    if 'lluvia' in desc or 'rain' in desc: return '🌧️'
    if 'nieve' in desc or 'snow' in desc: return '❄️'
    if 'niebla' in desc or 'fog' in desc or 'mist' in desc: return '🌫️'
    if 'nube' in desc or 'cloud' in desc: return '⛅'
    if 'despejado' in desc or 'clear' in desc: return '☀️'
    return '🌤️'

def obtener_clima(lat: float, lon: float) -> str:
    try:
        # Clima actual
        url = f'https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OWM_KEY}&units=metric&lang=es'
        response = requests.get(url)
        data = response.json()
        
        temp = round(data["main"]["temp"], 1)
        temp_sens = round(data["main"]["feels_like"], 1)
        temp_min = round(data["main"]["temp_min"], 1)
        temp_max = round(data["main"]["temp_max"], 1)
        humedad = data["main"]["humidity"]
        viento = round(data["wind"]["speed"] * 3.6, 1)
        descripcion = data["weather"][0]["description"].capitalize()
        ciudad = data.get("name", "Tu zona")
        icono = icono_clima(descripcion)

        texto = f"--- CLIMA EN {ciudad.upper()} ---\n\n"
        texto += f"{icono} {descripcion}\n"
        texto += f"Temp: {temp}C (sens. {temp_sens}C)\n"
        texto += f"Min: {temp_min}C | Max: {temp_max}C\n"
        texto += f"Humedad: {humedad}%\n"
        texto += f"Viento: {viento} km/h\n"

        # Pronostico 5 dias
        url2 = f'https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OWM_KEY}&units=metric&lang=es&cnt=40'
        resp2 = requests.get(url2)
        data2 = resp2.json()
        
        texto += f"\n--- PRONOSTICO 5 DIAS ---\n"
        dias_vistos = []
        for item in data2['list']:
            fecha = item['dt_txt'].split(' ')[0]
            hora = item['dt_txt'].split(' ')[1]
            if fecha not in dias_vistos and hora == '12:00:00':
                dias_vistos.append(fecha)
                from datetime import datetime
                d = datetime.strptime(fecha, '%Y-%m-%d')
                dia_nombre = ['Lun','Mar','Mie','Jue','Vie','Sab','Dom'][d.weekday()]
                t_min = round(item['main']['temp_min'], 1)
                t_max = round(item['main']['temp_max'], 1)
                hum = item['main']['humidity']
                desc = item['weather'][0]['description'].capitalize()
                ic = icono_clima(desc)
                texto += f"{dia_nombre} {d.day}/{d.month}: {ic} {t_min}-{t_max}C Hum:{hum}%\n"

        # Alertas para vinedos
        alertas = []
        if temp <= 0:
            alertas.append("HELADA - Proteger el vinedo urgente")
        if temp <= 3:
            alertas.append("RIESGO DE HELADA - Temperatura muy baja")
        if humedad >= 85:
            alertas.append("ALTO RIESGO DE MILDIU - Humedad critica")
        if humedad >= 70 and temp >= 15:
            alertas.append("CONDICIONES FAVORABLES PARA OIDEO")
        if viento >= 50:
            alertas.append("VIENTOS FUERTES - Cuidado con tutores")
        if viento >= 80:
            alertas.append("VIENTOS MUY FUERTES - Danger para la vid")

        if alertas:
            texto += f"\n--- ALERTAS PARA TU VINEDO ---\n"
            for a in alertas:
                texto += f"ADVERTENCIA {a}\n"
        else:
            texto += f"\nSin alertas - Condiciones normales para el vinedo"

        return texto
    except Exception as e:
        print(f"Error clima: {e}")
        return "No pude obtener el clima en este momento."

SOCKET_PATH = "/tmp/gemini_bot.sock"

vertexai.init(project="cleanbot-8f137", location="us-central1")
model = GenerativeModel("gemini-2.5-flash")

# ============================================================
# BASE DE CONOCIMIENTOS (se carga UNA sola vez al iniciar)
# ============================================================
def cargar_base_vid() -> str:
    contenido = ""
    ruta = "documentos_vid/"
    if not os.path.exists(ruta):
        return ""
    for archivo in sorted(os.listdir(ruta)):
        p = os.path.join(ruta, archivo)
        if archivo.endswith(".txt"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    contenido += f"\n--- {archivo} ---\n{f.read()}"
            except:
                pass
        elif archivo.endswith(".pdf"):
            try:
                with open(p, "rb") as f:
                    lector = PyPDF2.PdfReader(f)
                    for pag in lector.pages:
                        texto = pag.extract_text()
                        if texto:
                            contenido += texto
            except:
                pass
    return contenido[:400000]

print("Cargando base de conocimientos...")
BASE_VID = ''  # Desactivado - usa RAG
print("Base desactivada - usando RAG")

SYSTEM_PROMPT = (
    "Sos un Ingeniero Agronomo experto en viticultura y enologia, especializado en el cultivo "
    "de la vid en la region de Cuyo, Argentina. "
    "Respondas siempre en espanol argentino, de forma clara y practica para contratistas de vinas. "
    "Das recomendaciones concretas sobre tratamientos, productos fitosanitarios, podas, riegos y momentos de aplicacion. "
    "Cuando analizas imagenes, describis detalladamente lo que ves y das un diagnostico preciso. "
    "Recordas todo lo hablado anteriormente en la conversacion y mantenes el hilo. "
    "Sos amigable pero profesional. "
    "Tus respuestas van a ser convertidas a audio, por lo tanto NO uses markdown, asteriscos, guiones ni simbolos especiales. "
    "Escribi en texto plano como si estuvieras hablando. "
    "Se conciso, maximo 3 parrafos por respuesta para que el audio no sea muy largo."
)

if BASE_VID:
    SYSTEM_PROMPT += f"\n\nUSA ESTA BASE TECNICA COMO REFERENCIA PRINCIPAL:\n{BASE_VID}"

print("Sistema listo!")

# ============================================================
# GEMINI
# ============================================================

def generar_informe_pdf_agro(diagnostico: str, imagen_path: str = None, nombre_usuario: str = "Contratista") -> bytes:
    """Genera un PDF profesional con diagnóstico agronómico e imagen"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import io as io_mod
    from datetime import datetime
    import re
    import os

    buffer = io_mod.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm)

    styles = getSampleStyleSheet()
    
    estilo_titulo = ParagraphStyle("Titulo", parent=styles["Heading1"],
        fontSize=14, textColor=colors.HexColor("#1a5e1a"),
        spaceAfter=4, alignment=TA_CENTER, fontName="Helvetica-Bold")
    estilo_subtitulo = ParagraphStyle("Subtitulo", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor("#1a5e1a"),
        spaceAfter=4, alignment=TA_CENTER)
    estilo_seccion = ParagraphStyle("Seccion", parent=styles["Heading2"],
        fontSize=11, textColor=colors.HexColor("#1a5e1a"),
        spaceAfter=3, spaceBefore=8, fontName="Helvetica-Bold")
    estilo_normal = ParagraphStyle("Normal2", parent=styles["Normal"],
        fontSize=9, spaceAfter=3, leading=13)
    estilo_footer = ParagraphStyle("Footer", parent=styles["Normal"],
        fontSize=7, textColor=colors.grey, alignment=TA_CENTER)

    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    elementos = []

    # Encabezado
    elementos.append(Paragraph("🌿 INFORME TÉCNICO AGRONÓMICO", estilo_titulo))
    elementos.append(Paragraph("Bot Experto en Viñedos - Región de Cuyo, Mendoza", estilo_subtitulo))
    elementos.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a5e1a")))
    elementos.append(Spacer(1, 0.2*cm))
    elementos.append(Paragraph(f"Consultor: {nombre_usuario} | Fecha: {fecha}", estilo_footer))
    elementos.append(Spacer(1, 0.3*cm))

    # Imagen analizada
    if imagen_path and os.path.exists(imagen_path):
        try:
            elementos.append(Paragraph("📸 IMAGEN ANALIZADA", estilo_seccion))
            elementos.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#1a5e1a")))
            elementos.append(Spacer(1, 0.2*cm))
            img = Image(imagen_path, width=12*cm, height=9*cm, kind="proportional")
            elementos.append(img)
            elementos.append(Spacer(1, 0.3*cm))
        except Exception as e:
            elementos.append(Paragraph(f"[Imagen no disponible: {str(e)[:50]}]", estilo_normal))

    # Diagnóstico
    elementos.append(Paragraph("🔬 DIAGNÓSTICO Y RECOMENDACIONES", estilo_seccion))
    elementos.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#1a5e1a")))
    elementos.append(Spacer(1, 0.2*cm))

    def limpiar(txt):
        txt = re.sub(r"\*\*(.*?)\*\*", r"\1", txt)
        txt = re.sub(r"\*(.*?)\*", r"\1", txt)
        txt = txt.replace("`", "").strip()
        return txt

    parrafos = diagnostico.split("\n")
    for p in parrafos:
        p = limpiar(p.strip())
        if p:
            try:
                elementos.append(Paragraph(p[:800], estilo_normal))
            except:
                pass

    # Footer
    elementos.append(Spacer(1, 0.5*cm))
    elementos.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a5e1a")))
    elementos.append(Spacer(1, 0.2*cm))
    elementos.append(Paragraph(
        "Bot Experto en Viñedos · Fuentes: INTA, INV, Universidades agronómicas · "
        "Informe orientativo - No reemplaza asesoramiento de Ingeniero Agrónomo matriculado.",
        estilo_footer))

    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()


# RAG - Búsqueda semántica
_chroma_col_vid = None
_embed_model_vid = None

def inicializar_rag_vid():
    global _chroma_col_vid, _embed_model_vid
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
        client = chromadb.PersistentClient(path="/root/bot_whatsapp/vectordb_vid")
        _chroma_col_vid = client.get_collection("documentos_vid")
        _embed_model_vid = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        print(f"✅ RAG inicializado: {_chroma_col_vid.count()} chunks")
    except Exception as e:
        print(f"⚠️ RAG error: {e}")

def buscar_contexto_vid(pregunta: str, n_resultados: int = 2) -> str:
    global _chroma_col_vid, _embed_model_vid
    if not _chroma_col_vid or not _embed_model_vid:
        return ""
    try:
        emb = _embed_model_vid.encode([pregunta]).tolist()
        res = _chroma_col_vid.query(query_embeddings=emb, n_results=n_resultados)
        chunks = res.get("documents", [[]])[0]
        fuentes = [m.get("fuente","") for m in res.get("metadatas",[[]])[0]]
        return "\n\n".join([f"[{f}]\n{c}" for f,c in zip(fuentes,chunks)])[:2000]
    except Exception as e:
        print(f"⚠️ RAG búsqueda error: {e}")
        return ""

inicializar_rag_vid()



def generar_podcast_vid(tema: str, contexto_rag: str = ""):
    """Genera un podcast con dos voces sobre un tema agronómico"""
    import requests, base64, subprocess, tempfile, os
    import google.auth, google.auth.transport.requests

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    token = credentials.token
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base_url = "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/cleanbot-8f137/locations/us-central1/publishers/google/models"

    # Paso 1: Generar guión con Gemini REST
    prompt = f"""Sos un escritor de podcasts agronómicos para contratistas de viñas de Mendoza.
Generá un diálogo entre dos presentadores:
- Carlos: agrónomo experto, voz masculina
- Ana: contratista experimentada, voz femenina

Tema: {tema}
{"Info técnica: " + contexto_rag[:1000] if contexto_rag else ""}

Reglas:
- 2 minutos de audio aproximadamente
- Español rioplatense con "che", "mirá", "sabés qué"
- Datos técnicos concretos con productos y dosis
- Solo el diálogo, formato: Carlos: texto\nAna: texto\n...

Diálogo:"""

    r1 = requests.post(
        f"{base_url}/gemini-2.5-flash:generateContent",
        json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
        headers=headers, timeout=120
    )
    if r1.status_code != 200:
        raise Exception(f"Error guión: {r1.text[:200]}")
    guion = r1.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    # Paso 2: Generar audio con Gemini TTS REST
    r2 = requests.post(
        f"{base_url}/gemini-3.1-flash-tts-preview:generateContent",
        json={
            "contents": [{"role": "user", "parts": [{"text": guion}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "multiSpeakerVoiceConfig": {
                        "speakerVoiceConfigs": [
                            {"speaker": "Carlos", "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Puck"}}},
                            {"speaker": "Ana", "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Kore"}}}
                        ]
                    }
                }
            }
        },
        headers=headers, timeout=120
    )
    if r2.status_code != 200:
        raise Exception(f"Error TTS: {r2.text[:200]}")

    audio_pcm = base64.b64decode(r2.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])

    # Paso 3: Convertir PCM a OGG
    with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as f:
        f.write(audio_pcm)
        pcm_path = f.name
    ogg_path = pcm_path.replace(".pcm", ".ogg")
    subprocess.run(["ffmpeg", "-f", "s16le", "-ar", "24000", "-ac", "1",
        "-i", pcm_path, "-c:a", "libopus", ogg_path, "-y"], capture_output=True, check=True)
    with open(ogg_path, "rb") as f:
        ogg_bytes = f.read()
    os.unlink(pcm_path)
    os.unlink(ogg_path)
    return ogg_bytes, guion


def consultar_gemini(texto: str, contexto: str, imagen_path: str = None) -> str:
    try:
        prompt = f"{SYSTEM_PROMPT}\n\n{contexto}Usuario: {texto}"
        if imagen_path and os.path.exists(imagen_path):
            import PIL.Image
            imagen = PIL.Image.open(imagen_path)
            response = model.generate_content([prompt, Part.from_data(open(imagen_path, 'rb').read(), mime_type='image/jpeg')])
        else:
            response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error al consultar Gemini: {str(e)}"

# ============================================================
# AUDIO
# ============================================================
def generar_audio(texto: str) -> str:
    """
    Genera audio OGG con voz Puck (igual que /podcast)
    """
    import requests, base64, subprocess, tempfile, os, google.auth, google.auth.transport.requests
    try:
        texto = texto[:8000]
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        token = credentials.token
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        base_url = "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/cleanbot-8f137/locations/us-central1/publishers/google/models"

        # Detectar emociones automaticamente
        try:
            prompt_emo = f"Agrega etiquetas [serious] [panicked] [excited] [calm] al texto segun contexto. Solo devuelve el texto con etiquetas: {texto}"
            r_emo = requests.post(
                f"{base_url}/gemini-2.5-flash:generateContent",
                json={"contents": [{"role": "user", "parts": [{"text": prompt_emo}]}]},
                headers=headers, timeout=30
            )
            if r_emo.status_code == 200:
                texto = r_emo.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                print(f"Emociones: {texto[:80]}")
        except Exception as e:
            print(f"Error emociones: {e}")
        
        r = requests.post(
            f"{base_url}/gemini-3.1-flash-tts-preview:generateContent",
            json={
                "contents": [{"role": "user", "parts": [{"text": texto}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {"voiceName": "Puck"}
                        }
                    }
                }
            },
            headers=headers, timeout=120
        )
        
        if r.status_code != 200:
            print(f"Error TTS: {r.text[:200]}")
            return None
        
        # Decodificar PCM
        audio_pcm = base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
        
        # Convertir PCM a OGG (como /podcast)
        with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as f:
            f.write(audio_pcm)
            pcm_path = f.name
        
        ogg_path = pcm_path.replace(".pcm", ".ogg")
        subprocess.run(
            ["ffmpeg", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", pcm_path, "-c:a", "libopus", ogg_path, "-y"],
            capture_output=True, check=True
        )
        
        with open(ogg_path, "rb") as f:
            ogg_bytes = f.read()
        
        os.unlink(pcm_path)
        os.unlink(ogg_path)
        
        return base64.b64encode(ogg_bytes).decode('utf-8')
    
    except Exception as e:
        print(f"Error TTS: {e}")
        return None
        
        audio_pcm = base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
        return base64.b64encode(audio_pcm).decode('utf-8')
    
    except Exception as e:
        print(f"Error TTS: {e}")
        return None

# ============================================================
# SERVIDOR SOCKET
# ============================================================
def transcribir_audio(audio_b64: str) -> str:
    try:
        from google.cloud import speech
        audio_bytes = base64.b64decode(audio_b64)
        client = speech.SpeechClient()
        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            sample_rate_hertz=16000,
            language_code="es-US"
        )
        response = client.recognize(config=config, audio=audio)
        texto = " ".join([r.alternatives[0].transcript for r in response.results])
        return texto.strip()
    except Exception as e:
        print(f"Error transcribiendo: {e}")
        return ""

def manejar_cliente(conn):
    try:
        datos = b''
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            datos += chunk
            if datos.endswith(b'\n'):
                break

        request = json.loads(datos.decode('utf-8').strip())
        texto = request.get('texto', '')
        tipo = request.get('tipo', 'texto')
        
        if tipo == 'clima':
            lat = request.get('lat', 0)
            lon = request.get('lon', 0)
            clima = obtener_clima(lat, lon)
            resultado = json.dumps({'texto': clima, 'audio': None}) + '\n'
            conn.sendall(resultado.encode('utf-8'))
            return
        


        if tipo == 'podcast':
            tema = request.get('tema', '')
            contexto_rag = buscar_contexto_vid(tema, n_resultados=3)
            try:
                ogg_bytes, guion = generar_podcast_vid(tema, contexto_rag)
                import base64 as b64
                resultado = json.dumps({
                    'audio': b64.b64encode(ogg_bytes).decode('utf-8'),
                    'guion': guion[:500],
                    'error': None
                }) + '\n'
            except Exception as e:
                resultado = json.dumps({'audio': None, 'guion': None, 'error': str(e)}) + '\n'
            conn.sendall(resultado.encode('utf-8'))
            return

        if tipo == 'informe':
            diagnostico = request.get('diagnostico', '')
            imagen_path = request.get('imagenPath', '')
            nombre = request.get('nombre', 'Contratista')
            try:
                pdf_bytes = generar_informe_pdf_agro(diagnostico, imagen_path, nombre)
                pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
                resultado = json.dumps({'pdf': pdf_b64, 'error': None}) + '\n'
            except Exception as e:
                resultado = json.dumps({'pdf': None, 'error': str(e)}) + '\n'
            conn.sendall(resultado.encode('utf-8'))
            return

        if tipo == 'audio':
            audio_b64 = request.get('audio', '')
            transcripcion = transcribir_audio(audio_b64)
            resultado = json.dumps({'texto': transcripcion, 'audio': None}) + '\n'
            conn.sendall(resultado.encode('utf-8'))
            return
        contexto = request.get('contexto', '')
        imagen_path = request.get('imagenPath', '')
        user_id = request.get('userId', 'unknown')

        # Contexto bayesiano
        perfil = actualizar_perfil(user_id, texto)
        contexto_bayesiano = generar_contexto_bayesiano(user_id)
        contexto_completo = contexto
        if contexto_bayesiano:
            contexto_completo += '\nCONTEXTO BAYESIANO: ' + contexto_bayesiano

        respuesta_texto = consultar_gemini(texto, contexto_completo, imagen_path if imagen_path else None)
        audio_b64 = generar_audio(respuesta_texto)

        resultado = json.dumps({
            'texto': respuesta_texto,
            'audio': audio_b64
        }) + '\n'

        conn.sendall(resultado.encode('utf-8'))
    except Exception as e:
        error = json.dumps({'texto': f'Error: {str(e)}', 'audio': None}) + '\n'
        conn.sendall(error.encode('utf-8'))
    finally:
        conn.close()

def iniciar_servidor():
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen(5)
    os.chmod(SOCKET_PATH, 0o777)

    print(f"Servidor escuchando en {SOCKET_PATH}")

    while True:
        conn, _ = server.accept()
        hilo = threading.Thread(target=manejar_cliente, args=(conn,))
        hilo.daemon = True
        hilo.start()

if __name__ == "__main__":
    iniciar_servidor()
