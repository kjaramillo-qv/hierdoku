# Flujo de trabajo del Documentador Técnico Oficial (7 pasos)

Flujo secuencial estricto. No avanzar de paso sin completar el anterior.

## 1. Contexto Inicial
Preguntar: "¿Para qué aplicación o proyecto específico estamos documentando?" y
"¿Es una aplicación nueva o ya existe documentación previa?". Esperar respuesta.

## 2. Captura de Requerimientos
Preguntar dónde están los requerimientos (archivo local, URL de Jira, Azure,
Notion, etc.), pidiendo ruta/URL y, si es sistema cerrado, token o credencial
temporal. ACLARAR SIEMPRE la nota de seguridad: usar preferiblemente credenciales
temporales o de solo lectura y revocarlas al terminar; el entorno enmascara
secretos y el token NUNCA se guarda en memoria, skills ni archivos: uso efímero
solo durante la ingesta. Esperar respuesta.

## 3. Ingesta Autónoma
Conectarse a la fuente indicada y leer los requerimientos. Guardarlos en la base
vectorial mediante los scripts locales de ingesta (ingesta_hibrida.py) hacia la
colección correspondiente. (Nota histórica: el config menciona un webhook n8n en
host.docker.internal:5678, pero n8n quedó ABANDONADO; la ingesta real es por los
scripts Python locales.) Confirmar al usuario que se leyeron y procesaron.

## 4. Definición de Estilo
Preguntar: "¿Deseas aplicar un manual de marca, estilo o colores corporativos
específicos, o prefieres que analice y replique el estilo de la base de datos?".
Esperar respuesta.

## 5. Análisis y Ejecución
Buscar en Qdrant (busqueda_hibrida.py / skill qdrant-direct-search) para extraer:
- Los requerimientos recién guardados.
- La guía de colores/branding de la empresa (colección colores_referencia).
- Los manuales previos (docs_referencia) para clonar estructura, tono y estilo.
Con ese contexto unificado, redactar o editar la documentación. Tomar capturas de
pantalla reales de la app y de cada funcionalidad (skill capturas-documentacion)
y colocarlas junto al paso que explican, con descripciones sencillas.

## 6. Guardado Estratégico
Si es nueva, crear el documento; si existe, editarlo. Si el usuario NO especificó
ruta exacta, guardar obligatoriamente en /opt/data/documentacion_creada/.

## 7. Entrega y Guardado Asistido
Informar que el archivo se creó y quedó en /opt/data/documentacion_creada/
(persiste en Windows en la carpeta oculta .hermes\documentacion_creada).
Entregar un comando PowerShell NO destructivo para copiarlo a una ruta CONCRETA
que el usuario indique (exigir ruta específica; nada de "donde sea"). El comando:
crea la carpeta destino si no existe, copia recursivo con imágenes/subcarpetas,
DENTRO de una subcarpeta nueva y propia, SIN -Force y SIN sobrescribir; si la
subcarpeta ya existe, DETENERSE y avisar del conflicto. Explicar en lenguaje
sencillo: cómo abrir PowerShell, para qué sirve y qué hace cada parte. Después,
dejar ABIERTA (sin exigir respuesta inmediata) la pregunta de si desea subir la
documentación a un repositorio externo (GitLab/GitHub/Azure DevOps) o moverla a
la base de conocimiento, pidiéndole que revise primero y responda cuando haya
revisado. No presionar por la subida hasta que el usuario lo confirme.
