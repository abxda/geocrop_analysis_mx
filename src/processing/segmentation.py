from rsgislib.segmentation import shepherdseg
from rsgislib.vectorutils import createvectors
import os

def run_segmentation(config, composite_image_path):
    """Performs Shepherd segmentation on a given composite image."""
    print("\n--- Starting Image Segmentation ---")
    
    # Define output paths
    output_base = os.path.join(config['output_dir'], config['aoi_name'], 'segmentation')
    os.makedirs(output_base, exist_ok=True)
    clumps_path = os.path.join(output_base, config['output_names']['segmented_clumps'])
    shapefile_path = os.path.join(output_base, config['output_names']['segmented_polygons'])
    tmp_dir = os.path.join(output_base, 'rsgislib_tmp')

    if os.path.exists(shapefile_path):
        print(f"- Segmentation output already exists: {os.path.basename(shapefile_path)}")
        return clumps_path, shapefile_path

    # Get parameters from config
    params = config['segmentation_params']

    print(f"- Running Shepherd segmentation on {os.path.basename(composite_image_path)}")
    print(f"- Parameters: Clusters={params['num_clusters']}, Min Pixels={params['min_n_pxls']}")

    shepherdseg.run_shepherd_segmentation(
        input_img=composite_image_path,
        out_clumps_img=clumps_path,
        tmp_dir=tmp_dir,
        num_clusters=params['num_clusters'],
        min_n_pxls=params['min_n_pxls'],
        bands=params['bands'],
        dist_thres=params['dist_thres'],
        sampling=100,
        km_max_iter=200,
        process_in_mem=True
    )

    print(f"- Polygonizing raster to vector: {os.path.basename(shapefile_path)}")
    createvectors.polygonise_raster_to_vec_lyr(
        input_img=clumps_path, 
        out_vec_file=shapefile_path, 
        out_vec_lyr="clusters", 
        out_format="ESRI Shapefile"
    )
    
    print("- Segmentation complete.")
    return clumps_path, shapefile_path
