---
title: "Manual: Tokens y Cuentas Gratuitas para Descarga de Imágenes"
subtitle: "GeoCrop Analysis MX — Acceso a datos satelitales STAC/COG"
author: "GeoCrop Analysis MX"
date: "Julio 2026"
lang: es
geometry: margin=2.5cm
toc: true
toc-depth: 2
numbersections: true
colorlinks: true
linkcolor: blue
urlcolor: blue
fontsize: 11pt
---

\newpage

# Resumen

El pipeline de **GeoCrop Analysis MX** descarga imágenes satelitales (ópticas HLS y radar
Sentinel-1) desde tres catálogos abiertos en la nube. Este manual explica, catálogo por
catálogo, si necesitas crear una cuenta o generar un token, y los pasos exactos para
hacerlo cuando sí se requiere.

| Catálogo | Datos que provee | ¿Requiere cuenta? | ¿Requiere token? |
|---|---|:---:|:---:|
| **NASA Earthdata (LPCLOUD)** | HLS óptico — archivo completo | Sí (gratis) | Sí (gratis, ver §2) |
| **Microsoft Planetary Computer** | Radar Sentinel-1 RTC; HLS óptico (parcial) | **No** | **No** (automático) |
| **Earth Search (Element 84 / AWS)** | Óptico Sentinel-2 L2A (usado en el navegador/WASM) | **No** | **No** |

**En resumen: de los tres catálogos, solo uno (NASA Earthdata) requiere que tú hagas algo.**
Los otros dos funcionan de inmediato, sin registro, y el pipeline ya está configurado para
usarlos automáticamente. La sección 2 de este manual te guía paso a paso para obtener el
único token que sí necesitas gestionar.

\newpage

# ¿Por qué existen tres catálogos distintos?

El pipeline necesita dos tipos de imagen cada mes del periodo de estudio:

- **Óptico HLS** (Harmonized Landsat Sentinel-2): la fuente autoritativa y completa vive en
  el archivo de la NASA (LPCLOUD). Un espejo parcial —sin cuenta— existe en Microsoft
  Planetary Computer, pero tiene huecos: por ejemplo, en México casi no hay imágenes
  Sentinel-2 (HLS S30) antes de 2020 en ese espejo.
- **Radar Sentinel-1 RTC** (retrodispersión corregida por terreno): solo vive, de forma
  anónima y gratuita, en Microsoft Planetary Computer.

Por eso el archivo de configuración (`config.yaml` o `config.test.yaml`) tiene la opción:

```yaml
hls_provider: "auto"
```

Con `"auto"`, el pipeline decide así:

1. Si detecta la variable de entorno `EARTHDATA_TOKEN` → usa el archivo **completo** de la
   NASA (recomendado).
2. Si no la detecta → usa Planetary Computer (funciona sin hacer nada, pero con huecos en
   fechas antiguas).
3. Si el pipeline corre dentro de un navegador (WebAssembly) → usa Earth Search
   (Sentinel-2 L2A), la única fuente óptica compatible con ese entorno.

El radar **siempre** usa Planetary Computer, sin que tengas que configurar nada.

\newpage

# NASA Earthdata — el único token que debes generar

## ¿Por qué conviene generarlo?

Sin este token, el pipeline sigue funcionando (usa Planetary Computer como respaldo), pero
te perderás observaciones ópticas en algunas fechas — especialmente antes de 2020. Si tu
periodo de estudio incluye años anteriores a 2020, o si notas meses con pocas o ninguna
imagen óptica encontrada, este token resuelve el problema.

## Paso a paso

### Paso 1 — Crear la cuenta (gratis, sin aprobación manual)

1. Abre tu navegador y visita:

   **<https://urs.earthdata.nasa.gov/users/new>**

2. Verás un formulario de registro (*"Earthdata Login — Register"*). Completa:
   - **Username** (nombre de usuario): elige uno que recuerdes; lo usarás para iniciar
     sesión, no para el pipeline.
   - **Password** (contraseña): sigue los requisitos indicados en pantalla.
   - **Email address**: usa un correo al que tengas acceso — la NASA envía un correo de
     verificación.
   - **First Name / Last Name**, **Country**, **Affiliation** (puedes seleccionar
     *"Public"* o *"Other"* si no perteneces a una institución en la lista), **Study Area**
     (por ejemplo, *"Agriculture"* o *"Land Use/Land Cover Change"*).
3. Presiona **"Register for Earthdata Login"**.
4. A diferencia de Google Earth Engine, **no hay lista de espera ni aprobación manual**: la
   cuenta queda activa de inmediato. Solo debes confirmar tu correo si el sistema lo pide.

### Paso 2 — Iniciar sesión

1. Ve a **<https://urs.earthdata.nasa.gov/home>**.
2. Inicia sesión con el usuario y contraseña que acabas de crear.

### Paso 3 — Generar el token

1. Una vez dentro, ve al menú superior y haz clic en tu nombre de usuario (esquina
   superior derecha), o navega directamente a:

   **<https://urs.earthdata.nasa.gov/profile/generate_token>**

2. Verás una página titulada **"Generate Token"** con un botón **"Generate Token"**.
3. Haz clic en **"Generate Token"**. El sistema mostrará un token largo, similar a esto
   (acortado aquí por espacio):

   ```
   eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJ0eXBlIjoiVXNlciIsInVpZCI6...
   ```

4. **Copia el token completo.** Es una sola línea muy larga — asegúrate de copiarla entera,
   sin cortes ni saltos de línea.

   > **Importante:** el token no caduca de inmediato (dura aproximadamente un año), pero
   > **solo se muestra una vez** al generarlo. Si lo pierdes, puedes volver a esta misma
   > página y generar uno nuevo (el anterior deja de funcionar).

### Paso 4 — Configurar el token en tu máquina

Hay dos formas de dárselo al pipeline. **Se recomienda la opción A**: es más simple y evita
que el token quede pegado en el historial de tu terminal o en archivos de configuración de
tu sistema (`.bashrc`, variables de usuario de Windows).

**Opción A (recomendada) — archivo `env` junto al proyecto**

1. En la carpeta raíz del proyecto (junto a `config.yaml`), crea un archivo de texto
   llamado exactamente **`env`** (sin extensión, sin punto al inicio).
2. Escribe dentro una sola línea:

   ```
   EARTHDATA_TOKEN=pega_aqui_tu_token_completo
   ```

3. Guarda el archivo. **No necesitas hacer nada más** — el pipeline lo detecta y lo carga
   automáticamente cada vez que corre, sin que tengas que exportar variables ni reabrir la
   terminal.
4. Este archivo `env` ya está incluido en `.gitignore`: nunca se subirá al repositorio por
   accidente, aunque hagas `git add -A`.

**Opción B — variable de entorno del sistema**

**Linux / macOS** (bash o zsh):

```bash
export EARTHDATA_TOKEN="pega_aqui_tu_token_completo"
```

Para que quede guardado entre sesiones, agrega esa línea al final de tu archivo
`~/.bashrc` (bash) o `~/.zshrc` (zsh), y luego ejecuta `source ~/.bashrc` (o abre una
terminal nueva).

**Windows (PowerShell)**:

```powershell
$Env:EARTHDATA_TOKEN = "pega_aqui_tu_token_completo"
```

Para que sea permanente, usa en su lugar:

```powershell
[System.Environment]::SetEnvironmentVariable(
    "EARTHDATA_TOKEN", "pega_aqui_tu_token_completo", "User")
```

y abre una terminal nueva para que tome efecto.

**Windows (CMD)**:

```cmd
set EARTHDATA_TOKEN=pega_aqui_tu_token_completo
```

### Paso 5 — Verificar que el pipeline lo detecta

Corre el script de validación del entorno:

```bash
python check_env.py
```

Al final del reporte verás una línea con el estado de tu token — por ejemplo:

```
[SUCCESS] EARTHDATA_TOKEN valid until 2026-08-31 (60 days remaining).
```

También puedes ejecutar cualquier fase de descarga; el registro (log) debe indicar que está
usando el proveedor `nasa` en vez del mensaje de aviso sobre Planetary Computer:

```bash
python src/main.py --config config.test.yaml --phase download
```

Si el token **no** está configurado, verás este aviso (no es un error, solo informativo):

```
- No EARTHDATA_TOKEN found: using Planetary Computer HLS (archive has gaps;
  set a free Earthdata token for the complete NASA archive).
```

### Paso 6 — Cómo saber si el token caducó (sin adivinar)

El token es un JWT que trae su propia fecha de vencimiento incrustada. El pipeline la lee
automáticamente — **no necesitas llevar la cuenta tú mismo** — y avisa en dos momentos
distintos, cada vez de forma más clara conforme se acerca la fecha:

- **`check_env.py`** (recomendado correrlo de vez en cuando, por ejemplo antes de una
  campaña de descarga larga): muestra siempre una línea con el estado —
  `[SUCCESS]` si falta más de dos semanas, `[WARNING]` si faltan 14 días o menos, y
  `[FAILURE]` si ya caducó.
- **Durante cualquier descarga real** (`--phase download` o `full_run`): el pipeline es
  silencioso mientras el token esté sano (para no llenar el log de ruido), pero imprime una
  advertencia visible si faltan 14 días o menos, y un aviso inequívoco si ya expiró:

  ```
  [EARTHDATA_TOKEN] EXPIRED on 2026-08-31 — NASA HLS downloads
  will fail with 401 until you generate a new token at
  https://urs.earthdata.nasa.gov/profile/generate_token
  and update EARTHDATA_TOKEN.
  ```

Así, en vez de tener que interpretar un error `401 Unauthorized` genérico en medio de una
descarga, el mensaje te dice exactamente qué pasó y qué hacer.

### Paso 7 — Renovación

El token de Earthdata expira aproximadamente **un año** después de generarse. Cuando
expire, el pipeline recibirá errores de autenticación al leer imágenes de la NASA; repite
el **Paso 3** para generar uno nuevo y actualiza la variable de entorno.

\newpage

# Microsoft Planetary Computer — no requiere ninguna acción

Este catálogo provee el radar Sentinel-1 RTC (siempre) y, como respaldo, el óptico HLS.

**No necesitas crear cuenta ni generar nada.** El pipeline usa la librería oficial
`planetary-computer` (incluida en `requirements.txt`), la cual solicita automáticamente un
token de firma temporal (SAS) de forma anónima cada vez que se necesita leer una imagen.
Microsoft lo explica así en su propia documentación: *"a subscription key is not required
for interacting with the service"* — la firma es solo un mecanismo de auditoría de
solicitudes, no una barrera de acceso.

Si en el futuro quisieras una cuota de solicitudes más alta (solo relevante para uso muy
intensivo), podrías registrarte gratis en <https://planetarycomputer.microsoft.com/> y
obtener una *subscription key* opcional — pero para el uso normal del pipeline (AOIs
municipales o estatales) esto **no es necesario**.

\newpage

# Earth Search (Element 84 / AWS) — no requiere ninguna acción

Este catálogo se usa como fuente óptica cuando el pipeline corre **dentro de un navegador**
(WebAssembly, ver el demo en `wasm/geocrop_wasm_demo.ipynb`), porque es la única fuente
óptica cuyo almacenamiento en la nube permite solicitudes directas desde un navegador
(cabeceras CORS habilitadas).

Provisto por [Element 84](https://element84.com/) sobre el bucket público
`sentinel-cogs` de AWS. Es **100 % anónimo**: no hay registro, no hay token, no hay firma.
El pipeline lo usa automáticamente sin ninguna configuración de tu parte.

\newpage

# Resumen de acciones

| # | Acción | ¿Obligatoria? | Tiempo estimado |
|---|---|:---:|---|
| 1 | Crear cuenta en urs.earthdata.nasa.gov | Recomendada | 3 minutos |
| 2 | Generar token en el perfil de Earthdata | Recomendada | 1 minuto |
| 3 | Exportar `EARTHDATA_TOKEN` en tu sistema | Recomendada | 1 minuto |
| 4 | Cualquier acción en Planetary Computer | No | — |
| 5 | Cualquier acción en Earth Search | No | — |

Si tu periodo de estudio es reciente (2020 en adelante) y no te preocupa perder algunas
observaciones ópticas puntuales, puedes **omitir por completo la sección 2** y correr el
pipeline tal cual — funcionará con Planetary Computer sin ninguna configuración.

\newpage

# Enlaces de referencia

- Registro NASA Earthdata: <https://urs.earthdata.nasa.gov/users/new>
- Generar token NASA Earthdata: <https://urs.earthdata.nasa.gov/profile/generate_token>
- Documentación NASA Earthdata Login: <https://urs.earthdata.nasa.gov/documentation>
- Microsoft Planetary Computer (catálogo): <https://planetarycomputer.microsoft.com/>
- Earth Search STAC API (Element 84): <https://earth-search.aws.element84.com/v1>
- Repositorio del proyecto: <https://github.com/abxda/geocrop_analysis_mx>
