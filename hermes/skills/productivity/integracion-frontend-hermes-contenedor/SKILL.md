---
name: integracion-frontend-hermes-contenedor
description: "Conectar frontend web y webhooks al contenedor Hermes."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, frontend, webhook, docker, api-server, streamlit, branding, deployment]
    related_skills: [acceso-archivos-host-contenedor, onboarding-primera-vez]
---

# Integración de frontend web y pipelines al contenedor Hermes

Cómo dar a los usuarios finales una interfaz "montar y listo" sobre el
contenedor Hermes de este proyecto (Documentador HierDoku / QVision), sin que
instalen nada. Cubre: elección de superficie, API OpenAI-compatible, cambio de
modelo/proveedor en vivo, pipelines por webhook, marca (skin), y las reglas de
edición segura dentro del contenedor.

## When to Use

Carga esta skill cuando el usuario pida (a) que los usuarios finales interactúen
con el agente sin usar la terminal, (b) un frontend/página/web con la marca de la
empresa, (c) un selector de modelo/proveedor, (d) un "pipeline" o acción directa
que dispare al agente por webhook, o (e) que "solo con montar el contenedor" todo
quede listo. También aplica al editar la personalidad del agente, aplicar un skin
de marca, o reiniciar el gateway del contenedor.

Config de Hermes: NUNCA editar config.yaml a mano (rompe el gateway). Usar
`hermes config set KEY VALUE`. Secretos SIEMPRE en `.env`, referenciados desde
config.yaml con `${env:VAR}` (la config expande `${env:VAR}` y `${VAR}`).

## Elección de superficie (decisión clave)

Objetivo típico del usuario: "solo montar el contenedor y que el usuario tenga
todo, sin instalar ni recargar nada".

- **Correcto → frontend web** (el servicio `frontend` Streamlit del compose, o
  `hermes dashboard`). El usuario solo abre una URL. `docker compose up` lo deja
  listo. Esta es la superficie que cumple "montar y listo".
- **NO usar la app de escritorio nativa** para este objetivo: los desktop-plugins
  (`~/.hermes/desktop-plugins/`) se cargan desde el Windows de CADA usuario, no
  desde el contenedor. Montar el contenedor NO hace aparecer el plugin en la app
  de nadie. Solo tiene sentido si cada usuario instala la app de escritorio y
  copia el plugin — justo lo que se quiere evitar.
- Antes de construir un frontend nuevo, REVISA el compose: este proyecto ya trae
  un `frontend` (build ./frontend, Streamlit, publicado en puerto 80). Mejóralo
  en vez de duplicarlo con el dashboard nativo.

## API OpenAI-compatible (chat desde el frontend)

- Endpoint: `http://<host-o-servicio>:8642/v1/chat/completions`. Dentro de la red
  compose usa el nombre de servicio: `http://hermes:8642/...`.
- Auth: header `Authorization: Bearer ${API_SERVER_KEY}`. La clave sale de
  `API_SERVER_KEY` en `.env` (`gateway/platforms/api_server.py`). Vars relevantes:
  `API_SERVER_ENABLED=true`, `API_SERVER_HOST=0.0.0.0`.
- `/v1/models` solo anuncia el modelo virtual `hermes-agent` (= "usa el default
  del gateway"). NO lista los modelos reales.
- **Cambio de modelo/proveedor EN VIVO por petición**: manda `provider` y `model`
  en el body. Si envías `provider`, el override SIEMPRE se respeta
  (`_extract...` en api_server.py). Con solo `model` (sin provider) puede caer al
  default salvo que `direct_model_requests` esté activo.
- **La API KEY del proveedor NO se puede pasar por petición.** El body solo
  acepta `provider`/`model`/`model_options` (`_RUNTIME_AGENT_OVERRIDE_KEYS` filtra
  el resto). La clave del modelo (ANTHROPIC_API_KEY, OPENAI_API_KEY, …) se resuelve
  SIEMPRE desde la variable de entorno del proveedor vía `get_secret → os.environ`
  (`runtime_provider.py`, `agent/secret_scope.py`). Un frontend NO puede inyectar
  la key en el request; solo elegir proveedor/modelo entre los que ya tienen key.
- **El gateway lee `.env` SOLO al arrancar** (`gateway/run.py` → `load_hermes_dotenv`);
  no hay watcher de hot-reload del `.env`. Una key escrita en el `.env` DESPUÉS de
  que el contenedor arrancó NO se toma hasta reiniciar el gateway
  (`s6-svc -r /run/service/gateway-default`).

## Onboarding de la PRIMERA API key desde el frontend (usuario sin proveedor)

Un usuario de primera vez absoluta no tiene ninguna key → todo chat responde 401.
Como frontend y hermes SOLO comparten HTTP (8642/8644, sin volumen ni socket) y la
key no viaja por request (ver arriba), para que la cargue desde la web hay que (1)
hacer llegar la key al entorno de hermes y (2) reiniciar el gateway. Dos patrones,
elige por seguridad de distribución (ver `references/onboarding-primera-key.md`):

- **B (recomendada, sin privilegios): archivo de claves compartido + watcher.**
  Volumen compartido con un env-file pequeño (frontend rw, hermes rw/ro). En esta
  imagen s6 el entrypoint NO lanza su propio gateway (lo hace el servicio s6
  `gateway-default` con `--replace`, que desplazaría cualquier gateway propio);
  en su lugar sincroniza las keys a `/opt/data/.env` y reinicia el servicio con
  `s6-svc -r`. El frontend solo escribe texto; nunca toca Docker. Es la única
  apta para entregar a terceros. Entregas el archivo vacío → el cliente lo llena
  desde la web en su primer uso (no tocas el `.env` grande a mano). Scripts
  listos y probados: `scripts/hermes-entrypoint-s6.sh` + `scripts/sync_keys.py`.
- **A (más simple, insegura): docker.sock en el frontend.** El frontend escribe la
  key y hace `docker restart hermes`. Requiere montar `/var/run/docker.sock` en el
  contenedor web expuesto en :80 = root sobre el host (peor aún combinado con el
  bind de C: completo en hermes). Solo para uso interno en tu propia máquina.

La key de EMBEDDINGS (OmniRoute) ya viene preconfigurada por el operador vía
compose y NO entra en este onboarding; el usuario final solo carga la key del
modelo de chat.
- **TRAMPA que rompe el Patrón B en silencio:** hermes carga DOS `.env` y el de
  HOME (`${USERPROFILE}/.hermes/.env` = `/opt/data/.env`) se carga con
  `override=True`, así que PISA la key que el entrypoint exportó desde el env-file
  compartido. Si `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` siguen con valor ahí, el
  cliente carga su key pero el gateway usa la vieja. Hay que vaciar la key del
  modelo en AMBOS `.env` (proyecto + home) antes de entregar. Detalle, mecánica
  del entrypoint (parseo sin `source`, ready-file, s6 CMD) y limpieza de entrega en
  `references/onboarding-primera-key.md`.
- `hermes config check` (config faltante) + `hermes doctor` (health) sirven para
  detectar el estado "sin configurar". `hermes config env-path` da la ruta del
  `.env` del perfil activo. Multi-usuario real ⇒ un perfil por usuario
  (`~/.hermes/profiles/<name>/`) para aislar `.env`/config.

## Catálogo real de proveedores/modelos (para poblar un selector)

`/v1/models` no sirve. Genera el catálogo desde el inventario (dentro del venv
`/opt/hermes/.venv`):

```python
from hermes_cli.inventory import build_models_payload, load_picker_context
ctx = load_picker_context()
payload = build_models_payload(ctx, include_unconfigured=True, picker_hints=True, max_models=50)
# cada provider: slug, name, authenticated, is_current, models[]
```

Muestra al usuario SOLO los proveedores con `authenticated=True` (los que tienen
credencial y de verdad funcionan). Los ~47 slugs existen aunque no tengan key.
Ver `references/api-y-modelos.md`.

## Pipeline por webhook (acción directa sin chat)

Activar plataforma (una vez): `hermes config set platforms.webhook.enabled true`,
`...extra.port 8644`, `...extra.secret '${env:WEBHOOK_SECRET}'`, y `WEBHOOK_SECRET`
en `.env`. Publicar el puerto 8644 en el compose del servicio hermes para
llamadas externas. Requiere reiniciar el gateway.

Crear ruta: `hermes webhook subscribe <nombre> --prompt '...{payload.campo}...'
--deliver log --secret <secreto-propio>`. La plantilla mapea campos del POST con
`{dot.notation}`. Probar: `hermes webhook test <nombre> --payload '{...}'` (202 =
ok).

**Firma HMAC que debe generar el frontend** (V2 genérico, con anti-replay):
- Header `X-Webhook-Timestamp: <unix-segundos>`
- Header `X-Webhook-Signature-V2: hex(HMAC_SHA256(secret, "<timestamp>.<body>"))`
- El body firmado debe ser EXACTAMENTE los mismos bytes enviados. En Python manda
  `data=body_bytes` (no `json=`) para no re-serializar.
Otros esquemas aceptados: GitHub `X-Hub-Signature-256: sha256=<hex(body)>`,
GitLab `X-Gitlab-Token: <secreto>`. Ver `references/webhook-firma.md`.

## Marca / skin

Colores en las 3 superficies con un skin: `write_file` a
`/opt/data/skins/<nombre>.yaml`, luego `hermes config set display.skin <nombre>`
(repinta en vivo). Un color puntual del skin activo: `hermes skin set <key> <hex>`
(NUNCA forkear `default`). El skin NO pinta el frontend Streamlit — ahí la marca
va por CSS inyectado con `st.markdown(unsafe_allow_html=True)` usando los mismos
hex. El logo se muestra en Streamlit, no en la terminal.

## Editar la personalidad del agente sin romper YAML

Texto largo con comillas: escríbelo a un archivo y pásalo por sustitución:
`hermes config set agent.personalities.default "$(cat /opt/data/tmp/pers.txt)"`.
El aviso "not a recognized config key" para claves anidadas de personalidad es
NORMAL (se guarda igual). Verifica cargando el YAML con yaml.safe_load después.

## Reiniciar el gateway (imagen de contenedor, supervisada por s6)

El gateway corre bajo s6 (`hermes gateway run`). Reinicio limpio sin tumbar tu
sesión CLI: `/command/s6-svc -r /run/service/gateway-default`. s6 lo relevanta
solo. Verifica: `curl -s http://localhost:8644/health` → `{"status":"ok"}`.
Servicios s6 en `/run/service/` (gateway-default, dashboard, main-hermes). El
`dashboard` está declarado pero apagado hasta `HERMES_DASHBOARD=1` en el entorno
del contenedor (docker-compose), y en bind público exige auth
(`HERMES_DASHBOARD_BASIC_AUTH_USERNAME/PASSWORD` o OAuth).

## Escritura dentro del contenedor: HERMES_WRITE_SAFE_ROOT

`write_file` solo escribe bajo `/opt/data` (HERMES_WRITE_SAFE_ROOT). Para tocar
archivos del host (p.ej. el frontend en `/mnt/host/.../frontend/app.py`):
escribe primero en `/opt/data/tmp/...`, valida (`python -m py_compile`,
`node --check`), y COPIA al destino con `terminal` (`cp`). Igual para `.env` y
docker-compose del proyecto: respalda (`cp ... .bak.$(date +%s)`) antes de tocar.

## Pitfalls

- **`--force-recreate` NO reconstruye la imagen del frontend.** El formulario de
  onboarding vive en `frontend/app.py` y se hornea en la imagen con `COPY . .`
  (Dockerfile). Editar `app.py` en disco y hacer `docker compose up -d
  --force-recreate frontend` deja corriendo la imagen VIEJA (síntoma: el frontend
  muestra "no hay proveedor" o el selector antiguo, sin la pantalla de onboarding
  nueva). Recrear ≠ reconstruir. Para tomar cambios de `app.py`/Dockerfile hace
  falta `docker compose up -d --build frontend`. Cambios que solo afectan al
  contenedor hermes (entrypoint, .env) sí bastan con `--force-recreate hermes`.
- **No hay Docker CLI útil dentro del contenedor hermes** (correcto: no monta el
  socket). El paso `docker compose up -d --build frontend` lo corre el usuario en
  el HOST; el agente no puede reconstruir el frontend desde dentro. Prepara los
  archivos y entrega el comando exacto.
- Credenciales en claro en código del frontend: revisa `app.py` por tokens
  hardcodeados (este proyecto tenía el `API_SERVER_KEY` en claro en OneDrive).
  Muévelo a variable de entorno vía compose (`HERMES_API_KEY=${API_SERVER_KEY}`)
  y ROTA la clave expuesta. Sincroniza la clave nueva en AMBOS `.env` (el del
  contenedor `/opt/data/.env` y el del proyecto junto al compose).
- n8n está ABANDONADO en este proyecto: no reconectes botones a webhooks de n8n
  (puerto 5678); usa el webhook nativo de Hermes.
- El selector de modelo/proveedor no sirve si solo hay un proveedor con key.
  Verifica `authenticated=True` antes de prometer "cambio en vivo".
- El compose vive en OneDrive del proyecto y hay una copia en `~/.hermes`;
  mantenlas sincronizadas para no dejar versiones divergentes.

## Verificación

- Chat: `curl -H "Authorization: Bearer $KEY" -d '{"model":..,"provider":..,"messages":[..]}' :8642/v1/chat/completions`.
- Webhook: `hermes webhook test <ruta>` → 202; `curl :8644/health` → ok.
- Skin: `hermes config get display.skin`.
- Frontend: recrea con `docker compose up -d --build` desde la carpeta del proyecto.
