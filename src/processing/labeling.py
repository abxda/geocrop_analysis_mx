import geopandas as gpd
import pandas as pd
import os

def generate_label_map(output_dir, data_dir, config):
    """Performs a vector-based purity filter and creates a CSV map
    linking pure segment IDs to their text label and a numeric class ID.
    """
    print("\n--- Starting Label Mapping (Purity Filter) ---")

    # --- Define Paths ---
    segmentation_dir = os.path.join(output_dir, 'segmentation')
    labeling_dir = os.path.join(output_dir, 'labeling')
    os.makedirs(labeling_dir, exist_ok=True)

    segmented_polygons_path = os.path.join(segmentation_dir, config['output_names']['segmented_polygons'])
    ground_truth_path = os.path.join(data_dir, 'labels', config['labels_file'])
    output_csv_path = os.path.join(labeling_dir, 'segment_label_map.csv')

    if os.path.exists(output_csv_path):
        print(f"- Label map file already exists: {os.path.basename(output_csv_path)}. Skipping.")
        return

    # --- 1. Vector-based Purity Filter ---
    print("- Loading segments and ground truth labels for purity analysis.")
    gdf_segments = gpd.read_file(segmented_polygons_path)
    gdf_labels = gpd.read_file(ground_truth_path)

    if gdf_segments.crs != gdf_labels.crs:
        gdf_labels = gdf_labels.to_crs(gdf_segments.crs)

    print("- Performing spatial join...")
    sjoined = gpd.sjoin(gdf_segments, gdf_labels, how='inner', predicate='intersects')

    label_field = config['labels_field_name']
    labels_per_segment = sjoined.groupby('raster_val')[label_field].nunique()
    pure_segments_ids = labels_per_segment[labels_per_segment == 1].index
    print(f"- Found {len(pure_segments_ids)} purely labeled segments.")

    pure_sjoined = sjoined[sjoined['raster_val'].isin(pure_segments_ids)]
    label_map = pure_sjoined.groupby('raster_val')[label_field].first()

    # --- 2. Create Final Mapping DataFrame ---
    df_map = label_map.reset_index()
    df_map.columns = ['segment_id', 'label']

    # --- 3. Add Numeric Class ID ---
    print("- Adding numeric class IDs for traceability.")
    df_map['class_id'] = pd.factorize(df_map['label'])[0] + 1
    
    # --- 4. Save the Mapping to CSV ---
    print(f"- Saving segment-to-label map to: {os.path.basename(output_csv_path)}")
    df_map.to_csv(output_csv_path, index=False)

    print("- Label mapping phase complete.")
