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
import json

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

def run_gdal_merge(tile_paths, output_image_path):
    """Merges tile images into a single output image and cleans up."""
    if not tile_paths or not isinstance(tile_paths, list):
        _log(f"- No new tiles to merge for {os.path.basename(output_image_path)}.")
        return

    tile_dir = os.path.dirname(tile_paths[0])
    _log(f"- Merging {len(tile_paths)} tiles from {os.path.basename(tile_dir)} into {os.path.basename(output_image_path)}")
    
    command = ['gdal_merge.py', '-o', output_image_path, '-of', 'GTiff', '-co', 'COMPRESS=LZW'] + tile_paths
    
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        _log("- Merge successful.")
        shutil.rmtree(tile_dir)
        _log(f"- Cleaned up temporary tile directory: {os.path.basename(tile_dir)}")
    except subprocess.CalledProcessError as e:
        _log(f"- GDAL Merge FAILED. Error: {e.stderr}")
        _log(f"- Temporary tiles kept for inspection in: {tile_dir}")

def show_config(config_path, config_data):
    _log(f"--- Displaying settings from: {config_path} ---")
    print(json.dumps(config_data, indent=2))
    _log("--- End of settings ---")

def run_setup_test_phase(config):
    _log("Setting up test environment...")
    aoi_identifier = os.path.splitext(config['aoi_file'])[0]
    source_dir = os.path.join(os.path.dirname(__file__), '..', 'test_data')
    dest_aoi_dir = os.path.join(config['data_dir'], aoi_identifier)
    os.makedirs(os.path.join(dest_aoi_dir, 'labels'), exist_ok=True)

    # Copy AOI file
    source_aoi_path = os.path.join(source_dir, config['aoi_file'])
    dest_aoi_path = os.path.join(dest_aoi_dir, config['aoi_file'])
    _log(f"Copying {config['aoi_file']} to {dest_aoi_path}")
    shutil.copy(source_aoi_path, dest_aoi_path)

    # Copy labels file
    source_labels_path = os.path.join(source_dir, config['labels_file'])
    dest_labels_path = os.path.join(dest_aoi_dir, 'labels', config['labels_file'])
    _log(f"Copying {config['labels_file']} to {dest_labels_path}")
    shutil.copy(source_labels_path, dest_labels_path)
    _log("Test data setup complete.")

def run_download_phase(config, study_area, aoi_identifier):
    output_dir = os.path.join(config['output_dir'], aoi_identifier)
    study_period = config['study_period']
    monthly_ranges = _generate_monthly_ranges(study_period['start_date'], study_period['end_date'])
    
    # --- Download Main Segmentation Composite ---
    _log("--- Processing Main Segmentation Composite ---")
    if config['segmentation_composite_uses_full_study_period']:
        seg_start, seg_end = study_period['start_date'], study_period['end_date']
    else:
        seg_start, seg_end = config['segmentation_composite_custom_range']['start_date'], config['segmentation_composite_custom_range']['end_date']

    seg_output_dir = os.path.join(output_dir, 'segmentation')
    main_composite_path = os.path.join(seg_output_dir, config['output_names']['segmentation_image'])
    
    hls_collection = multispectral.get_hls_collection(seg_start, seg_end, study_area)
    if hls_collection.size().getInfo() > 0:
        main_composite = multispectral.get_geometric_median(hls_collection)
        tile_paths = multispectral.download_composite(main_composite, study_area, main_composite_path)
        run_gdal_merge(tile_paths, main_composite_path)
    else:
        _log(f"No images found for the main composite period ({seg_start} to {seg_end}). Skipping download.")

    # --- Download Monthly Composites ---
    _log("--- Processing Monthly Composites ---")
    for start, end in monthly_ranges:
        month_str = start[:7]
        _log(f"-- Processing month: {month_str} --")

        # Optical
        optical_dir = os.path.join(output_dir, 'multispectral', month_str)
        optical_path = os.path.join(optical_dir, f"multispectral_{month_str}.tif")
        hls_monthly = multispectral.get_hls_collection(start, end, study_area)
        if hls_monthly.size().getInfo() > 0:
            optical_composite = multispectral.get_geometric_median(hls_monthly)
            tile_paths_opt = multispectral.download_composite(optical_composite, study_area, optical_path)
            run_gdal_merge(tile_paths_opt, optical_path)
        else:
            _log(f"No optical images found for {month_str}. Skipping.")

        # Radar
        radar_dir = os.path.join(output_dir, 'radar', month_str)
        radar_path = os.path.join(radar_dir, f"radar_{month_str}.tif")
        s1_monthly = radar.get_s1_collection(start, end, study_area)
        if s1_monthly.size().getInfo() > 0:
            radar_composite = s1_monthly.median()
            tile_paths_rad = multispectral.download_composite(radar_composite, study_area, radar_path)
            run_gdal_merge(tile_paths_rad, radar_path)
        else:
            _log(f"No radar images found for {month_str}. Skipping.")

def main():
    parser = argparse.ArgumentParser(description="GeoCrop Analysis Pipeline")
    parser.add_argument('--config', default='config.yaml', help='Configuration file to use')
    parser.add_argument('--phase', choices=['show_config', 'setup_test', 'download', 'segment', 'label', 'extract', 'full_run'], default='full_run', help='The specific pipeline phase to run')
    args = parser.parse_args()

    _log(f"--- Geocrop Analysis Pipeline Initializing --- Config: {args.config}, Phase: {args.phase} ---")
    config = load_config(args.config)

    if args.phase in ['show_config', 'setup_test']:
        if args.phase == 'show_config': show_config(args.config, config)
        if args.phase == 'setup_test': run_setup_test_phase(config)
        return

    pipeline_start_time = time.time()
    _log("Initializing Google Earth Engine...")
    gee_utils.initialize_gee()
    
    aoi_identifier = os.path.splitext(config['aoi_file'])[0]
    data_dir = os.path.join(config['data_dir'], aoi_identifier)
    output_dir = os.path.join(config['output_dir'], aoi_identifier)
    os.makedirs(output_dir, exist_ok=True)

    aoi_path = os.path.join(data_dir, config['aoi_file'])
    study_area = ee.Geometry(gpd.read_file(aoi_path).geometry[0].__geo_interface__)

    if args.phase == 'download' or args.phase == 'full_run':
        phase_start_time = time.time()
        _log("Executing PHASE: Download")
        run_download_phase(config, study_area, aoi_identifier)
        _log(f"PHASE 'Download' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    if args.phase == 'segment' or args.phase == 'full_run':
        phase_start_time = time.time()
        _log("Executing PHASE: Segment")
        main_composite_path = os.path.join(output_dir, 'segmentation', config['output_names']['segmentation_image'])
        if not os.path.exists(main_composite_path):
            _log(f"Error: Main composite image not found. Please run the 'download' phase first.")
            return
        clumps_path, _ = segmentation.run_segmentation(config, main_composite_path)
        _log(f"PHASE 'Segment' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    if args.phase == 'label' or args.phase == 'full_run':
        phase_start_time = time.time()
        _log("Executing PHASE: Label")
        main_composite_path = os.path.join(output_dir, 'segmentation', config['output_names']['segmentation_image'])
        segmented_polygons_path = os.path.join(output_dir, 'segmentation', config['output_names']['segmented_polygons'])
        clumps_path = os.path.join(output_dir, 'segmentation', config['output_names']['segmented_clumps'])
        if not os.path.exists(segmented_polygons_path):
            _log("Error: Segmented polygons not found. Please run the 'segment' phase first.")
            return
        labeling.label_and_rasterize(config, segmented_polygons_path, clumps_path, main_composite_path)
        _log(f"PHASE 'Label' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    if args.phase == 'extract' or args.phase == 'full_run':
        phase_start_time = time.time()
        _log("Executing PHASE: Extract Features")
        clumps_path = os.path.join(output_dir, 'segmentation', config['output_names']['segmented_clumps'])
        if not os.path.exists(clumps_path):
            _log("Error: Clumps file not found. Please run the 'segment' and 'label' phases first.")
            return
        feature_extraction.extract_features_to_csv(config, clumps_path)
        _log(f"PHASE 'Extract Features' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    _log(f"--- Pipeline Finished --- Total Duration: {time.time() - pipeline_start_time:.2f} seconds ---")

if __name__ == "__main__":
    main()
