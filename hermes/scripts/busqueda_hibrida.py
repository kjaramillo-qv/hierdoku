#!/usr/bin/env python3
"""Busqueda HIBRIDA en Qdrant (dense jina 1024 + sparse BM25) con fusion RRF.

Uso: python busqueda_hibrida.py --collection <coll> --query "<pregunta>" [--k 5]
Debe usar los MISMOS modelos que la ingesta (jina 1024 + Qdrant/bm25).
"""
import argparse, json, urllib.request

QDRANT = "http://host.docker.internal:6333"
EMB_URL = "http://host.docker.internal:20128/v1/embeddings"
DENSE_MODEL = "jina-ai/jina-embeddings-v5-text-small"
SPARSE_MODEL = "Qdrant/bm25"


def _post(url, payload, timeout=60):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def dense_embed(text):
    return _post(EMB_URL, {"model": DENSE_MODEL, "input": [text]})["data"][0]["embedding"]


def search(collection, query, k=5):
    dv = dense_embed(query)
    from fastembed import SparseTextEmbedding
    sm = SparseTextEmbedding(model_name=SPARSE_MODEL)
    sp = list(sm.query_embed(query))[0]
    body = {
        "prefetch": [
            {"query": dv, "using": "dense", "limit": k * 4},
            {"query": {"indices": sp.indices.tolist(), "values": sp.values.tolist()},
             "using": "sparse", "limit": k * 4},
        ],
        "query": {"fusion": "rrf"},
        "limit": k,
        "with_payload": True,
    }
    url = f"{QDRANT}/collections/{collection}/points/query"
    return _post(url, body)["result"]["points"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()
    hits = search(args.collection, args.query, args.k)
    for h in hits:
        pl = h.get("payload", {})
        print(round(h.get("score", 0), 4), "|", pl.get("archivo"), "|",
              pl.get("tipo"), "|", str(pl.get("text"))[:100])


if __name__ == "__main__":
    main()
