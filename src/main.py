import os
import glob
import subprocess
import geopandas as gpd
import ee
import argparse
import time
from datetime import datetime
import pandas as pd
import shutil

from config import load_config
from data_download import gee_utils, multispectral, radar
from processing import segmentation, labeling, feature_extraction

def _log(message):
    """Prints a message with a timestamp."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def _generate_monthly_ranges(start_date, end_date):
    """Generates a list of month start/end date tuples from a period."""
    months = pd.date_range(start=start_date, end=end_date, freq='MS')
    date_ranges = []
    for month_start in months:
        month_end = month_start + pd.offsets.MonthEnd(1)
        date_ranges.append(
            (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d'))
        )
    return date_ranges

def run_gdal_merge(input_tile_pattern, output_image_path):
    """Merges tile images into a single output image using gdal_merge.py."""
    tile_files = glob.glob(input_tile_pattern)
    if not tile_files:
        _log(f"No tiles found for pattern: {input_tile_pattern}. Skipping merge.")
        return
    command = ['gdal_merge.py', '-o', output_image_path, '-of', 'GTiff', '-co', 'COMPRESS=LZW'] + tile_files
    _log(f"Merging {len(tile_files)} tiles into {os.path.basename(output_image_path)}")
    subprocess.run(command, check=True, capture_output=True, text=True)
    _log("Merge complete.")
    for tile_file in tile_files:
        os.remove(tile_file)
    _log("Cleaned up temporary tiles.")

def run_setup_test_phase(config):
    """Copies test data into the correct data directory structure."""
    _log("Setting up test environment...")
    aoi_identifier = os.path.splitext(config['aoi_file'])[0]
    source_dir = os.path.join(os.path.dirname(__file__), '..', 'test_data')
    dest_aoi_dir = os.path.join(config['data_dir'], aoi_identifier)
    dest_labels_dir = os.path.join(dest_aoi_dir, 'labels')
    os.makedirs(dest_labels_dir, exist_ok=True)

    source_aoi_path = os.path.join(source_dir, config['aoi_file'])
    dest_aoi_path = os.path.join(dest_aoi_dir, config['aoi_file'])
    source_labels_path = os.path.join(source_dir, config['labels_file'])
    dest_labels_path = os.path.join(dest_labels_dir, config['labels_file'])

    _log(f"Copying {config['aoi_file']} to {dest_aoi_path}")
    shutil.copy(source_aoi_path, dest_aoi_path)
    _log(f"Copying {config['labels_file']} to {dest_labels_path}")
    shutil.copy(source_labels_path, dest_labels_path)

    _log("Test data setup complete.")
    _log(f"You can now run the pipeline for the test case with:")
    _log(f"python src/main.py --config config.test.yaml")

def run_download_phase(config, study_area, aoi_identifier):
    """Runs the full data download and preprocessing phase."""
    study_period = config['study_period']
    monthly_ranges = _generate_monthly_ranges(study_period['start_date'], study_period['end_date'])
    
    if config['segmentation_composite_uses_full_study_period']:
        seg_start, seg_end = study_period['start_date'], study_period['end_date']
    else:
        seg_start, seg_end = config['segmentation_composite_custom_range']['start_date'], config['segmentation_composite_custom_range']['end_date']

    seg_output_dir = os.path.join(config['output_dir'], aoi_identifier, 'segmentation')
    main_composite_path = os.path.join(seg_output_dir, config['output_names']['segmentation_image'])
    
    if not os.path.exists(main_composite_path):
        _log(f"Downloading main segmentation composite for period {seg_start} to {seg_end}...")
        hls_collection = multispectral.get_hls_collection(seg_start, seg_end, study_area)
        main_composite = multispectral.get_geometric_median(hls_collection)
        multispectral.download_composite(main_composite, study_area, main_composite_path)
        run_gdal_merge(os.path.join(seg_output_dir, 'tile_*.tif'), main_composite_path)
    else:
        _log(f"Main composite already exists: {os.path.basename(main_composite_path)}")
    
    config['date_ranges'] = monthly_ranges
    # Note: The radar download function needs the full config to derive its paths
    radar_config = config.copy()
    radar_config['output_dir'] = os.path.join(config['output_dir'], aoi_identifier)
    radar.download_radar_composites(radar_config, study_area)
    
    _log("Download phase complete.")

def main():
    """Main orchestrator for the geocrop analysis pipeline."""
    parser = argparse.ArgumentParser(description="GeoCrop Analysis Pipeline")
    parser.add_argument('--config', default='config.yaml', help='Path to the configuration file (e.g., config.test.yaml)')
    parser.add_argument('--phase', choices=['setup_test', 'download', 'segment', 'label', 'extract', 'full_run'], default='full_run', help='Run a specific phase of the pipeline.')
    args = parser.parse_args()

    _log(f"--- Geocrop Analysis Pipeline Initializing --- Config: {args.config}, Phase: {args.phase} ---")
    start_time = time.time()

    config = load_config(args.config)

    if args.phase == 'setup_test':
        run_setup_test_phase(config)
        return

    aoi_identifier = os.path.splitext(config['aoi_file'])[0]
    data_dir = os.path.join(config['data_dir'], aoi_identifier)
    output_dir = os.path.join(config['output_dir'], aoi_identifier)
    os.makedirs(output_dir, exist_ok=True)

    gee_utils.initialize_gee()
    aoi_path = os.path.join(data_dir, config['aoi_file'])
    study_area = ee.Geometry(gpd.read_file(aoi_path).geometry[0].__geo_interface__)

    main_composite_path = os.path.join(output_dir, 'segmentation', config['output_names']['segmentation_image'])
    clumps_path = os.path.join(output_dir, 'segmentation', config['output_names']['segmented_clumps'])

    if args.phase == 'download' or args.phase == 'full_run':
        phase_start_time = time.time()
        _log("Executing PHASE: Download")
        run_download_phase(config, study_area, aoi_identifier)
        _log(f"PHASE 'Download' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    if args.phase == 'segment' or args.phase == 'full_run':
        phase_start_time = time.time()
        _log("Executing PHASE: Segment")
        if not os.path.exists(main_composite_path):
            _log("Error: Main composite image not found. Please run the 'download' phase first.")
            return
        segmentation.run_segmentation(config, main_composite_path)
        _log(f"PHASE 'Segment' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    if args.phase == 'label' or args.phase == 'full_run':
        phase_start_time = time.time()
        _log("Executing PHASE: Label")
        segmented_polygons_path = os.path.join(output_dir, 'segmentation', config['output_names']['segmented_polygons'])
        if not os.path.exists(segmented_polygons_path):
            _log("Error: Segmented polygons not found. Please run the 'segment' phase first.")
            return
        # Pass the full config to the labeling function
        labeling_config = config.copy()
        labeling_config['data_dir'] = data_dir
        labeling_config['output_dir'] = output_dir
        labeling.label_and_rasterize(labeling_config, segmented_polygons_path, clumps_path, main_composite_path)
        _log(f"PHASE 'Label' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    if args.phase == 'extract' or args.phase == 'full_run':
        phase_start_time = time.time()
        _log("Executing PHASE: Extract Features")
        if not os.path.exists(clumps_path):
            _log("Error: Clumps file not found. Please run the 'segment' and 'label' phases first.")
            return
        # Pass the full config to the feature extraction function
        feature_extraction_config = config.copy()
        feature_extraction_config['output_dir'] = output_dir
        feature_extraction.extract_features_to_csv(feature_extraction_config, clumps_path)
        _log(f"PHASE 'Extract Features' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    _log(f"--- Pipeline Finished --- Total Duration: {time.time() - start_time:.2f} seconds ---")

if __name__ == "__main__":
    main()
