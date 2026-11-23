# Onboarding de la primera API key desde el frontend

## Hechos duros del código (verificados, no suposición)

- **El API server (8642) NO acepta la api_key por request.** El body solo respeta
  `provider`, `model`, `model_options`. En `gateway/platforms/api_server.py`,
  `_extract_request_overrides` toma `provider`/`model`; y
  `_RUNTIME_AGENT_OVERRIDE_KEYS` incluye `api_key` pero se rellena desde
  `_resolve_request_runtime_agent_kwargs(provider)` → `resolve_runtime_provider`
  (`hermes_cli/runtime_provider.py`), que lee la clave del ENV del proveedor
  (`_getenv → get_secret`, `agent/secret_scope.py`). O sea: el frontend no puede
  mandar la clave del usuario; solo elegir entre proveedores que YA tienen key.
- **El gateway carga `.env` una vez, al arrancar.** `gateway/run.py` llama
  `load_hermes_dotenv()` a nivel módulo (`hermes_cli/env_loader.py`). No hay
  watcher que recargue el `.env` en caliente. Key nueva ⇒ reinicio del gateway
  (`/command/s6-svc -r /run/service/gateway-default`).
- **Frontend y hermes solo comparten HTTP** (8642 chat, 8644 webhook, red
  `appnet`). Sin volumen ni socket compartido, el frontend no tiene cómo escribir
  dentro de hermes.

Consecuencia: para que un usuario de PRIMERA VEZ cargue su primera key desde la
web, la key tiene que (1) llegar al entorno de hermes y (2) forzar recarga del
gateway. "Correr `hermes model`/`hermes setup`" NO encaja en un producto de una
sola ventana web (no hay TTY para el usuario). Elegir proveedor/modelo sí se
resuelve por request; el problema real es SIEMPRE la key.

## Detección de "sin configurar" (frontend/backend)

- `hermes config check` → marca config faltante/desactualizada.
- `hermes doctor` → health check (incluye si falta credencial).
- `hermes config get model.provider` + comprobar si existe la ENV del proveedor.
- `hermes config env-path` → ruta del `.env` del perfil activo.
Si no hay proveedor o su ENV está vacía ⇒ mostrar pantalla de onboarding.

## Persistencia correcta (regla de oro)

- NUNCA editar `config.yaml` a mano. Ajustes con `hermes config set model.provider …`
  y `hermes config set model.default …` (van a config.yaml).
- La API key va al `.env`, NO a config.yaml. Nombre de la ENV según proveedor:
  OpenRouter→OPENROUTER_API_KEY, Anthropic→ANTHROPIC_API_KEY,
  OpenAI→OPENAI_API_KEY, Google→GOOGLE_API_KEY/GEMINI_API_KEY,
  DeepSeek→DEEPSEEK_API_KEY, xAI→XAI_API_KEY.
- Proveedores OAuth (nous, openai-codex, qwen-oauth, minimax-oauth, copilot): no es
  "pegar una key"; el flujo es `hermes auth add <provider>` (device code). Soportar
  esto desde el front exige orquestar el device-code, no un input de texto.
- Multi-usuario real ⇒ un perfil por usuario (`~/.hermes/profiles/<name>/`, cada uno
  con su config/.env/secretos) para que las keys no se mezclen.

## Patrón B — archivo de claves compartido + watcher (RECOMENDADO)

El frontend nunca toca Docker; solo escribe un env-file. hermes se auto-reinicia.

- compose: volumen compartido para el env-file (frontend rw, hermes rw/ro). SIN
  docker.sock en ningún servicio.
- hermes: reemplaza `command: gateway run` por un entrypoint que (a) carga el
  env-file, (b) lanza el gateway, (c) vigila el archivo y relanza el gateway al
  cambiar (~30-40 líneas bash/python; script en el proyecto, no toca código de
  hermes).
- frontend: pantalla de onboarding (selector proveedor + input key). Escribe el
  env-file y hace polling a `/v1/models` hasta que responda OK para avisar "listo".
- Entrega: el env-file arranca vacío → el cliente lo llena en su primer uso. No se
  toca el `.env` grande a mano en cada entrega.

Ventaja: el contenedor expuesto en :80 no tiene ningún privilegio sobre el host;
solo escribe un archivo de texto. Es la única apta para repartir a terceros.

### Mecánica concreta del entrypoint (imagen s6 de este proyecto)

Verificado en la imagen `nousresearch/hermes-agent`:
- El `command:` del compose NO corre como servicio s6. Se ejecuta como el
  "main program" de `/init` vía `docker/main-wrapper.sh`, que hace `cd /opt/data`,
  activa el venv (`.venv/bin/activate`) y DROPEA a usuario `hermes`. El servicio
  s6 `main-hermes` es un `sleep infinity` (placeholder).
- **CORRECCIÓN CRÍTICA (verificado 2026-09, el entrypoint NO debe lanzar su
  propio gateway).** El gateway que sirve el puerto 8642 NO es el que lanza tu
  `command:`; es el servicio s6 `gateway-default` cuyo `run` hace
  `exec s6-setuidgid hermes hermes gateway run --replace` (ver
  `/run/service/gateway-default/run`). Ese servicio arranca por su cuenta y lee la
  key SOLO de `/opt/data/.env` al iniciar. Si tu entrypoint hace
  `hermes gateway run &` con la key exportada en SU proceso, el flag `--replace`
  del servicio s6 lo DESPLAZA y el gateway real nunca ve esas variables → guardar
  la key desde la web NO activa nada (fallo silencioso). Un entrypoint que lanza y
  mata su propio gateway pelea con s6; NO funciona en esta imagen.
- **Patrón B v2 correcto para esta imagen:** el entrypoint NO arranca ningún
  gateway. En su lugar: (a) hace UPSERT de las keys de chat de
  `/secrets/user_keys.env` HACIA `/opt/data/.env` (el que el gateway lee de verdad,
  y con `override=True` es la fuente de verdad definitiva — ver TRAMPA abajo);
  (b) reinicia el servicio s6 con `/command/s6-svc -r /run/service/gateway-default`
  (probado en vivo: el pid del gateway cambia y vuelve en ~8s; el 401 posterior es
  "vivo pero pide auth", correcto); (c) publica `.gateway_ready` tras confirmar que
  `:8642/v1/models` responde (http_code != 000); (d) vigila `user_keys.env` por
  `stat -c %Y` y repite. Ver `scripts/hermes-entrypoint-s6.sh` y
  `scripts/sync_keys.py` (upsert en Python, no bash).
- **El UPSERT de la key debe hacerse en Python, no en bash.** Una API key puede
  contener `$`, backticks o comillas; con `source`/`. archivo` bash los
  expande/ejecuta y corrompe la clave (o peor). Parsear/escribir como texto crudo
  línea a línea, preservando el resto del `.env`, y escritura atómica
  (`os.replace`). Probado: preserva `sk-ant-$abc\`ls\`def"quote` literal.
- **`finish` script del servicio s6:** solo evita relanzar en exit 0 (parada
  intencional) y exit 78 (EX_CONFIG). Un `s6-svc -r` (reinicio por señal) SÍ lo
  relevanta. Por eso `s6-svc -r` es el mecanismo correcto de reinicio, no `kill`.
- **`load_keys` NO debe usar `source`/`. archivo`.** Una API key puede contener
  `$`, backticks o comillas; con `source` bash los expande/ejecuta y corrompe la
  clave (o peor). Parsear línea a línea `KEY=VALUE` y `export "$name=$value"`,
  quitando solo comillas envolventes. (Probado: preserva `sk-ant-$abc\`ls\`def`
  literal.)
- **Handshake de "listo" con el frontend por ready-file.** Tras cada arranque, el
  entrypoint espera a que `http://127.0.0.1:8642/v1/models` responda y luego
  escribe el `mtime` del env-file cargado en `/secrets/.gateway_ready`. El
  frontend, tras guardar la key, hace polling de ese archivo hasta que el mtime
  publicado alcanza el de su escritura → sabe que el gateway ya arrancó con la
  clave nueva. Evita adivinar con un `sleep` fijo.
- Binarios disponibles en la imagen para el watcher: `bash`, `curl`, `stat`,
  `seq`. Reinicio ante cambio: comparar `stat -c %Y env-file` cada pocos segundos.

### TRAMPA CRÍTICA: hermes carga DOS `.env` y el de home hace override

`load_hermes_dotenv()` (`hermes_cli/env_loader.py`) carga
`${USERPROFILE}/.hermes/.env` (montado como `/opt/data/.env`) con
**`override=True`**. Es decir, ese `.env` de HOME PISA cualquier variable ya
presente en el entorno del proceso — incluida la que el entrypoint de Patrón B
acaba de exportar desde el env-file compartido.

Consecuencia: si `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` siguen con valor en
`/opt/data/.env`, la Opción B FALLA en silencio: el cliente cargaría su key desde
la web pero el gateway usaría la key vieja del operador. Para que el onboarding
funcione **hay que vaciar la key del modelo de chat también en el `.env` de HOME**
(no basta con el env-file compartido ni con el `.env` del proyecto).

Hay por tanto DOS `.env` con las keys de chat, ambos a vaciar antes de entregar:
1. `.env` del PROYECTO (junto al docker-compose). Sus copias de ANTHROPIC/OPENAI
   no las consume ningún contenedor directamente, pero no se reparten secretos.
2. `.env` de HERMES = `${USERPROFILE}/.hermes/.env` (= `/opt/data/.env`). Este es
   el que hermes lee de verdad y con override. OBLIGATORIO vaciarlo.

Mapeo proveedor→ENV confirmado (`hermes_cli/auth.py`): slug `anthropic` →
`ANTHROPIC_API_KEY`; slug `openai-api` → `OPENAI_API_KEY`. OJO: el alias BARE
`openai` mapea a `openrouter` (`hermes_cli/providers.py` ALIASES), no a OpenAI
directo — para OpenAI directo el slug es `openai-api`.

### Entrega limpia al cliente (qué vaciar, qué NO tocar)

- Vaciar `ANTHROPIC_API_KEY=` y `OPENAI_API_KEY=` en AMBOS `.env` (proyecto + home)
  y dejar `secrets/user_keys.env` sin líneas de key. Backup antes:
  `cp "$F" "$F.bak.$(date +%s)"`; vaciar con `sed -i -E 's/^(\s*(export\s+)?VAR=).*/\1/'`.
- Embeddings: NO existe ninguna `JINA_API_KEY` en los `.env`. La credencial de
  embeddings es `OMNIROUTE_API_KEY` (+ `OMNIROUTE_INITIAL_PASSWORD/JWT_SECRET/
  STORAGE_KEY`) y además OmniRoute persiste sus proveedores/keys DENTRO del volumen
  `omniroute_storage` (storage.sqlite), no solo en el `.env`. Si el cliente hereda
  los embeddings ya configurados, NO tocar ni el `OMNIROUTE_*` ni ese volumen.
  Entregar "en limpio" exigiría `docker volume rm omniroute_storage` (borra toda su
  config de proveedores).
- Inspeccionar keys sin exponer valores: listar solo nombres
  (`grep -vE '^\s*#' .env | grep = | sed -E 's/.*(\bVAR)=.*/\1/'`) o reportar
  VACIA/TIENE-VALOR comparando si el RHS (sin comillas/espacios) está vacío.

## Patrón A — docker.sock en el frontend (INSEGURO, solo interno)

El frontend escribe la key y ejecuta `docker restart hermes` vía
`/var/run/docker.sock` montado en el contenedor web. Rápido, pero montar el socket
= control total de Docker del host = root sobre la máquina. Peor combinado con el
bind de C: completo en hermes (frontend vulnerado ⇒ Docker del host + disco C:
entero). Aceptable solo para uso interno en tu propio equipo; NUNCA para entregar.
