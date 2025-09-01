# GeoCrop Analysis MX

This project provides a complete, modular pipeline for crop classification using satellite imagery from Google Earth Engine. It is designed to be configurable, extensible, and easy to use for different regions and time periods.

## Installation

This project has complex dependencies (`gdal`, `rsgislib`). Following these steps precisely is crucial for ensuring the environment is set up correctly.

1.  **Install Miniforge**: Download and install from the [Miniforge GitHub releases page](https://github.com/conda-forge/miniforge/releases).
2.  **Open the Miniforge Prompt**: Open the "Miniforge Prompt" (Windows) or your terminal (macOS/Linux).
3.  **Clone the Project**: `git clone https://github.com/abxda/geocrop_analysis_mx.git`
4.  **Create Project Directories**: Outside the project folder, create the `data` and `outputs` directories.
5.  **Create the Conda Environment**: Navigate into the `geocrop_analysis_mx` folder. This single command will create the environment and automatically configure the necessary PATH variables for Windows compatibility.
    ```bash
    # We recommend using Mamba for a significantly faster installation
    conda install mamba -n base -c conda-forge
    mamba env create -f environment.yml
    ```
6.  **Activate the Environment**: You must activate the environment every time you want to use the project.
    ```bash
    mamba activate geocrop_analysis_mx
    ```
7.  **Validate the Environment**: Before proceeding, run this script to ensure all critical libraries are installed and accessible.
    ```bash
    python check_env.py
    ```
    *You should see `[SUCCESS]` messages for all libraries. If not, please review the installation steps.*

8.  **Authenticate Google Earth Engine**: Run `earthengine authenticate` if it's your first time.

## Tutorial: Running the Test Case (Step-by-Step)

This tutorial will guide you through running the included test case one phase at a time. This is the best way to understand the pipeline and verify that your installation is correct.

**Prerequisite**: Ensure your Conda environment (`geocrop_analysis_mx`) is activated.

### Step 0: Prepare Test Data

This command copies the sample files into the correct `data/` directory. **It only needs to be run once.**

```bash
python src/main.py --config config.test.yaml --phase setup_test
```

### Step 1: Download Imagery

This phase connects to Google Earth Engine and downloads all the required images (the main composite and monthly composites for the period defined in `config.test.yaml`).

```bash
python src/main.py --config config.test.yaml --phase download
```

### Step 2: Segment the Image

This phase takes the main composite image and divides it into thousands of small, homogenous polygons (segments).

```bash
python src/main.py --config config.test.yaml --phase segment
```

### Step 3: Label the Segments

This phase assigns a crop label to each segment based on the provided ground-truth data and creates a rasterized version of the labels.

```bash
python src/main.py --config config.test.yaml --phase label
```

### Step 4: Extract Features

This is the final processing step. It calculates all the statistical features for each segment from all the downloaded images and saves the result to a CSV file.

```bash
python src/main.py --config config.test.yaml --phase extract
```

### Step 5: Verify the Output

After a successful run, the main output is the final features file, ready for analysis or machine learning:

-   `outputs/aoi_yaqui_test/features_test.csv`

### (Optional) Step 6: Clean Up Temporary Files

Once you have verified that everything works, you can run this command to delete the intermediate tile folders (`*_tiles`) created during the download process.

```bash
python src/main.py --config config.test.yaml --phase cleanup_tiles
```

## Advanced Usage

-   **End-to-End Run (`full_run`):** To execute all steps (Download to Extract) at once, use the `full_run` phase.
    ```bash
    python src/main.py --config config.test.yaml --phase full_run
    ```

-   **Viewing Configuration (`show_config`):** To quickly view the active settings from a configuration file.
    ```bash
    python src/main.py --config config.test.yaml --phase show_config
    ```

-   **Using Your Own Data:** Prepare your data and a custom configuration file (`config.my_region.yaml`), then run the pipeline.
    ```bash
    python src/main.py --config config.my_region.yaml
    ```
