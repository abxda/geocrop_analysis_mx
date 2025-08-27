# GeoCrop Analysis MX

This project provides a complete pipeline for crop classification using multispectral (Landsat, Sentinel-2) and radar (Sentinel-1) satellite imagery from Google Earth Engine. It is designed to be modular, configurable, and extensible.

## Workflow Overview

The pipeline executes the following major steps:

1.  **Download**: Downloads all required satellite imagery (monthly composites and a main segmentation composite) from Google Earth Engine.
2.  **Segment**: Divides the main composite image into meaningful segments (polygons) using the Shepherd segmentation algorithm.
3.  **Label**: Assigns a class to each segment based on your ground-truth data and populates the necessary attribute tables.
4.  **Extract**: For every segment, it calculates a rich set of statistical features from all the downloaded images and exports the final dataset to a CSV file, ready for machine learning.

## Project Structure

The project uses a clean directory structure that separates source code from data and outputs.

```
working_directory/
├── geocrop_analysis_mx/  <-- Project folder (This is the Git repository)
│   ├── src/                # All Python source code
│   ├── environment.yml     # Conda environment definition
│   ├── config.yaml         # Pipeline configuration file
│   └── README.md           # This file
│
├── data/                   <-- Input data (Place this folder next to the project folder)
│
└── outputs/                <-- Generated results (Place this folder next to the project folder)
```

## Installation (Step-by-Step)

This project relies on a specific set of geospatial libraries. Using Conda is **required**. We recommend **Miniforge** as it is a minimal, conda-forge-first installer that works very well for scientific packages.

**1. Install Miniforge**

-   Go to the [Miniforge GitHub releases page](https://github.com/conda-forge/miniforge/releases).
-   Download the installer appropriate for your operating system (e.g., `Miniforge3-Windows-x86_64.exe`).
-   Run the installer. It is recommended to accept the defaults and allow the installer to add Conda to your PATH if prompted.

**2. Open the Miniforge Prompt**

-   After installation, open the "Miniforge Prompt" from your Start Menu (on Windows) or your terminal (on macOS/Linux).

**3. Clone the Project**

-   Navigate to your desired working directory and clone this repository.
    ```bash
    git clone <repository_url>
    ```

**4. Create Project Directories**

-   Navigate *outside* the `geocrop_analysis_mx` folder and create the `data` and `outputs` directories.
    ```bash
    # From your working_directory
    mkdir data
    mkdir outputs
    ```
-   Place your AOI data (e.g., the `AOI_Chihuahua_2023` folder) inside the `data` directory.

**5. Create and Activate the Conda Environment**

-   Navigate into the project folder (`cd geocrop_analysis_mx`).
-   Run the following command to create the environment from the provided file. This will take several minutes.
    ```bash
    conda env create -f environment.yml
    ```
-   Activate the new environment. You must do this every time you want to run the code.
    ```bash
    conda activate geocrop_analysis_mx
    ```

**6. Authenticate Google Earth Engine**

-   If you have never used GEE on your machine before, run the authentication command and follow the prompts in your web browser.
    ```bash
    earthengine authenticate
    ```

## Configuration

The entire pipeline is controlled by the `config.yaml` file. Modify this file to change the Area of Interest (AOI), date ranges, or algorithm parameters before running the pipeline.

## Usage

Ensure your Conda environment is activated. All commands should be run from the root of the `geocrop_analysis_mx` directory.

**Full Run**

To execute the entire pipeline from start to finish, run:

```bash
python src/main.py
```

**Running a Specific Phase**

You can run a single part of the pipeline using the `--phase` argument. This is useful for debugging or re-running a failed step.

```bash
# Only run the data download phase
python src/main.py --phase download

# Only run the segmentation phase
python src/main.py --phase segment

# Only run the labeling phase
python src/main.py --phase label

# Only run the feature extraction phase
python src/main.py --phase extract
```

The script will print timestamped messages indicating the start and end of each phase and the total duration.