# Classifying a New Area of Interest

This guide takes you from "I have a new region I want to map" to "I have a GeoPackage with predicted crop classes" — step by step, explaining **what** to prepare, **why** it matters, and **how** to inspect each result before moving on.

> Spanish version: [NEW_AOI.es.md](NEW_AOI.es.md)
> First-time installation: [TUTORIAL.md](TUTORIAL.md)

---

## 0. What you'll build

By the end of this guide you will have:

1. A trained crop-classification model tuned to **your** region and **your** label scheme.
2. A GeoPackage map (`.gpkg`) where every segment of your AOI carries a predicted class and a confidence score.
3. A reusable pipeline you can rerun for **other years** without retraining.

The pipeline does **object-based** classification: it first cuts your image into homogeneous polygons (segments), then assigns one class to each polygon. That makes results easier to inspect and integrate with vector workflows (QGIS, PostGIS, etc.).

---

## 1. Concepts you need to know

Just enough to follow the rest of the guide:

| Term | What it is | Why it matters |
|---|---|---|
| **AOI** (Area of Interest) | A single polygon describing the region you want to classify. | Defines what GEE downloads and where the segmentation runs. |
| **Labels (ground truth)** | A vector of **points**, each tagged with the class observed at that location (field GPS, photo-interpretation, known parcels). Polygons work too but points are the expected input. | Points seed the segments with classes; the segmentation does the work of "expanding" each point into the homogeneous polygon around it. |
| **Segment** | A homogeneous polygon produced by the Shepherd algorithm. | The fundamental unit of classification — every segment gets one class. |
| **Composite** | A single multiband image summarising the study period (geometric median of HLS scenes). | What segmentation runs on; smoother and less cloudy than any individual scene. |
| **Features** | Per-segment statistics (mean/stdev/min/max/count/sum) for every band of every monthly mosaic. | The inputs to the classifier. |
| **Class** | A category in your label scheme (e.g. wheat, corn, no_crop). | What the model predicts. |

---

## 2. Materials checklist

Before touching the pipeline, gather these:

- **A working installation** of GeoCrop Analysis MX. If you haven't done this yet, finish [TUTORIAL.md](TUTORIAL.md) first — the test run will fail-fast if anything is broken.
- **An AOI vector file** (GeoPackage `.gpkg` recommended; Shapefile also works). Single polygon. Any projected or geographic CRS — the pipeline reprojects on the fly, but if you have a choice, give it WGS84 (`EPSG:4326`) because that's what GEE uses.
- **A labels vector file** (GeoPackage strongly preferred). A **point** layer where each point is a ground-truth observation (GPS visit, drone photo, photo-interpretation pin, known parcel centroid) with a categorical attribute holding the class name (e.g. `crop_name = "wheat"`). The bundled Yaqui example uses 1645 points across 6 classes. *(Polygons are accepted too — the pipeline reads any geometry — but points are the canonical, lower-effort input.)*
- **A clear study period** — the months you want to characterise. For an annual crop you typically want the full growing cycle plus a month before and after to capture bare-soil and senescence patterns.
- **A Google Earth Engine account** approved on a Google Cloud project (only if you're downloading new imagery — see §5).
- **Time and disk**: budget ~10–30 minutes of pipeline time per ~1000 km² of AOI, and ~1 GB of disk per year of mosaics.

---

## 3. Prepare your AOI

The AOI is just a boundary, but a few choices here save you pain later:

1. **Keep it tight.** Every extra km² is more GEE bandwidth, more disk, and more segmentation noise. Buffer your real area of interest by 1–2 km if you want context, not more.
2. **Single polygon, single feature.** If you have a multipart or several disjoint polygons, dissolve them first. The pipeline reads `gdf.geometry[0]` — only the first feature is used.
3. **Validate geometry.** In QGIS: *Vector → Geometry Tools → Check Validity*. Fix any self-intersections or null geometries.
4. **Save as GeoPackage**: `File → Save Features As → GeoPackage`. Pick a short, descriptive name with no spaces: `aoi_bajio_2023.gpkg`.

---

## 4. Prepare your training labels (POINTS)

This is the **single most important step**. Garbage labels → garbage map. The pipeline expects a vector of **points**, each one a single ground-truth observation tagged with its class.

### 4.1. Why points?

When the pipeline runs the `label` phase it does this internally:

1. Spatial join: every label point is matched to the segment it falls inside.
2. *Purity filter*: a segment is kept for training only if **all the points inside it agree on one class** (`nunique() == 1`). A segment with 5 *wheat* points is pure → used for training. A segment with 3 *wheat* and 1 *corn* is impure → discarded.
3. Segments with no points inside are not used for training but they **are** classified later in the `predict` phase.

So you don't need to draw precise field boundaries — you mark *where* you know the class and the segmentation does the spatial expansion for you.

### 4.2. How to collect points

Any of these sources works (combine freely):

- **Field GPS visits**: drop a waypoint inside each parcel you visit.
- **Drone or aerial photo interpretation**: drop pins on parcels you can confidently identify.
- **Known parcels from cadastre or contracts**: a single point inside each known parcel is enough.
- **Photo-interpretation in QGIS** over very-high-resolution basemaps (Google Satellite, Bing, ESRI World Imagery).

A point near the **centre of the parcel** is best — points near edges risk landing in a neighbour segment.

### 4.3. Label content

- **Schema**: one attribute column holding the class name. Example field: `klass` or `crop_name`. Keep the values short and consistent — `"wheat"` not `"Wheat / trigo (irrigated)"`.
- **Include a `no_crop` / background class** if you want to differentiate cropped from non-cropped. The test exercise uses `no_crop` to absorb roads, settlements, bare ground, water.

### 4.4. How many points per class?

Aim for **at least 50 points per class**, more for visually similar crops. The pipeline caps each class at `max_samples_per_class` (default 500), so beyond a few hundred per class you stop benefiting.

Reference: the bundled Yaqui example uses **1645 points** (wheat 1028 · corn 258 · chickpea 150 · no_crop 89 · other_crops 81 · walnut 39) → after the purity filter only **681 pure segments** survive for training. Expect ~30–50% attrition from points to pure-segments depending on how clustered your sampling is.

Practical recipe:

| Situation | Suggestion |
|---|---|
| 6 classes, distinct spectra (corn, wheat, alfalfa, fallow, water, urban) | 50–100 points/class. |
| 6 classes, two look almost identical (wheat vs. barley) | 150+ points each for the confusable pair, broaden the study period, or merge them. |
| One rare class with only ~20 known parcels | Either accept weak recall or fuse it into a neighbouring class (e.g. `other_crops`). |

### 4.5. Spatial distribution

Spread your points **across the whole AOI**, not just the easy parts. A model trained only on the southern third generalises poorly to the northern third (different soil, micro-climate, planting dates). Many points in one corner is wasted effort — the purity filter caps each segment's contribution, and the class-balance cap caps each class.

### 4.6. CRS

Use the same CRS as your AOI (ideally WGS84 / `EPSG:4326`). The pipeline reprojects automatically, but matching CRS avoids subtle precision artefacts (a point landing just outside its parcel).

### 4.7. Save it

`labels_bajio_2023.gpkg` as a **Point** layer with one attribute `crop_name` (or whatever you choose — you'll tell the pipeline the name in §6).

---

## 5. Set up Google Earth Engine (skip if you have offline mosaics)

You only need this if you don't already have the satellite mosaics on disk. To download fresh imagery:

1. **Sign up** at https://earthengine.google.com and wait for approval.
2. **Create a Google Cloud project** at https://console.cloud.google.com (any project; just note its ID).
3. **Authenticate locally**:

   ```bash
   conda activate geocrop_analysis_mx
   earthengine authenticate
   ```

   A browser window opens; copy the auth code back into the terminal.

4. **Set application-default credentials and the project**:

   ```bash
   gcloud auth application-default login
   gcloud config set project YOUR_GCP_PROJECT_ID
   ```

5. **Check quotas**: `getDownloadURL` is rate-limited. The pipeline auto-tiles your AOI into pieces ≤ 0.05° to stay under per-request limits, but very large AOIs (>10,000 km²) may need an attended run.

---

## 6. Create your configuration file

Copy `config.yaml` to `config.<your_region>.yaml`. Walk through it section by section.

### 6.1. Place your files in the expected folders

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

The folder name under `data/` **must match the AOI filename without extension** (`aoi_bajio_2023.gpkg` → `aoi_bajio_2023/`). The pipeline derives the output subfolder the same way.

### 6.2. Edit the config

```yaml
data_dir: "../data"
output_dir: "../outputs"

# --- Data sources ---
aoi_file: "aoi_bajio_2023.gpkg"
labels_file: "labels_bajio_2023.gpkg"
labels_field_name: "crop_name"   # the attribute in your labels file

# --- Study period ---
# Cover the full agricultural cycle. For winter wheat in the Bajío, Oct–May.
# For a spring/summer cycle, April–November.
study_period:
  start_date: "2023-04-01"
  end_date: "2023-11-30"

# Composite used for segmentation. Use a tighter window (peak greenness)
# if the full period mixes too many surface states.
segmentation_composite_uses_full_study_period: false
segmentation_composite_custom_range:
  start_date: "2023-06-01"
  end_date: "2023-09-30"

# --- Segmentation ---
segmentation_params:
  num_clusters: 80      # ↑ for finer/more polygons, ↓ for coarser
  min_n_pxls: 100       # minimum pixels per segment
  bands: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]   # keep all 13

# --- Output filenames (give them a region-specific suffix to avoid collisions) ---
output_names:
  segmentation_image: "GM_Seg_Composite_bajio.tif"
  segmented_clumps: "segmented_clumps_bajio.kea"
  segmented_polygons: "segmented_polygons_bajio.shp"
  labeled_polygons: "labeled_polygons_bajio.shp"
  rasterized_labels: "rasterized_labels_bajio.tif"
  features_csv: "features_bajio.csv"      # NOTE: key is features_csv, NOT features_file

# --- Modeling ---
modeling_params:
  test_size: 0.3
  random_state: 42
  balance_classes: true
  max_samples_per_class: 500
  tpot_generations: 5            # ↑ for better models, slower training
  tpot_population_size: 20       # ↑ for broader search
  output_model_name: "tpot_model_bajio.pkl"
  output_prediction_name: "predictions_bajio.csv"
  output_map_name: "predicted_map_bajio.gpkg"
```

> ⚠️ **Common gotcha**: the key in `output_names` must be **`features_csv`**, not `features_file`. The pipeline code reads `config['output_names']['features_csv']`; with `features_file` the `extract` phase crashes with `KeyError`.

### 6.3. How to choose parameters

| Parameter | Effect | Tune up when... | Tune down when... |
|---|---|---|---|
| `num_clusters` | Granularity of segments. | Parcels are small / mixed. | AOI is large and parcels are huge. |
| `min_n_pxls` | Smallest allowed segment. | You want to suppress speckle. | You want to preserve narrow features. |
| `tpot_generations` × `tpot_population_size` | AutoML search budget. | Accuracy is poor. | Training is too slow. |
| `max_samples_per_class` | Class balance cap. | One class dwarfs the others. | You have very few labels in any class. |

---

## 7. Run the pipeline, phase by phase

**Don't run `full_run` the first time.** Run each phase and inspect its output. The pipeline is deliberately resumable: any phase whose output already exists is skipped automatically.

### Phase 1 — Download imagery

```bash
python src/main.py --config config.bajio.yaml --phase download
```

What to inspect: open `outputs/aoi_bajio_2023/segmentation/GM_Seg_Composite_bajio.tif` in QGIS as RGB (R=4, G=3, B=2). It should look like a clean, cloud-minimal composite covering your AOI. If there are large NoData holes, your study period might include a season with no cloud-free overpasses.

### Phase 2 — Segment

```bash
python src/main.py --config config.bajio.yaml --phase segment
```

What to inspect: load `segmented_polygons_bajio.shp` over the composite. Field parcels should mostly map to one segment each. If segments are way too large or too small, adjust `num_clusters` and rerun (you must delete the segmentation output first).

### Phase 3 — Label

```bash
python src/main.py --config config.bajio.yaml --phase label
```

What to inspect: open `labeling/segment_label_map.csv`. Count how many **pure** segments you have per class (this is points-collapsed-to-segments, not raw point counts):

```bash
awk -F, 'NR>1 {print $2}' outputs/aoi_bajio_2023/labeling/segment_label_map.csv | sort | uniq -c
```

If a class has <30 pure segments, you have two possible problems:
- **Too few points**: add more in zones where that class is visible.
- **Mixed points on the same segments**: the purity filter is throwing them out. Re-segment with a higher `num_clusters` (smaller segments) so each parcel has its own segment.

### Phase 4 — Extract

```bash
python src/main.py --config config.bajio.yaml --phase extract
```

What to inspect: `features_bajio.csv` should have one row per segment and ~600–900 columns. Open it in pandas:

```python
import pandas as pd
df = pd.read_csv("../outputs/aoi_bajio_2023/features_bajio.csv")
print(df.shape, df['label'].value_counts())
```

### Phase 5 — Train

```bash
python src/main.py --config config.bajio.yaml --phase train
```

What to inspect: `modeling/classification_report.txt`. Look at per-class **recall** — that tells you how well the model finds each class. Anything below 0.5 means the model struggles with that class; revisit your labels or merge it into a neighbouring class.

### Phase 6 — Predict

```bash
python src/main.py --config config.bajio.yaml --phase predict
```

Open `modeling/predicted_map_bajio.gpkg` in QGIS, style by the `prediction` column. The `probability` column is the model's confidence — symbolise it to highlight low-confidence segments that may need manual review.

---

## 8. Iterate

Object-based classification rewards iteration. If the first map is disappointing:

1. **Look at the confusion**. In the classification report, which two classes get swapped? Are they actually distinguishable from the data you have?
2. **Add labels** in the regions where the model is wrong. New labels in already-easy areas don't help much.
3. **Adjust the study period** to better capture phenology differences. Two crops that look identical in midsummer may be very different at planting or harvest.
4. **Increase the AutoML budget**. Bump `tpot_generations` to 10–20 once you trust your labels.
5. **Re-segment** if parcels are being split or merged badly. Delete the segmentation output before rerunning.

> Remember: each phase **skips itself** if its output exists. To force a rerun, delete the specific output file or the whole phase folder.

---

## 9. Predict another year with the same model

Once you trust your model, predicting a new year is one command:

```bash
python src/main.py --config config.bajio.yaml --phase predict_full_run --prediction-year 2024
```

This downloads 2024 imagery shifted from your original study period, segments and extracts features, then applies your **2023** model. Results go to `outputs/aoi_bajio_2023/prediction_2024/`. No retraining, no new labels.

---

## 10. Common issues

- **`KeyError: 'features_csv'`** during `extract` → check `output_names.features_csv` is spelled exactly this way (not `features_file`).
- **`TypeError: TransformerMixin.__sklearn_tags__()`** during `train` → your scikit-learn is ≥ 1.6. The pinned `environment.yml` should prevent this; if it slipped, run `mamba install -n geocrop_analysis_mx -c conda-forge "scikit-learn=1.5.*"`.
- **A phase silently skipped** → its output file already exists. Delete to force a rerun.
- **`EE Quota exceeded`** → reduce AOI size or split into sub-AOIs and merge predicted maps afterwards.
- **Very low accuracy (<0.5)** → almost always a labels problem: too few points, too unbalanced across classes, or points clustered in one part of the AOI.
- **Many points discarded by the purity filter** → segments are too coarse; raise `num_clusters` so each parcel gets its own segment, and avoid placing points near parcel boundaries.
- **Model confuses two classes constantly** → they probably aren't separable from your data. Either merge them or add a discriminating feature (e.g. extend the study period).

---

## 11. Where to go next

- Re-read your `classification_report.txt` after every iteration; it's the cheapest feedback you have.
- Keep your labels in version control or a clearly-versioned folder — they're more valuable than the trained model itself.
- For very large AOIs, consider splitting into tiles, training per-tile if landscapes differ, and mosaicking results.
