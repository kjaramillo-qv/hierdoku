# Onboarding de primera vez y explicación de la API key de Jina

## Secuencia de arranque (cada primera interacción)
1. Verificar la conexión de embeddings en OmniRoute.
   - Si falta la credencial del proveedor Jina, el endpoint responde:
     "No credentials for embedding provider: jina-ai".
2. Ejecutar el onboarding de primera vez (skill onboarding-primera-vez).
3. Solo después, actuar como Documentador Técnico Oficial (config.yaml, 7 pasos).

## Cómo explicar al usuario la API key de Jina (cuando falte)
Pedir la API key de Jina explicando de forma clara:
- PARA QUÉ SIRVE: únicamente para vectorizar texto (convertir la documentación en
  vectores) y poder guardarla/buscarla en la base de conocimiento.
- POR QUÉ ES SEGURO: es efímera. Se hace UN solo POST a OmniRoute, que la guarda
  cifrada de su lado; el agente la descarta en el acto y NUNCA la guarda en
  memoria, skills ni archivos. El entorno enmascara secretos en logs.
- CÓMO OBTENERLA: entrar a https://jina.ai -> iniciar sesión -> panel de API /
  "API Key" -> copiar la clave (empieza por "jina_..."). El plan gratuito trae
  tokens suficientes para empezar.
- Recomendar rotar la clave por higiene si el usuario la compartió por chat.

## Nota
El procedimiento TÉCNICO de registro del proveedor en OmniRoute NO vive aquí ni
en Qdrant (paradoja de bootstrap: si los embeddings fallan no se puede buscar en
Qdrant). Vive en la skill 'omniroute-jina-embeddings' para estar siempre
accesible sin depender de la base vectorial.
