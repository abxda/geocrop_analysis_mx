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

7.  **Authenticate Google Earth Engine**: Run `earthengine authenticate` if it's your first time.

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

## Execution Workflows

The pipeline is designed for flexibility. You can run it end-to-end, step-by-step, or on pre-existing data.

### 1. End-to-End Run (Piloto Automático)

This is the most common use case. It runs all necessary steps from start to finish, automatically skipping completed stages.

```bash
# Example for the test case
python src/main.py --config config.test.yaml --phase full_run
```

### 2. Step-by-Step Execution

This gives you full control to inspect the outputs of each phase.

```bash
# Step 1: Download all data
python src/main.py --config config.test.yaml --phase download

# Step 2: After inspecting, run segmentation
python src/main.py --config config.test.yaml --phase segment

# ...and so on for 'label' and 'extract'
```

### 3. Hybrid Execution (Using Pre-existing Data)

You can place your own previously downloaded or processed files in the correct `outputs/<your_aoi_name>/` subfolder. When you run a later phase, the script will detect these files and use them as input.

### Included Test Case

-   **Step 1: Set up the test data.** This command copies the sample files into `data/aoi_yaqui_test/`.
    ```bash
    python src/main.py --phase setup_test
    ```

-   **Step 2: Run the test pipeline.**
    ```bash
    python src/main.py --config config.test.yaml
    ```