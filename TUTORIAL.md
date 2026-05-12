# Step-by-Step Tutorial: Replicating the Yaqui Valley Test Run

This tutorial walks you through a complete, end-to-end run of the GeoCrop Analysis pipeline using the **bundled offline test data** (no Google Earth Engine credentials required). At the end you will have a trained crop-classification model and a final GeoPackage map for the Yaqui Valley.

> Spanish version: [TUTORIAL.es.md](TUTORIAL.es.md)

---

## 0. Prerequisites

- A computer with at least **8 GB RAM** and **10 GB free disk**.
- **Miniforge** (recommended) or Miniconda installed. Download from the [Miniforge releases page](https://github.com/conda-forge/miniforge/releases).
- **Git** installed.
- Linux, macOS, or Windows (use the Miniforge Prompt on Windows).

You do **not** need a Google Earth Engine account to run this tutorial — all satellite mosaics are bundled in `test_data/preprocessed_mosaics/`.

---

## 1. Clone the repository

Open the Miniforge Prompt (Windows) or a regular terminal (Linux/macOS) and place the project inside a parent folder of your choice:

```bash
mkdir geocrop_workspace
cd geocrop_workspace
git clone https://github.com/abxda/geocrop_analysis_mx.git
```

After cloning you should see:

```
geocrop_workspace/
└── geocrop_analysis_mx/
```

## 2. Create the sibling `data/` and `outputs/` folders

The pipeline expects two empty folders **next to** the cloned repo, not inside it:

```bash
mkdir data
mkdir outputs
```

Your tree must look like this:

```
geocrop_workspace/
├── geocrop_analysis_mx/
├── data/        <-- empty
└── outputs/     <-- empty
```

## 3. Create the conda environment

From inside the project folder:

```bash
cd geocrop_analysis_mx
```

We recommend **mamba** for a faster solve (5-15 minutes vs. 30+ for plain conda):

```bash
conda install -n base -c conda-forge mamba -y
mamba env create -f environment.yml
```

If you prefer plain conda, the equivalent is:

```bash
conda env create -f environment.yml
```

The `environment.yml` pins `scikit-learn<1.6` so that `tpot==0.12.2` works out of the box.

## 4. Activate the environment

You must do this every time you open a new terminal:

```bash
conda activate geocrop_analysis_mx
```

## 5. Validate the environment

Run the bundled check script. **All eight checks must read `[SUCCESS]`** before continuing:

```bash
python check_env.py
```

Expected output:

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

If any library fails, re-run `mamba env create -f environment.yml` after deleting the broken environment (`conda env remove -n geocrop_analysis_mx`).

---

## 6. Run the pipeline — phase by phase

We run each of the six phases separately so you can verify intermediate outputs.

### Phase 1 — `setup_test`

Copies the included AOI, ground-truth labels, and preprocessed mosaics into the `data/` and `outputs/` folders.

```bash
python src/main.py --config config.test.yaml --phase setup_test
```

Expected (abridged):

```
[...] --- Geocrop Analysis Pipeline Initializing --- Config: config.test.yaml, Phase: setup_test ---
[...] Setting up test environment...
[...] Copying aoi_yaqui_test.gpkg to ../data/aoi_yaqui_test/aoi_yaqui_test.gpkg
[...] Copying crop_labels_yaqui_test.gpkg to ../data/aoi_yaqui_test/labels/crop_labels_yaqui_test.gpkg
[...] - Found pre-processed mosaics. Copying to output directory to enable offline run...
[...] Test data setup complete.
```

After this, `../outputs/aoi_yaqui_test/` will contain `segmentation/`, `multispectral/`, `radar/`, and `prediction_2019/`.

### Phase 2 — `segment`

Performs Shepherd image segmentation on the multitemporal composite (uses `pyshepseg`). Expect ≈10 seconds.

```bash
python src/main.py --config config.test.yaml --phase segment
```

Expected:

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

Outputs in `../outputs/aoi_yaqui_test/segmentation/`:
- `segmented_clumps_test.tif`
- `segmented_polygons_test.shp` (+ `.dbf`, `.shx`, `.prj`)

### Phase 3 — `label`

Joins the ground-truth polygons against the segmentation and keeps only segments that fall entirely inside a single class (purity filter).

```bash
python src/main.py --config config.test.yaml --phase label
```

Expected:

```
--- Starting Label Mapping (Purity Filter) ---
- Loading segments and ground truth labels for purity analysis.
- Performing spatial join...
- Found 681 purely labeled segments.
- Adding numeric class IDs for traceability.
- Saving segment-to-label map to: segment_label_map.csv
- Label mapping phase complete.
```

Output: `../outputs/aoi_yaqui_test/labeling/segment_label_map.csv` (~681 rows).

### Phase 4 — `extract`

Computes per-segment statistics (mean/stdev/min/max/count/sum) for all bands across the geometric-median composite, eight monthly multispectral mosaics, and eight monthly radar mosaics. Expect ≈1 minute.

```bash
python src/main.py --config config.test.yaml --phase extract
```

Expected:

```
--- Starting Feature Extraction (Surgical Post-processing) ---
- Loading ALL segments from: segmented_polygons_test.shp
- Extracting stats from GM_Seg_Composite_Test.tif...
- Extracting stats from multispectral_2017-10.tif...
- Extracting stats from radar_2017-10.tif...
[...repeats for 2017-11 through 2018-05...]
- Post-processing and structuring data for final CSV...
- Merging labels with features...
- Saving final, structured features to features_test.csv
- Feature extraction complete.
PHASE 'Extract Features' complete. Duration: ~60 seconds.
```

Output: `../outputs/aoi_yaqui_test/features_test.csv` (~846 feature columns).

### Phase 5 — `train`

Runs TPOT (genetic-programming AutoML) to find a classifier pipeline. With the defaults from `config.test.yaml` (5 generations × population 20 = 120 pipelines), this takes ≈30-60 seconds.

```bash
python src/main.py --config config.test.yaml --phase train
```

Expected:

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

> Note: TPOT explores pipelines stochastically with a fixed seed, but tiny variations across BLAS / OS versions can shift the final pipeline. Expect overall accuracy in the 0.83-0.88 range.

Outputs in `../outputs/aoi_yaqui_test/modeling/`:
- `tpot_model_test.pkl` (trained pipeline)
- `classification_report.txt`

### Phase 6 — `predict`

Applies the trained model to **all** segments (labelled + unlabelled) and writes the final GeoPackage map.

```bash
python src/main.py --config config.test.yaml --phase predict
```

Expected:

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

Final outputs in `../outputs/aoi_yaqui_test/modeling/`:
- `predicted_map_test.gpkg` (≈6 MB) — open in QGIS to visualise.
- `predictions_test.csv` — segment_id, predicted class_id, probability.

---

## 7. Verify success

You should now have these three artefacts:

| File | Purpose |
|---|---|
| `outputs/aoi_yaqui_test/modeling/tpot_model_test.pkl` | Trained classifier |
| `outputs/aoi_yaqui_test/modeling/classification_report.txt` | Per-class precision/recall |
| `outputs/aoi_yaqui_test/modeling/predicted_map_test.gpkg` | Final crop map |

Open `predicted_map_test.gpkg` in QGIS, style by the `prediction` column, and you should see a coherent map of the Yaqui Valley with classes such as wheat, corn, etc.

---

## 8. Running everything at once (optional)

Once the step-by-step run succeeds, you can replay the whole pipeline in a single command by first removing the outputs:

```bash
rm -rf ../outputs/aoi_yaqui_test
python src/main.py --config config.test.yaml --phase setup_test
python src/main.py --config config.test.yaml --phase full_run
```

`full_run` chains `download → segment → label → extract → train → predict`. With `setup_test` already done and offline mosaics present, the `download` phase will skip GEE downloads automatically.

---

## 9. Next steps

- **Predict a new year** with the same model: see the *Prediction for a New Year* section of [README.md](README.md). Preprocessed 2019 mosaics for the Yaqui AOI are bundled under `test_data/preprocessed_mosaics/prediction_2019/`.
- **Use your own AOI**: create `config.my_region.yaml` mirroring `config.yaml`, place your AOI + label GeoPackages in `../data/<aoi_name>/`, authenticate Google Earth Engine (`earthengine authenticate`), and run `python src/main.py --config config.my_region.yaml --phase full_run`.

---

## Troubleshooting

- **`TypeError: TransformerMixin.__sklearn_tags__() missing 1 required positional argument: 'self'`** during `train` → your scikit-learn is ≥1.6. The pinned `environment.yml` should prevent this; if it still happens, run `mamba install -n geocrop_analysis_mx -c conda-forge "scikit-learn=1.5.*"`.
- **`gdal_merge.py` not found** during `download` (Windows) → ensure the environment is activated; `gdal_merge.py` lives in `<env>/Scripts/` on Windows and is invoked automatically.
- **Phase silently skips** → check the `outputs/aoi_yaqui_test/` folder; each phase skips itself if its output file already exists. Delete the offending file to force a rerun.
