---
name: qdrant-direct-search
description: Query Qdrant directly with Ollama embeddings.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [rag, qdrant, embeddings, ollama, vector-search, knowledge-base]
    related_skills: [knowledge-base-webhook]
---

# Búsqueda directa en Qdrant (RAG barato y efectivo)

Consulta la base vectorial Qdrant directamente, sin pasar por el webhook de n8n,
para extraer los fragmentos reales de documentación (texto, imágenes,
admonitions) gastando menos tokens y tiempo.

## Cuándo usar

- Necesitas el CONTENIDO real de la documentación (estilo, pasos, aspecto), no
  solo saber qué documentos existen.
- El webhook de n8n devuelve solo títulos/metadata y no el cuerpo (síntoma de
  colección mal ingestada — ver Pitfalls).
- Quieres ahorrar tokens saltándote el LLM intermedio del flujo n8n.

## Infraestructura (verificada 2026-09)

- Qdrant REST: `http://host.docker.internal:6333` (NO localhost).
- Ollama embeddings: `http://host.docker.internal:11434/api/embeddings`,
  modelo `nomic-embed-text` → vectores de 768 dims (gratis, local).
- Listar colecciones: `GET /collections`. Inspeccionar una:
  `GET /collections/<name>` (mira `config.params.vectors.size`) y
  `POST /collections/<name>/points/scroll {"limit":2,"with_payload":true}`.

## Procedimiento

1. Elige la colección BIEN ingestada: su `points/scroll` muestra `content` con
   texto markdown real (no `"1.8 kB"` ni `"text/markdown"`).
2. Genera el embedding de la pregunta con Ollama (dim debe coincidir con la
   colección: 768 para `nomic-embed-text`).
3. Busca por vector: `POST /collections/<name>/points/search`.
4. Usa los `content` de los hits (con su `score`) como base factual.

### Script

```python
import json, urllib.request
OLLAMA="http://host.docker.internal:11434/api/embeddings"
COLL="documentacion_izytesting"  # ajustar a la colección buena del proyecto
QDRANT=f"http://host.docker.internal:6333/collections/{COLL}/points/search"

def post(url, payload):
    req=urllib.request.Request(url, data=json.dumps(payload).encode(),
                               headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))

def embed(t): return post(OLLAMA, {"model":"nomic-embed-text","prompt":t})["embedding"]
def search(q, k=5):
    return post(QDRANT, {"vector":embed(q),"limit":k,"with_payload":True})["result"]

for h in search("tu pregunta aquí", 5):
    print(round(h["score"],3), h["payload"]["content"][:200])
```

## Pitfalls

- Nombres de colección pueden venir con comillas simples dentro del string
  (p.ej. `'docs_izytesting_1024'`); pásalos tal cual, URL-encoded si hace falta.
- Colección MAL ingestada: `content` contiene metadata del blob (`"1.8 kB"`,
  `"text/markdown"`, `"application/json"`) en vez del texto. NO sirve; el webhook
  de n8n puede estar apuntando ahí — por eso "no trae contenido".
- La dimensión del vector de consulta DEBE igualar la de la colección (768 vs
  1024). Mezclar dims da error o resultados basura.
- `localhost:6333` no conecta desde el contenedor; usa `host.docker.internal`.
- Qdrant `scroll` no filtra por substring; para keyword, trae los puntos y filtra
  en Python. Para semántica, usa `points/search` con el embedding.

## Verification

- `GET /collections` responde `status: ok`.
- Los hits de `points/search` traen `content` con markdown real y `score` > ~0.6
  para consultas on-topic.
