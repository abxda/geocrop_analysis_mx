import geopandas as gpd
import pandas as pd
import rasterio
import rasterio.features
import numpy as np
import os
from rsgislib import rastergis

def label_and_rasterize(config, segmented_polygons_path, clumps_path, reference_image_path):
    """Spatially joins segments with labels, rasterizes them, and populates the RAT."""
    print("\n--- Starting Segment Labeling and Rasterization ---")

    # Define paths
    aoi_dir = os.path.join(config['data_dir'], config['aoi_name'])
    labels_gpkg_path = os.path.join(aoi_dir, 'labels', config['labels_file'])
    output_base = os.path.join(config['output_dir'], config['aoi_name'], 'labeling')
    os.makedirs(output_base, exist_ok=True)
    labeled_shp_path = os.path.join(output_base, config['output_names']['labeled_polygons'])
    rasterized_labels_path = os.path.join(output_base, config['output_names']['rasterized_labels'])

    if os.path.exists(rasterized_labels_path):
        print(f"- Labeled and rasterized outputs already exist.")
        return rasterized_labels_path

    # 1. Load data
    print("- Loading segments and ground truth labels.")
    polygons = gpd.read_file(segmented_polygons_path)
    samples = gpd.read_file(labels_gpkg_path)

    if polygons.crs != samples.crs:
        samples = samples.to_crs(polygons.crs)

    # 2. Spatial Join
    print("- Performing spatial join to label polygons.")
    intersecting_data = gpd.sjoin(polygons, samples, predicate='intersects')

    # 3. Aggregate labels for each polygon
    label_field = config['labels_field_name']
    grouped_names = intersecting_data.groupby(level=0)[label_field].apply(lambda x: list(x.dropna().unique()))
    temp_df = pd.DataFrame(grouped_names.tolist(), index=grouped_names.index)
    # Rename columns to etiqueta_1, etiqueta_2, etc.
    temp_df.columns = [f'etiqueta_{i+1}' for i in range(temp_df.shape[1])]
    results = polygons.join(temp_df)

    # 4. Filter for polygons with exactly one unique label
    print("- Filtering for polygons with a single, unique label.")
    single_label_mask = results['etiqueta_1'].notna() & results['etiqueta_2'].isna()
    filtered_results = results[single_label_mask].copy()
    filtered_results.rename(columns={'etiqueta_1': 'label'}, inplace=True)

    # 5. Create integer classes for rasterization
    filtered_results['class_int'], class_map = pd.factorize(filtered_results['label'])
    filtered_results['class_int'] += 1 # Start classes from 1
    print(f"- Found {len(class_map)} classes: {class_map.to_list()}")
    
    # Save labeled shapefile
    filtered_results.to_file(labeled_shp_path)

    # 6. Rasterize labeled polygons
    print(f"- Rasterizing labeled polygons to {os.path.basename(rasterized_labels_path)}")
    with rasterio.open(reference_image_path) as ref_tiff:
        ref_meta = ref_tiff.meta

    shapes = ((geom, value) for geom, value in zip(filtered_results.geometry, filtered_results.class_int))
    
    burned_array = rasterio.features.rasterize(
        shapes=shapes, 
        out_shape=(ref_meta['height'], ref_meta['width']),
        transform=ref_meta['transform'],
        fill=0, # Use 0 as the no-data value for the class raster
        dtype=rasterio.uint16
    )

    ref_meta.update(dtype=rasterio.uint16, count=1, nodata=0)
    with rasterio.open(rasterized_labels_path, 'w', **ref_meta) as dst:
        dst.write(burned_array, 1)

    # 7. Populate RAT of the original clumps file
    print(f"- Populating RAT of {os.path.basename(clumps_path)} with class proportions.")
    rastergis.populate_rat_with_cat_proportions(rasterized_labels_path, clumps_path, out_cols_name='klass_', maj_col_name='klass')

    print("- Labeling process complete.")
    return rasterized_labels_path
