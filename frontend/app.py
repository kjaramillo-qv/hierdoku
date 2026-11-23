import os
import time
import hashlib
import hmac
import json
import re

import requests
import streamlit as st

# ==========================================================================
# HierDoku — Documentador Funcional Oficial (frontend)
# ==========================================================================
# Este frontend es una "ventana con filtro": muestra la conversacion con la
# marca de la empresa y deja que Hermes sea el motor (herramientas, memoria,
# skills, base vectorial). No guarda logica de negocio.
#
# Configuracion por variables de entorno (definidas en docker-compose / .env):
#   HERMES_API_URL       -> endpoint OpenAI-compatible de Hermes (chat)
#   HERMES_API_KEY       -> API_SERVER_KEY de Hermes (NUNCA en el codigo)
#   HERMES_WEBHOOK_URL   -> URL del webhook 'documentar-pipeline'
#   HERMES_WEBHOOK_SECRET-> secreto HMAC de ese webhook (para firmar el POST)
# ==========================================================================

HERMES_API_URL = os.environ.get(
    "HERMES_API_URL", "http://host.docker.internal:8642/v1/chat/completions"
)
HERMES_API_KEY = os.environ.get("HERMES_API_KEY", "")
HERMES_WEBHOOK_URL = os.environ.get(
    "HERMES_WEBHOOK_URL",
    "http://host.docker.internal:8644/webhooks/documentar-pipeline",
)
HERMES_WEBHOOK_SECRET = os.environ.get("HERMES_WEBHOOK_SECRET", "")

# --- Marca HierDoku ---------------------------------------------------------
BRAND = {
    "background": "#16191D",
    "accent": "#4FB5FF",
    "text": "#F8FAFC",
    "dim": "#8A99A8",
    "border": "#2B333E",
    "ok": "#34D399",
    "warn": "#F59E0B",
    "error": "#F87171",
}

# Proveedores, métodos de autenticación y modelos.
PROVIDERS = {
    "Anthropic": {
        "models": ["claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-5", "claude-fable-5"],
        "auth_options": {
            "Anthropic API Key": {
                "slug": "anthropic",
                "key_env": "ANTHROPIC_API_KEY",
                "type": "text"
            },
            "Suscripción Claude Pro/Max (Setup Token)": {
                "slug": "anthropic",
                "key_env": "ANTHROPIC_TOKEN",
                "type": "text"
            }
        }
    },
    "OpenAI": {
        "models": ["gpt-5.6-sol", "gpt-5.6-sol-pro", "gpt-5.6-terra", "gpt-5.6-terra-pro"],
        "auth_options": {
            "OpenAI API Key": {
                "slug": "openai-api",
                "key_env": "OPENAI_API_KEY",
                "type": "text"
            },
            "Suscripción ChatGPT / Codex (OAuth)": {
                "slug": "codex",
                "key_env": None,
                "type": "oauth_instructions"
            }
        }
    },
    "Google Gemini": {
        "models": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"],
        "auth_options": {
            "Gemini API Key": {
                "slug": "google-ai-studio",
                "key_env": "GEMINI_API_KEY",
                "type": "text"
            }
        }
    },
    "DeepSeek": {
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "auth_options": {
            "DeepSeek API Key": {
                "slug": "deepseek",
                "key_env": "DEEPSEEK_API_KEY",
                "type": "text"
            }
        }
    }
}

SECRETS_DIR = os.environ.get("SECRETS_DIR", "/secrets")
KEYS_FILE = os.path.join(SECRETS_DIR, "user_keys.env")
READY_FILE = os.path.join(SECRETS_DIR, ".gateway_ready")

# Extraer dinámicamente las variables de entorno de todas las opciones
MANAGED_KEY_ENVS = set()
for prov in PROVIDERS.values():
    for auth in prov["auth_options"].values():
        if auth["key_env"]:
            MANAGED_KEY_ENVS.add(auth["key_env"])


def read_configured_keys():
    """Devuelve {ENV_VAR: valor} con las keys de chat ya presentes en el archivo."""
    found = {}
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                name = name.strip()
                value = value.strip().strip('"').strip("'")
                if name in MANAGED_KEY_ENVS and value:
                    found[name] = value
    except FileNotFoundError:
        pass
    except OSError:
        pass
    return found


def is_first_run():
    """Primera vez absoluta = ninguna key de chat configurada todavia."""
    return len(read_configured_keys()) == 0


def _valid_key_shape(value):
    """Rechaza pegados obvios: vacio, espacios o caracteres no ASCII imprimibles."""
    if not value or value.strip() != value:
        return False
    return bool(re.fullmatch(r"[\x21-\x7e]{8,}", value))


def save_provider_key(key_env, value):
    """Escribe/actualiza una sola linea KEY=valor en el archivo compartido.

    Preserva las demas keys ya presentes y las lineas de comentario.
    Devuelve el mtime resultante del archivo (para saber cuando hermes lo tomo).
    """
    lines = []
    replaced = False
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        pass
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            name = stripped.split("=", 1)[0].strip()
            if name == key_env:
                out.append(f"{key_env}={value}\n")
                replaced = True
                continue
        out.append(line if line.endswith("\n") else line + "\n")
    if not replaced:
        out.append(f"{key_env}={value}\n")
    os.makedirs(SECRETS_DIR, exist_ok=True)
    with open(KEYS_FILE, "w", encoding="utf-8") as fh:
        fh.writelines(out)
    try:
        return os.stat(KEYS_FILE).st_mtime
    except OSError:
        return time.time()


def wait_until_ready(min_mtime, timeout=60):
    """Espera a que hermes reinicie y publique que ya aplico las keys.

    hermes-entrypoint.sh escribe en READY_FILE el mtime del archivo de keys
    que acaba de cargar. Cuando ese valor alcanza el mtime de nuestra
    escritura, el gateway ya arranco con la nueva key.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with open(READY_FILE, "r", encoding="utf-8") as fh:
                published = float((fh.read() or "0").strip() or 0)
            if published >= float(min_mtime) - 1:
                return True
        except (FileNotFoundError, ValueError, OSError):
            pass
        time.sleep(1.5)
    return False

# ==========================================================================
# Interfaz
# ==========================================================================
st.set_page_config(page_title="HierDoku — Documentador Funcional", layout="wide", page_icon="📘")

# Tema HierDoku (colores de marca) inyectado por CSS.
st.markdown(
    f"""
    <style>
      .stApp {{ background-color: {BRAND['background']}; color: {BRAND['text']}; }}
      section[data-testid="stSidebar"] {{ background-color: #101317; border-right: 1px solid {BRAND['border']}; }}
      h1, h2, h3, h4 {{ color: {BRAND['text']}; }}
      .hd-accent {{ color: {BRAND['accent']}; }}
      .stButton>button {{
        background-color: {BRAND['accent']}; color: #0B1116; border: 0; font-weight: 600;
      }}
      .stButton>button:hover {{ filter: brightness(1.08); }}
      a {{ color: {BRAND['accent']}; }}
      .hd-badge {{
        display:inline-block; padding:2px 8px; border-radius:6px;
        background:{BRAND['border']}; color:{BRAND['dim']}; font-size:0.75rem;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Compuerta de onboarding: PRIMERA VEZ ABSOLUTA --------------------------
# Si no hay ninguna API key de chat configurada, el usuario no puede usar el
# producto todavia. Mostramos una pantalla para que cargue su primera key y
# detenemos el resto de la app hasta que hermes la tome.
if is_first_run() and not st.session_state.get("onboarding_done"):
    st.markdown(
        "<h1 class='hd-accent'>📘 Bienvenido a HierDoku</h1>"
        "<p style='color:#8A99A8'>Para empezar, elige tu proveedor de IA y pega tu "
        "API key. Es un paso de una sola vez.</p>",
        unsafe_allow_html=True,
    )

    with st.form("onboarding_form"):
        prov_nombre = st.selectbox("1. Elige tu proveedor de IA:", list(PROVIDERS.keys()))
        
        # Sub-menú dinámico
        auth_opts = list(PROVIDERS[prov_nombre]["auth_options"].keys())
        auth_nombre = st.selectbox("2. Método de autenticación:", auth_opts)
        
        auth_info = PROVIDERS[prov_nombre]["auth_options"][auth_nombre]
        key_env = auth_info["key_env"]
        
        if auth_info["type"] == "text":
            api_key = st.text_input(
                f"3. Pega tu {auth_nombre}:",
                type="password",
                help="La clave se guarda cifrada solo en este equipo.",
            )
            activar = st.form_submit_button("Guardar y activar 🚀")
        else:
            # Instrucciones para OAuth / Codex
            api_key = "" # No usamos campo de texto aquí
            st.info(
                "**Para vincular tu suscripción de OpenAI Codex:**\n\n"
                "1. Abre una terminal en tu computadora (CMD o WSL).\n"
                "2. Ejecuta: `docker exec -it hermes hermes model`\n"
                "3. Selecciona 'OpenAI' -> 'ChatGPT or Codex Subscription'.\n"
                "4. Entra a auth.openai.com/codex/device e ingresa el código que te dará la terminal.\n"
                "5. Una vez inicies sesión allá, presiona el botón de abajo."
            )
            activar = st.form_submit_button("Confirmar vinculación completada 🚀")

    with st.expander("¿Dónde consigo mi credencial?"):
        st.markdown(
            "- **Anthropic API:** console.anthropic.com → API Keys\n"
            "- **Claude Pro (Token):** Se obtiene corriendo `claude setup-token` en tu terminal y pegando aquí el resultado (`sk-ant-oat-...`).\n"
            "- **OpenAI API:** platform.openai.com → API keys\n"
            "- **OpenAI Codex:** Inicia sesión con tu cuenta Plus/Team desde la terminal como se indica arriba."
        )

    if activar:
        if auth_info["type"] == "text":
            if not _valid_key_shape(api_key):
                st.error("La credencial no parece válida. Revisa que la pegaste completa.")
            else:
                try:
                    mtime = save_provider_key(key_env, api_key)
                except OSError:
                    st.error("Error de permisos al guardar en /secrets.")
                else:
                    with st.spinner("Activando el motor con tu clave..."):
                        ok = wait_until_ready(mtime, timeout=90)
                    if ok:
                        st.session_state["onboarding_done"] = True
                        st.success("¡Listo! Tu asistente ya está activo.")
                        st.rerun()
                    else:
                        st.warning("Guardé la clave, pero el motor tarda. Recarga la página.")
        else:
            # Para flujos OAuth, el usuario hace el trabajo en la terminal, solo damos acceso.
            st.session_state["onboarding_done"] = True
            st.success("¡Acceso habilitado! Si completaste la vinculación en la terminal, el chat ya funcionará.")
            st.rerun()
    st.stop()


# --- Barra lateral: marca + seleccion de modelo/proveedor -------------------
with st.sidebar:
    st.markdown(
        f"<h2 class='hd-accent'>📘 HierDoku</h2>"
        f"<div class='hd-badge'>Documentador Funcional Oficial</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.subheader("Modelo y proveedor")

    nombre_proveedor = st.selectbox("Proveedor:", list(PROVIDERS.keys()))
    auth_opts = list(PROVIDERS[nombre_proveedor]["auth_options"].keys())
    auth_nombre = st.selectbox("Autenticación:", auth_opts)
    
    slug_proveedor = PROVIDERS[nombre_proveedor]["auth_options"][auth_nombre]["slug"]
    modelo = st.selectbox("Modelo:", PROVIDERS[nombre_proveedor]["models"])

    st.caption("El cambio aplica a la conversación actual.")
    st.markdown("---")

    if not HERMES_API_KEY:
        st.error("Falta HERMES_API_KEY en el entorno.")

    # --- Gestion de la API key del proveedor (post-onboarding) --------------
    _configured = read_configured_keys()
    _key_env = PROVIDERS[nombre_proveedor]["auth_options"][auth_nombre]["key_env"]
    
    with st.expander("🔑 Gestionar credencial"):
        if _key_env:
            if _key_env in _configured:
                st.caption(f"✓ Configurada")
            else:
                st.caption(f"✕ Sin configurar")
                
            _nueva = st.text_input("Nueva credencial:", type="password", key="side_key_input")
            if st.button("Actualizar", key="side_key_btn"):
                if not _valid_key_shape(_nueva):
                    st.error("Credencial inválida.")
                else:
                    try:
                        _mt = save_provider_key(_key_env, _nueva)
                    except OSError:
                        st.error("Error de permisos en /secrets.")
                    else:
                        with st.spinner("Aplicando..."):
                            _ok = wait_until_ready(_mt, timeout=90)
                        if _ok:
                            st.success("Actualizada.")
                        else:
                            st.warning("Recarga en unos segundos.")
        else:
            st.info("La autenticación por OAuth se vincula directamente en la terminal.")


def _headers():
    h = {"Content-Type": "application/json"}
    if HERMES_API_KEY:
        h["Authorization"] = f"Bearer {HERMES_API_KEY}"
    return h


def _webhook_headers(body_bytes: bytes):
    """Firma V2 del webhook generico: HMAC-SHA256 de '<timestamp>.<body>'."""
    ts = str(int(time.time()))
    h = {"Content-Type": "application/json", "X-Webhook-Timestamp": ts}
    if HERMES_WEBHOOK_SECRET:
        mac = hmac.new(
            HERMES_WEBHOOK_SECRET.encode(),
            (ts + "." + body_bytes.decode()).encode(),
            hashlib.sha256,
        ).hexdigest()
        h["X-Webhook-Signature-V2"] = mac
    return h


# ==========================================================================
# Area principal
# ==========================================================================
st.markdown("<h1>🤖 Asistente de Documentacion</h1>", unsafe_allow_html=True)
tab1, tab2 = st.tabs(["💬 Chat con el Documentador", "🚀 Pipeline automatico"])

# --------------------------------------------------------------------------
# Pestana 1: Chat
# --------------------------------------------------------------------------
with tab1:
    st.markdown("### Conversa con HierDoku para crear o editar documentacion")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ej: Necesito documentar una aplicacion nueva llamada 'Gestor Ventas'...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⏳ Analizando e interactuando con la base de conocimiento...")
            try:
                payload = {
                    "model": modelo,
                    "provider": slug_proveedor,
                    "messages": st.session_state.messages,
                }
                res = requests.post(
                    HERMES_API_URL, json=payload, headers=_headers(), timeout=3600
                )
                if res.status_code == 200:
                    texto = res.json()["choices"][0]["message"]["content"]
                    placeholder.markdown(texto)
                    st.session_state.messages.append({"role": "assistant", "content": texto})
                elif res.status_code in (401, 403):
                    placeholder.error("Error de autenticacion con Hermes. Revisa HERMES_API_KEY.")
                else:
                    placeholder.error(f"Error de Hermes: codigo {res.status_code}.")
            except requests.exceptions.RequestException:
                placeholder.error("No se pudo contactar a Hermes (puerto 8642).")

# --------------------------------------------------------------------------
# Pestana 2: Pipeline automatico (via webhook documentar-pipeline)
# --------------------------------------------------------------------------
with tab2:
    st.markdown("### Ejecucion directa (post-onboarding)")
    st.write(
        "Envia el enlace, las credenciales y los requerimientos. HierDoku "
        "documenta de forma autonoma sin pasos intermedios."
    )

    with st.form("pipeline_form"):
        app_nombre = st.text_input("Aplicacion / proyecto:")
        link = st.text_input("Link de la pagina:")
        credenciales = st.text_input("Credenciales de acceso (temporales / solo lectura):", type="password")
        requerimientos = st.text_area("Requerimiento(s):")
        submit_btn = st.form_submit_button("Ejecutar documentacion ⚙️")

        if submit_btn:
            if not (app_nombre and link and requerimientos):
                st.warning("Completa al menos aplicacion, link y requerimientos.")
            elif not HERMES_WEBHOOK_SECRET:
                st.error("Falta HERMES_WEBHOOK_SECRET en el entorno del contenedor.")
            else:
                with st.spinner("HierDoku esta trabajando en segundo plano..."):
                    try:
                        body = json.dumps(
                            {
                                "app": app_nombre,
                                "link": link,
                                "credenciales": credenciales,
                                "requerimientos": requerimientos,
                            }
                        ).encode()
                        res = requests.post(
                            HERMES_WEBHOOK_URL,
                            data=body,
                            headers=_webhook_headers(body),
                            timeout=60,
                        )
                        if res.status_code in (200, 202):
                            st.success("¡Solicitud aceptada! HierDoku esta documentando en segundo plano.")
                            st.caption("El resultado se guarda en la carpeta de documentacion configurada.")
                        elif res.status_code in (401, 403):
                            st.error("Firma rechazada. Revisa HERMES_WEBHOOK_SECRET.")
                        else:
                            st.error(f"Error en el pipeline: codigo {res.status_code}.")
                    except requests.exceptions.RequestException:
                        st.error("No se pudo contactar el webhook (puerto 8644).")
