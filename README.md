# **GeoCrop Analysis MX**

This project provides a complete and modular pipeline for crop classification using satellite imagery from Google Earth Engine. It is designed to be configurable, extensible, and easy to use for different regions and time periods.

## **Installation**

This project has complex dependencies (gdal, geopandas, etc.). Following these steps precisely is essential for ensuring the environment is set up correctly.

1. **Install Conda**: We recommend installing **Miniforge**. If you don't have it yet, download and install Miniforge from the [Miniforge GitHub releases page](https://github.com/conda-forge/miniforge/releases).  
2. **Open the Conda Terminal**: Open "Miniforge Prompt" (on Windows) or your terminal (macOS/Linux).  
3. **Clone the Project**: git clone https://github.com/abxda/geocrop\_analysis\_mx.git  
4. **Create Project Directories**: Outside the project folder, create the data and outputs directories. Your folder structure should look like this:  
  \- /path/to/your/projects/  
     |- geocrop\_analysis\_mx/  \<-- The cloned repository  
     |- data/                 \<-- Empty folder  
     |- outputs/              \<-- Empty folder

5. **Create the Conda Environment**: Navigate into the geocrop\_analysis\_mx folder. This command will create the environment with all the necessary dependencies.  
   conda env create \-f environment.yml

6. **Activate the Environment**: You must activate the environment every time you want to use the project.  
   conda activate geocrop\_analysis\_mx

7. **Validate the Environment**: Before proceeding, run this script to ensure all critical libraries are installed and accessible.  
   python check\_env.py

   *You should see \[SUCCESS\] messages for all libraries. If not, please review the installation steps.*  
8. **Authenticate Google Earth Engine**: Run earthengine authenticate if it's your first time using the platform on this machine. Follow the instructions in your browser.

## **Tutorial: Running the Test Case (Step-by-Step)**

This tutorial will guide you through running the included test case, phase by phase. This is the best way to understand the pipeline and verify that your installation is correct.

**Prerequisite**: Ensure your Conda environment (geocrop\_analysis\_mx) is activated.

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

* **Full Run (full\_run):** To execute all steps (from download to prediction) at once. *Note: requires active GEE authentication.*  
  \# This will download real data and may take some time  
  python src/main.py \--config config.test.yaml \--phase full\_run

* **View Configuration (show\_config):** To quickly view the active settings from a configuration file.  
  python src/main.py \--config config.test.yaml \--phase show\_config

* **Using Your Own Data:** Prepare your own data (AOI, labels) and a custom configuration file (config.my\_region.yaml), then run the pipeline.  
  python src/main.py \--config config.my\_region.yaml \--phase full\_run

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
