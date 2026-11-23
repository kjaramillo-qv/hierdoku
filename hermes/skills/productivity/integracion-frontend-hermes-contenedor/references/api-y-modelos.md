# API OpenAI-compatible y catálogo de modelos de Hermes

## Endpoint de chat

`POST http://hermes:8642/v1/chat/completions` (nombre de servicio en la red
compose; desde el host `localhost:8642` o `host.docker.internal:8642`).

Body:

```json
{
  "model": "claude-opus-4-8",
  "provider": "anthropic",
  "messages": [{"role": "user", "content": "..."}]
}
```

- Header `Authorization: Bearer <API_SERVER_KEY>`.
- Mandar `provider` fuerza el cambio de proveedor/modelo en vivo para esa
  petición (siempre respetado). Solo `model` sin `provider` puede caer al default
  a menos que `direct_model_requests` esté activo.
- Respuesta OpenAI estándar: `res.json()["choices"][0]["message"]["content"]`.
- 401/403 = clave inválida (`API_SERVER_KEY`).

`/v1/models` devuelve solo el modelo virtual `hermes-agent`; NO usarlo para
poblar selectores.

## Catálogo real (para el selector de la barra lateral)

```python
from hermes_cli.inventory import build_models_payload, load_picker_context
ctx = load_picker_context()
payload = build_models_payload(ctx, include_unconfigured=True,
                               picker_hints=True, max_models=50)
for p in payload["providers"]:
    # p: slug, name, authenticated (bool), is_current (bool), models[]
    ...
```

- Existen ~47 slugs de proveedor (anthropic, openai-api, openrouter, gemini,
  deepseek, xai, zai, minimax, nous, bedrock, vertex, etc.). La mayoría llega con
  `authenticated=False` (sin API key configurada).
- Mostrar en el selector SOLO los `authenticated=True`, con sus `models` reales.
  En este proyecto: Anthropic (modelos claude-*) y openai-api (gpt-*) suelen ser
  los autenticados; MoA y OpenCode-Free también pueden aparecer.
- No listar proveedores sin credencial: el usuario elegiría algo que devuelve
  error de auth.

## Marca del frontend Streamlit

El skin de Hermes NO pinta Streamlit. Inyecta CSS con los mismos hex de marca:

```python
st.markdown(f"""<style>
  .stApp {{ background-color: {BG}; color: {TEXT}; }}
  .stButton>button {{ background-color: {ACCENT}; color: #0B1116; }}
</style>""", unsafe_allow_html=True)
```

El logo (JPG/PNG/data-URL) se muestra con `st.image` o `st.markdown`; en la
terminal la marca es solo colores + nombre.
