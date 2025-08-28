import geopandas as gpd
import pandas as pd
import os
from exactextract import exact_extract
from osgeo import gdal
import ast

# Enable GDAL exceptions for cleaner error handling
gdal.UseExceptions()

def extract_features(output_dir, config, image_list):
    """Extracts statistics for ALL segments and saves them to a clean, structured CSV file."""
    print("\n--- Starting Feature Extraction (Surgical Post-processing) ---")

    # --- Define Paths ---
    segmentation_dir = os.path.join(output_dir, 'segmentation')
    labeling_dir = os.path.join(output_dir, 'labeling')
    features_csv_path = os.path.join(output_dir, config['output_names']['features_csv'])
    
    full_segmentation_path = os.path.join(segmentation_dir, config['output_names']['segmented_polygons'])
    label_map_path = os.path.join(labeling_dir, 'segment_label_map.csv')

    if os.path.exists(features_csv_path):
        print(f"- Features CSV already exists: {os.path.basename(features_csv_path)}. Skipping.")
        return

    # --- 1. Load Full Segmentation and Label Map ---
    print(f"- Loading ALL segments from: {os.path.basename(full_segmentation_path)}")
    gdf_zones = gpd.read_file(full_segmentation_path)

    print(f"- Loading label map from: {os.path.basename(label_map_path)}")
    df_label_map = pd.read_csv(label_map_path)

    # --- 2. Define stats to extract ---
    stats_to_calc = ['mean', 'stdev', 'min', 'max', 'count', 'sum']

    # --- 3. Loop and Extract Stats (Fast Method) ---
    # This part is fast but creates malformed columns (e.g., 'gm_properties')
    raw_df = gdf_zones[['raster_val']].copy()
    raw_df.rename(columns={'raster_val': 'segment_id'}, inplace=True)

    for image_info in image_list:
        image_path = image_info['path']
        if not os.path.exists(image_path):
            print(f"- WARNING: Image not found, skipping: {os.path.basename(image_path)}")
            continue
        
        print(f"- Extracting stats from {os.path.basename(image_path)}...")
        results = exact_extract(image_path, gdf_zones, stats_to_calc)
        df_stats = pd.DataFrame(results)
        df_stats = df_stats.add_prefix(image_info['prefix'])
        raw_df = raw_df.join(df_stats)

    # --- 4. Post-Processing Step (Surgical Fix) ---
    print("- Post-processing and structuring data for final CSV...")
    
    # Start with the clean segment_id column
    clean_df = raw_df[['segment_id']].copy()
    
    # Find all the properties columns that need to be flattened
    prop_cols = [col for col in raw_df.columns if 'properties' in str(col)]

    for col_name in prop_cols:
        prefix = col_name.replace('properties', '') # e.g., 'gm_', 'ms_201710_' 
        
        # Safely convert string representation of dict to dict
        def safe_literal_eval(val):
            try:
                return ast.literal_eval(str(val))
            except (ValueError, SyntaxError):
                return {}
        
        props_as_dicts = raw_df[col_name].apply(safe_literal_eval)
        
        # Flatten the list of dictionaries into a DataFrame
        df_flat = pd.json_normalize(props_as_dicts)

        # Rename the flattened columns with the correct prefix
        rename_dict = {}
        for flat_col in df_flat.columns:
            # flat_col is like 'band_1.mean'
            parts = flat_col.split('.')
            if len(parts) == 2:
                band_num = parts[0].split('_')[1]
                stat_name = parts[1]
                rename_dict[flat_col] = f"{prefix}b{band_num}_{stat_name}"
            else:
                rename_dict[flat_col] = f"{prefix}{flat_col}"
        
        df_flat.rename(columns=rename_dict, inplace=True)
        clean_df = clean_df.join(df_flat)

    # --- 5. Merge Labels and Save Final CSV ---
    print("- Merging labels with features...")
    final_df = pd.merge(clean_df, df_label_map, on='segment_id', how='left')
    
    final_df['label'] = final_df['label'].fillna('UNLABELED')
    final_df['class_id'] = final_df['class_id'].fillna(0)
    final_df['class_id'] = final_df['class_id'].astype(int)

    print(f"- Saving final, structured features to {os.path.basename(features_csv_path)}")
    final_df.to_csv(features_csv_path, index=False)

    print("- Feature extraction complete.")
