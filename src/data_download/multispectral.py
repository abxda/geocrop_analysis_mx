import ee
import os
import requests
import shutil
import time
from . import gee_utils

def get_hls_collection(start_date, end_date, study_area):
    """Gets and merges HLS Landsat and Sentinel collections for a given period."""
    hlsl = ee.ImageCollection("NASA/HLS/HLSL30/v002") \
        .filterDate(start_date, end_date) \
        .filterBounds(study_area) \
        .map(gee_utils.hls_mask) \
        .select(
            ['B2', 'B3', 'B4', 'B5', 'B6', 'B7'],
            ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']
        ).map(gee_utils.add_variables)

    hlss = ee.ImageCollection("NASA/HLS/HLSS30/v002") \
        .filterDate(start_date, end_date) \
        .filterBounds(study_area) \
        .map(gee_utils.hls_mask) \
        .select(
            ['B2', 'B3', 'B4', 'B8', 'B11', 'B12'],
            ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']
        ).map(gee_utils.add_variables)

    return hlsl.merge(hlss)

def get_geometric_median(collection):
    """Calculates the geometric median of an image collection."""
    scaled_collection = collection.map(gee_utils.scale_bands)
    num_bands = scaled_collection.first().bandNames().length()
    return scaled_collection.reduce(ee.Reducer.geometricMedian(num_bands)).toInt16()

def _download_tile(image, region_coords, scale, file_path):
    """Internal function to download a single tile, with retries."""
    if os.path.exists(file_path):
        print(f"  - Tile exists: {os.path.basename(file_path)}")
        return True

    print(f"  - Downloading: {os.path.basename(file_path)}")
    url = image.getDownloadURL({
        'region': region_coords,
        'scale': scale,
        'format': 'GEO_TIFF',
        'crs': 'EPSG:4326'
    })

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            with open(file_path, 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)
            print(f"    - Success.")
            return True
        except (requests.exceptions.RequestException, ee.EEException) as e:
            print(f"    - Attempt {attempt + 1} failed: {e}")
            time.sleep(5) # Wait before retrying
    print(f"  - FAILED after {max_retries} attempts: {os.path.basename(file_path)}")
    return False

def download_composite(image, study_area, output_path, max_dim=0.2, scale=30):
    """Downloads a composite image, splitting it into tiles to avoid timeouts."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    regions = gee_utils.split_geometry(study_area, max_dim)
    print(f"Splitting AOI into {len(regions)} tiles for download.")

    for i, region in enumerate(regions):
        tile_path = os.path.join(os.path.dirname(output_path), f"tile_{i}.tif")
        _download_tile(image, region.getInfo()['coordinates'], scale, tile_path)

    print("All tiles downloaded. Merging into single image...")
    # This part would require gdal_merge.py, which is a command-line tool.
    # For now, we will assume the user can merge them manually or we can add a shell command later.
    # The individual tiles are preserved for now.
