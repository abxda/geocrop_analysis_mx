"""External raster layers as additional model features.

Many users already have rasters produced elsewhere — a DEM, slope,
precipitation, temperature, land use, etc. — and want them as extra
predictor variables. Declaring them in the config file is enough:

    extra_layers:
      - path: "../data/my_aoi/dem.tif"     # absolute paths also work
        prefix: "dem_"
      - path: "../data/my_aoi/slope.tif"
        prefix: "slope_"

Each layer is validated with clear messages (does the file exist? does it
overlap the study area? what CRS is it in?) and, when its CRS differs from
the pipeline grid (EPSG:4326), it is reprojected automatically into
`<outputs>/extra_layers/` — the original file is never modified. The
prepared layers then flow through the exact same per-segment statistics
(mean/stdev/min/max/count/sum per band) as the satellite mosaics, with
column names like  dem_mean  (single-band) or  clima_b2_mean  (multiband).

No knowledge of GIS reprojection or code changes is needed: fix-it hints
are printed for every problem the validation finds.
"""

import os

from data_download import stac_utils

_log = stac_utils.log

PIPELINE_CRS = "EPSG:4326"


def prepare_extra_layers(config, output_dir, aoi_geometry):
    """Validates every configured extra layer and returns feature-extraction
    entries: [{'path': ..., 'prefix': ...}, ...].

    Problems do not abort the pipeline: each bad layer is skipped with a
    clear explanation, and the good ones proceed."""
    layers = config.get("extra_layers") or []
    if not layers:
        return []

    import rasterio

    _log(f"--- Preparing {len(layers)} external raster layer(s) ---")
    prepared = []
    seen_prefixes = set()
    for index, layer in enumerate(layers, start=1):
        label = f"extra layer {index}"
        if not isinstance(layer, dict) or "path" not in layer:
            _log(f"- {label}: SKIPPED. Each entry under extra_layers needs at "
                 f"least a 'path:'. Example:\n"
                 f"    extra_layers:\n      - path: \"../data/dem.tif\"\n        prefix: \"dem_\"")
            continue

        path = layer["path"]
        prefix = layer.get("prefix") or _default_prefix(path)
        if not prefix.endswith("_"):
            prefix += "_"
        if prefix in seen_prefixes:
            _log(f"- {label} ({path}): SKIPPED. The prefix '{prefix}' is already "
                 f"used by another extra layer; give each layer a unique prefix.")
            continue

        if not os.path.isabs(path):
            path = os.path.normpath(os.path.join(os.getcwd(), path))
        if not os.path.exists(path):
            _log(f"- {label}: SKIPPED. File not found: {path}\n"
                 f"    Check the 'path:' in your config file (relative paths "
                 f"are resolved from the folder you run the pipeline from).")
            continue

        try:
            with rasterio.open(path) as src:
                crs, bounds, band_count = src.crs, src.bounds, src.count
        except rasterio.errors.RasterioIOError as error:
            _log(f"- {label}: SKIPPED. The file exists but could not be opened "
                 f"as a raster ({error}). Supported formats include GeoTIFF.")
            continue

        if crs is None:
            _log(f"- {label} ({os.path.basename(path)}): SKIPPED. The raster has "
                 f"no coordinate system defined, so it cannot be located on the "
                 f"map. Open it in QGIS and use 'Assign projection' to fix it.")
            continue

        ready_path = path
        if crs.to_string() != PIPELINE_CRS:
            ready_path = _reproject(path, output_dir, prefix)
            _log(f"- {label} ({os.path.basename(path)}): reprojected from "
                 f"{crs.to_string()} to {PIPELINE_CRS} -> {os.path.relpath(ready_path)}")

        if not _overlaps_aoi(ready_path, aoi_geometry):
            _log(f"- {label} ({os.path.basename(path)}): SKIPPED. The raster does "
                 f"not overlap the study area — check that it covers your AOI.")
            continue

        example = f"{prefix}mean" if band_count == 1 else f"{prefix}b1_mean"
        _log(f"- {label}: OK. {os.path.basename(path)} ({band_count} band(s)) will "
             f"add features with prefix '{prefix}' (e.g. {example}).")
        seen_prefixes.add(prefix)
        prepared.append({"path": ready_path, "prefix": prefix})

    _log(f"--- {len(prepared)} of {len(layers)} external layer(s) ready ---")
    return prepared


def _default_prefix(path):
    """Derives a feature prefix from the file name: dem.tif -> dem_."""
    stem = os.path.splitext(os.path.basename(path))[0]
    safe = "".join(ch if ch.isalnum() else "_" for ch in stem.lower()).strip("_")
    return (safe or "extra") + "_"


def _reproject(path, output_dir, prefix):
    """Reprojects a raster to the pipeline CRS, cached under
    <output_dir>/extra_layers/. The source file is never touched."""
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling

    cache_dir = os.path.join(output_dir, "extra_layers")
    os.makedirs(cache_dir, exist_ok=True)
    out_path = os.path.join(cache_dir, f"{prefix}wgs84.tif")

    with rasterio.open(path) as src:
        if os.path.exists(out_path) and os.path.getmtime(out_path) >= os.path.getmtime(path):
            return out_path
        transform, width, height = calculate_default_transform(
            src.crs, PIPELINE_CRS, src.width, src.height, *src.bounds)
        profile = src.profile.copy()
        profile.update(crs=PIPELINE_CRS, transform=transform, width=width,
                       height=height, compress="LZW")
        with rasterio.open(out_path, "w", **profile) as dst:
            for band in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band),
                    destination=rasterio.band(dst, band),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=PIPELINE_CRS,
                    resampling=Resampling.bilinear,
                )
    return out_path


def _overlaps_aoi(raster_path, aoi_geometry):
    """True when the raster's bounds intersect the AOI geometry."""
    import rasterio
    from shapely.geometry import box, shape

    with rasterio.open(raster_path) as src:
        raster_box = box(*src.bounds)
    return raster_box.intersects(shape(aoi_geometry))
