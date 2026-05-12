# Clasificar una Nueva Área de Interés

Esta guía te lleva de "tengo una nueva región que quiero mapear" a "tengo un GeoPackage con clases predichas" — paso a paso, explicando **qué** preparar, **por qué** importa y **cómo** revisar cada resultado antes de avanzar.

> English version: [NEW_AOI.md](NEW_AOI.md)
> Instalación inicial: [TUTORIAL.es.md](TUTORIAL.es.md)

---

## 0. Qué vas a construir

Al final de esta guía vas a tener:

1. Un modelo de clasificación de cultivos entrenado para **tu** región y **tu** esquema de clases.
2. Un mapa en GeoPackage (`.gpkg`) donde cada segmento del AOI lleva una clase predicha y una puntuación de confianza.
3. Un pipeline reutilizable que puedes correr de nuevo para **otros años** sin tener que reentrenar.

El pipeline hace clasificación **orientada a objetos**: primero corta la imagen en polígonos homogéneos (segmentos) y luego le asigna una sola clase a cada polígono. Eso hace que los resultados sean más fáciles de revisar e integrar con flujos de trabajo vectoriales (QGIS, PostGIS, etc.).

---

## 1. Conceptos que conviene tener claros

Lo justo para seguir la guía:

| Término | Qué es | Por qué importa |
|---|---|---|
| **AOI** (Área de Interés) | Un único polígono que describe la región a clasificar. | Define qué descarga GEE y dónde se hace la segmentación. |
| **Etiquetas (verdad-en-terreno)** | Un vector de **puntos**, cada uno marcado con la clase observada en ese sitio (GPS de campo, foto-interpretación, parcelas conocidas). Polígonos también funcionan pero los puntos son el insumo esperado. | Los puntos siembran a los segmentos con clases; la segmentación se encarga de "expandir" cada punto al polígono homogéneo que lo rodea. |
| **Segmento** | Un polígono homogéneo producido por el algoritmo Shepherd. | Es la unidad básica de clasificación — a cada segmento se le asigna una clase. |
| **Composite** | Una imagen multibanda que resume el período de estudio (mediana geométrica de las escenas HLS). | Es sobre la que corre la segmentación; más limpia y menos nublada que cualquier escena individual. |
| **Features** | Estadísticas por segmento (mean/stdev/min/max/count/sum) de todas las bandas de todos los mosaicos mensuales. | Son la entrada al clasificador. |
| **Clase** | Una categoría de tu esquema (p.ej. trigo, maíz, no_crop). | Lo que el modelo predice. |

---

## 2. Checklist de materiales

Antes de tocar el pipeline, reúne esto:

- **Una instalación funcional** de GeoCrop Analysis MX. Si aún no la tienes, termina primero [TUTORIAL.es.md](TUTORIAL.es.md) — la corrida de prueba fallará rápido si algo está roto.
- **Un archivo vectorial de AOI** (GeoPackage `.gpkg` recomendado; Shapefile también funciona). Un solo polígono. Cualquier CRS proyectado o geográfico — el pipeline reproyecta al vuelo, pero si tienes opción, usa WGS84 (`EPSG:4326`) porque es lo que usa GEE.
- **Un archivo vectorial de etiquetas** (preferentemente GeoPackage). Una capa de **puntos** donde cada punto es una observación de verdad-en-terreno (visita con GPS, foto de dron, pin de foto-interpretación, centroide de parcela conocida) con un atributo categórico con el nombre de la clase (p.ej. `crop_name = "wheat"`). El ejemplo del Yaqui usa 1645 puntos en 6 clases. *(El pipeline también acepta polígonos — la geometría es flexible — pero los puntos son el insumo canónico y de menor esfuerzo.)*
- **Un período de estudio claro** — los meses que quieres caracterizar. Para un cultivo anual normalmente quieres el ciclo completo más un mes antes y otro después, para capturar suelo desnudo y senescencia.
- **Una cuenta de Google Earth Engine** aprobada y asociada a un proyecto de Google Cloud (sólo si vas a descargar imágenes nuevas — ver §5).
- **Tiempo y disco**: presupuesta ~10–30 minutos de pipeline por cada ~1000 km² de AOI, y ~1 GB de disco por año de mosaicos.

---

## 3. Preparar tu AOI

El AOI sólo define el contorno, pero unas cuantas decisiones aquí te ahorran dolor después:

1. **Mantenlo apretado.** Cada km² extra es más ancho de banda de GEE, más disco y más ruido en la segmentación. Si quieres contexto, deja un buffer de 1–2 km, no más.
2. **Un solo polígono, una sola feature.** Si tienes multipart o varios polígonos disjuntos, dissuélvelos primero. El pipeline lee `gdf.geometry[0]` — sólo usa el primero.
3. **Valida la geometría.** En QGIS: *Vectorial → Herramientas de geometría → Comprobar validez*. Arregla auto-intersecciones o geometrías nulas.
4. **Guárdalo como GeoPackage**: `Archivo → Guardar features como → GeoPackage`. Usa un nombre corto y descriptivo sin espacios: `aoi_bajio_2023.gpkg`.

---

## 4. Preparar tus etiquetas de entrenamiento (PUNTOS)

Este es el **paso más importante** de todos. Etiquetas malas → mapa malo. El pipeline espera un vector de **puntos**, cada uno una observación de verdad-en-terreno con su clase.

### 4.1. ¿Por qué puntos?

Cuando el pipeline corre la fase `label` hace esto internamente:

1. Spatial join: cada punto se cruza con el segmento que lo contiene.
2. *Filtro de pureza*: un segmento se conserva para entrenamiento sólo si **todos los puntos dentro de él están de acuerdo en una sola clase** (`nunique() == 1`). Un segmento con 5 puntos de *wheat* es puro → se usa para entrenar. Un segmento con 3 de *wheat* y 1 de *corn* es impuro → se descarta.
3. Los segmentos sin puntos dentro **no** se usan para entrenamiento, pero **sí** se clasifican después en la fase `predict`.

O sea: no necesitas dibujar polígonos precisos de cada parcela — marcas *dónde* sabes la clase y la segmentación hace la expansión espacial por ti.

### 4.2. Cómo recolectar los puntos

Cualquiera de estas fuentes funciona (puedes mezclarlas):

- **Visitas con GPS de campo**: pones un waypoint dentro de cada parcela que recorres.
- **Foto-interpretación con dron o imagen aérea**: pones pines en parcelas que reconoces con confianza.
- **Parcelas conocidas de catastro o contratos**: un solo punto dentro de cada parcela basta.
- **Foto-interpretación en QGIS** sobre basemaps de muy alta resolución (Google Satellite, Bing, ESRI World Imagery).

Lo ideal: el punto cerca del **centro de la parcela** — puntos cerca de los bordes corren el riesgo de caer en un segmento vecino.

### 4.3. Contenido

- **Esquema**: una columna de atributo con el nombre de la clase. Ejemplo de campo: `klass` o `crop_name`. Mantén los valores cortos y consistentes — `"wheat"` en vez de `"Wheat / trigo (riego)"`.
- **Incluye una clase `no_crop` / fondo** si quieres distinguir lo que es cultivo de lo que no. El ejercicio de prueba usa `no_crop` para absorber caminos, asentamientos, suelo desnudo, agua.

### 4.4. ¿Cuántos puntos por clase?

Apunta a **al menos 50 puntos por clase**, más para cultivos visualmente parecidos. El pipeline acota cada clase a `max_samples_per_class` (default 500), así que más allá de unos cientos por clase deja de aportar.

Referencia: el ejemplo del Yaqui usa **1645 puntos** (wheat 1028 · corn 258 · chickpea 150 · no_crop 89 · other_crops 81 · walnut 39) → después del filtro de pureza sobreviven solo **681 segmentos puros** para entrenar. Espera una atrición del 30–50% de puntos a segmentos puros, dependiendo de qué tan agrupado fue tu muestreo.

Receta práctica:

| Situación | Sugerencia |
|---|---|
| 6 clases con espectros distintos (maíz, trigo, alfalfa, barbecho, agua, urbano) | 50–100 puntos/clase. |
| 6 clases con dos muy parecidas (trigo vs. cebada) | 150+ puntos para el par confuso, ampliar el período de estudio, o considerar fusionarlas. |
| Una clase rara con sólo ~20 parcelas conocidas | O aceptas recall bajo o la fundes en una clase vecina (p.ej. `other_crops`). |

### 4.5. Distribución espacial

Reparte los puntos **por todo el AOI**, no sólo en las zonas fáciles. Un modelo entrenado sólo en el tercio sur del AOI generaliza mal al tercio norte (otro suelo, otro microclima, otras fechas de siembra). Muchos puntos en una esquina son esfuerzo perdido — el filtro de pureza acota la contribución de cada segmento y el balance de clases acota la de cada clase.

### 4.6. CRS

Usa el mismo CRS que el AOI (idealmente WGS84 / `EPSG:4326`). El pipeline reproyecta automáticamente, pero alinear los CRS evita artefactos sutiles de precisión (un punto que cae justo fuera de su parcela).

### 4.7. Guarda el archivo

`labels_bajio_2023.gpkg` como capa de **Puntos** con un atributo `crop_name` (o el nombre que prefieras — se lo dirás al pipeline en §6).

---

## 5. Configurar Google Earth Engine (omite si ya tienes mosaicos offline)

Sólo necesitas esto si no tienes ya los mosaicos en disco. Para descargar imágenes frescas:

1. **Regístrate** en https://earthengine.google.com y espera la aprobación.
2. **Crea un proyecto de Google Cloud** en https://console.cloud.google.com (cualquier proyecto; anota su ID).
3. **Autentícate localmente**:

   ```bash
   conda activate geocrop_analysis_mx
   earthengine authenticate
   ```

   Se abre una ventana del navegador; copia el código de autenticación de vuelta a la terminal.

4. **Configura credenciales de aplicación y el proyecto**:

   ```bash
   gcloud auth application-default login
   gcloud config set project TU_ID_DE_PROYECTO_GCP
   ```

5. **Revisa cuotas**: `getDownloadURL` tiene rate-limit. El pipeline divide tu AOI en piezas ≤ 0.05° automáticamente, pero un AOI muy grande (>10,000 km²) puede requerir una corrida supervisada.

---

## 6. Crear tu archivo de configuración

Copia `config.yaml` a `config.<tu_region>.yaml`. Repasa sección por sección.

### 6.1. Coloca tus archivos en las carpetas esperadas

```
geocrop_workspace/
├── geocrop_analysis_mx/
├── data/
│   └── aoi_bajio_2023/
│       ├── aoi_bajio_2023.gpkg
│       └── labels/
│           └── labels_bajio_2023.gpkg
└── outputs/
```

El nombre de la carpeta dentro de `data/` **debe coincidir con el nombre del archivo AOI sin extensión** (`aoi_bajio_2023.gpkg` → `aoi_bajio_2023/`). El pipeline deriva la subcarpeta de salida de la misma manera.

### 6.2. Edita el config

```yaml
data_dir: "../data"
output_dir: "../outputs"

# --- Fuentes de datos ---
aoi_file: "aoi_bajio_2023.gpkg"
labels_file: "labels_bajio_2023.gpkg"
labels_field_name: "crop_name"   # el atributo en tu archivo de etiquetas

# --- Período de estudio ---
# Cubre el ciclo agrícola completo. Para trigo de invierno en el Bajío, Oct–May.
# Para ciclo primavera/verano, abril–noviembre.
study_period:
  start_date: "2023-04-01"
  end_date: "2023-11-30"

# Composite usado para segmentación. Usa una ventana más cerrada (pico de
# verdor) si el período completo mezcla demasiados estados de superficie.
segmentation_composite_uses_full_study_period: false
segmentation_composite_custom_range:
  start_date: "2023-06-01"
  end_date: "2023-09-30"

# --- Segmentación ---
segmentation_params:
  num_clusters: 80      # ↑ para más/menores polígonos, ↓ para más gruesos
  min_n_pxls: 100       # mínimo de píxeles por segmento
  bands: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]   # deja las 13

# --- Nombres de archivo (ponle sufijo de región para no chocar con otros) ---
output_names:
  segmentation_image: "GM_Seg_Composite_bajio.tif"
  segmented_clumps: "segmented_clumps_bajio.kea"
  segmented_polygons: "segmented_polygons_bajio.shp"
  labeled_polygons: "labeled_polygons_bajio.shp"
  rasterized_labels: "rasterized_labels_bajio.tif"
  features_csv: "features_bajio.csv"      # OJO: la clave es features_csv, NO features_file

# --- Modelado ---
modeling_params:
  test_size: 0.3
  random_state: 42
  balance_classes: true
  max_samples_per_class: 500
  tpot_generations: 5            # ↑ para modelos mejores, entrenamiento más lento
  tpot_population_size: 20       # ↑ para búsqueda más amplia
  output_model_name: "tpot_model_bajio.pkl"
  output_prediction_name: "predictions_bajio.csv"
  output_map_name: "predicted_map_bajio.gpkg"
```

> ⚠️ **Trampa frecuente**: la clave en `output_names` debe ser **`features_csv`**, no `features_file`. El código del pipeline lee `config['output_names']['features_csv']`; con `features_file` la fase `extract` revienta con `KeyError`.

### 6.3. Cómo escoger los parámetros

| Parámetro | Efecto | Súbelo cuando... | Bájalo cuando... |
|---|---|---|---|
| `num_clusters` | Granularidad de los segmentos. | Las parcelas son chicas o mixtas. | El AOI es grande y las parcelas enormes. |
| `min_n_pxls` | Tamaño mínimo de segmento. | Quieres suprimir ruido fino. | Quieres preservar elementos angostos. |
| `tpot_generations` × `tpot_population_size` | Presupuesto de búsqueda AutoML. | El accuracy es bajo. | El entrenamiento es muy lento. |
| `max_samples_per_class` | Tope para balance de clases. | Una clase domina demasiado. | Tienes muy pocas etiquetas en alguna clase. |

---

## 7. Correr el pipeline, fase por fase

**No corras `full_run` la primera vez.** Ejecuta cada fase y revisa su salida. El pipeline es a propósito reanudable: cualquier fase cuyo archivo de salida ya existe se salta automáticamente.

### Fase 1 — Descarga

```bash
python src/main.py --config config.bajio.yaml --phase download
```

Qué revisar: abre `outputs/aoi_bajio_2023/segmentation/GM_Seg_Composite_bajio.tif` en QGIS como RGB (R=4, G=3, B=2). Debe verse un composite limpio, con mínimas nubes, cubriendo todo tu AOI. Si hay huecos grandes de NoData, tu período de estudio incluye una temporada sin pasadas despejadas.

### Fase 2 — Segmentación

```bash
python src/main.py --config config.bajio.yaml --phase segment
```

Qué revisar: carga `segmented_polygons_bajio.shp` sobre el composite. La mayoría de las parcelas debe quedar como un solo segmento. Si los segmentos son demasiado grandes o chicos, ajusta `num_clusters` y vuelve a correr (tendrás que borrar primero la salida de segmentación).

### Fase 3 — Label

```bash
python src/main.py --config config.bajio.yaml --phase label
```

Qué revisar: abre `labeling/segment_label_map.csv`. Cuenta cuántos segmentos **puros** tienes por clase (esto es puntos-colapsados-a-segmentos, no el conteo crudo de puntos):

```bash
awk -F, 'NR>1 {print $2}' outputs/aoi_bajio_2023/labeling/segment_label_map.csv | sort | uniq -c
```

Si una clase tiene <30 segmentos puros, tienes dos problemas posibles:
- **Pocos puntos**: agrega más en zonas donde esa clase sea visible.
- **Puntos mezclados en los mismos segmentos**: el filtro de pureza los descarta. Re-segmenta con un `num_clusters` mayor (segmentos más chicos) para que cada parcela tenga su propio segmento.

### Fase 4 — Extract

```bash
python src/main.py --config config.bajio.yaml --phase extract
```

Qué revisar: `features_bajio.csv` debe tener una fila por segmento y ~600–900 columnas. Ábrelo con pandas:

```python
import pandas as pd
df = pd.read_csv("../outputs/aoi_bajio_2023/features_bajio.csv")
print(df.shape, df['label'].value_counts())
```

### Fase 5 — Train

```bash
python src/main.py --config config.bajio.yaml --phase train
```

Qué revisar: `modeling/classification_report.txt`. Fíjate sobre todo en el **recall** por clase — te dice qué tan bien el modelo encuentra cada clase. Algo bajo (<0.5) significa que el modelo no la distingue; revisa esas etiquetas o fusiona la clase con una vecina.

### Fase 6 — Predict

```bash
python src/main.py --config config.bajio.yaml --phase predict
```

Abre `modeling/predicted_map_bajio.gpkg` en QGIS, dale estilo por la columna `prediction`. La columna `probability` es la confianza del modelo — simbolízala para resaltar segmentos de baja confianza que conviene revisar manualmente.

---

## 8. Iterar

La clasificación orientada a objetos premia la iteración. Si el primer mapa no convence:

1. **Mira la confusión**. En el reporte, ¿qué dos clases se intercambian? ¿Son realmente distinguibles con los datos que tienes?
2. **Agrega etiquetas** en las zonas donde el modelo falla. Etiquetas nuevas en zonas ya fáciles aportan poco.
3. **Ajusta el período de estudio** para capturar diferencias fenológicas. Dos cultivos idénticos en pleno verano pueden ser muy distintos en siembra o cosecha.
4. **Sube el presupuesto de AutoML**. Aumenta `tpot_generations` a 10–20 una vez que confíes en tus etiquetas.
5. **Re-segmenta** si las parcelas se parten o se fusionan mal. Borra primero la salida de segmentación.

> Recuerda: cada fase **se salta a sí misma** si su salida ya existe. Para forzar re-ejecución, borra el archivo de salida específico o la carpeta de la fase.

---

## 9. Predecir otro año con el mismo modelo

Cuando confíes en tu modelo, predecir un año nuevo es un solo comando:

```bash
python src/main.py --config config.bajio.yaml --phase predict_full_run --prediction-year 2024
```

Descarga imágenes 2024 desplazadas del período original, segmenta y extrae features, luego aplica tu modelo **2023**. Los resultados van a `outputs/aoi_bajio_2023/prediction_2024/`. Sin reentrenamiento, sin etiquetas nuevas.

---

## 10. Problemas frecuentes

- **`KeyError: 'features_csv'`** durante `extract` → revisa que `output_names.features_csv` esté escrito exactamente así (no `features_file`).
- **`TypeError: TransformerMixin.__sklearn_tags__()`** durante `train` → tu scikit-learn es ≥ 1.6. El pin del `environment.yml` lo previene; si se coló, corre `mamba install -n geocrop_analysis_mx -c conda-forge "scikit-learn=1.5.*"`.
- **Una fase se salta sin avisar** → su archivo de salida ya existe. Bórralo para forzar re-ejecución.
- **`EE Quota exceeded`** → reduce el AOI o divídelo en sub-AOIs y mosaiquea los mapas predichos al final.
- **Accuracy muy bajo (<0.5)** → casi siempre es problema de etiquetas: pocos puntos, desbalanceadas entre clases, o puntos agrupados en una sola parte del AOI.
- **Muchos puntos descartados por el filtro de pureza** → los segmentos son demasiado gruesos; sube `num_clusters` para que cada parcela tenga su propio segmento y evita poner puntos cerca de los bordes de la parcela.
- **El modelo confunde dos clases todo el tiempo** → seguramente no son separables con tus datos. Fúndelas o agrega una feature discriminante (p.ej. extiende el período).

---

## 11. Hacia dónde seguir

- Relee tu `classification_report.txt` después de cada iteración; es el feedback más barato que tienes.
- Mantén tus etiquetas bajo control de versiones o en una carpeta con versión clara — valen más que el modelo entrenado.
- Para AOIs muy grandes, considera dividirlos en tiles, entrenar por tile si los paisajes difieren, y mosaiquear los resultados al final.
