# Infraestructura del contenedor (Docker / WSL2)

## Aislamiento del sistema de archivos
El agente corre dentro de un contenedor Docker sobre WSL2. NO ve C:\ ni /mnt/c del
host Windows directamente. El puente es un bind-mount.

## Mapeo del bind-mount (docker-compose.unificado.yml, servicio 'hermes')
- Bind: `C:\Users\KevinJaramilloRuiz\.hermes` (host)  ->  `/opt/data` (contenedor).
- Es decir, /opt/data DENTRO del contenedor ES esa carpeta oculta del host, y
  PERSISTE aunque se recree el contenedor.
- Todo lo que el agente guarda en /opt/data/documentacion_creada/ aparece en el
  host en: C:\Users\KevinJaramilloRuiz\.hermes\documentacion_creada\

## Caso "carpeta local de referencia" SIN bind-mount propio
Cuando el usuario tiene documentación de referencia en una carpeta cualquiera de
su Windows que NO está montada, el flujo es:
1. El usuario copia esos archivos con PowerShell hacia
   ...\.hermes\documentacion_referencia\
2. Automáticamente aparecen dentro del contenedor en
   /opt/data/documentacion_referencia/
3. Ante cualquier ruta del host que mencione el usuario: verificar con `test -d` /
   `test -f`; si falta, AVISAR al usuario. NUNCA sustituir en silencio ni inventar
   contenido.

## Composición unificada
docker-compose.unificado.yml levanta: frontend + hermes + qdrant + omniroute.
n8n quedó ABANDONADO (ya no forma parte del flujo activo de ingesta).
La comunicación entre servicios es por host.docker.internal.

## Entrega asistida al usuario (PowerShell no destructivo)
Al terminar un documento, se entrega al usuario un comando PowerShell que copia
desde $env:USERPROFILE\.hermes\documentacion_creada\ (o la subcarpeta del
documento) hacia una ruta CONCRETA que el usuario indique. Reglas:
- Copiar SIEMPRE dentro de una subcarpeta nueva y propia en el destino.
- NUNCA usar -Force ni sobrescribir. Si la subcarpeta ya existe, DETENERSE y
  avisar del conflicto.
- Exigir ruta concreta; no aceptar respuestas vagas ("donde sea", "tú decide").
