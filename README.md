# GeoCrop Analysis MX

This project provides a complete, modular pipeline for crop classification using satellite imagery from Google Earth Engine. It is designed to be configurable, extensible, and easy to use for different regions and time periods.

## Features

- **Modular Structure**: The code is organized into logical modules for data downloading, processing, and feature extraction.
- **Fully Configurable**: All parameters, paths, and settings are controlled via a central `config.yaml` file. No code changes are needed to run a new analysis.
- **Automated GEE Downloads**: Downloads and preprocesses multispectral (HLS: Landsat/Sentinel-2) and radar (Sentinel-1) data from Google Earth Engine.
- **Advanced Image Processing**: Performs image segmentation using `rsgislib` to create meaningful objects for analysis.
- **Built-in Test Mode**: Includes a sample dataset and a dedicated test configuration to verify the pipeline and demonstrate its functionality.
- **Flexible Execution**: The pipeline can be run end-to-end or in specific phases (`download`, `segment`, `label`, `extract`) for easier debugging and testing.

## Installation

This project relies on a specific set of geospatial libraries. Using **Conda** is required. We recommend **Miniforge** as it is a minimal, conda-forge-first installer that is ideal for scientific packages.

1.  **Install Miniforge**: Download and install the [Miniforge installer](https://github.com/conda-forge/miniforge/releases) for your operating system.

2.  **Open the Miniforge Prompt**: Open the "Miniforge Prompt" (on Windows) or your terminal (on macOS/Linux).

3.  **Clone the Project**: Navigate to your working directory and clone the repository.
    ```bash
    git clone https://github.com/abxda/geocrop_analysis_mx.git
    ```

4.  **Create Project Directories**: Navigate *outside* the `geocrop_analysis_mx` folder and create the `data` and `outputs` directories. The project expects this structure.
    ```bash
    # From your main working directory
    mkdir data
    mkdir outputs
    ```

5.  **Create and Activate Conda Environment**: Navigate into the project folder (`cd geocrop_analysis_mx`) and run the following commands:
    ```bash
    # This creates the environment from the file and may take several minutes
    conda env create -f environment.yml

    # Activate the environment (must be done every time you use the project)
    conda activate geocrop_analysis_mx
    ```

6.  **Authenticate Google Earth Engine**: If this is your first time using GEE, authenticate your machine.
    ```bash
    earthengine authenticate
    ```

## Preparing Your Own Data

To run the pipeline on your own data, place your files in a dedicated folder inside the main `data/` directory (e.g., `data/My_Region/`). Your data must meet the following requirements:

-   **Area of Interest (AOI) File**:
    -   **Format**: GeoPackage (`.gpkg`) or ESRI Shapefile (`.shp`).
    -   **Content**: Must contain a **single polygon** defining the boundary of your study area.
    -   **CRS**: Must be in a geographic coordinate system, preferably `EPSG:4326` (WGS 84).

-   **Labels File**:
    -   **Format**: GeoPackage (`.gpkg`) or ESRI Shapefile (`.shp`).
    -   **Content**: Must contain points or polygons representing ground truth samples.
    -   **CRS**: Must match the CRS of your AOI file.
    -   **Required Field**: Must contain a column with the class names (e.g., "wheat", "corn"). You will specify the name of this column in the `config.yaml` file.

## Configuration (`config.yaml`)

This is the main control file for the pipeline. To run your own analysis, create a copy (e.g., `config.my_region.yaml`) and edit it:

-   `aoi_name`: The name of your AOI. **Must match the folder name** you created in `data/`.
-   `aoi_file`: The filename of your AOI boundary file (e.g., `my_region_boundary.gpkg`).
-   `labels_file`: The filename of your ground truth labels file.
-   `labels_field_name`: The **exact name** of the column in your labels file that contains the crop names.
-   `study_period`: Set the `start_date` and `end_date` for your analysis. The pipeline will automatically generate monthly composites for this period.
-   `segmentation_composite_*`: Configure the date range for the main image used for segmentation. It can use the full study period or a custom range.
-   `segmentation_params`: Fine-tune the `rsgislib` segmentation algorithm.

## Usage

Ensure your Conda environment is activated and you are in the `geocrop_analysis_mx` directory.

### 1. Running the Included Test Case

To verify your installation and see how the pipeline works, you can use the included test data.

-   **Step 1: Set up the test data.** This command copies the sample files to the `data/` directory.
    ```bash
    python src/main.py --phase setup_test
    ```

-   **Step 2: Run the pipeline with the test configuration.** This runs the full process on the small test dataset.
    ```bash
    python src/main.py --config config.test.yaml --phase full_run
    ```

### 2. Running on Your Own Data

-   **Step 1**: Prepare your data and place it in the `data/` directory as described above.
-   **Step 2**: Create and configure your custom config file (e.g., `config.my_region.yaml`).
-   **Step 3**: Run the pipeline, pointing to your new configuration file.
    ```bash
    python src/main.py --config config.my_region.yaml
    ```

### 3. Running Individual Phases

You can run a single part of the pipeline using the `--phase` argument. This is useful for debugging or re-running a failed step. Remember to include your `--config` file if you are not using the default.

```bash
# Only run the data download phase for the test case
python src/main.py --config config.test.yaml --phase download

# Only run the segmentation phase for the test case
python src/main.py --config config.test.yaml --phase segment
```
