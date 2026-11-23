# Proyecto_Documentacion

HierDoku — Documentador Funcional Oficial. Frontend Streamlit que usa a
[Hermes](https://github.com/anthropics/hermes) como motor (herramientas,
memoria, skills, base vectorial) junto con Qdrant y OmniRoute.

## Despliegue (solo 2 claves)

```bash
# 1) Crear el archivo de entorno y poner SOLO 2 claves
cp .env.example .env
#    -> OPENAI_API_KEY  (la "key de Hermes", modelo de chat)
#    -> JINA_API_KEY    (embeddings, se registra sola en OmniRoute)

# 2) Levantar el stack
docker compose up -d

# 3) Abrir http://localhost
```

El **primer arranque** del contenedor `hermes` ejecuta `secrets/bootstrap.sh`,
que deja todo listo de forma automática:

- Copia el "cerebro" (`hermes/` → `~/.hermes`): personalidad, skills y scripts.
- Escribe `~/.hermes/.env` con los secretos.
- Registra la clave de Jina en OmniRoute (`POST /api/providers`).
- Crea el venv de ingesta (`fastembed` + `qdrant-client`).
- Genera el webhook `documentar-pipeline`.

> ⚠️ El primer arranque tarda **1-3 minutos** en terminar de provisionar el venv
> y registrar Jina. Espera un par de minutos antes de hacer el onboarding.
> Puedes ver el progreso con `docker logs hermes` (busca `[bootstrap]`).

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
├── secrets/                    # bootstrap.sh + entrypoint + sync de keys
├── hermes/                     # EL "CEREBRO" del agente (config, skills, scripts)
├── .env.example                # plantilla: solo 2 claves que rellenar
└── README.md
```

## El cerebro de Hermes (`hermes/`)

Versionado y sanitizado (sin claves). Se copia solo a `${USERPROFILE}/.hermes`
en el primer arranque. Contiene:

- `config.yaml` — personalidad "Documentador Funcional Oficial" (flujo 7 pasos),
  modelo, terminal y plataforma webhook (puerto 8644).
- `webhook_subscriptions.example.json` — prompt del pipeline automático (secret
  enmascarado; el bootstrap lo sustituye por el real).
- `skills/**` — `onboarding-primera-vez`, `qdrant-direct-search`,
  `capturas-documentacion`, `knowledge-base-webhook`,
  `integracion-frontend-hermes-contenedor`, `acceso-archivos-host-contenedor`,
  `documenting-web-app-ui`.
- `scripts/**` — `ingesta_hibrida.py`, `busqueda_hibrida.py`, `izy_cdp.py` + docs.
- `skins/hierdoku.yaml` — tema de marca.

### Cómo conecta Hermes con todo

- **Hermes → Qdrant**: `http://host.docker.internal:6333`
- **Hermes → OmniRoute (embeddings)**: `http://host.docker.internal:20128/v1/embeddings`,
  modelo `jina-ai/jina-embeddings-v5-text-small` (1024 dims)
- **Frontend → Hermes**: `hermes:8642` (chat) + `hermes:8644` (webhook)
- Red `appnet` + `host.docker.internal` (`extra_hosts` en el compose).

## Seguridad

- `.env`, `secrets/user_keys.env`, `secrets/.gateway_ready`, y las carpetas de
  datos (`mis_datos_qdrant/`, `mis_datos_omniroute/`) están en `.gitignore` y
  **nunca** se suben.
- `hermes/webhook_subscriptions.example.json` tiene el secret **enmascarado**.
- `config.yaml` no contiene claves (usa `${env:WEBHOOK_SECRET}`).
- Los secretos internos del `.env.example` son valores generados de ejemplo:
  **regéneralos** si despliegas para un cliente distinto.

## Solución de problemas

- **Embeds no responden / error de credencial Jina**: revisa
  `docker logs hermes | grep bootstrap`. Asegúrate de que `JINA_API_KEY` está
  en `.env` y reinicia con `docker compose up -d --force-recreate hermes`.
- **El frontend pide API key en el onboarding**: es lo esperado si no pusiste
  `OPENAI_API_KEY` en `.env`; cárgala en la pantalla de bienvenida.
- **Sin capturas**: el navegador Playwright se instala bajo demanda (ver skill
  `capturas-documentacion`).
