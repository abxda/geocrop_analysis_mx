import os
import glob
import subprocess
import geopandas as gpd
import ee
import argparse
import time
from datetime import datetime

from config import load_config
from data_download import gee_utils, multispectral, radar
from processing import segmentation, labeling, feature_extraction

def _log(message):
    """Prints a message with a timestamp."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

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

def run_download_phase(config, study_area):
    """Runs the full data download and preprocessing phase."""
    # Download main segmentation composite
    seg_config = config['segmentation_composite']
    seg_output_dir = os.path.join(config['output_dir'], config['aoi_name'], 'segmentation')
    main_composite_path = os.path.join(seg_output_dir, config['output_names']['segmentation_image'])
    
    if not os.path.exists(main_composite_path):
        _log("Downloading main segmentation composite...")
        hls_collection = multispectral.get_hls_collection(seg_config['start_date'], seg_config['end_date'], study_area)
        main_composite = multispectral.get_geometric_median(hls_collection)
        multispectral.download_composite(main_composite, study_area, main_composite_path)
        run_gdal_merge(os.path.join(seg_output_dir, 'tile_*.tif'), main_composite_path)
    else:
        _log(f"Main composite already exists: {os.path.basename(main_composite_path)}")
    
    # Download monthly radar composites
    radar.download_radar_composites(config, study_area)
    # Here you would add the call to download monthly multispectral and merge them as well
    _log("Download phase complete.")
    return main_composite_path

def main():
    """Main orchestrator for the geocrop analysis pipeline."""
    parser = argparse.ArgumentParser(description="GeoCrop Analysis Pipeline")
    parser.add_argument(
        '--phase',
        choices=['download', 'segment', 'label', 'extract', 'full_run'],
        default='full_run',
        help='Run a specific phase of the pipeline.'
    )
    args = parser.parse_args()

    _log(f"--- Geocrop Analysis Pipeline Initializing --- Phase: {args.phase} ---")
    start_time = time.time()

    # --- Setup ---
    config = load_config()
    aoi_name = config['aoi_name']
    output_dir = os.path.join(config['output_dir'], aoi_name)
    data_dir = os.path.join(config['data_dir'], aoi_name)
    os.makedirs(output_dir, exist_ok=True)
    gee_utils.initialize_gee()
    aoi_path = os.path.join(data_dir, config['aoi_file'])
    study_area = ee.Geometry(gpd.read_file(aoi_path).geometry[0].__geo_interface__)

    # --- Phase Execution ---
    main_composite_path = os.path.join(output_dir, 'segmentation', config['output_names']['segmentation_image'])
    clumps_path = os.path.join(output_dir, 'segmentation', config['output_names']['segmented_clumps'])

    if args.phase == 'download' or args.phase == 'full_run':
        phase_start_time = time.time()
        _log("Executing PHASE: Download")
        run_download_phase(config, study_area)
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
        labeling.label_and_rasterize(config, segmented_polygons_path, clumps_path, main_composite_path)
        _log(f"PHASE 'Label' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    if args.phase == 'extract' or args.phase == 'full_run':
        phase_start_time = time.time()
        _log("Executing PHASE: Extract Features")
        if not os.path.exists(clumps_path):
            _log("Error: Clumps file not found. Please run the 'segment' and 'label' phases first.")
            return
        feature_extraction.extract_features_to_csv(config, clumps_path)
        _log(f"PHASE 'Extract Features' complete. Duration: {time.time() - phase_start_time:.2f} seconds.")

    _log(f"--- Pipeline Finished --- Total Duration: {time.time() - start_time:.2f} seconds ---")

if __name__ == "__main__":
    main()