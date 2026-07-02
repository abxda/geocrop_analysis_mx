"""Optional Google Earth Engine download backend.

The pipeline's default backend ("stac") needs no account and runs the
compositing locally. Users who already have a Google Earth Engine account
can instead set

    download_backend: "gee"

in their config file to compute the geometric medians on Google's servers
and only download the finished composites — much less local CPU time, at
the cost of requiring GEE credentials. GEE is strictly OPTIONAL: nothing
in this module is imported unless the user opts in, and the earthengine-api
package is not part of requirements.txt.

This wraps the original (pre-STAC) GEE modules of the project — gee_utils,
multispectral and radar — which are kept verbatim; the only modernisation
is that downloaded tiles are merged with rasterio instead of the
gdal_merge.py CLI, so no GDAL installation is needed.
"""

import glob
import os
import shutil

from . import stac_utils

_log = stac_utils.log

HELP_INSTALL = (
    "The optional Google Earth Engine backend needs the earthengine-api "
    "package, which is not installed.\n"
    "  1. Install it with:  pip install earthengine-api\n"
    "  2. Authenticate once with:  earthengine authenticate\n"
    "Or simply remove/set download_backend: \"stac\" in your config file to "
    "use the default backend, which needs no account."
)

HELP_AUTH = (
    "Google Earth Engine is installed but could not be initialised.\n"
    "  1. Run:  earthengine authenticate  (a browser window will open)\n"
    "  2. If GEE asks for a Cloud project, create one at "
    "https://console.cloud.google.com and run:\n"
    "     earthengine authenticate --project YOUR_PROJECT_ID\n"
    "Or set download_backend: \"stac\" in your config file to use the "
    "default backend, which needs no account."
)


def _import_ee():
    """Imports earthengine-api with a friendly, actionable error message."""
    try:
        import ee
        return ee
    except ImportError:
        raise SystemExit(f"\n[GEE BACKEND] {HELP_INSTALL}")


def initialize():
    """Initialises GEE with clear guidance when authentication is missing."""
    ee = _import_ee()
    try:
        ee.Initialize()
        _log("- Google Earth Engine initialised (optional backend enabled).")
    except Exception as error:
        raise SystemExit(f"\n[GEE BACKEND] {HELP_AUTH}\n\nOriginal error: {error}")
    return ee


def merge_tiles(tile_paths, output_path):
    """Merges downloaded GEE tiles into one GeoTIFF using rasterio (no GDAL
    CLI needed) and removes the temporary tile directory on success."""
    import rasterio
    from rasterio.merge import merge as rio_merge

    if not tile_paths or not isinstance(tile_paths, list):
        _log(f"- No new tiles to merge for {os.path.basename(output_path)}.")
        return
    _log(f"- Merging {len(tile_paths)} tiles into {os.path.basename(output_path)}...")
    sources = [rasterio.open(p) for p in tile_paths]
    try:
        mosaic, transform = rio_merge(sources)
        profile = sources[0].profile.copy()
        profile.update(height=mosaic.shape[1], width=mosaic.shape[2],
                       transform=transform, compress="LZW")
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(mosaic)
    finally:
        for src in sources:
            src.close()
    shutil.rmtree(os.path.dirname(tile_paths[0]), ignore_errors=True)
    _log("- Merge successful.")


def run_download_phase(config, study_area_geojson, output_dir, monthly_ranges):
    """GEE flavour of the download phase: geometric medians are computed on
    Google's servers and only the finished composites are downloaded.

    Produces exactly the same files, names and grid as the STAC backend, so
    every later phase (segment/label/extract/train/predict) is unaffected.
    """
    ee = initialize()
    from . import multispectral as gee_multispectral
    from . import radar as gee_radar

    study_area = ee.Geometry(study_area_geojson)

    _log("--- Processing Main Segmentation Composite (via Google Earth Engine) ---")
    if config['segmentation_composite_uses_full_study_period']:
        seg_start = config['study_period']['start_date']
        seg_end = config['study_period']['end_date']
    else:
        seg_start = config['segmentation_composite_custom_range']['start_date']
        seg_end = config['segmentation_composite_custom_range']['end_date']

    main_composite_path = os.path.join(
        output_dir, 'segmentation', config['output_names']['segmentation_image'])
    os.makedirs(os.path.dirname(main_composite_path), exist_ok=True)
    hls = gee_multispectral.get_hls_collection(seg_start, seg_end, study_area)
    if hls.size().getInfo() > 0:
        composite = gee_multispectral.get_geometric_median(hls)
        tiles = gee_multispectral.download_composite(composite, study_area, main_composite_path)
        merge_tiles(tiles, main_composite_path)
    else:
        _log("No images found for the main composite period. Skipping.")

    _log("--- Processing Monthly Composites (via Google Earth Engine) ---")
    for month_index, (start, end) in enumerate(monthly_ranges, start=1):
        month_str = start[:7]
        _log(f"-- Processing month {month_index} of {len(monthly_ranges)}: {month_str} --")

        optical_path = os.path.join(output_dir, 'multispectral', month_str,
                                    f"multispectral_{month_str}.tif")
        os.makedirs(os.path.dirname(optical_path), exist_ok=True)
        hls_month = gee_multispectral.get_hls_collection(start, end, study_area)
        if hls_month.size().getInfo() > 0:
            composite = gee_multispectral.get_geometric_median(hls_month)
            tiles = gee_multispectral.download_composite(composite, study_area, optical_path)
            merge_tiles(tiles, optical_path)
        else:
            _log(f"No optical images found for {month_str}. Skipping.")

        radar_path = os.path.join(output_dir, 'radar', month_str,
                                  f"radar_{month_str}.tif")
        os.makedirs(os.path.dirname(radar_path), exist_ok=True)
        s1_month = gee_radar.get_s1_collection(start, end, study_area)
        if s1_month.size().getInfo() > 0:
            composite = s1_month.median()
            tiles = gee_multispectral.download_composite(composite, study_area, radar_path)
            merge_tiles(tiles, radar_path)
        else:
            _log(f"No radar images found for {month_str}. Skipping.")
