---
name: onboarding-primera-vez
description: "Onboarding 1a vez: docs referencia y colores a Qdrant."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [onboarding, documentacion, qdrant, omniroute, colores, referencia, hibrido]
    related_skills: [capturas-documentacion, qdrant-direct-search, knowledge-base-webhook]
---

# Onboarding de primera vez (Especialista de Documentación)

## Secuencia de arranque (ORDEN OBLIGATORIO en la primera interacción)

Antes de cualquier otra cosa, en cada primera interacción con un usuario, seguir
este orden estricto:

EMBEDDINGS (importante — cambio 2026-09): la credencial de embeddings YA viene
PRECONFIGURADA en OmniRoute dentro del docker compose que se distribuye al cliente
(clave única incluida por el operador). Por tanto el agente NUNCA pide, configura,
registra ni borra API key, y NUNCA menciona Jina al usuario. Solo USA OmniRoute
directamente para vectorizar (POST `http://host.docker.internal:20128/v1/embeddings`,
modelo `jina-ai/jina-embeddings-v5-text-small`, 1024d). NO hay Paso 0 de
verificación de credencial ni flujo de pedir key.

PASO 1 — Onboarding de primera vez (referencia + colores): el resto de este
documento (detección de primera vez + Pasos 1-7).

PASO 2 — Convertirse en el Documentador Funcional Oficial: una vez cerrado el
onboarding (marcador .onboarding_done), seguir el flujo normal de 7 pasos de
creación/edición de la personalidad `personalities.default` del config.yaml.

Flujo OBLIGATORIO que se ejecuta UNA sola vez, la primera vez que un usuario/empresa
entra a la aplicación. Recoge la documentación de referencia y la paleta de colores
de la empresa, los vectoriza (localmente, ver más abajo) y los deja en Qdrant para que
TODA creación/actualización de documentación posterior lea ese estilo y colores.
Después de la primera vez NUNCA se repiten estas preguntas: se pasa al flujo normal
(la personalidad "Documentador Funcional Oficial" del config.yaml, 7 pasos).

## Cómo saber si ES la primera vez (doble check)

1. Qdrant: `GET http://host.docker.internal:6333/collections/docs_referencia` y
   `.../colores_referencia`. Si AMBAS tienen `points_count == 0` (o no existen) →
   es primera vez.
2. Marcador local: si NO existe `/opt/data/.onboarding_done` → refuerza que es
   primera vez.
Si las colecciones tienen puntos O existe el marcador → NO es primera vez: saltar
todo esto e ir al flujo normal (no volver a preguntar por referencia ni colores).

## Infraestructura de vectorización (n8n ABANDONADO)

n8n queda DESCARTADO para ingesta: su nodo Qdrant no escribe vectores sparse y usa
vector sin nombre → daba HTTP 200 pero 0 puntos. La ingesta y la búsqueda las hago
YO con scripts Python locales, que es además lo más barato en tokens/tiempo: el
trabajo pesado (embeddings + sparse + upsert) ocurre en terminal y NO pasa por mi
contexto — solo leo un JSON de confirmación de una línea.

Qdrant: `http://host.docker.internal:6333` (NO localhost). Las 3 colecciones
(`docs_referencia`, `colores_referencia`, `requerimientos`) son HÍBRIDAS e idénticas:
- vector denso NOMBRADO `dense` (1024, Cosine) — modelo jina-embeddings-v5-text-small
- vector sparse NOMBRADO `sparse` (modifier IDF) — modelo Qdrant/bm25

Embeddings densos vía OmniRoute `http://host.docker.internal:20128/v1/embeddings`
(sin key desde este host), modelo `jina-ai/jina-embeddings-v5-text-small` = 1024d.
REGLA DE EFICIENCIA: usar SIEMPRE OmniRoute para densos y Qdrant directo para
leer/escribir; nunca meter el contenido vectorizado por mi contexto.

## Ingesta y búsqueda: scripts locales (vía ÚNICA y autoritativa)

- Ingesta: `/opt/data/scripts/ingesta_hibrida.py`
  `source /opt/data/.venv-ingesta/bin/activate` (tiene fastembed + qdrant-client)
  `python ingesta_hibrida.py --file <ruta.md> --collection <coll> \
     --directorio <dir> --tipo <estructura|redaccion|capturas|documento>`
  Hace: split recursivo (~1000/overlap 150) + denso jina 1024 (OmniRoute) + sparse
  BM25/IDF (local) + upsert de puntos con vector {dense, sparse} y payload {text,
  archivo, directorio, tipo, chunk}. Vale para las 3 colecciones (docs_referencia,
  colores_referencia, requerimientos). Verifica `status: ok` y `points_count > 0`.
- Búsqueda: `/opt/data/scripts/busqueda_hibrida.py --collection <coll> --query "..."`
  Fusión RRF de denso + sparse (MISMOS modelos que la ingesta). Recupera por
  semántica y por keyword exacta. Usar esto para leer estilo/estructura/capturas
  (docs_referencia) y paleta (colores_referencia) antes de crear/actualizar.

Editar/borrar un documento SIN borrar la colección: filtrar por payload `archivo`,
p.ej. `POST /collections/<coll>/points/delete {"filter":{"must":[{"key":"archivo",
"match":{"value":"<fileName>"}}]}}`. Recrear una colección híbrida vacía:
`PUT /collections/<c>` con
`{"vectors":{"dense":{"size":1024,"distance":"Cosine"}},"sparse_vectors":{"sparse":{"modifier":"idf"}}}`.

## Procedimiento (primera vez)

### Paso 1 — Pedir documentación de referencia (INSISTIR hasta obtenerla)
Preguntar si tiene documentación de referencia: propia de la empresa, o una que
quiera tomar como referencia para la que se creará. Insistir hasta que entregue
UNA de estas fuentes:
- Carpeta local: ver sub-procedimiento "Carpeta local por copia del host" abajo.
- Repositorio (git u otro): pedir CREDENCIALES (efímeras/solo lectura) para
  clonar/analizar. NUNCA persistir esas credenciales en memoria/skills/archivos.
- Link a documentación de referencia (web): usar el link directamente.
No avanzar sin una fuente real.

#### Sub-procedimiento: Carpeta local por copia del host (SIN bind-mount)
El contenedor NO ve C:\ ni /mnt/c. Solución preferida y estándar: que el usuario
COPIE su carpeta a la zona del host que YA está bind-mounteada a /opt/data, y yo
la leo desde ahí. Mapeo (de docker-compose.unificado.yml, servicio hermes):
`C:\Users\<USUARIO>\.hermes  ->  /opt/data`. Por tanto lo que se copie a
`C:\Users\<USUARIO>\.hermes\documentacion_referencia\` aparece en
`/opt/data/documentacion_referencia/`.
Pasos:
1. Confirmar el mapeo host->/opt/data leyendo el bind con target /opt/data en el
   compose (NO asumir el usuario; puede cambiar de máquina). El origen de ese bind
   es la base del host donde el usuario debe copiar.
2. Pedir al usuario la RUTA de su carpeta de referencia y explicarle cómo sacarla:
   abrir el Explorador de archivos, entrar a la carpeta, hacer clic en la barra de
   direcciones de arriba, copiar la ruta completa y pegármela TAL CUAL.
3. Generar un comando de copia para que lo ejecute EN SU HOST (Windows =
   PowerShell; explicarle cómo abrir la terminal: menú Inicio -> "PowerShell" o
   "Terminal"). Explicarle EXACTAMENTE qué hace el comando y POR QUÉ (copiar su
   carpeta a la zona compartida .hermes para que yo tenga acceso), no solo pegarlo.
   Plantilla (ajustar origen a lo que pegó y base .hermes al mapeo real):
   `Copy-Item -LiteralPath "<RUTA_ORIGEN_DEL_USUARIO>" -Destination "C:\Users\<USUARIO>\.hermes\documentacion_referencia\" -Recurse -Force`
   Notas al usuario: comillas obligatorias (rutas con espacios como "OneDrive -
   Empresa"/"Escritorio"); si la carpeta está en OneDrive con "archivos a demanda",
   marcarla antes como "Conservar siempre en este dispositivo" o se copian
   placeholders vacíos.
4. VERIFICAR desde el contenedor que llegó: `test -d /opt/data/documentacion_referencia/<carpeta>`
   y `ls`/conteo de archivos. Si no existe, avisar y NO usar un sustituto silencioso.
5. Recién entonces analizar (Paso 2) e ingestar (Paso 4) leyendo de esa ruta.

### Paso 2 — Analizar la referencia (OBLIGATORIO, los 3 ejes)
Sobre la fuente entregada, analizar y anotar:
1. ESTRUCTURA: cómo está organizada y dividida la información (secciones,
   jerarquía, orden, índice, granularidad por página/tema).
2. REDACCIÓN: cómo escriben y generan los textos (tono, persona, longitud de
   frase, uso de admonitions/notas/avisos, imperativo vs descriptivo, glosario).
3. CAPTURAS: dónde y cómo son las capturas que usan para guiar al usuario
   (posición respecto al paso, recorte, anotaciones/flechas/resaltados, tamaño,
   qué muestran). Ver skill `capturas-documentacion` para replicarlas.

### Paso 3 — Informar sobre gestión de la referencia
Decir al usuario que SIEMPRE que quiera se puede modificar o borrar estos
documentos de referencia, PERO SIN BORRAR LA COLECCIÓN (`docs_referencia`
permanece; solo se editan/borran sus puntos/documentos).

### Paso 4 — Ingestar la documentación de referencia a Qdrant
Subir cada documento con el script de ingesta híbrida:
`source /opt/data/.venv-ingesta/bin/activate`
`python /opt/data/scripts/ingesta_hibrida.py --file <ruta.md> \
  --collection docs_referencia --directorio /opt/data/ref/<empresa> --tipo estructura`
Subir el contenido completo (análisis de estructura/redacción/capturas) como
archivos .md, sin resumir/truncar; usa `--tipo` para etiquetar cada aspecto
(estructura|redaccion|capturas|documento). Verificar `docs_referencia.points_count > 0`.
Nota capturas: las imágenes crudas NO se vectorizan útilmente como texto; guardar la
DESCRIPCIÓN de las capturas en markdown (posición, qué muestran, textos de UI,
anotaciones) y conservar las imágenes aparte en disco, no en la base vectorial.

### Paso 5 — Pedir colores de la empresa (INSISTIR hasta obtenerlos)
Preguntar cuáles son los colores que representan a su empresa o que desea usar para
las documentaciones. Insistir hasta que los otorgue (aceptar hex, nombres, o
paleta). Decirle que en cualquier momento puede cambiarlos cuando lo pida.

### Paso 6 — Ingestar los colores a Qdrant
Igual que Paso 4, con el script y la colección de colores:
`python /opt/data/scripts/ingesta_hibrida.py --file <ruta/colores.md> \
  --collection colores_referencia --tipo documento`
Guardar la paleta como archivo .md (hex + nombres + uso: primario, secundario,
acento, fondo, texto). Verificar `colores_referencia.points_count > 0`.

### Paso 7 — Cerrar onboarding
Crear el marcador `/opt/data/.onboarding_done` (con fecha) para no repetir. A
partir de aquí, cada creación/actualización de documentación LEE `docs_referencia`
(estilo/estructura/capturas) y `colores_referencia` (paleta) antes de generar, y se
sigue el flujo normal de 7 pasos de la personalidad. No volver a preguntar por
referencia ni colores salvo que el usuario lo pida explícitamente.

## Persistencia de OmniRoute (CRÍTICO — sin esto se borra la config al recrear)

VERIFICADO en la doc de OmniRoute (/docs/operations/DATABASE_GUIDE, SQLITE_RUNTIME):
- Toda la config, proveedores, API keys y settings de OmniRoute viven en UNA sola
  base: `${DATA_DIR}/storage.sqlite` (+ storage.sqlite-wal/-shm, embeddings/,
  call_logs/, runtime/, skills/).
- DATA_DIR por defecto: `~/.omniroute/` (o `$XDG_CONFIG_HOME/omniroute/`). En Docker
  la recomendación oficial es `DATA_DIR=/data` + montar un volumen en `/data`.

PROBLEMA (bug real detectado): si el servicio omniroute del compose NO tiene
`volumes`, la BD vive DENTRO del contenedor y se PIERDE en cada recreate/upgrade
(`docker compose up --force-recreate`) -> se borran la clave de embeddings
preconfigurada, la OMNIROUTE_API_KEY guardada, proveedores y settings. Qdrant ya
trae su volumen (qdrant_storage); OmniRoute hay que agregárselo igual.

ARREGLO (servicio omniroute en docker-compose.unificado.yml):
  environment:
    - DATA_DIR=/data
    - OMNIROUTE_API_KEY=${OMNIROUTE_API_KEY}
    - INITIAL_PASSWORD=${OMNIROUTE_INITIAL_PASSWORD}
    - JWT_SECRET=${OMNIROUTE_JWT_SECRET}
    - STORAGE_ENCRYPTION_KEY=${OMNIROUTE_STORAGE_KEY}
  volumes:
    - omniroute_storage:/data
Y declarar el volumen al final: `volumes: { qdrant_storage:, omniroute_storage: }`.

Doble seguridad del acceso del agente: la OMNIROUTE_API_KEY viene de env var (.env),
así que aunque se borrara el volumen, el compose la reinyecta al arrancar -> el
agente nunca pierde acceso. El volumen protege el RESTO (clave de embeddings
preconfigurada, settings). REGLA DE ORO: reutilizar SIEMPRE el mismo nombre de
volumen; un nombre nuevo = arranque vacío.

## Embeddings preconfigurados (cambio 2026-09 — el agente NO gestiona credenciales)

CAMBIO DE MODELO: la credencial de embeddings YA viene incluida en el docker compose
que se distribuye al cliente. El programa llega funcionando. Por tanto el agente:
- NUNCA pide, registra, configura ni borra API key de embeddings.
- NUNCA menciona Jina al usuario ni le pide entrar a jina.ai.
- Solo USA OmniRoute directamente para vectorizar: POST
  `http://host.docker.internal:20128/v1/embeddings`, modelo
  `jina-ai/jina-embeddings-v5-text-small` (1024d, Cosine). Sin header en rutas /v1/*.
No existe Paso 0 de verificación de credencial. Si por un fallo de despliegue los
embeddings NO respondieran (error de credencial), es un problema del OPERADOR que
armó el compose, NO algo que el agente resuelva pidiendo key al usuario final:
avisar al usuario que contacte a su proveedor/operador.

La OMNIROUTE_API_KEY del entorno (`Authorization: Bearer ${OMNIROUTE_API_KEY}` en
rutas /api/*) sigue disponible por si se necesita inspeccionar OmniRoute, pero el
flujo normal de documentación NO requiere tocar /api/providers.

## Pitfalls

- Insistir de verdad en pasos 1 y 5: no avanzar con la fuente/colores faltantes.
- Credenciales de repos: efímeras, solo lectura, NUNCA guardarlas.
- Modificar/borrar referencia = editar puntos; JAMÁS borrar la colección.
- Dim de consulta debe ser 1024 (named vector `dense`), no 768.
- host.docker.internal, no localhost.
- n8n ABANDONADO para ingesta: su nodo Qdrant no escribe sparse y usa vector sin
  nombre → HTTP 200 pero 0 puntos. Toda ingesta/consulta va por los scripts locales.
  Verificar SIEMPRE points_count tras subir.
- Colecciones híbridas: vectores nombrados `dense` (1024/Cosine) + `sparse` (IDF).
  Ingesta y búsqueda deben usar los MISMOS modelos (jina 1024 + Qdrant/bm25).
- Metadata por punto: `text`, `archivo` (=fileName, clave para editar/borrar un doc
  sin borrar la colección), `directorio`, `tipo`, `chunk`.
- venv de ingesta: `/opt/data/.venv-ingesta` (fastembed + qdrant-client).
- Capturas: guardar DESCRIPCIÓN en markdown; imágenes crudas aparte en disco.

## Verification

- `docs_referencia` y `colores_referencia` con `points_count > 0`.
- Existe `/opt/data/.onboarding_done`.
- `busqueda_hibrida.py` sobre `docs_referencia` con una query on-topic devuelve el
  texto real de la referencia (recupera por semántica y por keyword exacta).
