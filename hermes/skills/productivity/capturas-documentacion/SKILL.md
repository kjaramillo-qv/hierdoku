---
name: capturas-documentacion
description: Real web app screenshots via Playwright headless.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [documentation, screenshots, playwright, chromium, web]
    related_skills: [knowledge-base-webhook]
---

# Capturas de pantalla para documentación

Toma capturas reales de una aplicación web para ilustrar documentación técnica,
colocándolas junto al paso o funcionalidad que explican. Pensado para el rol de
especialista de documentación dentro de este contenedor.

## Cuándo usar

- Documentas una app web y necesitas imágenes de sus pantallas/funcionalidades.
- Quieres que el lector entienda visualmente de qué trata la app y cómo se usa.

## Entorno (una sola vez por contenedor)

- Chromium headless vía Playwright ya suele estar instalado en:
  `PLAYWRIGHT_BROWSERS_PATH=/opt/data/.cache/ms-playwright`
- La ruta por defecto `/opt/hermes/.playwright` NO tiene permisos de escritura.
- No hay sudo/root: NO usar `--with-deps`. Instalar solo el binario y usar rutas
  bajo `/opt/data`.

Instalación (si falta el navegador), en background porque tarda varios minutos:

```
export PLAYWRIGHT_BROWSERS_PATH=/opt/data/.cache/ms-playwright
mkdir -p "$PLAYWRIGHT_BROWSERS_PATH"
python3 -m playwright install chromium
```

## Procedimiento

1. Define la lista de URLs/pantallas a capturar y una carpeta de salida (dentro
   del proyecto de docs, típicamente un `static/img/` o `_capturas/`).
2. Ejecuta un script Playwright headless que navegue y capture cada pantalla.
   Para pantallas internas detrás de login, primero rellena usuario/contraseña
   (pedir credenciales de prueba al usuario; nunca inventarlas).
3. Verifica cada PNG con `vision_analyze` para confirmar que se ve lo esperado.
4. Inserta las imágenes en el `.md` con el formato que use la empresa
   (p.ej. `![alt](/img/nombre.png)`), justo tras el paso que describen, y añade
   una explicación sencilla.

### Script base

```python
import os
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/opt/data/.cache/ms-playwright"
from playwright.sync_api import sync_playwright

shots = [
    ("http://HOST/ruta", "/ruta/salida/nombre.png"),
]
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    for url, out in shots:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        pg.goto(url, wait_until="networkidle", timeout=30000)
        pg.screenshot(path=out, full_page=True)
        print("SAVED", out, os.path.getsize(out))
    b.close()
```

### Login antes de capturar (cuando aplica)

```python
pg.goto(LOGIN_URL, wait_until="networkidle")
pg.fill("input[name='username']", USER)   # ajustar selector a la app
pg.fill("input[name='password']", PWD)
pg.click("input[type='submit'], button[type='submit']")
pg.wait_for_load_state("networkidle")
```

## Pitfalls

- Si `playwright install` falla con EACCES en `/opt/hermes/.playwright`, es la
  ruta por defecto sin permisos: exporta `PLAYWRIGHT_BROWSERS_PATH` a `/opt/data`.
- `--with-deps` requiere root y fallará (`su: Authentication failure`); no lo uses.
- La descarga del navegador puede superar 5 min: lánzala en background con
  `notify_on_complete=true`.
- Si una app necesita fuentes/librerías del sistema que faltan (requieren root),
  el render puede degradarse; avísalo al usuario.
- Refleja los textos de la UI tal cual aparecen (idioma incluido); si la app está
  en otro idioma, aclara la traducción entre paréntesis.
- Nunca inventes credenciales; pídelas al usuario para las pantallas internas.

## Verification

- Cada PNG existe, pesa > 0 y `vision_analyze` confirma el contenido esperado.
- Las imágenes quedan referenciadas en el `.md` junto al paso correcto.
