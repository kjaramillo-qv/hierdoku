#!/usr/bin/env python3
"""Ingesta HIBRIDA (denso jina 1024 + sparse BM25/IDF) a Qdrant.

Uso:
  python ingesta_hibrida.py --file <ruta> --collection <coll> \
      [--directorio <dir>] [--tipo <tipo>]

- Densos: OmniRoute /v1/embeddings, modelo jina-embeddings-v5-text-small (1024d).
- Sparse: fastembed Qdrant/bm25 (IDF) -> el mismo modelo debe usarse al consultar.
- Chunking: recursivo por separadores, ~1000 chars, overlap 150.
- Upsert: vectores NOMBRADOS {dense, sparse} + payload {text, archivo, directorio, tipo}.
"""
import argparse, json, os, sys, uuid, urllib.request

QDRANT = "http://host.docker.internal:6333"
EMB_URL = "http://host.docker.internal:20128/v1/embeddings"
DENSE_MODEL = "jina-ai/jina-embeddings-v5-text-small"
DENSE_DIM = 1024
SPARSE_MODEL = "Qdrant/bm25"


def _post(url, payload, timeout=120):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _put(url, payload, timeout=120):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def recursive_split(text, size=1000, overlap=150):
    """Split respetando separadores (parrafos>lineas>frases>palabras)."""
    seps = ["\n\n", "\n", ". ", " "]

    def _split(t, seps):
        if len(t) <= size:
            return [t] if t.strip() else []
        if not seps:
            # corte duro
            return [t[i:i + size] for i in range(0, len(t), size - overlap)]
        sep = seps[0]
        parts = t.split(sep)
        chunks, cur = [], ""
        for p in parts:
            piece = (p + sep)
            if len(cur) + len(piece) <= size:
                cur += piece
            else:
                if cur.strip():
                    chunks.append(cur)
                if len(piece) > size:
                    chunks.extend(_split(p, seps[1:]))
                    cur = ""
                else:
                    cur = piece
        if cur.strip():
            chunks.append(cur)
        return chunks

    raw = _split(text, seps)
    # aplicar overlap entre chunks consecutivos
    out = []
    for i, c in enumerate(raw):
        c = c.strip()
        if not c:
            continue
        if out and overlap > 0:
            tail = out[-1][-overlap:]
            c = tail + c
        out.append(c)
    return out


def dense_embed(texts):
    res = _post(EMB_URL, {"model": DENSE_MODEL, "input": texts})
    vecs = [d["embedding"] for d in res["data"]]
    for v in vecs:
        if len(v) != DENSE_DIM:
            raise SystemExit(f"dim densa {len(v)} != {DENSE_DIM}")
    return vecs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--collection", required=True)
    ap.add_argument("--directorio", default="")
    ap.add_argument("--tipo", default="documento")
    args = ap.parse_args()

    with open(args.file, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    if not text.strip():
        raise SystemExit("archivo vacio")

    chunks = recursive_split(text)
    if not chunks:
        raise SystemExit("sin chunks")

    # densos (batch) + sparse (fastembed)
    dense = dense_embed(chunks)
    from fastembed import SparseTextEmbedding
    sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL)
    sparse = list(sparse_model.embed(chunks))

    archivo = os.path.basename(args.file)
    points = []
    for i, ch in enumerate(chunks):
        sp = sparse[i]
        points.append({
            "id": str(uuid.uuid4()),
            "vector": {
                "dense": dense[i],
                "sparse": {
                    "indices": sp.indices.tolist(),
                    "values": sp.values.tolist(),
                },
            },
            "payload": {
                "text": ch,
                "archivo": archivo,
                "directorio": args.directorio,
                "tipo": args.tipo,
                "chunk": i,
            },
        })

    url = f"{QDRANT}/collections/{args.collection}/points?wait=true"
    r = _put(url, {"points": points})
    print(json.dumps({
        "collection": args.collection,
        "archivo": archivo,
        "chunks": len(chunks),
        "status": r.get("status"),
        "result": r.get("result"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
