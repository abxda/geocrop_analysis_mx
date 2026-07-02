"""Sentinel-1 radar download via STAC/COG.

Replaces radar.py: instead of GEE's COPERNICUS/S1_GRD it uses Microsoft
Planetary Computer's sentinel-1-rtc collection — radiometrically
terrain-corrected gamma-0 backscatter (a step above GEE's S1_GRD, which is
geometrically but not radiometrically terrain-corrected). Values are
converted to dB and the RVI is computed on the dB bands to stay consistent
with the historical composites; the monthly composite is the per-band
median, as in the original pipeline (s1_collection.median()).
"""

import os
import numpy as np

from . import stac_utils
from . import cog_fetch

RADAR_BANDS = ["VV", "VH", "RVI"]


_log = stac_utils.log


def search_s1_items(catalog, start_date, end_date, aoi_geometry):
    """Searches sentinel-1-rtc for IW dual-pol (VV+VH) items."""
    search = catalog.search(
        collections=["sentinel-1-rtc"],
        intersects=aoi_geometry,
        datetime=f"{start_date}/{end_date}",
        query={
            "sar:instrument_mode": {"eq": "IW"},
            "sar:polarizations": {"eq": ["VV", "VH"]},
        },
    )
    return list(search.items())


def load_s1_stack(items, geobox):
    """Loads gamma-0 VV/VH onto the target grid and converts to dB.

    Returns an xarray.Dataset with float variables VV and VH in dB
    (NaN where there is no data). Uses odc-stac on regular Python and the
    cog_fetch fallback inside Pyodide/WebAssembly."""
    if cog_fetch.is_emscripten():
        ds = cog_fetch.load_stack(
            items, {"vv": "VV", "vh": "VH"}, geobox,
            resampling="bilinear", fill=np.nan)
    else:
        import xarray as xr
        from odc.stac import load as odc_load

        by_day = {}
        for item in items:
            by_day.setdefault(str(item.datetime.date()), []).append(item)
        progress = stac_utils.Progress(
            f"downloading {len(items)} S1 RTC scenes / {len(by_day)} solar days",
            len(by_day), step_pct=20)
        parts = []
        for day in sorted(by_day):
            parts.append(odc_load(
                by_day[day],
                bands=["vv", "vh"],
                geobox=geobox,
                groupby="solar_day",
                resampling="bilinear",
                dtype="float32",
            ))
            progress.update()
        progress.finish()
        ds = xr.concat(parts, dim="time") if len(parts) > 1 else parts[0]
        ds = ds.rename({"vv": "VV", "vh": "VH"})

    for name in ("VV", "VH"):
        linear = ds[name].where(ds[name] > 0)
        ds[name] = 10.0 * np.log10(linear)
    return ds.sortby("time")


def build_composite(stack):
    """dB stack -> (3, y, x) median composite [VV, VH, RVI].

    RVI = 4*VH/(VV+VH) computed on dB values, matching radar.py. Uses
    float32 (half the RAM) in a browser, float64 elsewhere."""
    import gc

    work_dtype = np.float32 if stac_utils.low_memory_mode() else np.float64
    stack["RVI"] = (4 * stack["VH"]) / (stack["VV"] + stack["VH"])
    arrays = []
    for name in RADAR_BANDS:
        arrays.append(np.nanmedian(stack[name].values.astype(work_dtype), axis=0))
        if work_dtype is np.float32:
            stack = stack.drop_vars(name)
            gc.collect()
    return np.stack(arrays, axis=0)


def download_composite(catalog, start_date, end_date, aoi_geometry, geobox, output_path):
    """End-to-end: search, stream, dB, RVI, median, write GeoTIFF.

    Returns True if a composite was written (or already existed)."""
    if os.path.exists(output_path):
        _log(f"- Composite already exists: {os.path.basename(output_path)}. Skipping.")
        return True

    _log(f"- Searching Planetary Computer for Sentinel-1 RTC, {start_date}..{end_date}...")
    items = search_s1_items(catalog, start_date, end_date, aoi_geometry)
    _log(f"- Found {len(items)} Sentinel-1 RTC items")
    if not items:
        return False

    stack = load_s1_stack(items, geobox)
    _log(f"- Loaded stack with {stack.sizes['time']} observations. Computing per-band median...")
    composite = build_composite(stack)
    stac_utils.write_geotiff(
        composite, geobox, RADAR_BANDS, output_path, dtype="float64")
    _log(f"- Wrote {os.path.basename(output_path)}")
    return True
