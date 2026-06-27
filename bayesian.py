import json
import os
from datetime import datetime

BAYESIAN_FILE = '/root/bot_whatsapp/bayesian_data.json'

# Enfermedades y temas conocidos del vinedo
TEMAS = {
    'mildiu': ['mildiu', 'mildiú', 'peronóspora', 'mancha', 'hongo', 'humedad'],
    'oidio': ['oídio', 'oidio', 'polvo', 'cenicilla', 'blanco'],
    'botrytis': ['botrytis', 'podredumbre', 'gris', 'moho'],
    'helada': ['helada', 'frio', 'frío', 'temperatura', 'hielo'],
    'plagas': ['plaga', 'insecto', 'oruga', 'araña', 'trips', 'cochinilla'],
    'poda': ['poda', 'corte', 'brazos', 'sarmiento', 'yema'],
    'riego': ['riego', 'agua', 'goteo', 'humedad', 'sequía'],
    'nutricion': ['abono', 'fertilizante', 'nutriente', 'nitrogeno', 'fosforo'],
    'vendimia': ['vendimia', 'cosecha', 'uva', 'grado', 'madurez'],
    'clima': ['clima', 'tiempo', 'lluvia', 'viento', 'granizo']
}

def cargar_datos():
    if os.path.exists(BAYESIAN_FILE):
        try:
            return json.load(open(BAYESIAN_FILE))
        except:
            pass
    return {}

def guardar_datos(datos):
    json.dump(datos, open(BAYESIAN_FILE, 'w'), indent=2, ensure_ascii=False)

def detectar_temas(texto):
    texto_lower = texto.lower()
    temas_detectados = []
    for tema, palabras in TEMAS.items():
        for palabra in palabras:
            if palabra in texto_lower:
                temas_detectados.append(tema)
                break
    return temas_detectados

def actualizar_perfil(user_id: str, texto: str, clima: dict = None):
    datos = cargar_datos()
    
    if user_id not in datos:
        datos[user_id] = {
            'consultas': 0,
            'temas': {},
            'ultima_consulta': None,
            'clima_zona': None
        }
    
    perfil = datos[user_id]
    perfil['consultas'] += 1
    perfil['ultima_consulta'] = datetime.now().isoformat()
    
    # Actualizar frecuencia de temas
    temas = detectar_temas(texto)
    for tema in temas:
        perfil['temas'][tema] = perfil['temas'].get(tema, 0) + 1
    
    # Guardar clima si se provee
    if clima:
        perfil['clima_zona'] = clima
    
    guardar_datos(datos)
    return perfil

def generar_contexto_bayesiano(user_id: str, clima_actual: dict = None) -> str:
    datos = cargar_datos()
    
    if user_id not in datos:
        return ''
    
    perfil = datos[user_id]
    contexto = ''
    
    # Temas mas frecuentes del usuario
    if perfil['temas']:
        temas_ordenados = sorted(perfil['temas'].items(), key=lambda x: x[1], reverse=True)
        top_temas = temas_ordenados[:3]
        contexto += f'Este usuario consulta frecuentemente sobre: {", ".join([t[0] for t in top_temas])}. '
        
        # Probabilidades bayesianas
        total = sum(perfil['temas'].values())
        contexto += 'Probabilidades de interes: '
        for tema, count in top_temas:
            prob = round(count / total * 100)
            contexto += f'{tema} ({prob}%), '
        contexto = contexto.rstrip(', ') + '. '
    
    # Alertas basadas en clima actual
    if clima_actual:
        humedad = clima_actual.get('humedad', 0)
        temp = clima_actual.get('temp', 20)
        
        if humedad >= 85:
            contexto += 'ALERTA BAYESIANA: Alta humedad detectada, priorizar respuestas sobre mildiu y botrytis. '
        if humedad >= 70 and temp >= 15:
            contexto += 'ALERTA BAYESIANA: Condiciones favorables para oidio. '
        if temp <= 3:
            contexto += 'ALERTA BAYESIANA: Temperatura critica, priorizar informacion sobre heladas. '
    
    # Recomendacion personalizada
    if perfil['consultas'] > 5 and perfil['temas']:
        tema_principal = max(perfil['temas'], key=perfil['temas'].get)
        contexto += f'Usuario experto en consultas de {tema_principal}, dar respuestas tecnicas detalladas. '
    
    return contexto

