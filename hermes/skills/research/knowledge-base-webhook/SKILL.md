---
name: knowledge-base-webhook
description: Answer doc/manual/process questions from a vector KB.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [rag, vector-database, documentation, webhook, knowledge-base]
    related_skills: []
---

# Knowledge Base Webhook Skill

Answers any question about documentation, manuals, technical processes, or
internal information by querying a vector knowledge base over an HTTP webhook
(backed by n8n + a vector DB). NEVER guess or answer from general knowledge for
these questions — always retrieve grounded content from the endpoint first.

## Embedding Alignment (CRITICAL for query side)

The n8n INGEST flow embeds via OmniRoute (OpenAI-compatible base
`http://host.docker.internal:20128/v1`, provider = Jina) using model
`jina-ai/jina-embeddings-v5-text-small` => **1024 dims**. Collection is created
on first real ingest with this dimension.

When you later QUERY Qdrant directly you MUST embed the query with the SAME
model/dim (1024d via OmniRoute jina-embeddings-v5-text-small) — NOT
nomic-embed-text (768d), or Qdrant rejects the search on dimension mismatch.
Recommended collection config: Global search (one collection per company/
project, no multitenancy) + Simple Single dense embedding. Optional quality
boost at query time only: jina-reranker-v3 (does not change the collection).

OmniRoute other Jina dims (measured): v5-text-nano=768d, v4=2048d,
clip-v2=1024d. The API key is user-supplied and ephemeral — never persist it.

## Two Endpoints: Ingest (write) vs Query (read)

This vector KB has TWO n8n webhooks:

- INGEST (write / upload requirements): POST to
  `http://host.docker.internal:5678/webhook/ae86d922-4760-4053-a79d-727955cd5618`
  The workflow takes whatever you send, converts it (embeddings) and stores it in
  the vector DB. Use this whenever you have EXTRACTED requirements/content that
  must be persisted so it can be retrieved later. Send the FULL extracted content
  (do not summarize/truncate). Never POST test junk — only real captured content.
- QUERY (read / ask): POST to the query webhook below (`chatInput`) or query
  Qdrant directly. Use this to retrieve grounded content afterwards.

Typical flow: someone tells you WHERE and HOW to extract requirements -> you
extract them -> POST the complete extraction to the INGEST webhook -> later you
read them back via the QUERY webhook / Qdrant. If unsure which JSON key the
INGEST flow expects, probe it once and inspect the n8n response before bulk
uploading.

## When to Use

- The user asks to consult documentation, manuals, or technical processes.
- The user asks anything whose authoritative answer lives in the internal
  knowledge base.
- Don't use for: general/unrelated questions with no internal-doc scope.

## Prerequisites

- The webhook endpoint must be reachable from this machine:
  `http://host.docker.internal:5678/webhook/66834f95-a7ce-4444-b36b-9561e65f1d59`
  (an n8n production webhook backed by the vector DB; n8n runs in Docker).
- No auth header is required by default.

## How to Run

Send an HTTP request using the POST method with a JSON body containing the
user's exact question under the `chatInput` key. The n8n workflow reads the
value via the expression `$json.body.chatInput`, so the body form is required
(POST, not GET). Use the `terminal` tool with `curl`:

```
curl -sS -X POST \
  http://host.docker.internal:5678/webhook/66834f95-a7ce-4444-b36b-9561e65f1d59 \
  -H "Content-Type: application/json" \
  -d '{"chatInput": "THE USER EXACT QUESTION"}'
```

Pass the user's question verbatim (properly JSON-escaped). Read the text the API
returns and use it as the factual basis for your final written answer.

## Procedure

1. Take the user's exact question and place it as the value of `chatInput`.
   - Completion: payload is exactly `{"chatInput": "<exact question>"}`.
2. Send it to the webhook via `terminal` + `curl` using the POST method
   (command above). Always POST with a JSON body; GET will not work because the
   workflow reads `$json.body.chatInput`.
   - Completion: the request returns a body without a curl/network error.
3. Parse the response. It comes back as JSON `{"output": "..."}` (may also be
   plain text or `{"text": "..."}`). Extract the human-readable answer text.
   - Completion: you have the returned answer string in hand.
4. Write your final reply to the user grounded ONLY in that returned text.
   Do not add invented details. If the response is empty or unhelpful, say so
   plainly rather than filling gaps with guesses.
   - Completion: reply is based on retrieved content, not prior assumptions.

## Pitfalls

- This is an n8n production `/webhook/` URL served from a Docker container
  (hence `host.docker.internal`). If you get a 404 saying the webhook is not
  registered, tell the user to activate the n8n workflow rather than
  fabricating an answer.
- The workflow expects the question in the request BODY (`$json.body.chatInput`).
  Sending it as a URL query parameter, or using GET, returns an empty body.
- Escape quotes/newlines in the question so the JSON body stays valid; prefer
  building the payload safely instead of naive string interpolation.
- Never answer documentation questions from memory when this endpoint is the
  designated source of truth.

## Verification

- Confirm the POST returned a non-empty body and your answer quotes/derives from
  that body's content, not from general knowledge.
