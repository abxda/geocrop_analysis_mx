import os
import subprocess
import glob
import shutil

def _log(message):
    from datetime import datetime
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def run_compression_phase(output_dir, config):
    """Compresses all mosaic files from the main output and all prediction subdirectories."""
    _log("--- Executing PHASE: Compress Mosaics ---")

    gdal_translate_path = shutil.which('gdal_translate')
    if not gdal_translate_path:
        _log("  - FAILED: 'gdal_translate' command not found. Is GDAL installed and in your system's PATH?")
        return
    _log(f"- Using gdal_translate found at: {gdal_translate_path}")

    # The single, top-level directory for all compressed mosaics
    compressed_dir = os.path.join(output_dir, 'mosaics_compressed')
    os.makedirs(compressed_dir, exist_ok=True)

    # --- Build list of all directories to scan ---
    dirs_to_scan = [output_dir]
    prediction_dirs = glob.glob(os.path.join(output_dir, 'prediction_*'))
    dirs_to_scan.extend(prediction_dirs)
    _log(f"- Scanning for mosaics in: {dirs_to_scan}")

    # --- Build list of all mosaics to compress ---
    mosaics_to_compress = []
    for scan_dir in dirs_to_scan:
        # Add monthly mosaics
        mosaics_to_compress.extend(glob.glob(os.path.join(scan_dir, "multispectral", "**", "*.tif"), recursive=True))
        mosaics_to_compress.extend(glob.glob(os.path.join(scan_dir, "radar", "**", "*.tif"), recursive=True))
        # Add main composite
        seg_composite_name = config['output_names']['segmentation_image']
        seg_composite_path = os.path.join(scan_dir, 'segmentation', seg_composite_name)
        if os.path.exists(seg_composite_path):
            mosaics_to_compress.append(seg_composite_path)

    if not mosaics_to_compress:
        _log("- No mosaics found to compress.")
        return

    _log(f"Found {len(mosaics_to_compress)} unique mosaics to compress.")

    for input_path in mosaics_to_compress:
        filename = os.path.basename(input_path)
        
        # --- Determine the correct output path and name ---
        # If the mosaic is a main composite from a prediction year, rename it
        if filename == config['output_names']['segmentation_image'] and 'prediction_' in input_path:
            try:
                year = os.path.basename(os.path.dirname(os.path.dirname(input_path))).split('_')[-1]
                base, ext = os.path.splitext(filename)
                output_filename = f"{base}_{year}{ext}"
            except (IndexError, ValueError):
                # Fallback if the directory structure is unexpected
                output_filename = filename
        else:
            output_filename = filename
        
        output_path = os.path.join(compressed_dir, output_filename)

        if os.path.exists(output_path):
            _log(f"- Compressed file already exists: {output_filename}. Skipping.")
            continue

        _log(f"- Compressing {filename} -> {output_filename}...")

        command = [
            gdal_translate_path,
            '-co', 'COMPRESS=DEFLATE',
            '-co', 'PREDICTOR=2',
            '-co', 'ZLEVEL=9',
            input_path,
            output_path
        ]

        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            input_size = os.path.getsize(input_path) / (1024 * 1024)
            output_size = os.path.getsize(output_path) / (1024 * 1024)
            _log(f"  - Success. Size: {input_size:.2f} MB -> {output_size:.2f} MB")
        except subprocess.CalledProcessError as e:
            _log(f"  - FAILED to compress {filename}. Error: {e.stderr}")

    _log("--- Compress Mosaics phase complete ---")

