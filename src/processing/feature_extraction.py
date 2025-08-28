import geopandas as gpd
import pandas as pd
import os
from exactextract import exact_extract

def extract_features(output_dir, data_dir, config):
    """Extracts statistics from all composites for each labeled segment and saves to CSV."""
    print("\n--- Starting Feature Extraction (using exactextract) ---")

    # --- Define Paths ---
    labeling_dir = os.path.join(output_dir, 'labeling')
    features_csv_path = os.path.join(output_dir, config['output_names']['features_csv'])
    labeled_polygons_path = os.path.join(labeling_dir, config['output_names']['labeled_polygons'])

    if os.path.exists(features_csv_path):
        print(f"- Features CSV already exists: {os.path.basename(features_csv_path)}. Skipping.")
        return

    # --- 1. Load Labeled Polygons ---
    print(f"- Loading pure labeled polygons from: {os.path.basename(labeled_polygons_path)}")
    gdf = gpd.read_file(labeled_polygons_path)
    # We only need the geometry and the final label for the extraction
    gdf_zones = gdf[['geometry', 'raster_val', 'label']]

    # --- 2. Define images and stats to extract ---
    stats_to_calc = ['mean', 'stddev', 'min', 'max', 'count', 'sum']
    image_list = []
    # Add main composite
    image_list.append({
        'path': os.path.join(output_dir, 'segmentation', config['output_names']['segmentation_image']),
        'prefix': 'gm_' # Geomedian
    })
    # Add monthly composites
    from main import _generate_monthly_ranges # Use the same date logic
    monthly_ranges = _generate_monthly_ranges(config['study_period']['start_date'], config['study_period']['end_date'])
    for start, _ in monthly_ranges:
        month_str = start[:7]
        image_list.append({
            'path': os.path.join(output_dir, 'multispectral', month_str, f"multispectral_{month_str}.tif"),
            'prefix': f'ms_{month_str.replace("-", "")}_' # e.g., ms_201710_
        })
        image_list.append({
            'path': os.path.join(output_dir, 'radar', month_str, f"radar_{month_str}.tif"),
            'prefix': f'sar_{month_str.replace("-", "")}_' # e.g., sar_201710_
        })

    # --- 3. Loop and Extract ---
    final_df = gdf_zones.drop(columns='geometry').copy()

    for image_info in image_list:
        image_path = image_info['path']
        if not os.path.exists(image_path):
            print(f"- WARNING: Image not found, skipping: {os.path.basename(image_path)}")
            continue
        
        print(f"- Extracting stats from {os.path.basename(image_path)}...")
        # exactextract returns a list of dicts, one for each feature
        results = exact_extract(image_path, gdf_zones, stats_to_calc)
        df_stats = pd.DataFrame(results)

        # Rename columns with a unique prefix
        df_stats.columns = [f"{image_info['prefix']}{col}" for col in df_stats.columns]
        
        # Join with the main dataframe
        final_df = final_df.join(df_stats)

    # --- 4. Save Final CSV ---
    print(f"- Saving final features to {os.path.basename(features_csv_path)}")
    final_df.to_csv(features_csv_path, index=False)

    print("- Feature extraction complete.")
