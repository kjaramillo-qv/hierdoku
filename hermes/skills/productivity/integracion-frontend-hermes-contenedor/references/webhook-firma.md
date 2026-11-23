# Firma de webhooks Hermes (para clientes que hacen POST)

Fuente: `gateway/platforms/webhook.py`. El adaptador prueba varios esquemas de
firma según los headers presentes. Para un cliente propio (frontend Streamlit,
servicio externo) el más robusto es el V2 genérico.

## V2 genérico (recomendado, anti-replay)

- `X-Webhook-Timestamp: <unix-segundos>`
- `X-Webhook-Signature-V2: <hex HMAC-SHA256 de "<timestamp>.<body>">`
- La presencia de `X-Webhook-Signature-V2` SELECCIONA modo V2 y se compromete a
  él: no cae a V1 aunque el timestamp falte/expire.

Python (cliente):

```python
import time, hmac, hashlib, json, requests

body = json.dumps({"app": "...", "link": "...", "credenciales": "...",
                   "requerimientos": "..."}).encode()
ts = str(int(time.time()))
mac = hmac.new(secret.encode(), (ts + "." + body.decode()).encode(),
               hashlib.sha256).hexdigest()
headers = {
    "Content-Type": "application/json",
    "X-Webhook-Timestamp": ts,
    "X-Webhook-Signature-V2": mac,
}
# CLAVE: enviar los MISMOS bytes que se firmaron -> data=body, no json=
r = requests.post(url, data=body, headers=headers, timeout=60)
# 200/202 = aceptado; 401/403 = firma rechazada
```

## Otros esquemas aceptados (por si integras un servicio conocido)

- GitHub: `X-Hub-Signature-256: sha256=<hex HMAC-SHA256 del body>`
- GitLab: `X-Gitlab-Token: <secreto en claro>`
- Linear: `linear-signature: <hex HMAC-SHA256 del body>`
- Svix/AgentMail: headers `svix-id`, `svix-timestamp`, `svix-signature`;
  contenido firmado `"{id}.{timestamp}.{body}"`, secreto suele empezar `whsec_`.
- V1 legacy (deprecado, sin anti-replay): `X-Webhook-Signature` = HMAC del body
  solo. Aún aceptado con warning.

## Notas operativas

- Cada ruta puede tener su propio `--secret`; si no, usa el secreto global de la
  plataforma (`platforms.webhook.extra.secret`).
- Secreto de testing `INSECURE_NO_AUTH` salta validación (solo pruebas).
- Rate limit por ruta (ventana fija, `extra.rate_limit`, def. 30/min) e
  idempotencia por delivery-id para no duplicar corridas en reintentos.
- `--deliver-only` entrega el prompt renderizado como mensaje directo (sin correr
  el agente, coste 0). Requiere un `--deliver` real (no `log`).
