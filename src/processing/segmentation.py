import rasterio
import rasterio.features
import geopandas as gpd
import numpy as np
from pyshepseg import shepseg
import os

def run_segmentation(segmentation_params, composite_image_path, output_dir, output_names):
    """Performs Shepherd segmentation using the pyshepseg library and polygonizes the result."""
    print("\n--- Starting Image Segmentation (using pyshepseg) ---")
    
    os.makedirs(output_dir, exist_ok=True)
    # Ensure output is a TIF file, as KEA is specific to rsgislib
    clumps_path = os.path.join(output_dir, output_names['segmented_clumps'].replace('.kea', '.tif'))
    shapefile_path = os.path.join(output_dir, output_names['segmented_polygons'])

    if os.path.exists(shapefile_path):
        print(f"- Segmentation output already exists: {os.path.basename(shapefile_path)}")
        return clumps_path, shapefile_path

    print(f"- Reading composite image: {os.path.basename(composite_image_path)}")
    with rasterio.open(composite_image_path) as src:
        # pyshepseg expects (bands, rows, cols)
        img_array = src.read()
        transform = src.transform
        crs = src.crs
        # pyshepseg handles nulls with a specific parameter, so we don't need to mask here.
        # Assuming the null value is something identifiable, e.g., the raster's nodata value.
        img_null_val = src.nodata

    print(f"- Running Shepherd segmentation with pyshepseg...")
    # Note: pyshepseg parameters might differ slightly from rsgislib's version.
    # We are mapping them as closely as possible.
    seg_result = shepseg.doShepherdSegmentation(
        img_array,
        numClusters=segmentation_params.get('num_clusters', 80),
        minSegmentSize=segmentation_params.get('min_n_pxls', 100),
        imgNullVal=img_null_val
    )

    # The result is an object containing the segmentation image as a numpy array
    segments_array = seg_result.segimg

    # Save the segmentation result as a raster (GeoTIFF)
    print(f"- Saving segmentation raster to: {os.path.basename(clumps_path)}")
    with rasterio.open(
        clumps_path,
        'w',
        driver='GTiff',
        height=segments_array.shape[0],
        width=segments_array.shape[1],
        count=1,
        dtype=segments_array.dtype,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(segments_array, 1)

    # Polygonize the output raster to Shapefile
    print(f"- Polygonizing raster to vector: {os.path.basename(shapefile_path)}")
    results = (
        {'properties': {'raster_val': v}, 'geometry': s}
        for i, (s, v) 
        in enumerate(rasterio.features.shapes(segments_array, transform=transform)))

    gdf = gpd.GeoDataFrame.from_features(list(results))
    gdf.set_crs(crs=crs, inplace=True)
    gdf.to_file(shapefile_path, driver='ESRI Shapefile')
    
    print("- Segmentation and polygonizing complete.")
    return clumps_path, shapefile_path