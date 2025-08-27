import ee
import os
from . import gee_utils
from . import multispectral # To reuse the download logic

def _calculate_rvi(image):
    """Calculates Radar Vegetation Index (RVI)."""
    vv = image.select('VV')
    vh = image.select('VH')
    # Formula for RVI
    rvi = (vh.multiply(4)).divide(vv.add(vh)).rename('RVI')
    return image.addBands(rvi)

def get_s1_collection(start_date, end_date, study_area):
    """Gets Sentinel-1 collection, filters it, and calculates RVI."""
    s1_collection = ee.ImageCollection('COPERNICUS/S1_GRD') \
        .filterDate(start_date, end_date) \
        .filterBounds(study_area) \
        .filter(ee.Filter.eq('instrumentMode', 'IW')) \
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')) \
        .select(['VV', 'VH']) \
        .map(_calculate_rvi)
    return s1_collection

def download_radar_composites(config, study_area):
    """Main function to download monthly radar composites."""
    print("\n--- Starting Radar Data Download ---")
    gee_utils.initialize_gee()
    
    base_output_dir = os.path.join(config['output_dir'], config['aoi_name'], 'radar')
    os.makedirs(base_output_dir, exist_ok=True)

    for start_date, end_date in config['date_ranges']:
        month_str = start_date[:7] # YYYY-MM
        print(f"Processing Radar data for {month_str}")
        
        output_path = os.path.join(base_output_dir, f"radar_composite_{month_str}.tif")
        if os.path.exists(output_path):
            print(f"- Composite exists: {os.path.basename(output_path)}")
            continue

        s1_collection = get_s1_collection(start_date, end_date, study_area)
        
        if s1_collection.size().getInfo() == 0:
            print(f"- No Sentinel-1 images found for {month_str}. Skipping.")
            continue

        # Create a median composite for the month
        monthly_median = s1_collection.median()
        
        # Use the same tiled download logic from the multispectral module
        multispectral.download_composite(monthly_median, study_area, output_path)
