#!/usr/bin/env python3
# ===========================================================================
# sync_keys.py  —  Patron B v2 (encaja con el gateway supervisado por s6)
# ===========================================================================
# Copia las API keys de chat que el usuario final carga desde el frontend
# (archivo compartido /secrets/user_keys.env) HACIA el .env que el gateway
# realmente lee al arrancar (/opt/data/.env = ${USERPROFILE}/.hermes/.env).
#
# Por que hacia /opt/data/.env y no solo exportar variables:
#   El gateway que sirve el puerto 8642 es el servicio s6 'gateway-default'
#   (hermes gateway run --replace). Arranca por su cuenta y lee la key SOLO
#   de su .env al iniciar. Ademas Hermes carga /opt/data/.env con override=True,
#   asi que esa es la fuente de verdad definitiva. Escribir aqui y reiniciar el
#   servicio (s6-svc -r) es lo unico que hace que la key del usuario se tome.
#
# Reglas:
#   - Solo se sincronizan claves con VALOR no vacio en user_keys.env. Una linea
#     vacia (KEY=) se ignora: asi, para entregar "en limpio", basta vaciar la
#     clave en /opt/data/.env y dejar user_keys.env vacio -> modo primera vez.
#   - UPSERT: si la clave ya existe en /opt/data/.env se reemplaza esa linea; si
#     no, se anade. El resto del .env queda intacto.
#   - Salida: imprime "CHANGED" si /opt/data/.env cambio, "NOCHANGE" si no.
#     El entrypoint usa eso para reiniciar el gateway solo cuando hace falta.
#
# Texto crudo (sin shell): keys con $, comillas o backticks se preservan literal.
import os
import sys

KEYS_FILE = os.environ.get("KEYS_FILE", "/secrets/user_keys.env")
ENV_FILE = os.environ.get("HERMES_ENV_FILE", "/opt/data/.env")

# Solo las keys del modelo de chat. La key de embeddings (OMNIROUTE_*) NO se toca.
MANAGED = {"ANTHROPIC_API_KEY", "OPENAI_API_KEY"}


def parse_env(path):
    out = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                s = raw.rstrip("\n").strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                name, _, value = s.partition("=")
                name = name.strip()
                if name.startswith("export "):
                    name = name[len("export "):].strip()
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                out[name] = value
    except FileNotFoundError:
        pass
    return out


def read_user_keys():
    parsed = parse_env(KEYS_FILE)
    return {k: v for k, v in parsed.items() if k in MANAGED and v.strip()}


def upsert_env(desired):
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as fh:
            original = fh.read()
    except FileNotFoundError:
        original = ""

    lines = original.splitlines(keepends=True)
    seen = set()
    out = []
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            name = s.split("=", 1)[0].strip()
            if name.startswith("export "):
                name = name[len("export "):].strip()
            if name in desired:
                out.append(f"{name}={desired[name]}\n")
                seen.add(name)
                continue
        out.append(line if line.endswith("\n") else line + "\n")

    for name, value in desired.items():
        if name not in seen:
            out.append(f"{name}={value}\n")

    new_content = "".join(out)
    if new_content == original:
        return False
    tmp = ENV_FILE + ".synctmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(new_content)
    os.replace(tmp, ENV_FILE)
    try:
        os.chmod(ENV_FILE, 0o600)
    except OSError:
        pass
    return True


def main():
    desired = read_user_keys()
    if not desired:
        print("NOCHANGE")
        return 0
    print("CHANGED" if upsert_env(desired) else "NOCHANGE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
