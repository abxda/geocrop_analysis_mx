# **GeoCrop Analysis MX**

This project provides a complete and modular pipeline for crop classification using satellite imagery accessed through open **STAC/COG** cloud catalogs (no Google Earth Engine required). Optical time series come from **HLS** (Harmonized Landsat Sentinel-2) and radar from **Sentinel-1 RTC** (radiometrically terrain-corrected gamma-0); composites (geometric medians) are computed locally with a portable pure-NumPy implementation. It is designed to be configurable, extensible, and easy to use for different regions and time periods.

> **First time here?** Follow the end-to-end walk-through in [TUTORIAL.md](TUTORIAL.md) (or [TUTORIAL.es.md](TUTORIAL.es.md) in Spanish). It reproduces the bundled offline Yaqui Valley exercise from scratch in about 15 minutes.
>
> **Bringing your own region?** See [NEW_AOI.md](NEW_AOI.md) / [NEW_AOI.es.md](NEW_AOI.es.md) — a didactic, step-by-step guide for classifying a new Area of Interest, with quality recommendations for AOI and training labels.
>
> **Prefer Jupyter?** [`validacion_geocrop.ipynb`](validacion_geocrop.ipynb) runs the same end-to-end validation — environment check, a live STAC/COG download demo, and every pipeline phase through the final crop map — as a notebook. Open it from the repository root (same folder as `check_env.py`) so its relative paths resolve. For the in-browser (JupyterLite/Pyodide) version, see [`wasm/geocrop_wasm_demo.ipynb`](wasm/geocrop_wasm_demo.ipynb).

## **Installation**

All dependencies install from **plain pip** (every binary dependency ships pre-built wheels on PyPI for Linux, macOS and Windows) — **no conda required**.

1. **Install Python 3.10+** (3.11 recommended) from [python.org](https://www.python.org/downloads/) or your system package manager.  
2. **Clone the Project**: git clone https://github.com/abxda/geocrop_analysis_mx  
3. **Create Project Directories**: Outside the project folder, create the data and outputs directories. Your folder structure should look like this:  
  \- /path/to/your/projects/  
     |- geocrop\_analysis\_mx/  \<-- The cloned repository  
     |- data/                 \<-- Empty folder  
     |- outputs/              \<-- Empty folder

4. **Create a virtual environment and install** (from inside the geocrop\_analysis\_mx folder):  
   `python -m venv .venv`  
   `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)  
   `pip install -r requirements.txt`

5. **Activate the environment** every time you want to use the project: `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`).

6. **Validate the Environment**: Before proceeding, run this script to ensure all critical libraries are installed and accessible.  
   python check\_env.py

   *You should see \[SUCCESS\] messages for all libraries. If not, please review the installation steps.*  
8. **(Optional) NASA Earthdata token for the complete HLS archive**: the pipeline downloads imagery from open STAC/COG catalogs and needs **no account by default** (Microsoft Planetary Computer, anonymous access). However, MPC's HLS mirror has gaps (little/no Sentinel-2 HLS before ~2020 in some regions). For the authoritative, complete HLS archive, create a free account at [urs.earthdata.nasa.gov](https://urs.earthdata.nasa.gov), generate a token (Profile → Generate Token), and export it before running:
   `export EARTHDATA_TOKEN=<your token>` (Windows: `set EARTHDATA_TOKEN=...`).
   With the token set (or `hls_provider: "nasa"` in the config), HLS is fetched from NASA LPCLOUD; without it the pipeline falls back to Planetary Computer. Sentinel-1 RTC radar always comes from Planetary Computer (anonymous).
   *Step-by-step manual (Spanish, PDF):* [`docs/manual_tokens_gratuitos.pdf`](docs/manual_tokens_gratuitos.pdf).

## **Tutorial: Running the Test Case (Step-by-Step)**

This tutorial will guide you through running the included test case, phase by phase. This is the best way to understand the pipeline and verify that your installation is correct.

**Prerequisite**: Ensure your virtual environment is activated (`source .venv/bin/activate`).

### **Step 0: Prepare Test Data**

This command copies the example files into the correct data/ directory and prepares the pre-processed mosaics to run the tutorial without needing to download imagery. **It only needs to be run once.**

python src/main.py \--config config.test.yaml \--phase setup\_test

### **Step 1: Segment the Image**

This phase takes the main composite image and divides it into thousands of small, homogeneous polygons (segments).

python src/main.py \--config config.test.yaml \--phase segment

### **Step 2: Label the Segments**

This phase assigns a crop label to each segment based on the provided ground-truth data.

python src/main.py \--config config.test.yaml \--phase label

### **Step 3: Extract Features**

This is an essential step. It calculates all the statistical features (spectral, texture, etc.) for each segment from all the satellite images and saves the result to a CSV file.

python src/main.py \--config config.test.yaml \--phase extract

### **Step 4: Train the Classification Model**

With the features already extracted, this command uses the labeled data to train a machine learning model using TPOT, which automatically searches for the best pipeline. The trained model is saved as a .pkl file.

python src/main.py \--config config.test.yaml \--phase train

### **Step 5: Generate Predictions and the Final Map**

This phase uses the model trained in the previous step to predict the crop type for **all** segments (even those without an initial label). The final result is a GeoPackage (.gpkg) file containing the crop classification map.

python src/main.py \--config config.test.yaml \--phase predict

### **Step 6: Verify the Results**

After a successful run, the main products ready for analysis are:

* **Trained Model**: outputs/aoi\_yaqui\_test/modeling/tpot\_model\_test.pkl  
* **Classification Report**: outputs/aoi\_yaqui\_test/modeling/classification\_report.txt  
* **Final Crop Map**: outputs/aoi\_yaqui\_test/modeling/predicted\_map\_test.gpkg

You can open the .gpkg file in GIS software like QGIS to visualize the crop classification map.

## **Advanced Usage**

* **Full Run (full\_run):** To execute all steps (from download to prediction) at once. *Note: downloads imagery from the open STAC catalogs (internet connection required; EARTHDATA\_TOKEN recommended for the complete HLS archive).*  
  \# This will download real data and may take some time  
  python src/main.py \--config config.test.yaml \--phase full\_run

* **View Configuration (show\_config):** To quickly view the active settings from a configuration file.  
  python src/main.py \--config config.test.yaml \--phase show\_config

* **Using Your Own Data:** Prepare your own data (AOI, labels) and a custom configuration file (config.my\_region.yaml), then run the pipeline.  
  python src/main.py \--config config.my\_region.yaml \--phase full\_run

## **Optional: Google Earth Engine backend**

The default download backend (`"stac"`) needs **no account** and computes the composites locally. If you already have a Google Earth Engine account, you can offload the compositing to Google's servers — less local CPU time — by opting in:

1. `pip install earthengine-api` and run `earthengine authenticate` once.
2. In your config file set:
   ```yaml
   download_backend: "gee"
   ```

Output files, names and grid are identical either way, so every later phase is unaffected. If GEE is selected but not installed or not authenticated, the pipeline stops with step-by-step instructions instead of a traceback. **GEE is strictly optional — it is not part of `requirements.txt` and nothing else depends on it.**

## **Optional: external raster layers as extra features**

Rasters you already have (a DEM, slope, precipitation, temperature, land-use maps, …) can join the classification as additional per-segment features **without touching any code**. Declare them in your config:

```yaml
extra_layers:
  - path: "../data/my_aoi/dem.tif"
    prefix: "dem_"          # -> features dem_mean, dem_stdev, dem_min, ...
  - path: "../data/my_aoi/precipitacion.tif"
    prefix: "lluvia_"
```

During the `extract` phase each layer is validated with plain-language messages (missing file, no CRS, no overlap with the AOI, …) and reprojected automatically when its CRS differs from the pipeline grid — the original file is never modified. Multiband rasters produce one feature set per band (`clima_b1_mean`, `clima_b2_mean`, …). Remember to use the **same layers** when predicting a new year with a model trained with them.

## **Running in the Browser (WebAssembly)**

The time-series generation core (STAC search → windowed COG reads → geomedian composites → Shepherd segmentation) also runs **entirely inside a web browser** via [Pyodide](https://pyodide.org) — no server, no installation. See [`wasm/geocrop_wasm_demo.ipynb`](wasm/geocrop_wasm_demo.ipynb): open it in a Pyodide-backed JupyterLite (for example the one from [portable-satelital](https://github.com/abxda/portable-satelital)) or run it unchanged in regular Jupyter.

How it works in WASM:

* GDAL's network layer (`/vsicurl`) does not exist in the browser, so `src/data_download/cog_fetch.py` replays odc-stac's windowed reads with **HTTP Range requests + [tifffile](https://pypi.org/project/tifffile/)** (including a pure-NumPy decoder for TIFF's floating-point predictor, normally a C extension). A ~1.9 GB Sentinel-1 RTC scene costs only a few MB per AOI.
* Optical data comes from **Earth Search Sentinel-2 L2A** (`hls_provider: "earthsearch"`), the optical source whose storage sends CORS headers; radar keeps using **Planetary Computer Sentinel-1 RTC** (CORS-enabled). The HLS blobs (NASA and MPC) do not allow browser requests, so true HLS remains CPython-only.
* Segmentation uses [shepherd-wasm](https://github.com/abxda/shepherd-wasm), the pure NumPy/SciPy port of pyshepseg (bit-exact, numba-free) — the same library the regular pipeline now uses.
* The ML phases (TPOT) are not WASM-compatible; in the browser use scikit-learn directly.

## **Prediction for a New Year**

The pipeline includes a powerful "prediction mode" to use an already trained model to classify a completely new year.

### **How it Works**

When you run the pipeline with the \--prediction-year flag, it automatically:

* Creates a new subdirectory for the results (e.g., outputs/aoi\_yaqui\_test/prediction\_2019/).  
* Shifts the study\_period to the new year, keeping the same months and days.  
* Skips the label and train phases.  
* Uses the **original trained model** for the final prediction.

### **Running the Prediction for a New Year**

You can run the prediction workflow step-by-step or all at once.

**Step-by-Step Execution (e.g., for the year 2019):**

\# 1\. Segment the new year's image (assuming data is already downloaded)  
python src/main.py \--config config.test.yaml \--phase segment \--prediction-year 2019

\# 2\. Extract features for the new year  
python src/main.py \--config config.test.yaml \--phase extract \--prediction-year 2019

\# 3\. Predict and generate the final map using the original model  
python src/main.py \--config config.test.yaml \--phase predict \--prediction-year 2019

**Full Prediction Run:**

To execute all prediction steps at once (download, segmentation, extraction, and prediction), use the predict\_full\_run phase:

python src/main.py \--config config.test.yaml \--phase predict\_full\_run \--prediction-year 2019

The final map will be saved as a GeoPackage file in the outputs/aoi\_yaqui\_test/prediction\_2019/modeling/ directory.
