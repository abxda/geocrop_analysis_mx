import ee
from . import gee_utils

def _calculate_rvi(image):
    """Calculates Radar Vegetation Index (RVI)."""
    vv = image.select('VV')
    vh = image.select('VH')
    # Formula for RVI - Note: There are several formulas for RVI. This one is based on the original script.
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