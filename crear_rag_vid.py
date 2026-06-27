import os
import PyPDF2
import chromadb
from sentence_transformers import SentenceTransformer

DOCS_DIR = "/root/bot_whatsapp/documentos_vid"
VECTOR_DIR = "/root/bot_whatsapp/vectordb_vid"

print("🔄 Iniciando creación de base vectorial para bot de vid...")
print("🔄 Cargando modelo de embeddings...")

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
client = chromadb.PersistentClient(path=VECTOR_DIR)

# Eliminar colección existente si hay
try:
    client.delete_collection("documentos_vid")
except:
    pass

collection = client.create_collection("documentos_vid")

def dividir_en_chunks(texto, max_chars=800):
    parrafos = texto.split("\n\n")
    chunks = []
    chunk_actual = ""
    for parrafo in parrafos:
        if len(chunk_actual) + len(parrafo) < max_chars:
            chunk_actual += parrafo + "\n\n"
        else:
            if chunk_actual.strip():
                chunks.append(chunk_actual.strip())
            chunk_actual = parrafo + "\n\n"
    if chunk_actual.strip():
        chunks.append(chunk_actual.strip())
    return chunks if chunks else [texto[:max_chars]]

archivos_procesados = 0
total_chunks = 0

for archivo in sorted(os.listdir(DOCS_DIR)):
    ruta = os.path.join(DOCS_DIR, archivo)
    texto = ""

    if archivo.endswith(".txt"):
        try:
            with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
                texto = f.read()
        except Exception as e:
            print(f"❌ Error leyendo {archivo}: {e}")
            continue

    elif archivo.endswith(".pdf"):
        try:
            with open(ruta, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                texto = "".join([p.extract_text() or "" for p in reader.pages])
        except Exception as e:
            print(f"❌ Error leyendo {archivo}: {e}")
            continue

    if len(texto.strip()) < 100:
        print(f"⚠️ Saltando {archivo} (vacío o muy corto)")
        continue

    chunks = dividir_en_chunks(texto)
    embeddings = model.encode(chunks).tolist()

    ids = [f"{archivo}_{i}" for i in range(len(chunks))]
    metadatas = [{"fuente": archivo} for _ in chunks]

    collection.add(
        documents=chunks,
        embeddings=embeddings,
        ids=ids,
        metadatas=metadatas
    )

    print(f"✅ {archivo}: {len(chunks)} chunks")
    archivos_procesados += 1
    total_chunks += len(chunks)

print(f"\n✅ Base vectorial creada")
print(f"📄 Archivos procesados: {archivos_procesados}")
print(f"🔢 Total chunks: {total_chunks}")
