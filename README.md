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
| `omniroute` | `kjaramillo/omniroute:listo`        | `20128`       | Rutas / storage de la app                |

## Requisitos

- Docker y Docker Compose
- Carpeta `${USERPROFILE}/.hermes` con la configuración de Hermes
- Carpetas locales `./mis_datos_qdrant` y `./mis_datos_omniroute` (datos)

## Configuración

1. Crea tu archivo de entorno a partir del ejemplo:

   ```bash
   cp .env.example .env
   ```

   Rellena las variables reales en `.env` (claves de Hermes y OmniRoute).

2. (Opcional) Pre-sembra el archivo de keys del usuario final:

   ```bash
   cp secrets/user_keys.env.example secrets/user_keys.env
   ```

   Normalmente no hace falta: el frontend crea este archivo durante el
   onboarding de primera vez.

3. Levanta los servicios:

   ```bash
   docker compose up -d
   ```

4. Abre `http://localhost` y carga tu API key del proveedor de IA en la
   pantalla de bienvenida.

## Seguridad

- `.env`, `secrets/user_keys.env`, `secrets/.gateway_ready` y las carpetas de
  datos (`mis_datos_qdrant/`, `mis_datos_omniroute/`) están en `.gitignore` y
  **nunca** se suben al repositorio.
- Los secretos viven solo en el equipo del operador.
