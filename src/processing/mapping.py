import pandas as pd
import geopandas as gpd
import joblib
import os
import numpy as np
from datetime import datetime

def _log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def generate_map(config, output_dir):
    _log("--- Executing PHASE: Predict and Generate Map ---")

    # --- Define Paths ---
    modeling_dir = os.path.join(output_dir, 'modeling')
    model_path = os.path.join(modeling_dir, config['modeling_params']['output_model_name'])
    features_path = os.path.join(output_dir, config['output_names']['features_csv'])
    label_map_path = os.path.join(output_dir, 'labeling', 'segment_label_map.csv')
    polygons_path = os.path.join(output_dir, 'segmentation', config['output_names']['segmented_polygons'])
    
    predictions_csv_path = os.path.join(modeling_dir, config['modeling_params']['output_prediction_name'])
    output_map_path = os.path.join(modeling_dir, config['modeling_params']['output_map_name'])

    if not os.path.exists(model_path):
        _log(f"Model not found at {model_path}. Please run the 'train' phase first.")
        return

    if os.path.exists(output_map_path):
        _log(f"Predicted map already exists at {output_map_path}. Skipping.")
        return

    # --- Load Model and Data ---
    _log(f"Loading model from {model_path}")
    model = joblib.load(model_path)

    _log(f"Loading full feature set from {features_path}")
    features_df = pd.read_csv(features_path)

    _log(f"Loading label map for class name lookup from {label_map_path}")
    label_map_df = pd.read_csv(label_map_path)

    # --- Predict on Full Dataset ---
    _log("Generating predictions for all segments...")
    # Prepare features for prediction (drop non-feature columns)
    # Ensure 'klass' is handled correctly if it exists
    cols_to_drop = ['segment_id', 'label', 'class_id']
    if 'klass' in features_df.columns:
        cols_to_drop.append('klass')
    
    # Only drop columns that actually exist in the dataframe
    cols_to_drop_existing = [col for col in cols_to_drop if col in features_df.columns]
    features_to_predict = features_df.drop(columns=cols_to_drop_existing)
    
    predictions_numeric = model.predict(features_to_predict)
    predictions_proba = model.predict_proba(features_to_predict)
    _log("Prediction complete.")

    # --- Format Results ---
    _log("Formatting prediction results...")
    # Create a mapping from numeric class_id to text label
    class_id_to_label = dict(zip(label_map_df['class_id'], label_map_df['label']))

    # Get the probability of the predicted class
    confidence = np.max(predictions_proba, axis=1)

    # Create results DataFrame
    results_df = pd.DataFrame({
        'segment_id': features_df['segment_id'],
        'class_id': predictions_numeric,
        'probability': confidence
    })
    results_df['prediction'] = results_df['class_id'].map(class_id_to_label)

    _log(f"Saving prediction data to {predictions_csv_path}")
    results_df.to_csv(predictions_csv_path, index=False)

    # --- Generate Final Map ---
    _log("Generating final map by joining predictions with polygons...")
    _log(f"Loading polygons from {polygons_path}")
    polygons_gdf = gpd.read_file(polygons_path)

    # Merge predictions with polygons
    # The segmented shapefile has a 'raster_val' column corresponding to 'segment_id'
    merged_gdf = polygons_gdf.merge(results_df, left_on='raster_val', right_on='segment_id')

    _log(f"Saving final predicted map to {output_map_path}")
    merged_gdf.to_file(output_map_path)

    _log("--- Predict and Generate Map phase complete ---")