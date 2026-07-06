"""HLS (Harmonized Landsat Sentinel-2) download via STAC/COG.

Replaces multispectral.py: instead of GEE's NASA/HLS collections it searches
Microsoft Planetary Computer for hls2-l30 / hls2-s30 items, streams only the
AOI window of each COG, applies the Fmask cloud/shadow mask, computes the
seven vegetation indices and reduces the stack to a 13-band geometric-median
composite written directly as a single GeoTIFF (no tiling/merge step needed).
"""

import os
import numpy as np

from . import stac_utils
from . import cog_fetch

# Asset-name crosswalk to the common band names used across the pipeline.
# L30 (Landsat 8/9) and S30 (Sentinel-2) use different HLS band ids; the
# selection mirrors the original GEE code (B2-B7 for L30, B2/3/4/8/11/12
# for S30).
L30_BANDS = {"B02": "blue", "B03": "green", "B04": "red",
             "B05": "nir", "B06": "swir1", "B07": "swir2"}
S30_BANDS = {"B02": "blue", "B03": "green", "B04": "red",
             "B08": "nir", "B11": "swir1", "B12": "swir2"}

# Optical providers:
#  - nasa: HLS v2.0 from LPCLOUD, the authoritative complete archive; asset
#    reads require a free Earthdata Login token (EARTHDATA_TOKEN).
#  - mpc: HLS v2.0 from Planetary Computer, anonymous access but with
#    archive gaps (e.g. little/no S30 before ~2020 over Mexico).
#  - earthsearch: Sentinel-2 L2A COGs from Element 84 / AWS. Not HLS (no
#    Landsat), but fully anonymous AND CORS-enabled, so it is the provider
#    that works inside a browser (Pyodide/WebAssembly).
S2_BANDS = {"blue": "blue", "green": "green", "red": "red",
            "nir": "nir", "swir16": "swir1", "swir22": "swir2"}

PROVIDERS = {
    "nasa": {"HLSL30_2.0": L30_BANDS, "HLSS30_2.0": S30_BANDS},
    "mpc": {"hls2-l30": L30_BANDS, "hls2-s30": S30_BANDS},
    "earthsearch": {"sentinel-2-l2a": S2_BANDS},
}
# Quality band per provider style: HLS ships Fmask, S2 L2A ships SCL.
QA_BAND = {"nasa": "Fmask", "mpc": "Fmask", "earthsearch": "scl"}

HLS_SCALE = 0.0001   # HLS and S2 L2A COGs store reflectance * 10000 as int16
HLS_FILL = -9999
S2_FILL = 0          # Sentinel-2 L2A uses DN 0 as nodata
S2_BASELINE_OFFSET = 1000  # DN offset added from processing baseline 04.00


_log = stac_utils.log


def resolve_provider(provider="auto"):
    """Resolves the optical provider and opens its catalog.

    "auto" picks earthsearch inside a browser (the only CORS-enabled
    optical source), NASA LPCLOUD when an Earthdata token is available
    (complete HLS archive), and Planetary Computer otherwise."""
    if provider == "auto":
        if cog_fetch.is_emscripten():
            _log("- Running in WebAssembly: using Earth Search Sentinel-2 "
                 "L2A (the CORS-enabled optical source).")
            provider = "earthsearch"
        elif stac_utils.earthdata_token():
            provider = "nasa"
        else:
            _log("- No EARTHDATA_TOKEN found: using Planetary Computer HLS "
                 "(archive has gaps; set a free Earthdata token for the "
                 "complete NASA archive).")
            provider = "mpc"
    if provider == "nasa":
        stac_utils.check_earthdata_token(stac_utils.earthdata_token())
    catalogs = {
        "nasa": stac_utils.get_nasa_catalog,
        "mpc": stac_utils.get_catalog,
        "earthsearch": stac_utils.get_earthsearch_catalog,
    }
    return provider, catalogs[provider]()


def search_hls_items(catalog, start_date, end_date, aoi_geometry, provider="mpc"):
    """Searches both HLS collections; returns {collection_id: [items]}."""
    results = {}
    for collection_id in PROVIDERS[provider]:
        search = catalog.search(
            collections=[collection_id],
            intersects=aoi_geometry,
            datetime=f"{start_date}/{end_date}",
        )
        results[collection_id] = list(search.items())
    return results


def load_hls_stack(items_by_collection, geobox, provider="mpc"):
    """Loads and masks all HLS items onto the target grid.

    Returns an xarray.Dataset with dims (time, y, x) and float reflectance
    variables blue/green/red/nir/swir1/swir2 (NaN where masked), or None if
    there are no items.

    Uses odc-stac (windowed /vsicurl reads) on regular Python; inside
    Pyodide/WebAssembly it falls back to cog_fetch (browser fetch +
    in-memory warp), where /vsicurl is unavailable.
    """
    import xarray as xr

    parts = []
    for collection_id, items in items_by_collection.items():
        if not items:
            continue
        crosswalk = PROVIDERS[provider][collection_id]
        qa_band = QA_BAND[provider]
        # Sentinel-2 items processed with baseline >= 04.00 carry a +1000 DN
        # offset unless the catalog already removed it; load each offset
        # group separately so the correction is exact per scene.
        if provider == "earthsearch":
            groups = {}
            for item in items:
                groups.setdefault(_s2_dn_offset(item), []).append(item)
            groups = list(groups.items())
        else:
            groups = [(0, items)]

        for dn_offset, group_items in groups:
            ds = _load_group(group_items, crosswalk, qa_band, geobox)
            if provider == "earthsearch":
                qa = ds[qa_band].fillna(0)
                clear = xr.apply_ufunc(stac_utils.s2_clear_mask, qa)
                fill = S2_FILL
            else:
                qa = ds[qa_band].fillna(255)
                clear = xr.apply_ufunc(stac_utils.hls_clear_mask, qa)
                fill = HLS_FILL
            ds = ds.drop_vars(qa_band)
            for name in ds.data_vars:
                band = (ds[name].astype("float32") - dn_offset) * HLS_SCALE
                band = band.where((ds[name] != fill) & ds[name].notnull() & clear)
                ds[name] = band
            parts.append(ds)

    if not parts:
        return None
    stack = xr.concat(parts, dim="time") if len(parts) > 1 else parts[0]
    return stack.sortby("time")


# NASA's CMR-STAC items do not advertise the nodata value of HLS assets, so
# without this hint odc-stac treats the -9999 fill at tile edges as valid
# data when mosaicking same-day granules from adjacent MGRS tiles. In tile
# overlap zones (the AOI-wide "stripe" artifact) the fill from the first
# tile then shadows the real data of the second one. Declaring nodata per
# asset makes the fuser fall through to the neighbouring granule instead.
# (Earth Search / Planetary Computer items carry proper raster metadata, so
# this is only needed for the HLS collections.)
HLS_STAC_CFG = {
    "*": {"assets": {
        "*": {"data_type": "int16", "nodata": HLS_FILL},
        "Fmask": {"data_type": "uint8", "nodata": 255},
    }},
}


def _load_group(items, crosswalk, qa_band, geobox):
    """Loads one homogeneous group of items onto the geobox (odc-stac on
    regular Python, cog_fetch inside WebAssembly).

    Loads one solar day at a time so progress (with a remaining-time
    estimate) is reported while the scenes stream in — the mosaicking
    result is identical to a single grouped load because solar days are
    independent slices of the time axis."""
    if cog_fetch.is_emscripten():
        asset_map = dict(crosswalk)
        asset_map[qa_band] = qa_band
        return cog_fetch.load_stack(items, asset_map, geobox,
                                    resampling="nearest", fill=np.nan)
    import xarray as xr
    from odc.stac import load as odc_load

    is_hls = qa_band == "Fmask"
    by_day = {}
    for item in items:
        by_day.setdefault(str(item.datetime.date()), []).append(item)

    collection = items[0].collection_id
    progress = stac_utils.Progress(
        f"downloading {len(items)} scenes / {len(by_day)} solar days "
        f"({collection})", len(by_day), step_pct=20)
    parts = []
    for day in sorted(by_day):
        parts.append(odc_load(
            by_day[day],
            bands=list(crosswalk) + [qa_band],
            geobox=geobox,
            groupby="solar_day",
            resampling="nearest",
            dtype=None if is_hls else "int16",
            stac_cfg=HLS_STAC_CFG if is_hls else None,
        ))
        progress.update()
    progress.finish()
    ds = xr.concat(parts, dim="time") if len(parts) > 1 else parts[0]
    return ds.rename(crosswalk)


def _s2_dn_offset(item):
    """DN offset still present in a Sentinel-2 L2A item (0 or 1000)."""
    if item.properties.get("earthsearch:boa_offset_applied", False):
        return 0
    baseline = item.properties.get("s2:processing_baseline", "0.0")
    try:
        needs_offset = float(baseline) >= 4.0
    except ValueError:
        needs_offset = False
    return S2_BASELINE_OFFSET if needs_offset else 0


def build_composite(stack):
    """Masked reflectance stack -> 13-band int16 geomedian composite array.

    Base bands are scaled to reflectance*10000 and indices to index*10000
    before the reduction, matching gee_utils.scale_bands, so the geometric
    median is computed in the same 13-dimensional space GEE used.

    In low-memory mode (browser) the stack variables are released one by
    one as the working cube is assembled.
    """
    import gc

    low_mem = stac_utils.low_memory_mode()
    stack = stac_utils.add_indices(stack)
    arrays = []
    for name in stac_utils.COMPOSITE_BANDS:
        arrays.append((stack[name].values * 10000.0).astype(np.float32))
        if low_mem:
            stack = stack.drop_vars(name)
            gc.collect()
    cube = np.stack(arrays, axis=1)  # (time, band, y, x)
    if low_mem:
        del arrays, stack
        gc.collect()
    return stac_utils.geometric_median(cube)


def download_composite(catalog, start_date, end_date, aoi_geometry, geobox,
                       output_path, provider="mpc"):
    """End-to-end: search, stream, mask, geomedian, write GeoTIFF.

    Returns True if a composite was written (or already existed)."""
    if os.path.exists(output_path):
        _log(f"- Composite already exists: {os.path.basename(output_path)}. Skipping.")
        return True

    _log(f"- Searching the {provider} STAC catalog for {start_date}..{end_date}...")
    items = search_hls_items(catalog, start_date, end_date, aoi_geometry, provider)
    n_items = sum(len(v) for v in items.values())
    counts = ", ".join(f"{cid}: {len(v)}" for cid, v in items.items())
    _log(f"- Found {n_items} HLS items ({counts})")
    if n_items == 0:
        return False

    # Rough download estimate calibrated on real runs (~27 s per scene per
    # megapixel of AOI at 7 assets/scene) so long waits are announced.
    mpix = geobox.width * geobox.height / 1e6
    est = n_items * mpix * 27
    _log(f"- Streaming the AOI window of each scene "
         f"({geobox.width}x{geobox.height} px). Rough estimate: "
         f"~{max(1, round(est / 60))} min. Progress below:")

    if provider == "nasa":
        # odc-stac loads eagerly here, so the auth header only lives while
        # the LPCLOUD COGs are being read.
        with stac_utils.earthdata_gdal_session(stac_utils.earthdata_token()):
            stack = load_hls_stack(items, geobox, provider)
    else:
        stack = load_hls_stack(items, geobox, provider)
    _log(f"- Loaded stack with {stack.sizes['time']} observations. "
         f"Computing the geometric median (CPU-bound, no network)...")
    composite = build_composite(stack)
    stac_utils.write_geotiff(
        composite, geobox, stac_utils.COMPOSITE_BANDS, output_path, dtype="int16")
    _log(f"- Wrote {os.path.basename(output_path)}")
    return True
