#!/usr/bin/env bash
# =============================================================================
# bootstrap.sh — primer arranque del contenedor hermes (HierDoku)
# =============================================================================
# Prepara /opt/data (home persistente de Hermes = ${USERPROFILE}/.hermes) la
# PRIMERA vez que se monta el stack, para que "docker compose up + 2 claves"
# deje todo funcionando sin pasos manuales.
#
# Todo es idempotente y NO toca instalaciones previas:
#   - si /opt/data/config.yaml ya existe, sale sin hacer nada.
#
# Hace:
#   1. Copia el "cerebro" (config, skills, scripts, skin) desde /opt/bootstrap.
#   2. Escribe /opt/data/.env con los secretos y las claves del usuario.
#   3. Genera webhook_subscriptions.json con el secret real.
#   4. Crea el venv de ingesta (fastembed + qdrant-client) en background.
#   5. Registra la clave Jina en OmniRoute (POST /api/providers) en background.
#   6. Reinicia el gateway para que tome el .env nuevo.
# =============================================================================
set -u

MARKER="/opt/data/.bootstrapped"
BOOT="/opt/bootstrap"
DATA="/opt/data"
OMNI="http://host.docker.internal:20128"
GATEWAY_SVC="/run/service/gateway-default"

log() { echo "[bootstrap] $*" >&2; }

# --- No reintentar si ya se completó ----------------------------------------
if [ -f "$MARKER" ]; then
  log "ya bootstrapeado; salgo"
  exit 0
fi

# --- Respetar instalaciones existentes (no es primer arranque) ---------------
if [ -f "$DATA/config.yaml" ]; then
  log "config.yaml ya existe (instalación previa); no toco nada"
  touch "$MARKER"
  exit 0
fi

log "=== BOOTSTRAP: primer arranque detectado ==="

# --- 1) Copiar cerebro -------------------------------------------------------
if [ -d "$BOOT" ] && [ -n "$(ls -A "$BOOT" 2>/dev/null)" ]; then
  cp -a "$BOOT"/. "$DATA"/
  log "cerebro copiado a /opt/data (config, skills, scripts, skin)"
else
  log "AVISO: /opt/bootstrap vacío o ausente; ¿montaste ./hermes como /opt/bootstrap?"
fi

# --- 2) Escribir /opt/data/.env (solo si no existía) -------------------------
if [ ! -f "$DATA/.env" ]; then
  {
    echo "# Generado por bootstrap.sh — primer arranque"
    echo "API_SERVER_ENABLED=true"
    echo "API_SERVER_HOST=0.0.0.0"
    [ -n "${API_SERVER_KEY:-}" ]          && echo "API_SERVER_KEY=${API_SERVER_KEY}"
    [ -n "${OPENAI_API_KEY:-}" ]          && echo "OPENAI_API_KEY=${OPENAI_API_KEY}"
    [ -n "${ANTHROPIC_API_KEY:-}" ]       && echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}"
    [ -n "${PIPELINE_WEBHOOK_SECRET:-}" ] && echo "PIPELINE_WEBHOOK_SECRET=${PIPELINE_WEBHOOK_SECRET}"
    [ -n "${WEBHOOK_SECRET:-}" ]          && echo "WEBHOOK_SECRET=${WEBHOOK_SECRET}"
    [ -n "${OMNIROUTE_API_KEY:-}" ]       && echo "OMNIROUTE_API_KEY=${OMNIROUTE_API_KEY}"
  } > "$DATA/.env"
  chmod 600 "$DATA/.env" 2>/dev/null || true
  log "/opt/data/.env escrito"
else
  log "/opt/data/.env ya existía; no lo piso"
fi

# --- 2b) Pre-sembrar la key de chat en /secrets/user_keys.env ----------------
# Asi el frontend detecta que ya hay key y se SALTA el onboarding de bienvenida.
if [ -n "${OPENAI_API_KEY:-}" ] || [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  {
    echo "# Autogenerado por bootstrap.sh (key de chat del operador)"
    [ -n "${ANTHROPIC_API_KEY:-}" ] && echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}"
    [ -n "${OPENAI_API_KEY:-}" ] && echo "OPENAI_API_KEY=${OPENAI_API_KEY}"
  } > /secrets/user_keys.env
  log "key de chat pre-sembrada en /secrets/user_keys.env (onboarding saltado)"
fi

# --- 3) Webhook documentar-pipeline con el secret real -----------------------
if [ -f "$DATA/webhook_subscriptions.example.json" ] && [ -n "${PIPELINE_WEBHOOK_SECRET:-}" ]; then
  sed "s/REEMPLAZA_ESTE_SECRET/${PIPELINE_WEBHOOK_SECRET}/g" \
    "$DATA/webhook_subscriptions.example.json" > "$DATA/webhook_subscriptions.json"
  log "webhook_subscriptions.json generado"
fi

# --- 4) Venv de ingesta (background) -----------------------------------------
(
  if [ ! -x "$DATA/.venv-ingesta/bin/python" ]; then
    log "creando .venv-ingesta (puede tardar ~1-2 min) ..."
    python3 -m venv "$DATA/.venv-ingesta" 2>&1 | sed 's/^/[venv] /'
  fi
  "$DATA/.venv-ingesta/bin/pip" install --quiet --upgrade pip 2>&1 | sed 's/^/[pip] /'
  "$DATA/.venv-ingesta/bin/pip" install --quiet fastembed qdrant-client 2>&1 | sed 's/^/[pip] /'
  log "venv de ingesta listo"
) > /tmp/bootstrap-venv.log 2>&1 &

# --- 5) Registrar Jina en OmniRoute (background) -----------------------------
(
  if [ -z "${JINA_API_KEY:-}" ]; then
    log "JINA_API_KEY vacía; omito registro de embeddings (se puede cargar luego)"
    exit 0
  fi
  # esperar a que OmniRoute responda (hasta ~3 min)
  for _ in $(seq 1 90); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "$OMNI/v1/models" 2>/dev/null || true)
    case "$code" in 200|401|403) break;; esac
    sleep 2
  done
  # ¿ya existe jina-ai?
  existing=$(curl -s -H "Authorization: Bearer ${OMNIROUTE_API_KEY:-}" "$OMNI/api/providers" 2>/dev/null || true)
  if printf '%s' "$existing" | grep -qi 'jina'; then
    log "jina-ai ya registrada en OmniRoute"
    exit 0
  fi
  resp=$(curl -s -X POST "$OMNI/api/providers" \
    -H "Authorization: Bearer ${OMNIROUTE_API_KEY:-}" \
    -H "Content-Type: application/json" \
    -d "{\"provider\":\"jina-ai\",\"apiKey\":\"${JINA_API_KEY}\",\"name\":\"main\"}" 2>/dev/null || true)
  log "registro jina-ai en OmniRoute: ${resp}"
) > /tmp/bootstrap-jina.log 2>&1 &

# --- 6) Reiniciar gateway para que tome el .env nuevo ------------------------
if [ -x /command/s6-svc ]; then
  /command/s6-svc -r "$GATEWAY_SVC" 2>/dev/null \
    && log "gateway reiniciado para tomar el .env nuevo" \
    || log "aviso: no se pudo reiniciar el gateway (s6-svc)"
fi

touch "$MARKER"
log "bootstrap (parte rápida) completado; venv y Jina siguen en background"
exit 0
