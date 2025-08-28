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

## Installation (Definitive Guide)

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
    conda activate geocrop_analysis_mx
    ```
7.  **Validate the Environment**: Before proceeding, run this script to ensure all critical libraries are installed and accessible.
    ```bash
    python check_env.py
    ```
    *You should see `[SUCCESS]` messages for all libraries. If not, please review the installation steps.*

8.  **Authenticate Google Earth Engine**: Run `earthengine authenticate` if it's your first time.

## How to Run the Pipeline

(Instructions for running the test case and custom workflows remain the same as in the previous version of this README.)
