#!/usr/bin/env bash
# ===========================================================================
# hermes-entrypoint.sh  —  Opcion B (v2, encaja con el gateway s6)
# ===========================================================================
# Reemplaza a `command: gateway run` en el contenedor hermes.
#
# CONTEXTO IMPORTANTE (por que esta v2 es distinta):
#   En esta imagen el gateway que sirve el puerto 8642 NO lo lanza este script:
#   lo lanza el servicio s6 'gateway-default' (hermes gateway run --replace),
#   que arranca por su cuenta y lee la API key SOLO de /opt/data/.env al iniciar.
#   Ademas Hermes carga /opt/data/.env con override=True (fuente de verdad).
#   Por eso este entrypoint NO arranca ningun gateway propio: seria desplazado
#   por --replace y sus variables nunca las veria el gateway real.
#
# Que hace este script:
#   1. Sincroniza las keys de chat que el frontend escribe en
#      /secrets/user_keys.env HACIA /opt/data/.env (via sync_keys.py, upsert
#      seguro que preserva el resto del archivo).
#   2. Reinicia el servicio s6 'gateway-default' para que tome la key nueva
#      (Hermes no recarga el .env en caliente).
#   3. Publica /secrets/.gateway_ready (mtime del user_keys.env aplicado) para
#      que el frontend sepa cuando ya puede chatear.
#   4. Vigila /secrets/user_keys.env y repite 1-3 cuando el usuario final carga
#      o cambia su key desde el onboarding web.
#
# El frontend NUNCA toca Docker ni el host: solo escribe un archivo de texto en
# el volumen compartido /secrets. Toda la logica vive aqui, dentro de hermes.
# Corre como usuario 'hermes' (lo enruta docker/main-wrapper.sh) con el venv
# activo, asi que `python3` y las rutas de Hermes resuelven bien.
# ===========================================================================
set -u

KEYS_FILE="/secrets/user_keys.env"
READY_FILE="/secrets/.gateway_ready"
SYNC_PY="/secrets/sync_keys.py"
API_PORT="${HERMES_API_PORT:-8642}"
GATEWAY_SVC="/run/service/gateway-default"

export KEYS_FILE
export HERMES_ENV_FILE="/opt/data/.env"

log() { echo "[hermes-entrypoint] $*" >&2; }

mtime() { stat -c %Y "$KEYS_FILE" 2>/dev/null || echo 0; }

sync_keys() {
  # Sincroniza user_keys.env -> /opt/data/.env. Imprime CHANGED / NOCHANGE.
  python3 "$SYNC_PY" 2>>/tmp/sync_keys.err
}

restart_gateway() {
  # Reinicio limpio del servicio s6. s6 lo relevanta solo (el finish script
  # solo evita relanzar en exit 0/78, no en un reinicio por senal).
  if [ -x /command/s6-svc ]; then
    /command/s6-svc -r "$GATEWAY_SVC" 2>/dev/null \
      && log "gateway s6 reiniciado" \
      || log "aviso: no se pudo reiniciar via s6-svc"
  else
    log "aviso: s6-svc no disponible; no se pudo reiniciar el gateway"
  fi
}

wait_api() {
  # Espera a que el API server (8642) responda tras el reinicio. Cualquier
  # http_code != 000 = el servidor esta arriba (401 sin auth es normal).
  local i code
  for i in $(seq 1 40); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${API_PORT}/v1/models" 2>/dev/null)"
    if [ -n "$code" ] && [ "$code" != "000" ]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

publish_ready() {
  local loaded_mtime="$1"
  if wait_api; then
    log "gateway listo (keys mtime=$loaded_mtime)"
  else
    log "aviso: el API server no respondio a tiempo (mtime=$loaded_mtime)"
  fi
  echo "$loaded_mtime" > "$READY_FILE" 2>/dev/null || log "aviso: no se pudo escribir $READY_FILE"
}

apply_and_restart() {
  # Sincroniza; si cambio /opt/data/.env, reinicia el gateway. Siempre publica
  # ready con el mtime actual de user_keys.env.
  local result cur
  result="$(sync_keys)"
  cur="$(mtime)"
  if [ "$result" = "CHANGED" ]; then
    log "keys sincronizadas a /opt/data/.env; reiniciando gateway"
    restart_gateway
    publish_ready "$cur"
  else
    log "sin cambios de key que aplicar (result=$result)"
    # Publica ready igual para no dejar al frontend esperando en el 1er arranque.
    publish_ready "$cur"
  fi
}

on_term() { log "senal de parada recibida"; exit 0; }
trap on_term TERM INT

# --- Arranque inicial ------------------------------------------------------
log "entrypoint v2 iniciado; sincronizando keys de usuario si las hay"
apply_and_restart
LAST_MTIME="$(mtime)"

# --- Bucle de vigilancia ---------------------------------------------------
while true; do
  sleep 3
  CUR="$(mtime)"
  if [ "$CUR" != "$LAST_MTIME" ]; then
    log "detectado cambio en $KEYS_FILE ($LAST_MTIME -> $CUR); aplicando"
    apply_and_restart
    LAST_MTIME="$CUR"
  fi
done
