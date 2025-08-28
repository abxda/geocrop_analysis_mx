import geopandas as gpd
import pandas as pd
import rasterio
import rasterio.features
import numpy as np
import os

def label_and_rasterize(output_dir, data_dir, config):
    """Performs a vector-based purity filter and then rasterizes the pure labels."""
    print("\n--- Starting Segment Labeling (with Purity Filter) ---")

    # --- Define Paths ---
    segmentation_dir = os.path.join(output_dir, 'segmentation')
    labeling_dir = os.path.join(output_dir, 'labeling')
    os.makedirs(labeling_dir, exist_ok=True)

    segmented_polygons_path = os.path.join(segmentation_dir, config['output_names']['segmented_polygons'])
    ground_truth_path = os.path.join(data_dir, 'labels', config['labels_file'])
    # This is now an intermediate but important, inspectable output
    pure_labeled_polygons_path = os.path.join(labeling_dir, config['output_names']['labeled_polygons'])
    rasterized_labels_path = os.path.join(labeling_dir, config['output_names']['rasterized_labels'])
    reference_image_path = os.path.join(segmentation_dir, config['output_names']['segmentation_image'])

    if os.path.exists(rasterized_labels_path):
        print(f"- Labeled and rasterized outputs already exist. Skipping.")
        return pure_labeled_polygons_path, rasterized_labels_path

    # --- 1. Vector-based Purity Filter ---
    print("- Loading segments and ground truth labels for purity analysis.")
    gdf_segments = gpd.read_file(segmented_polygons_path)
    gdf_labels = gpd.read_file(ground_truth_path)

    if gdf_segments.crs != gdf_labels.crs:
        gdf_labels = gdf_labels.to_crs(gdf_segments.crs)

    print("- Performing spatial join...")
    # Use 'inner' join to only keep segments that intersect with labels
    sjoined = gpd.sjoin(gdf_segments, gdf_labels, how='inner', predicate='intersects')

    # Find unique labels per segment
    label_field = config['labels_field_name']
    labels_per_segment = sjoined.groupby('raster_val')[label_field].unique().apply(list)
    
    # Filter for segments with only one unique label
    pure_segments_ids = labels_per_segment[labels_per_segment.str.len() == 1].index
    pure_labels = labels_per_segment[labels_per_segment.str.len() == 1].str[0]
    
    print(f"- Found {len(pure_segments_ids)} purely labeled segments.")

    # Create the final GeoDataFrame of pure polygons
    gdf_pure = gdf_segments[gdf_segments['raster_val'].isin(pure_segments_ids)].copy()
    gdf_pure['label'] = gdf_pure['raster_val'].map(pure_labels)
    
    print(f"- Saving pure labeled polygons to: {os.path.basename(pure_labeled_polygons_path)}")
    gdf_pure.to_file(pure_labeled_polygons_path)

    # --- 2. Rasterize Pure Labels ---
    print(f"- Rasterizing pure polygons...")
    gdf_pure['class_int'], class_names = pd.factorize(gdf_pure['label'])
    gdf_pure['class_int'] += 1
    
    with rasterio.open(reference_image_path) as ref_src:
        ref_meta = ref_src.meta

    shapes = ((geom, value) for geom, value in zip(gdf_pure.geometry, gdf_pure.class_int))
    rasterized_labels = rasterio.features.rasterize(
        shapes=shapes, 
        out_shape=(ref_meta['height'], ref_meta['width']),
        transform=ref_meta['transform'],
        fill=0, # No-data value
        dtype=rasterio.uint16
    )

    ref_meta.update(dtype=rasterio.uint16, count=1, nodata=0)
    with rasterio.open(rasterized_labels_path, 'w', **ref_meta) as dst:
        dst.write(rasterized_labels, 1)
    
    print(f"- Saved rasterized pure labels to: {os.path.basename(rasterized_labels_path)}")
    print("- Labeling phase complete.")
    return pure_labeled_polygons_path, rasterized_labels_path