from rsgislib import rastergis
import os

def _add_stats_for_image(image_path, clumps_path, band_offset, num_bands):
    """Helper function to populate RAT with stats for a single image."""
    print(f"  - Extracting stats from: {os.path.basename(image_path)}")
    band_stats = []
    for i in range(1, num_bands + 1):
        # Define column names based on the band number and offset
        col_prefix = f'b{band_offset + i}'
        band_stats.append(rastergis.BandAttStats(
            band=i,
            min_field=f'{col_prefix}Min',
            max_field=f'{col_prefix}Max',
            mean_field=f'{col_prefix}Mean',
            sum_field=f'{col_prefix}Sum',
            std_dev_field=f'{col_prefix}StdDev'
        ))
    
    rastergis.populate_rat_with_stats(image_path, clumps_path, band_stats)

def extract_features_to_csv(config, clumps_path):
    """Extracts features from all composites and saves them to a CSV file."""
    print("\n--- Starting Feature Extraction ---")

    output_dir = os.path.join(config['output_dir'], config['aoi_name'])
    features_csv_path = os.path.join(output_dir, config['output_names']['features_csv'])

    if os.path.exists(features_csv_path):
        print(f"- Features CSV already exists: {os.path.basename(features_csv_path)}")
        return

    # --- Define image lists and parameters ---
    # These could be further customized in config.yaml if needed
    multispectral_dir = os.path.join(output_dir, 'multispectral')
    radar_dir = os.path.join(output_dir, 'radar')
    seg_dir = os.path.join(output_dir, 'segmentation')

    # List of images to process
    # The order is important for consistent band numbering
    images_to_process = []
    # 1. Main segmentation composite
    images_to_process.append({
        'path': os.path.join(seg_dir, config['output_names']['segmentation_image']),
        'num_bands': 13 # As defined in segmentation_params
    })
    # 2. Monthly multispectral composites
    for start_date, _ in config['date_ranges']:
        month_str = start_date[:7]
        images_to_process.append({
            'path': os.path.join(multispectral_dir, f"multispectral_composite_{month_str}.tif"),
            'num_bands': 13
        })
    # 3. Monthly radar composites
    for start_date, _ in config['date_ranges']:
        month_str = start_date[:7]
        images_to_process.append({
            'path': os.path.join(radar_dir, f"radar_composite_{month_str}.tif"),
            'num_bands': 3 # VV, VH, RVI
        })

    # --- Iterate and extract stats ---
    band_offset = 0
    for image_info in images_to_process:
        if os.path.exists(image_info['path']):
            _add_stats_for_image(image_info['path'], clumps_path, band_offset, image_info['num_bands'])
            band_offset += image_info['num_bands']
        else:
            print(f"  - WARNING: Image not found, skipping: {os.path.basename(image_info['path'])}")

    # --- Export to CSV ---
    print(f"- Exporting RAT to CSV: {os.path.basename(features_csv_path)}")
    all_columns = rastergis.get_rat_columns(clumps_path)
    
    # Filter out columns we don't need in the final CSV
    columns_to_export = [name for name in all_columns if not (
        name.startswith('Histogram') or
        name.startswith('Red') or
        name.startswith('Green') or
        name.startswith('Blue') or
        name.startswith('Alpha'))]

    rastergis.export_rat_cols_to_ascii(clumps_path, features_csv_path, columns_to_export)

    print("- Feature extraction complete.")
