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

(For a detailed guide, please refer to the previous instructions on setting up Miniforge, Conda, and authenticating with GEE.)

1.  **Activate Environment**: `conda activate geocrop_analysis_mx`
2.  **Validate Environment**: `python check_env.py`

## How to Run the Pipeline

### Using the Included Test Case (Step-by-Step)

This is the recommended workflow for first-time users to understand the pipeline and verify the installation.

```bash
# Step 0: Prepare test data (only needs to be run once)
python src/main.py --config config.test.yaml --phase setup_test

# Step 1: Download all required imagery for the test period
python src/main.py --config config.test.yaml --phase download

# Step 2: Segment the main composite image into polygons
python src/main.py --config config.test.yaml --phase segment

# Step 3: Label the segments using ground truth data
python src/main.py --config config.test.yaml --phase label

# Step 4: Calculate all features and export to CSV
python src/main.py --config config.test.yaml --phase extract
```

After a successful run, you should find the key output files in your `outputs/aoi_yaqui_test/` directory, such as `features_test.csv`.

### Advanced Workflows & Usage

-   **End-to-End Run (`full_run`):** To execute all steps at once, use the `full_run` phase. The script will automatically skip any stages where the output files already exist.
    ```bash
    python src/main.py --config config.test.yaml --phase full_run
    ```

-   **Viewing Configuration (`show_config`):** To quickly view the active settings from a configuration file without opening it, use this phase.
    ```bash
    # Show settings from the test config
    python src/main.py --config config.test.yaml --phase show_config
    ```

-   **Using Your Own Data:** Prepare your data and a custom configuration file, then run the pipeline.
    ```bash
    python src/main.py --config config.my_region.yaml
    ```