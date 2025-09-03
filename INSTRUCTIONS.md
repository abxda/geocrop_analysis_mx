# Guía de Uso Exhaustiva: GeoCrop Analysis Pipeline

Este documento proporciona una guía completa para instalar, configurar y ejecutar el pipeline de análisis de cultivos.

## 1. Instalación y Configuración Inicial

Sigue estos pasos para preparar tu entorno de trabajo en un sistema nuevo (probado en Linux/Ubuntu).

### 1.1. Clonar el Repositorio
```bash
git clone https://github.com/abxda/geocrop_analysis_mx.git
cd geocrop_analysis_mx
```

### 1.2. Configurar el Entorno de Conda
Este proyecto depende de librerías geoespaciales complejas. Usar Conda es esencial. El archivo `environment.yml` contiene todas las dependencias con las versiones correctas.

```bash
# Se recomienda usar Mamba para una instalación significativamente más rápida
conda install mamba -n base -c conda-forge

# Usa Mamba (o Conda) para crear el entorno desde el archivo
mamba env create -f environment.yml
```

### 1.3. Activar el Entorno
Cada vez que vayas a usar el pipeline, debes activar el entorno:
```bash
conda activate geocrop_analysis_mx
```

### 1.4. Autenticación con Google Earth Engine (Opcional)
Si no vas a usar los datos de prueba offline, necesitarás acceso a Google Earth Engine para descargar las imágenes.

```bash
earthengine authenticate
```
Sigue las instrucciones en tu navegador. Es posible que también necesites configurar un proyecto de facturación con `gcloud`:
```bash
gcloud auth application-default login
gcloud config set project TU_PROYECTO_DE_GCP
```

## 2. Estructura de Carpetas
El pipeline espera una estructura de carpetas específica. Desde la raíz del proyecto (`geocrop_analysis_mx`), estas carpetas deben existir al mismo nivel:
```
../
├── geocrop_analysis_mx/  <-- Tu proyecto
├── data/                   <-- Aquí van tus datos de entrada (AOI, etiquetas)
└── outputs/                <-- Aquí se guardarán todos los resultados
```
Crea las carpetas `data` y `outputs` si no existen.

## 3. Flujo de Trabajo Principal (Modo Online)
Este es el flujo de trabajo estándar, que procesa los datos desde la descarga en GEE hasta la predicción final.

### 3.1. Configuración
Edita el archivo `config.yaml` para definir tu área de interés, fechas de estudio y otros parámetros.

### 3.2. Ejecución Paso a Paso
Puedes ejecutar cada fase del pipeline de forma individual:
```bash
# Descarga de imágenes
python src/main.py --config config.yaml --phase download

# Segmentación de la imagen principal
python src/main.py --config config.yaml --phase segment

# Generación del mapa de etiquetas (para entrenamiento)
python src/main.py --config config.yaml --phase label

# Extracción de características de todas las imágenes
python src/main.py --config config.yaml --phase extract

# Entrenamiento del modelo
python src/main.py --config config.yaml --phase train

# Predicción y generación del mapa final
python src/main.py --config config.yaml --phase predict
```

### 3.3. Ejecución Completa
Para ejecutar todas las fases anteriores en secuencia:
```bash
python src/main.py --config config.yaml --phase full_run
```

## 4. Flujo de Trabajo Offline (Para Pruebas)
Esta es una nueva funcionalidad que te permite correr el pipeline sin necesidad de GEE, usando un set de imágenes pre-procesadas y comprimidas.

### 4.1. (Opcional) Generar los Archivos Comprimidos
Si quieres generar o actualizar los archivos comprimidos a partir de una ejecución online, usa la fase `compress_mosaics`. Esta fase busca todos los mosaicos en tu carpeta de `outputs` (incluyendo los de los años de predicción) y los guarda en una carpeta `mosaics_compressed`.
```bash
python src/main.py --config config.yaml --phase compress_mosaics
```

### 4.2. Organizar los Archivos de Prueba
El repositorio incluye un script para organizar los mosaicos comprimidos en la estructura que la fase de `setup_test` espera.
```bash
# 1. Dar permisos de ejecución (solo la primera vez)
chmod +x organize_mosaics.sh

# 2. Ejecutar el script
./organize_mosaics.sh
```
Esto poblará la carpeta `test_data/preprocessed_mosaics/`.

### 4.3. Ejecutar el Pipeline en Modo Offline
Ahora, al ejecutar la fase `setup_test`, el pipeline se volverá "offline".
```bash
# 1. Copia todos los datos de prueba (AOI, etiquetas y mosaicos) a las carpetas 'data' y 'outputs'
python src/main.py --config config.test.yaml --phase setup_test

# 2. Ejecuta el pipeline. Notarás que la fase 'download' se salta la descarga.
python src/main.py --config config.test.yaml --phase full_run
```

## 5. Predicción de un Año Nuevo
Esta funcionalidad te permite usar un modelo ya entrenado para predecir sobre un año completamente nuevo.

### 5.1. Configuración
Añade o modifica la clave `prediction_year` en tu archivo `config.yaml` o `config.test.yaml`.
```yaml
prediction_year: 2019
```

### 5.2. Ejecución
Puedes ejecutar el flujo de predicción paso a paso o de forma completa. **Importante:** Usa siempre el argumento `--prediction-year`.

**Paso a Paso:**
```bash
# Descarga, segmenta y extrae features para el nuevo año
python src/main.py --config config.yaml --phase download --prediction-year 2019
python src/main.py --config config.yaml --phase segment --prediction-year 2019
python src/main.py --config config.yaml --phase extract --prediction-year 2019

# Usa el modelo original para predecir sobre los datos del nuevo año
python src/main.py --config config.yaml --phase predict --prediction-year 2019
```

**Ejecución Completa:**
Usa la fase `predict_full_run` para ejecutar los 4 pasos anteriores de una sola vez.
```bash
python src/main.py --config config.yaml --phase predict_full_run --prediction-year 2019
```
Los resultados se guardarán en un subdirectorio separado, ej. `outputs/aoi_yaqui_test/prediction_2019/`.
