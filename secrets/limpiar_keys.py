#!/usr/bin/env python3
# ===========================================================================
# limpiar_keys.py  —  Limpieza de keys de CHAT (Anthropic/OpenAI)
# ===========================================================================
# Dos modos:
#   entrega : vacia las keys de chat en el .env del PROYECTO, el .env de HOME
#             (/opt/data/.env, el que hermes lee de verdad) y quita las lineas
#             de key en /secrets/user_keys.env. Respaldo .bak.<ts> de cada
#             archivo. Deja el paquete en modo "primera vez" para entregar.
#             NO reinicia el gateway (para entregar se recrea todo igual).
#
#   reset   : borra la key que un cliente cargo (HOME .env + user_keys.env) y
#             REINICIA el gateway s6, para que la app vuelva al onboarding.
#             No toca el .env del proyecto.
#
# En AMBOS modos: la key de embeddings (OMNIROUTE_*) y cualquier otro secreto
# quedan INTACTOS. Solo se tocan ANTHROPIC_API_KEY y OPENAI_API_KEY.
#
# Rutas (vista desde el contenedor hermes; correr con `docker exec hermes ...`):
#   HOME .env    : /opt/data/.env
#   user_keys    : /secrets/user_keys.env
#   PROYECTO .env: /mnt/host/.../Proyecto_Documentacion/.env
# Se pueden sobreescribir por variables de entorno para pruebas.
# ===========================================================================
import os
import sys
import time
import subprocess

MANAGED = {"ANTHROPIC_API_KEY", "OPENAI_API_KEY"}

HOME_ENV = os.environ.get("HERMES_ENV_FILE", "/opt/data/.env")
USER_KEYS = os.environ.get("KEYS_FILE", "/secrets/user_keys.env")
PROJECT_ENV = os.environ.get(
    "PROJECT_ENV_FILE",
    "/mnt/host/Users/KevinJaramilloRuiz/OneDrive - QVisionSAS/"
    "Escritorio/Proyecto_Documentacion/.env",
)
GATEWAY_SVC = os.environ.get("GATEWAY_SVC", "/run/service/gateway-default")


def backup(path):
    if not os.path.exists(path):
        return None
    dst = f"{path}.bak.{int(time.time())}"
    with open(path, "rb") as s, open(dst, "wb") as d:
        d.write(s.read())
    return dst


def _var_name(stripped):
    name = stripped.split("=", 1)[0].strip()
    if name.startswith("export "):
        name = name[len("export "):].strip()
    return name


def blank_env(path):
    """Deja ANTHROPIC/OPENAI presentes pero VACIAS (VAR=). No agrega nada."""
    if not os.path.exists(path):
        return None, "(ausente)"
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    out, changed = [], False
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s and _var_name(s) in MANAGED:
            prefix = "export " if s.startswith("export ") else ""
            newline = f"{prefix}{_var_name(s)}=\n"
            if line != newline:
                changed = True
            out.append(newline)
            continue
        out.append(line if line.endswith("\n") else line + "\n")
    if changed:
        tmp = path + ".cleantmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.writelines(out)
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return changed, "limpio" if changed else "ya estaba limpio"


def drop_user_keys(path):
    """Elimina las lineas de key gestionadas de user_keys.env (deja comentarios)."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    out, changed = [], False
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s and _var_name(s) in MANAGED:
            changed = True
            continue
        out.append(line if line.endswith("\n") else line + "\n")
    if changed:
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(out)
    return changed


def status(path):
    if not os.path.exists(path):
        return "(archivo ausente)"
    vals = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if s and not s.startswith("#") and "=" in s and _var_name(s) in MANAGED:
                v = s.split("=", 1)[1].strip().strip('"').strip("'")
                vals[_var_name(s)] = "TIENE-VALOR" if v else "VACIA"
    return ", ".join(f"{k}={v}" for k, v in vals.items()) or "(sin keys de chat)"


def restart_gateway():
    svc_bin = "/command/s6-svc"
    if os.path.exists(svc_bin):
        try:
            subprocess.run([svc_bin, "-r", GATEWAY_SVC], check=False)
            print("[reset] gateway s6 reiniciado")
        except Exception as e:  # noqa
            print(f"[reset] aviso: no se pudo reiniciar el gateway: {e}")
    else:
        print("[reset] aviso: s6-svc no disponible; reinicia el gateway a mano")


def do_entrega():
    print("=== LIMPIEZA DE ENTREGA ===")
    for path in (PROJECT_ENV, HOME_ENV):
        b = backup(path)
        ch, msg = blank_env(path)
        print(f"- {path}")
        print(f"    respaldo: {b or '(no existia)'}")
        print(f"    resultado: {msg}")
        print(f"    ahora: {status(path)}")
    b = backup(USER_KEYS)
    ch = drop_user_keys(USER_KEYS)
    print(f"- {USER_KEYS}")
    print(f"    respaldo: {b or '(no existia)'}")
    print(f"    resultado: {'lineas de key eliminadas' if ch else 'ya estaba sin keys'}")
    print("\nLISTO: paquete en modo primera vez. Recrea/entrega cuando quieras.")


def do_reset():
    print("=== RESET DE KEY DEL CLIENTE ===")
    for path in (HOME_ENV,):
        b = backup(path)
        ch, msg = blank_env(path)
        print(f"- {path}  (respaldo: {b or '(no existia)'}) -> {msg}")
        print(f"    ahora: {status(path)}")
    b = backup(USER_KEYS)
    ch = drop_user_keys(USER_KEYS)
    print(f"- {USER_KEYS} (respaldo: {b or '(no existia)'}) -> "
          f"{'keys eliminadas' if ch else 'ya estaba sin keys'}")
    restart_gateway()
    print("\nLISTO: la app volvera al onboarding. El cliente puede cargar otra key.")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "entrega":
        do_entrega()
    elif mode == "reset":
        do_reset()
    else:
        print("Uso: limpiar_keys.py [entrega|reset]")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
