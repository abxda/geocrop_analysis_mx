# Tutorial Paso a Paso: Replicar la Ejecución de Prueba del Valle del Yaqui

Esta guía te lleva por una corrida completa del pipeline GeoCrop Analysis usando los **datos de prueba offline incluidos** en el repositorio (no necesitas credenciales de Google Earth Engine). Al terminar tendrás un modelo de clasificación de cultivos entrenado y un mapa final en GeoPackage para el Valle del Yaqui.

> English version: [TUTORIAL.md](TUTORIAL.md)

---

## 0. Requisitos

- Una computadora con al menos **8 GB de RAM** y **10 GB libres en disco**.
- **Miniforge** (recomendado) o Miniconda instalado. Descárgalo desde la [página de releases de Miniforge](https://github.com/conda-forge/miniforge/releases).
- **Git** instalado.
- Linux, macOS o Windows (en Windows usa la "Miniforge Prompt").

**No** necesitas cuenta de Google Earth Engine para este tutorial — todos los mosaicos satelitales vienen empaquetados en `test_data/preprocessed_mosaics/`.

---

## 1. Clonar el repositorio

Abre la Miniforge Prompt (Windows) o tu terminal (Linux/macOS) y coloca el proyecto dentro de una carpeta padre:

```bash
mkdir geocrop_workspace
cd geocrop_workspace
git clone https://github.com/abxda/geocrop_analysis_mx.git
```

Después de clonar deberías ver:

```
geocrop_workspace/
└── geocrop_analysis_mx/
```

## 2. Crear las carpetas hermanas `data/` y `outputs/`

El pipeline espera dos carpetas vacías **al mismo nivel** del repo clonado, no dentro de él:

```bash
mkdir data
mkdir outputs
```

Tu árbol debe verse así:

```
geocrop_workspace/
├── geocrop_analysis_mx/
├── data/        <-- vacía
└── outputs/     <-- vacía
```

## 3. Crear el entorno conda

Desde dentro de la carpeta del proyecto:

```bash
cd geocrop_analysis_mx
```

Recomendamos **mamba** porque resuelve dependencias mucho más rápido (5-15 min vs. 30+ con conda puro):

```bash
conda install -n base -c conda-forge mamba -y
mamba env create -f environment.yml
```

Si prefieres conda puro:

```bash
conda env create -f environment.yml
```

El archivo `environment.yml` ya fija `scikit-learn<1.6` para que `tpot==0.12.2` funcione sin parches.

## 4. Activar el entorno

Hay que hacerlo cada vez que abras una terminal nueva:

```bash
conda activate geocrop_analysis_mx
```

## 5. Validar el entorno

Ejecuta el script de validación incluido. **Las ocho líneas deben decir `[SUCCESS]`** antes de continuar:

```bash
python check_env.py
```

Salida esperada:

```
--- Running Environment Validation Check ---
[SUCCESS] GDAL library found and is importable.
[SUCCESS] GeoPandas library found and is importable.
[SUCCESS] Rasterio library found and is importable.
[SUCCESS] Earth Engine API library found and is importable.
[SUCCESS] PyShepSeg library found and is importable.
[SUCCESS] ExactExtract library found and is importable.
[SUCCESS] Scikit-Image library found and is importable.
[SUCCESS] Scikit-Learn library found and is importable.

--- Validation Summary ---
All critical libraries are installed correctly. Your environment is ready!
```

Si alguna librería falla, borra el entorno (`conda env remove -n geocrop_analysis_mx`) y vuelve a ejecutar `mamba env create -f environment.yml`.

---

## 6. Ejecutar el pipeline — fase por fase

Ejecutamos cada una de las seis fases por separado para que puedas verificar las salidas intermedias.

### Fase 1 — `setup_test`

Copia el AOI, las etiquetas de verdad-en-terreno y los mosaicos preprocesados a las carpetas `data/` y `outputs/`.

```bash
python src/main.py --config config.test.yaml --phase setup_test
```

Salida esperada (resumida):

```
[...] --- Geocrop Analysis Pipeline Initializing --- Config: config.test.yaml, Phase: setup_test ---
[...] Setting up test environment...
[...] Copying aoi_yaqui_test.gpkg to ../data/aoi_yaqui_test/aoi_yaqui_test.gpkg
[...] Copying crop_labels_yaqui_test.gpkg to ../data/aoi_yaqui_test/labels/crop_labels_yaqui_test.gpkg
[...] - Found pre-processed mosaics. Copying to output directory to enable offline run...
[...] Test data setup complete.
```

Después, `../outputs/aoi_yaqui_test/` contendrá `segmentation/`, `multispectral/`, `radar/` y `prediction_2019/`.

### Fase 2 — `segment`

Aplica segmentación de Shepherd al composite multitemporal (con `pyshepseg`). Toma ≈10 segundos.

```bash
python src/main.py --config config.test.yaml --phase segment
```

Salida esperada:

```
--- Starting Image Segmentation (using pyshepseg) ---
- Reading composite image: GM_Seg_Composite_Test.tif
- Running Shepherd segmentation with pyshepseg...
- Converting segmentation array from uint32 to int32 for polygonizing.
- Saving segmentation raster to: segmented_clumps_test.tif
- Polygonizing raster to vector: segmented_polygons_test.shp
- Segmentation and polygonizing complete.
PHASE 'Segment' complete. Duration: ~6 seconds.
```

Archivos generados en `../outputs/aoi_yaqui_test/segmentation/`:
- `segmented_clumps_test.tif`
- `segmented_polygons_test.shp` (+ `.dbf`, `.shx`, `.prj`)

### Fase 3 — `label`

Cruza los polígonos de verdad-en-terreno contra la segmentación y conserva solo los segmentos que caen completamente dentro de una sola clase (filtro de pureza).

```bash
python src/main.py --config config.test.yaml --phase label
```

Salida esperada:

```
--- Starting Label Mapping (Purity Filter) ---
- Loading segments and ground truth labels for purity analysis.
- Performing spatial join...
- Found 681 purely labeled segments.
- Adding numeric class IDs for traceability.
- Saving segment-to-label map to: segment_label_map.csv
- Label mapping phase complete.
```

Archivo generado: `../outputs/aoi_yaqui_test/labeling/segment_label_map.csv` (~681 filas).

### Fase 4 — `extract`

Calcula estadísticas por segmento (mean/stdev/min/max/count/sum) para todas las bandas del composite mediano-geométrico, ocho mosaicos multiespectrales mensuales y ocho mosaicos de radar mensuales. Toma ≈1 minuto.

```bash
python src/main.py --config config.test.yaml --phase extract
```

Salida esperada:

```
--- Starting Feature Extraction (Surgical Post-processing) ---
- Loading ALL segments from: segmented_polygons_test.shp
- Extracting stats from GM_Seg_Composite_Test.tif...
- Extracting stats from multispectral_2017-10.tif...
- Extracting stats from radar_2017-10.tif...
[...repite para 2017-11 a 2018-05...]
- Post-processing and structuring data for final CSV...
- Merging labels with features...
- Saving final, structured features to features_test.csv
- Feature extraction complete.
PHASE 'Extract Features' complete. Duration: ~60 seconds.
```

Archivo generado: `../outputs/aoi_yaqui_test/features_test.csv` (~846 columnas de features).

### Fase 5 — `train`

Corre TPOT (AutoML por programación genética) para encontrar el mejor pipeline de clasificación. Con los valores por defecto de `config.test.yaml` (5 generaciones × 20 de población = 120 pipelines), tarda ≈30-60 s.

```bash
python src/main.py --config config.test.yaml --phase train
```

Salida esperada:

```
[...] --- Executing PHASE: Train Model ---
[...] Loading features from ../outputs/aoi_yaqui_test/features_test.csv
[...] Loading label map from ../outputs/aoi_yaqui_test/labeling/segment_label_map.csv
[...] Preparing data for training...
[...] Balancing classes to a max of 500 samples per class.
[...] Data balanced. New size: 681 rows.
[...] Training data shape: (476, 846)
[...] Testing data shape: (205, 846)
[...] Starting TPOT training...
Optimization Progress: 100%|██████████| 120/120 [...]
Generation 5 - Current best internal CV score: ~0.86
Best pipeline: LogisticRegression(MinMaxScaler(MaxAbsScaler(input_matrix)), C=10.0, dual=False, penalty=l2)
[...] Classification Report:
              precision    recall  f1-score   support
           1       0.92      0.92      0.92       102
           2       0.86      0.77      0.81        31
           3       0.93      0.93      0.93        27
           4       0.78      0.84      0.81        25
           5       0.69      0.69      0.69        13
           6       0.75      0.86      0.80         7
    accuracy                           0.87       205
```

> Nota: TPOT explora pipelines de forma estocástica con semilla fija, pero pequeñas variaciones entre versiones de BLAS / SO pueden cambiar el pipeline final. Espera una exactitud global entre 0.83 y 0.88.

Archivos generados en `../outputs/aoi_yaqui_test/modeling/`:
- `tpot_model_test.pkl` (pipeline entrenado)
- `classification_report.txt`

### Fase 6 — `predict`

Aplica el modelo entrenado a **todos** los segmentos (etiquetados y sin etiqueta) y escribe el mapa final en GeoPackage.

```bash
python src/main.py --config config.test.yaml --phase predict
```

Salida esperada:

```
--- Executing PHASE: Predict and Generate Map ---
Loading model from .../tpot_model_test.pkl
Loading full feature set from .../features_test.csv
Generating predictions for all segments...
Prediction complete.
Saving prediction data to .../predictions_test.csv
Generating final map by joining predictions with polygons...
Saving final predicted map to .../predicted_map_test.gpkg
PHASE 'Predict and Generate Map' complete. Duration: <1 second.
```

Archivos finales en `../outputs/aoi_yaqui_test/modeling/`:
- `predicted_map_test.gpkg` (≈6 MB) — ábrelo en QGIS para visualizarlo.
- `predictions_test.csv` — segment_id, class_id predicho, probabilidad.

---

## 7. Verificar el éxito

Debes tener estos tres productos:

| Archivo | Propósito |
|---|---|
| `outputs/aoi_yaqui_test/modeling/tpot_model_test.pkl` | Clasificador entrenado |
| `outputs/aoi_yaqui_test/modeling/classification_report.txt` | Precision/recall por clase |
| `outputs/aoi_yaqui_test/modeling/predicted_map_test.gpkg` | Mapa final de cultivos |

Abre `predicted_map_test.gpkg` en QGIS, dale estilo por la columna `prediction` y deberías ver un mapa coherente del Valle del Yaqui con clases como trigo, maíz, etc.

---

## 8. Ejecutar todo de una vez (opcional)

Una vez que la corrida paso-a-paso funcione, puedes repetir el pipeline completo con un solo comando, borrando primero los outputs:

```bash
rm -rf ../outputs/aoi_yaqui_test
python src/main.py --config config.test.yaml --phase setup_test
python src/main.py --config config.test.yaml --phase full_run
```

`full_run` encadena `download → segment → label → extract → train → predict`. Con `setup_test` ya hecho y los mosaicos offline presentes, la fase `download` se salta la descarga de GEE automáticamente.

---

## 9. Siguientes pasos

- **Predecir un año nuevo** con el mismo modelo: revisa la sección *Prediction for a New Year* en el [README.md](README.md). Los mosaicos preprocesados de 2019 para el AOI del Yaqui están en `test_data/preprocessed_mosaics/prediction_2019/`.
- **Usar tu propio AOI**: crea `config.mi_region.yaml` siguiendo la estructura de `config.yaml`, coloca tus GeoPackages de AOI y etiquetas en `../data/<nombre_aoi>/`, autentícate con Google Earth Engine (`earthengine authenticate`) y corre `python src/main.py --config config.mi_region.yaml --phase full_run`.

---

## Solución de problemas

- **`TypeError: TransformerMixin.__sklearn_tags__() missing 1 required positional argument: 'self'`** durante `train` → tu scikit-learn es ≥1.6. El pin del `environment.yml` lo previene; si aun así ocurre, ejecuta `mamba install -n geocrop_analysis_mx -c conda-forge "scikit-learn=1.5.*"`.
- **`gdal_merge.py` no encontrado** durante `download` (Windows) → asegúrate de que el entorno está activado; `gdal_merge.py` vive en `<env>/Scripts/` en Windows y se invoca automáticamente.
- **Una fase se salta silenciosamente** → revisa `outputs/aoi_yaqui_test/`; cada fase se salta a sí misma si su archivo de salida ya existe. Borra ese archivo para forzar la re-ejecución.
