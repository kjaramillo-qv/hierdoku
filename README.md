# Proyecto_Documentacion

HierDoku — Documentador Funcional Oficial. Frontend Streamlit que usa a
[Hermes](https://github.com/anthropics/hermes) como motor (herramientas,
memoria, skills, base vectorial) junto con Qdrant y OmniRoute.

## Servicios (docker-compose)

| Servicio    | Imagen                              | Puerto (host) | Descripción                              |
|-------------|-------------------------------------|---------------|------------------------------------------|
| `frontend`  | `kjaramillo/frontend_app:listo`     | `80` → `8501` | Interfaz Streamlit (HierDoku)            |
| `hermes`    | `kjaramillo/hermes:listo`           | `8642`, `8644`| Motor / API + webhook de documentación   |
| `qdrant`    | `qdrant/qdrant`                     | `6333`        | Base vectorial                           |
| `omniroute` | `kjaramillo/omniroute:listo`        | `20128`       | Rutas / storage / embeddings             |

## Estructura del repositorio

```
.
├── docker-compose.yml          # 4 contenedores
├── frontend/                   # app Streamlit (onboarding + chat + pipeline)
├── secrets/                    # entrypoint + sync de keys del usuario final
├── hermes/                     # EL "CEREBRO" del agente (ver abajo)
├── .env.example                # plantilla de secretos (copiar a .env)
└── README.md
```

## El cerebro de Hermes (`hermes/`)

Hermes vive en `${USERPROFILE}/.hermes` (fuera de este repo, montado como
`/opt/data` dentro del contenedor). Para que el sistema funcione, esa carpeta
debe contener los siguientes elementos, que aquí están versionados y
**sanitizados** (sin claves):

| Elemento | Ubicación en el repo | Qué es |
|---|---|---|
| `config.yaml` | `hermes/config.yaml` | Personalidad "Documentador Funcional Oficial" (flujo de 7 pasos), modelo, terminal y plataforma webhook (puerto 8644) |
| Webhook pipeline | `hermes/webhook_subscriptions.example.json` | Prompt del pipeline automático `documentar-pipeline` (secret enmascarado) |
| Skills | `hermes/skills/**` | `onboarding-primera-vez`, `qdrant-direct-search`, `capturas-documentacion`, `knowledge-base-webhook`, `integracion-frontend-hermes-contenedor`, `acceso-archivos-host-contenedor`, `documenting-web-app-ui` |
| Scripts | `hermes/scripts/**` | `ingesta_hibrida.py`, `busqueda_hibrida.py`, `izy_cdp.py` + docs de flujo/infraestructura |

### Cómo conectar Hermes con todo lo demás

- **Hermes → Qdrant**: `http://host.docker.internal:6333` (búsqueda híbrida: denso + sparse)
- **Hermes → OmniRoute (embeddings)**: `http://host.docker.internal:20128/v1/embeddings`, modelo `jina-ai/jina-embeddings-v5-text-small` (1024 dims)
- **Hermes → Ollama**: `http://host.docker.internal:11434` (modelo `nomic-embed-text`, 768 dims; vía skill `qdrant-direct-search`)
- **Frontend → Hermes**: `hermes:8642` (chat) + `hermes:8644` (webhook)
- Todo depende de la red `appnet` + `host.docker.internal` (`extra_hosts` en el compose).

## Requisitos

- Docker y Docker Compose
- Carpeta `${USERPROFILE}/.hermes` poblada con el contenido de `hermes/` (ver abajo)
- Carpetas locales `./mis_datos_qdrant` y `./mis_datos_omniroute` (datos; no se versionan)

## Configuración

1. Crea tu archivo de entorno a partir del ejemplo:

   ```bash
   cp .env.example .env
   ```

   Rellena las variables reales en `.env` (claves de Hermes y OmniRoute).

2. Copia el "cerebro" de Hermes a `${USERPROFILE}/.hermes`:

   ```powershell
   # Windows (PowerShell)
   Copy-Item -Recurse -Force ".\hermes\*" "$env:USERPROFILE\.hermes\"
   ```

   Esto deja `config.yaml`, las skills y los scripts donde Hermes los lee.
   Luego configura el webhook (una sola vez) sustituyendo el secret real:

   ```bash
   cp hermes/webhook_subscriptions.example.json \
      ~/.hermes/webhook_subscriptions.json   # reemplaza REEMPLAZA_ESTE_SECRET
   ```

3. (Opcional) Pre-sembra el archivo de keys del usuario final:

   ```bash
   cp secrets/user_keys.env.example secrets/user_keys.env
   ```

   Normalmente no hace falta: el frontend crea este archivo durante el
   onboarding de primera vez.

4. Levanta los servicios:

   ```bash
   docker compose up -d
   ```

5. Abre `http://localhost` y carga tu API key del proveedor de IA en la
   pantalla de bienvenida.

## Seguridad

- `.env`, `secrets/user_keys.env`, `secrets/.gateway_ready` y las carpetas de
  datos (`mis_datos_qdrant/`, `mis_datos_omniroute/`) están en `.gitignore` y
  **nunca** se suben al repositorio.
- `hermes/webhook_subscriptions.example.json` tiene el secret **enmascarado**
  (`REEMPLAZA_ESTE_SECRET`); el real vive solo en el `~/.hermes` del operador.
- El `config.yaml` versionado no contiene claves: usa `${env:WEBHOOK_SECRET}` y
  las credenciales se resuelven desde `.env`.
- Los secretos viven solo en el equipo del operador.
