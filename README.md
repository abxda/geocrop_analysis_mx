# GeoCrop Analysis MX

This project provides a complete, modular pipeline for crop classification using satellite imagery from Google Earth Engine. It is designed to be configurable, extensible, and easy to use for different regions and time periods.

## Features

- **Modular Structure**: The code is organized into logical modules for data downloading, processing, and feature extraction.
- **Fully Configurable**: All parameters, paths, and settings are controlled via a central `config.yaml` file.
- **Dynamic Naming**: Output folders are automatically named based on the input AOI file, creating a clear link between inputs and results.
- **Automated GEE Downloads**: Downloads and preprocesses multispectral (HLS: Landsat/Sentinel-2) and radar (Sentinel-1) data.
- **Intelligent Caching**: Automatically detects and uses existing data, skipping completed steps to save time on subsequent runs.
- **Built-in Test Mode**: Includes a sample dataset and a dedicated test configuration to verify the pipeline.
- **Flexible Execution**: The pipeline can be run end-to-end or in specific phases for easier debugging and testing.

## Installation

Using **Conda** is required. We recommend **Miniforge** as it is a minimal, conda-forge-first installer that is ideal for scientific packages.

1.  **Install Miniforge**: Download and install from the [Miniforge GitHub releases page](https://github.com/conda-forge/miniforge/releases).
2.  **Open the Miniforge Prompt**: Open the "Miniforge Prompt" (Windows) or your terminal (macOS/Linux).
3.  **Clone the Project**: `git clone https://github.com/abxda/geocrop_analysis_mx.git`
4.  **Create Project Directories**: Outside the project folder, create the `data` and `outputs` directories.
5.  **Install Mamba & Create Environment**: Mamba is a much faster, parallel re-implementation of conda. We highly recommend using it for a faster setup. Navigate into the `geocrop_analysis_mx` folder and run:
    ```bash
    # First, install mamba into your base conda environment
    conda install mamba -n base -c conda-forge

    # Now, use mamba to create the project environment (this will be much faster)
    mamba env create -f environment.yml
    ```
    *(If you prefer not to use Mamba, the original `conda env create -f environment.yml` command will also work, but may take significantly longer.)*

6.  **Activate the Environment**: This command remains the same.
    ```bash
    conda activate geocrop_analysis_mx
    ```

7.  **Validate the Environment**: Before running the main pipeline, verify that all critical libraries were installed correctly.
    ```bash
    python check_env.py
    ```
    *You should see `[SUCCESS]` messages for all libraries. If you see any `[FAILURE]` messages, your environment may not have been created correctly.*

8.  **Authenticate Google Earth Engine**: Run `earthengine authenticate` if it's your first time.

## Preparing Your Own Data

To run the pipeline on your data, create a folder inside `data/`. The folder name **must match the name of your AOI file without the extension** (e.g., `data/my_region/` for `my_region.shp`).

-   **Area of Interest (AOI) File**: `data/<your_aoi_name>/<your_aoi_name>.gpkg` (or `.shp`). Must contain a **single polygon** in `EPSG:4326`.
-   **Labels File**: `data/<your_aoi_name>/labels/<your_labels_file>.gpkg` (or `.shp`). Must contain points/polygons with a class name column. The CRS must match the AOI.

## Configuration (`config.yaml`)

This is the main control file. Copy it to `config.custom.yaml` and edit it for your project. Key fields:

-   `aoi_file`: Filename of your AOI. Determines the name of your data and results folders.
-   `labels_file`: Filename of your ground truth labels.
-   `labels_field_name`: The **exact column name** in your labels file that contains the crop names.
-   `study_period`: Set the `start_date` and `end_date` for your analysis. The pipeline automatically generates monthly composites for this period.

## How to Run the Pipeline

### Using the Included Test Case

This is the best way to start, to ensure your environment is working correctly.

-   **Step 1: Set up the test data.** This command reads `config.test.yaml` to identify the test files and copies them into the `data/` directory.
    ```bash
    python src/main.py --config config.test.yaml --phase setup_test
    ```

-   **Step 2: Run the test pipeline.** This executes the full workflow on the sample data.
    ```bash
    python src/main.py --config config.test.yaml --phase full_run
    ```

-   **Step 3: Verify the results.** After a successful run, you should find the following key files in your `outputs/aoi_yaqui_test/` directory:
    -   `segmentation/GM_Seg_Composite_Test.tif`: The main composite image used for segmentation.
    -   `segmentation/segmented_polygons_test.shp`: The vector file of the generated segments.
    -   `labeling/rasterized_labels_test.tif`: The rasterized ground truth labels.
    -   `features_test.csv`: The final output file with all calculated features for each segment, ready for analysis or machine learning.

### Execution Workflows

The pipeline is designed for flexibility. You can run it end-to-end, step-by-step, or on pre-existing data.

-   **End-to-End Run (`full_run`):** Runs all necessary steps from start to finish, automatically skipping completed stages.
-   **Step-by-Step (`--phase download`, `--phase segment`, etc.):** Gives you full control to run each phase individually and inspect the outputs. See the `main.py` file for all phase options.
-   **Hybrid Execution:** You can place your own processed files (e.g., downloaded images) in the correct `outputs/` subfolder. The pipeline will detect them and continue from the next required step.