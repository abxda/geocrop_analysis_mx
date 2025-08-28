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

def extract_features_to_csv(features_csv_path, clumps_path, image_paths):
    """Extracts features from all composites and saves them to a CSV file."""
    print("\n--- Starting Feature Extraction ---")

    if os.path.exists(features_csv_path):
        print(f"- Features CSV already exists: {os.path.basename(features_csv_path)}")
        return

    # --- Iterate and extract stats ---
    band_offset = 0
    for image_info in image_paths:
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