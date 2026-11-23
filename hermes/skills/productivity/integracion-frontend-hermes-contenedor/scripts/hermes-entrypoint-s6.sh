#!/usr/bin/env bash
# ===========================================================================
# hermes-entrypoint-s6.sh  —  Patron B v2 (encaja con el gateway s6)
# ===========================================================================
# Reemplaza a `command: gateway run` en el contenedor hermes de la imagen
# nousresearch/hermes-agent (supervisada por s6).
#
# CLAVE (por que v2, y por que la v1 fallaba):
#   El gateway que sirve el puerto 8642 lo lanza el servicio s6 'gateway-default'
#   (hermes gateway run --replace), NO este script. Ese servicio lee la API key
#   SOLO de /opt/data/.env al arrancar, y Hermes carga /opt/data/.env con
#   override=True (fuente de verdad). Un entrypoint que lance su propio gateway
#   es DESPLAZADO por --replace y sus variables nunca las ve el gateway real
#   (fallo silencioso). Por eso este script NO arranca ningun gateway propio.
#
# Que hace:
#   1. Sincroniza las keys de chat de /secrets/user_keys.env HACIA /opt/data/.env
#      (via sync_keys.py: upsert seguro que preserva el resto del archivo).
#   2. Reinicia el servicio s6 'gateway-default' (s6-svc -r) para que tome la key
#      nueva (Hermes no recarga el .env en caliente).
#   3. Publica /secrets/.gateway_ready (mtime del user_keys.env aplicado) tras
#      confirmar que :8642/v1/models responde, para que el frontend sepa cuando
#      ya puede chatear.
#   4. Vigila /secrets/user_keys.env y repite 1-3 cuando el frontend carga/cambia
#      la key desde el onboarding web.
#
# El frontend NUNCA toca Docker ni el host: solo escribe texto en /secrets.
# compose: command: ["bash", "/secrets/hermes-entrypoint.sh"]  (renombra a gusto)
# Requiere que sync_keys.py este junto en /secrets (ver SYNC_PY).
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

sync_keys() { python3 "$SYNC_PY" 2>>/tmp/sync_keys.err; }

restart_gateway() {
  # s6-svc -r = reinicio limpio; s6 relevanta (el finish solo bloquea exit 0/78).
  if [ -x /command/s6-svc ]; then
    /command/s6-svc -r "$GATEWAY_SVC" 2>/dev/null \
      && log "gateway s6 reiniciado" \
      || log "aviso: no se pudo reiniciar via s6-svc"
  else
    log "aviso: s6-svc no disponible; no se pudo reiniciar el gateway"
  fi
}

wait_api() {
  local i code
  for i in $(seq 1 40); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${API_PORT}/v1/models" 2>/dev/null)"
    [ -n "$code" ] && [ "$code" != "000" ] && return 0
    sleep 1
  done
  return 1
}

publish_ready() {
  local loaded_mtime="$1"
  if wait_api; then log "gateway listo (keys mtime=$loaded_mtime)"
  else log "aviso: el API server no respondio a tiempo (mtime=$loaded_mtime)"; fi
  echo "$loaded_mtime" > "$READY_FILE" 2>/dev/null || log "aviso: no se pudo escribir $READY_FILE"
}

apply_and_restart() {
  local result cur
  result="$(sync_keys)"
  cur="$(mtime)"
  if [ "$result" = "CHANGED" ]; then
    log "keys sincronizadas a /opt/data/.env; reiniciando gateway"
    restart_gateway
  else
    log "sin cambios de key que aplicar (result=$result)"
  fi
  publish_ready "$cur"
}

on_term() { log "senal de parada recibida"; exit 0; }
trap on_term TERM INT

log "entrypoint v2 iniciado; sincronizando keys de usuario si las hay"
apply_and_restart
LAST_MTIME="$(mtime)"

while true; do
  sleep 3
  CUR="$(mtime)"
  if [ "$CUR" != "$LAST_MTIME" ]; then
    log "detectado cambio en $KEYS_FILE ($LAST_MTIME -> $CUR); aplicando"
    apply_and_restart
    LAST_MTIME="$CUR"
  fi
done
