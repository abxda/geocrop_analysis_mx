from rsgislib.segmentation import shepherdseg
from rsgislib.vectorutils import createvectors
import os

def run_segmentation(segmentation_params, composite_image_path, output_dir, output_names):
    """Performs Shepherd segmentation on a given composite image."""
    print("\n--- Starting Image Segmentation ---")
    
    os.makedirs(output_dir, exist_ok=True)
    clumps_path = os.path.join(output_dir, output_names['segmented_clumps'])
    shapefile_path = os.path.join(output_dir, output_names['segmented_polygons'])
    tmp_dir = os.path.join(output_dir, 'rsgislib_tmp')
    os.makedirs(tmp_dir, exist_ok=True) # Explicitly create tmp_dir to handle rsgislib bug on Windows

    if os.path.exists(shapefile_path):
        print(f"- Segmentation output already exists: {os.path.basename(shapefile_path)}")
        return clumps_path, shapefile_path

    print(f"- Running Shepherd segmentation on {os.path.basename(composite_image_path)}")
    print(f"- Parameters: Clusters={segmentation_params['num_clusters']}, Min Pixels={segmentation_params['min_n_pxls']}")

    shepherdseg.run_shepherd_segmentation(
        input_img=composite_image_path,
        out_clumps_img=clumps_path,
        tmp_dir=tmp_dir,
        num_clusters=segmentation_params['num_clusters'],
        min_n_pxls=segmentation_params['min_n_pxls'],
        bands=segmentation_params['bands'],
        dist_thres=segmentation_params['dist_thres'],
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