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
import sys
from dateutil.relativedelta import relativedelta

from config import load_config
from data_download import gee_utils, multispectral, radar
from processing import segmentation, labeling, feature_extraction, modeling, mapping

def _log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def _generate_monthly_ranges(start_date, end_date):
    months = pd.date_range(start=start_date, end=end_date, freq='MS')
    return [(s.strftime('%Y-%m-%d'), (s + pd.offsets.MonthEnd(1)).strftime('%Y-%m-%d')) for s in months]

def run_gdal_merge(tile_paths, output_image_path):
    if not tile_paths or not isinstance(tile_paths, list):
        _log(f"- No new tiles to merge for {os.path.basename(output_image_path)}.")
        return
    tile_dir = os.path.dirname(tile_paths[0])
    _log(f"- Merging {len(tile_paths)} tiles from {os.path.basename(tile_dir)} into {os.path.basename(output_image_path)}")

    if sys.platform == "win32":
        gdal_merge_script = os.path.join(os.path.dirname(sys.executable), 'Scripts', 'gdal_merge.py')
    else:
        gdal_merge_script = os.path.join(os.path.dirname(sys.executable), 'gdal_merge.py')

    if not os.path.exists(gdal_merge_script):
        gdal_merge_script = shutil.which("gdal_merge.py")
        if not gdal_merge_script:
            _log(f"- GDAL Merge FAILED. Could not find 'gdal_merge.py'. Please ensure it is in your PATH.")
            return

    command = [sys.executable, gdal_merge_script, '-o', output_image_path, '-of', 'GTiff', '-co', 'COMPRESS=LZW'] + tile_paths
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        _log("- Merge successful.")
        shutil.rmtree(tile_dir)
    except subprocess.CalledProcessError as e:
        error_message = e.stderr if e.stderr else str(e)
        _log(f"- GDAL Merge FAILED. Error: {error_message.strip()}")
        _log(f"- Temporary tiles kept for inspection in: {tile_dir}")

def show_config(config_path, config_data):
    _log(f"--- Displaying settings from: {config_path} ---")
    print(json.dumps(config_data, indent=2))

def run_setup_test_phase(config):
    _log("Setting up test environment...")
    aoi_identifier = os.path.splitext(config['aoi_file'])[0]
    source_dir = os.path.join(os.path.dirname(__file__), '..', 'test_data')
    dest_aoi_dir = os.path.join(config['data_dir'], aoi_identifier)
    os.makedirs(os.path.join(dest_aoi_dir, 'labels'), exist_ok=True)
    source_aoi_path = os.path.join(source_dir, config['aoi_file'])
    dest_aoi_path = os.path.join(dest_aoi_dir, config['aoi_file'])
    _log(f"Copying {config['aoi_file']} to {dest_aoi_path}")
    shutil.copy(source_aoi_path, dest_aoi_path)
    source_labels_path = os.path.join(source_dir, config['labels_file'])
    dest_labels_path = os.path.join(dest_aoi_dir, 'labels', config['labels_file'])
    _log(f"Copying {config['labels_file']} to {dest_labels_path}")
    shutil.copy(source_labels_path, dest_labels_path)
    _log("Test data setup complete.")

def run_cleanup_phase(output_dir):
    _log(f"--- Executing PHASE: Cleanup Tiles ---")
    tile_dirs = glob.glob(os.path.join(output_dir, "**", "*_tiles"), recursive=True)
    if not tile_dirs:
        _log("- No tile directories found to clean up.")
        return
    for tile_dir in tile_dirs:
        _log(f"- Removing temporary tile directory: {tile_dir}")
        shutil.rmtree(tile_dir)
    _log("- Cleanup complete.")

def run_download_phase(config, study_area, output_dir):
    monthly_ranges = _generate_monthly_ranges(config['study_period']['start_date'], config['study_period']['end_date'])
    _log("--- Processing Main Segmentation Composite ---")
    if config['segmentation_composite_uses_full_study_period']:
        seg_start, seg_end = config['study_period']['start_date'], config['study_period']['end_date']
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
        _log(f"No images found for the main composite period. Skipping.")
    _log("--- Processing Monthly Composites ---")
    for start, end in monthly_ranges:
        month_str = start[:7]
        _log(f"-- Processing month: {month_str} --")
        optical_dir = os.path.join(output_dir, 'multispectral', month_str)
        optical_path = os.path.join(optical_dir, f"multispectral_{month_str}.tif")
        hls_monthly = multispectral.get_hls_collection(start, end, study_area)
        if hls_monthly.size().getInfo() > 0:
            optical_composite = multispectral.get_geometric_median(hls_monthly)
            tile_paths_opt = multispectral.download_composite(optical_composite, study_area, optical_path)
            run_gdal_merge(tile_paths_opt, optical_path)
        else:
            _log(f"No optical images found for {month_str}. Skipping.")
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
    parser.add_argument('--phase', choices=['show_config', 'setup_test', 'download', 'segment', 'label', 'extract', 'train', 'predict', 'cleanup_tiles', 'full_run', 'predict_full_run'], default='full_run', help='The specific pipeline phase to run')
    parser.add_argument('--prediction-year', type=int, help='The year to run predictions for. Activates prediction mode.')
    args = parser.parse_args()

    _log(f"--- Geocrop Analysis Pipeline Initializing --- Config: {args.config}, Phase: {args.phase} ---")
    config = load_config(args.config)
    aoi_identifier = os.path.splitext(config['aoi_file'])[0]
    
    # --- Handle Prediction Mode ---
    prediction_mode = args.prediction_year is not None
    original_model_path = None

    if prediction_mode:
        _log(f"*** PREDICTION MODE ACTIVATED FOR YEAR: {args.prediction_year} ***")
        original_output_dir = os.path.join(config['output_dir'], aoi_identifier)
        output_dir = os.path.join(original_output_dir, f"prediction_{args.prediction_year}")
        original_model_path = os.path.join(original_output_dir, 'modeling', config['modeling_params']['output_model_name'])
        
        # Shift dates to the prediction year
        start_date_orig = datetime.strptime(config['study_period']['start_date'], '%Y-%m-%d')
        end_date_orig = datetime.strptime(config['study_period']['end_date'], '%Y-%m-%d')
        year_diff = args.prediction_year - start_date_orig.year
        
        config['study_period']['start_date'] = (start_date_orig + relativedelta(years=year_diff)).strftime('%Y-%m-%d')
        config['study_period']['end_date'] = (end_date_orig + relativedelta(years=year_diff)).strftime('%Y-%m-%d')
        _log(f"Shifted study period to: {config['study_period']['start_date']} to {config['study_period']['end_date']}")
    else:
        output_dir = os.path.join(config['output_dir'], aoi_identifier)

    data_dir = os.path.join(config['data_dir'], aoi_identifier)
    os.makedirs(output_dir, exist_ok=True)

    # --- Phase Execution ---
    if args.phase in ['show_config', 'setup_test', 'cleanup_tiles']:
        # These phases are not affected by prediction mode
        if args.phase == 'show_config': show_config(args.config, config)
        if args.phase == 'setup_test': run_setup_test_phase(config)
        if args.phase == 'cleanup_tiles': run_cleanup_phase(output_dir)
        return

    pipeline_start_time = time.time()
    
    run_all = args.phase == 'full_run'
    run_all_predict = args.phase == 'predict_full_run'

    if run_all_predict and not prediction_mode:
        _log("Error: --phase predict_full_run requires the --prediction-year argument.")
        return

    # --- Core Pipeline Phases ---
    if args.phase == 'download' or run_all or run_all_predict:
        _log("Initializing Google Earth Engine for Download...")
        gee_utils.initialize_gee()
        aoi_path = os.path.join(data_dir, config['aoi_file'])
        study_area = ee.Geometry(gpd.read_file(aoi_path).geometry[0].__geo_interface__)
        phase_start_time = time.time()
        _log(f"Executing PHASE: Download (Output: {output_dir})")
        run_download_phase(config, study_area, output_dir)
        _log(f"PHASE 'Download' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    if args.phase == 'segment' or run_all or run_all_predict:
        phase_start_time = time.time()
        _log(f"Executing PHASE: Segment (Output: {output_dir})")
        main_composite_path = os.path.join(output_dir, 'segmentation', config['output_names']['segmentation_image'])
        if not os.path.exists(main_composite_path):
            _log(f"Error: Main composite image not found. Please run the 'download' phase first.")
            return
        segmentation.run_segmentation(config['segmentation_params'], main_composite_path, os.path.join(output_dir, 'segmentation'), config['output_names'])
        _log(f"PHASE 'Segment' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    if args.phase == 'label' or run_all:
        if prediction_mode:
            _log("Skipping PHASE: Label in prediction mode.")
        else:
            phase_start_time = time.time()
            _log("Executing PHASE: Label")
            labeling.generate_label_map(output_dir, data_dir, config)
            _log(f"PHASE 'Label' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    if args.phase == 'extract' or run_all or run_all_predict:
        phase_start_time = time.time()
        _log(f"Executing PHASE: Extract Features (Output: {output_dir})")
        # Construct the list of images for feature extraction
        image_list = []
        image_list.append({'path': os.path.join(output_dir, 'segmentation', config['output_names']['segmentation_image']), 'prefix': 'gm_'})
        monthly_ranges = _generate_monthly_ranges(config['study_period']['start_date'], config['study_period']['end_date'])
        for start, _ in monthly_ranges:
            month_str = start[:7] # YYYY-MM
            month_only = month_str.split('-')[1] # MM
            image_list.append({'path': os.path.join(output_dir, 'multispectral', month_str, f"multispectral_{month_str}.tif"), 'prefix': f'ms_{month_only}_'})
            image_list.append({'path': os.path.join(output_dir, 'radar', month_str, f"radar_{month_str}.tif"), 'prefix': f'sar_{month_only}_'})
        
        feature_extraction.extract_features(output_dir, config, image_list)
        _log(f"PHASE 'Extract Features' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    if args.phase == 'train' or run_all:
        if prediction_mode:
            _log("Skipping PHASE: Train in prediction mode.")
        else:
            phase_start_time = time.time()
            _log("Executing PHASE: Train Model")
            modeling.train_model(config, output_dir)
            _log(f"PHASE 'Train Model' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    if args.phase == 'predict' or run_all or run_all_predict:
        phase_start_time = time.time()
        _log(f"Executing PHASE: Predict and Generate Map (Output: {output_dir})")
        mapping.generate_map(config, output_dir, model_path=original_model_path)
        _log(f"PHASE 'Predict and Generate Map' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    if run_all or run_all_predict:
        _log(f"--- Pipeline Finished --- Total Duration: {time.time() - pipeline_start_time:.2f} seconds ---")

if __name__ == "__main__":
    main()