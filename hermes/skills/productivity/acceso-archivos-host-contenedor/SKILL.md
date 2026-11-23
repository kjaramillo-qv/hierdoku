---
name: acceso-archivos-host-contenedor
description: "Leer archivos del host Windows/WSL desde el contenedor."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [docker, wsl, contenedor, filesystem, bind-mount, docker-compose, host]
    related_skills: [onboarding-primera-vez, capturas-documentacion]
---

# Acceso a archivos del host desde el contenedor Hermes

Cómo tratar rutas de archivos que el usuario da en su equipo host (Windows/WSL)
cuando Hermes corre DENTRO de un contenedor Docker aislado. Cubre por qué esas
rutas suelen ser invisibles, la regla de comportamiento (no sustituir en
silencio) y la solución permanente (bind-mount vía docker-compose).

## Regla de comportamiento (la más importante)

Cuando el usuario entregue una ruta de una fuente (carpeta de referencia, archivo
de requerimientos, compose, etc.):
1. VERIFICA primero que existe dentro del contenedor: `test -d <ruta>` / `test -f`.
2. Si NO existe, DÍSELO de inmediato y ofrece una alternativa (copiar a una ruta
   accesible, montar bind-mount, pegar el contenido, o pasar un repo/URL).
3. NUNCA caigas silenciosamente en otra carpeta/archivo parecido que sí exista
   (p.ej. una copia previa bajo /opt/data) haciéndola pasar por la que pidió.
   Aunque el contenido COINCIDA esta vez, puede no coincidir la próxima y estarías
   engañando al usuario sobre qué fuente analizaste. Si usas un sustituto, tiene
   que ser una decisión EXPLÍCITA que el usuario aprobó.

## Por qué las rutas del host son invisibles (diagnóstico)

Síntomas típicos en un despliegue Docker-sobre-WSL2:
- `mount` muestra `C:\ on /opt/data type 9p (...drvfs...)` → etiqueta ENGAÑOSA:
  `/opt/data` es el HOME persistente de Hermes, NO tu disco C:. No contiene
  `Users/`, `Windows/`, `Program Files/`.
- `/mnt/c` y `/mnt/host` NO existen dentro del contenedor.
- Por tanto `C:\Users\...\Escritorio\...` y su traducción `/mnt/c/Users/...` son
  inaccesibles. Confírmalo con `test -d`.
- `/opt/data` está respaldado por un montaje del host (9p/drvfs), por eso PERSISTE
  entre recreaciones del contenedor: ahí viven memoria (`/opt/data/memories`),
  skills (`/opt/data/skills`), config (`/opt/data/config.yaml`), docs creadas.

Comandos de diagnóstico útiles:
```
cat /proc/mounts | grep -E " /opt/data "     # qué respalda mi home
ls /mnt 2>/dev/null; ls /mnt/host 2>/dev/null # normalmente vacío/inexistente
test -f /.dockerenv && echo "soy Docker"
uname -a | grep -i microsoft                   # kernel WSL2
docker ps 2>&1                                  # suele FALLAR: sin socket dentro
```

## Solución rápida (puntual): copiar al contenedor

El usuario copia la carpeta/archivo a una ruta bajo `/opt/data` (p.ej.
`/opt/data/documentacion_referencia/`), o pega el contenido en el chat. Sirve para
casos únicos; hay que recopiar cuando la fuente cambie.

## Sacar archivos QUE YO CREÉ hacia el host (copy-OUT)

Lo que Hermes genera bajo `/opt/data` (p.ej. `/opt/data/documentacion_creada`)
YA ESTÁ en el disco del host: `/opt/data` = `C:\Users\<user>\.hermes`. No está
"dentro del contenedor" en el sentido de efímero — persiste. Solo está ESCONDIDO
dentro de `.hermes`. Si el usuario quiere el resultado en una carpeta normal como
`Documents\...`, esa carpeta está FUERA del bind-mount y NO la alcanzo (no hay
`/Users`, `/mnt/host` ni `/mnt/c`; confírmalo con `ls`). Flujo correcto:
1. Yo genero/guardo en mi única zona escribible del host: bajo `/opt/data`.
2. Como no alcanzo `Documents`, doy al usuario un comando PowerShell para el salto
   final `.hermes → Documents`, y le explico QUÉ hace y POR QUÉ lo corre él.
3. Verificación: yo confirmo el ORIGEN (`find`/`du` bajo `/opt/data`); el DESTINO
   solo lo verifica el usuario pegándome la salida — dilo honestamente, no afirmes
   que la copia llegó sin evidencia.

Comando PowerShell (crea destino idempotente + copia recursiva; `$env:USERPROFILE`
evita rutas a mano):
```
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\Documents\CARPETA_DESTINO"; Copy-Item -Path "$env:USERPROFILE\.hermes\SUBCARPETA_ORIGEN\*" -Destination "$env:USERPROFILE\Documents\CARPETA_DESTINO\" -Recurse -Force
```
El usuario verifica con:
`Get-ChildItem "$env:USERPROFILE\Documents\CARPETA_DESTINO" -Recurse | Select-Object FullName`

## Borrar SÍ funciona (asimetría entrada vs borrado)

Duda frecuente del usuario: "si copiaste con PowerShell, ¿pierdes acceso para
borrarlo?" NO. La regla es DÓNDE vive el archivo, no CÓMO llegó. PowerShell es solo
el "camión de entrada" porque no puedo entrar a `C:\` a recoger. Una vez el archivo
está bajo `/opt/data`, es 100% mío: lo borro con `rm -rf` desde mi terminal, sin
que el usuario corra nada. El borrado se refleja en el Windows real y persiste.
- SIEMPRE confirma QUÉ se borra antes de ejecutar (destructivo + persiste al host).
- Demostrable: crear una carpeta con archivos+subcarpeta y borrarla con `rm -rf`,
  luego `find . -mindepth 1 | wc -l` == 0 confirma que no queda cascarón.

## Solución permanente: bind-mount en docker-compose

Para leer EN VIVO una carpeta del host sin recopiar, se monta al arrancar el
contenedor. Desde DENTRO no se puede (no hay acceso al socket de Docker); lo hace
el usuario en el HOST.

- Origen en formato WSL, NO `C:\...`: `/mnt/c/Users/.../carpeta`.
- Comillas OBLIGATORIAS si la ruta tiene espacios (p.ej. `OneDrive - Empresa`,
  `Escritorio`). Sin comillas, Docker falla.
- `:ro` = solo lectura (recomendado para material de referencia).
- OneDrive "archivos a demanda": marca la carpeta como "Conservar siempre en este
  dispositivo" o Docker verá placeholders vacíos.

Ejemplo (servicio en compose):
```yaml
services:
  hermes:
    volumes:
      - "/mnt/c/Users/USUARIO/.../carpeta:/opt/data/documentacion_referencia/carpeta:ro"
```
Aplicar: `docker compose up -d --force-recreate hermes`.

### Acceso PORTABLE y TOTAL al equipo (Docker Desktop en Windows)

Cuando Hermes corre bajo Docker Desktop (no docker-en-WSL puro), el compose acepta
rutas Windows NATIVAS y variables de entorno de Windows en el lado izquierdo del
bind. Esto habilita dos cosas que el formato `/mnt/c/...` no da:

- Portabilidad real entre máquinas con `${USERPROFILE}` (Docker lo resuelve a
  `C:\Users\<usuario-actual>` en CADA PC). El MISMO compose funciona en cualquier
  equipo sin editar rutas por usuario. Ejemplos:
  - `- "${USERPROFILE}/.hermes:/opt/data"`  (home persistente de Hermes)
  - `- "${USERPROFILE}:/mnt/host"`          (perfil COMPLETO del usuario)
- Montar el DISCO ENTERO del equipo (Windows, Program Files, TODOS los usuarios):
  - `- "C:\\:/mnt/host"`  (nota: doble backslash `C:\\` en YAML)
  Con esto se ve todo `C:` (`/mnt/host/Windows`, `/mnt/host/Users`, ...) en vivo.

Alcance de lo que se monta (verifícalo, no lo supongas): si aparecen
`Documents/Downloads/OneDrive/NTUSER.DAT` pero NO `Windows`/`Program Files`/`Users`,
lo montado es solo un PERFIL de usuario, no el disco. `ls /mnt/host` + comprobar
`ls -d /mnt/host/Windows /mnt/host/Users` lo desambigua en un comando.

"Montar" NO es "copiar": aclaración que el usuario suele necesitar. Un bind-mount
es una ventana EN VIVO al disco real (cambios bidireccionales instantáneos, cero
espacio extra), no una duplicación. `cat /proc/mounts | grep <destino>` lo confirma.

### PITFALL crítico: discos extra (D:/E:) rompen TODO el stack

Si el compose lista un disco que NO existe en esa máquina (p.ej. `- "D:\\:/mnt/host-d"`
en un PC sin unidad D:), Docker Desktop FALLA al arrancar y NO levanta NINGÚN
servicio del compose. Como D:/E:/F: varían por equipo, montarlos "a ciegas" mata
la portabilidad. Solución: monta `C:\` (existe en toda máquina Windows) como base
garantizada, y deja las líneas de discos extra COMENTADAS con instrucción de
descomentar SOLO en máquinas que sí los tengan:
```yaml
      - "C:\\:/mnt/host"
      #- "D:\\:/mnt/host-d"   # descomentar solo si esa maquina tiene disco D:
      #- "E:\\:/mnt/host-e"
```

### Advertencia de seguridad al ampliar el bind

Montar `C:\` completo con lectura/escritura da al agente acceso total al equipo
(archivos de sistema, de todos los usuarios, credenciales guardadas). Es potente y
a veces es justo lo pedido, pero DÍSELO explícitamente al usuario antes de
desplegar: quien instale la imagen concede ese nivel de acceso. Si basta con menos,
ofrece `:ro` (solo lectura) o montar solo `${USERPROFILE}` en vez del disco entero.

## Recrear el contenedor SIN perder lo aprendido

Reconstruir/recrear el contenedor de Hermes NO borra memoria, skills, config ni
docs, PORQUE viven en `/opt/data`, que está respaldado por el host (ver arriba).
Servicios externos (p.ej. Qdrant en `host.docker.internal:6333`, OmniRoute en
:20128) son OTROS contenedores con sus propios volúmenes: recrear Hermes no los
toca. Regla de oro al editar/rehacer un docker-compose: REUTILIZA los volúmenes
existentes con su mismo nombre/ruta. Si compose crea volúmenes con nombres nuevos,
los servicios arrancan VACÍOS (Qdrant perdería colecciones). Para reconstruir la
receta de un contenedor existente desde el host: `assaflavie/runlike <nombre>`, o
`docker inspect <n> --format '{{json .Mounts}}'` + `... .NetworkSettings.Networks`.

## Pitfalls

- No confíes en la etiqueta `mount` "C:\ on /opt/data": no es el disco C:.
- Rutas del host las provee el usuario en formato WSL `/mnt/c/...` para el bind
  (aunque él escriba `C:\...`); dentro del contenedor esas rutas no se resuelven
  solas.
- Antes de pegar salidas de `runlike`/`inspect`: pueden traer API keys en `-e`;
  pedir al usuario que oculte los VALORES (el nombre de la variable sí se necesita)
  y referenciarlas desde un `.env` en el compose, nunca en claro.
- Contenedores compose comparten red `<proyecto>_default`; para conectar Hermes a
  un frontend/servicio ya existente, edita el compose que YA los define en lugar de
  crear uno nuevo, y mantenlos en la misma red.

## Verification

- `test -d`/`test -f` sobre la ruta del usuario confirma accesibilidad ANTES de
  analizar la fuente.
- Tras un bind-mount, `cat /proc/mounts | grep <destino>` lo muestra como montaje
  real (no una copia), y la carpeta destino tiene el contenido esperado.
