"""Shared utilities for the STAC/COG data download backend.

This module replaces the Google Earth Engine dependency (gee_utils.py) with
open, token-free data access:

  - STAC search via pystac-client against Microsoft Planetary Computer
    (anonymous SAS signing, no account required).
  - Windowed COG reads via odc-stac (HTTP range requests: only the AOI
    bytes are downloaded, never the full scenes).
  - A pure-NumPy Weiszfeld geometric median (multivariate L1 median), the
    portable equivalent of GEE's ee.Reducer.geometricMedian.

The masking / index / scaling functions reproduce gee_utils.py exactly so
that outputs are comparable with the historical GEE-generated composites.
"""

import os
import time
import numpy as np

MPC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# GEE's getDownloadURL(scale=30, crs='EPSG:4326') converts metres to degrees
# with the authalic radius factor used below; keeping it makes the output
# grids match the historical composites pixel for pixel.
METERS_PER_DEGREE = 111319.49079327358

# GDAL settings for efficient streaming of remote COGs.
GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "3",
    "CPL_VSIL_CURL_CACHE_SIZE": "200000000",
}


def log(message):
    """Timestamped, flushed print — renders identically in a terminal, a
    Jupyter notebook and Pyodide, so long stages never look frozen."""
    from datetime import datetime
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)


def _fmt_duration(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


class Progress:
    """Minimal progress reporter for long stages.

    Emits plain log lines at percentage steps with elapsed time and a
    remaining-time estimate. No terminal control codes and no widget
    dependencies, so the same output works in consoles, Jupyter notebooks
    and JupyterLite/Pyodide."""

    def __init__(self, label, total, step_pct=10):
        self.label = label
        self.total = max(int(total), 1)
        self.units_done = 0
        self._step = max(1, self.total * step_pct // 100)
        self._next_report = self._step
        self._t0 = time.time()

    def update(self, n=1):
        self.units_done += n
        if self.units_done >= self._next_report and self.units_done < self.total:
            elapsed = time.time() - self._t0
            remaining = elapsed / self.units_done * (self.total - self.units_done)
            pct = 100 * self.units_done // self.total
            log(f"  {self.label}: {pct}% ({self.units_done}/{self.total}) — "
                f"elapsed {_fmt_duration(elapsed)}, remaining ~{_fmt_duration(remaining)}")
            while self._next_report <= self.units_done:
                self._next_report += self._step

    def finish(self):
        log(f"  {self.label}: done in {_fmt_duration(time.time() - self._t0)}.")


def low_memory_mode():
    """True when running in a browser (Pyodide/JupyterLite), where RAM is
    the scarce resource: the pipeline then prefers float32 stacks, smaller
    processing chunks and eager garbage collection over raw speed."""
    from . import cog_fetch
    return cog_fetch.is_emscripten()


def configure_gdal_env():
    """Prepares the runtime for remote COG reads.

    Sets GDAL environment variables for efficient /vsicurl streaming and,
    when running inside Pyodide/WebAssembly, routes `requests` through the
    browser's fetch API so STAC search and asset downloads work there too."""
    for key, value in GDAL_ENV.items():
        os.environ.setdefault(key, value)
    from . import cog_fetch
    cog_fetch.enable_wasm_http()


NASA_STAC_URL = "https://cmr.earthdata.nasa.gov/stac/LPCLOUD"
EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1"


def get_catalog():
    """Opens the Planetary Computer STAC catalog with anonymous signing."""
    import planetary_computer
    from pystac_client import Client

    return Client.open(MPC_STAC_URL, modifier=planetary_computer.sign_inplace)


def get_nasa_catalog():
    """Opens NASA's LPCLOUD CMR-STAC catalog (search needs no auth)."""
    from pystac_client import Client

    return Client.open(NASA_STAC_URL)


def get_earthsearch_catalog():
    """Opens Element 84's Earth Search catalog (fully anonymous; both the
    API and the sentinel-cogs bucket send CORS headers, so it also works
    from inside a browser/WebAssembly)."""
    from pystac_client import Client

    return Client.open(EARTH_SEARCH_URL)


def s2_clear_mask(scl):
    """Returns a boolean array of clear pixels from the Sentinel-2 L2A SCL
    band: keeps vegetation/bare/water/unclassified (4,5,6,7) and dark-area
    (2); drops nodata, saturated, shadows, clouds, cirrus and snow."""
    scl = np.nan_to_num(scl, nan=0).astype(np.int32)
    return np.isin(scl, (2, 4, 5, 6, 7))


def earthdata_token():
    """Returns the NASA Earthdata bearer token, or None.

    Reading LPCLOUD assets requires a free Earthdata Login account
    (https://urs.earthdata.nasa.gov). Generate a token in your profile and
    export it as EARTHDATA_TOKEN."""
    return os.environ.get("EARTHDATA_TOKEN")


def earthdata_token_expiry(token):
    """Returns the token's expiration as a UTC datetime, or None if it is
    not a decodable JWT.

    Earthdata tokens are JWTs with a standard "exp" claim; this reads it
    locally (no network call, no verification — just enough to warn the
    user before NASA starts rejecting requests with it)."""
    import base64
    import json
    from datetime import datetime, timezone

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
    except Exception:
        return None


def check_earthdata_token(token, warn_within_days=14):
    """Logs one line about the Earthdata token's validity, if present.

    Silent when the token is comfortably valid; a clear WARNING as it
    nears expiry (default: within 14 days); a clear EXPIRED notice once
    past it, with the renewal link, so the reason for NASA download
    failures is obvious without digging through HTTP errors."""
    from datetime import datetime, timezone

    if not token:
        return
    expiry = earthdata_token_expiry(token)
    if expiry is None:
        return
    days_left = (expiry - datetime.now(timezone.utc)).total_seconds() / 86400
    renew_url = "https://urs.earthdata.nasa.gov/profile/generate_token"
    if days_left < 0:
        print(f"[EARTHDATA_TOKEN] EXPIRED on {expiry:%Y-%m-%d} — "
              f"NASA HLS downloads will fail with 401 until you generate a "
              f"new token at {renew_url} and update EARTHDATA_TOKEN.")
    elif days_left <= warn_within_days:
        print(f"[EARTHDATA_TOKEN] WARNING: expires in {days_left:.0f} day(s) "
              f"({expiry:%Y-%m-%d}). Renew soon at {renew_url}.")


class earthdata_gdal_session:
    """Context manager that points GDAL at the Earthdata bearer token while
    reading LPCLOUD COGs, without leaking the header to other providers.

    LPCLOUD assets redirect (HTTP 303) from data.lpdaac.earthdatacloud.nasa.gov
    to a presigned CloudFront/S3 URL. GDAL >= 3.10's /vsicurl issues a HEAD
    request first, and its handling of that HEAD-303 redirect chain combined
    with a custom Authorization header silently breaks (`not recognized as
    being in a supported file format`), even though the same request works
    fine over a plain GET (verified with curl and with GDAL 3.8). Forcing
    GET-based probing via CPL_VSIL_CURL_USE_HEAD=NO avoids the broken path.
    """

    ENV_VARS = ("GDAL_HTTP_HEADERS", "CPL_VSIL_CURL_USE_HEAD")

    def __init__(self, token):
        self.token = token
        self._previous = {}

    def __enter__(self):
        self._previous = {var: os.environ.get(var) for var in self.ENV_VARS}
        os.environ["GDAL_HTTP_HEADERS"] = f"Authorization: Bearer {self.token}"
        os.environ["CPL_VSIL_CURL_USE_HEAD"] = "NO"
        return self

    def __exit__(self, *exc):
        for var, value in self._previous.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value


def hls_clear_mask(fmask):
    """Returns a boolean array of clear pixels from the HLS Fmask band.

    Reproduces the exact bit arithmetic of gee_utils.hls_mask so composites
    stay comparable with the historical GEE outputs: it drops pixels flagged
    as cloud (bit 1), cloud shadow (bit 3) or high aerosol (bits 6-7 both
    set), plus the HLS fill value 255.
    """
    fmask = fmask.astype(np.int32)
    cloud = (fmask & 0b11) >= 2
    shadow = (fmask & 0b1100) >= 8
    high_aerosol = (fmask & 0b11000000) >= 192
    fill = fmask == 255
    return ~(cloud | shadow | high_aerosol | fill)


def add_indices(ds):
    """Adds the seven vegetation/tillage indices to a reflectance Dataset.

    Expects data variables blue/green/red/nir/swir1/swir2 as float
    reflectance (0-1 range, NaN where masked). Same formulas as
    gee_utils.add_variables.
    """
    blue, green, red = ds["blue"], ds["green"], ds["red"]
    nir, swir1, swir2 = ds["nir"], ds["swir1"], ds["swir2"]

    ds["NDVI"] = (nir - red) / (nir + red)
    ds["EVI"] = 2.5 * ((nir - red) / (nir + 6 * red - 7.5 * blue + 1))
    ds["GCVI"] = nir / green - 1
    ds["MSAVI2"] = 0.5 * (2 * nir + 1 - ((2 * nir + 1) ** 2 - 8 * (nir - red)) ** 0.5)
    ds["LSWI"] = (nir - swir1) / (nir + swir1)
    ds["NDSVI"] = (swir1 - red) / (swir1 + red)
    ds["NDTI"] = (swir1 - swir2) / (swir1 + swir2)
    return ds


# Band order of the final composites, matching gee_utils.scale_bands.
COMPOSITE_BANDS = [
    "blue", "green", "red", "nir", "swir1", "swir2",
    "NDVI", "EVI", "GCVI", "MSAVI2", "LSWI", "NDSVI", "NDTI",
]


def geometric_median(stack, max_iter=1000, tol=None, pixel_chunk=None):
    """Weiszfeld geometric median over the time axis of a (time, band, y, x)
    float array with NaN for masked observations.

    Treats each timestep's band vector as one multivariate observation per
    pixel and returns the (band, y, x) array minimising the sum of Euclidean
    distances — the same statistic as ee.Reducer.geometricMedian. Pure NumPy,
    vectorised over pixels, processed in chunks to bound memory, reporting
    progress per chunk.

    In a browser (Pyodide) it automatically switches to float32 arithmetic
    and smaller chunks — slower but roughly half the RAM.
    """
    low_mem = low_memory_mode()
    work_dtype = np.float32 if low_mem else np.float64
    if pixel_chunk is None:
        pixel_chunk = 50_000 if low_mem else 200_000
    if tol is None:
        # Values are reflectance*10000 (thousands); 1e-3 is already far below
        # the int16 quantisation of the output. float64 keeps the historical
        # tighter tolerance for bit-stable results.
        tol = 1e-3 if low_mem else 1e-7

    t, b, ny, nx = stack.shape
    n_chunks = (ny * nx + pixel_chunk - 1) // pixel_chunk
    progress = Progress(
        f"geometric median ({t} obs x {b} bands, "
        f"{'float32/low-mem' if low_mem else 'float64'})", n_chunks)
    flat = np.transpose(stack, (2, 3, 0, 1)).reshape(ny * nx, t, b)
    result = np.full((ny * nx, b), np.nan, dtype=work_dtype)

    for start in range(0, flat.shape[0], pixel_chunk):
        block = flat[start:start + pixel_chunk].astype(work_dtype)
        valid = np.isfinite(block).all(axis=2)  # (N, t)
        n_valid = valid.sum(axis=1)
        has_data = n_valid > 0
        if not has_data.any():
            progress.update()
            continue

        X = block[has_data]
        V = valid[has_data]
        Xz = np.where(V[:, :, None], X, 0.0)
        y = Xz.sum(axis=1) / np.maximum(V.sum(axis=1), 1)[:, None]  # mean init

        active = np.ones(y.shape[0], dtype=bool)
        for _ in range(max_iter):
            idx = np.flatnonzero(active)
            if idx.size == 0:
                break
            d = np.linalg.norm(Xz[idx] - y[idx][:, None, :], axis=2)  # (n, t)
            w = np.where(V[idx] & (d > 1e-9), 1.0 / np.maximum(d, 1e-9), 0.0)
            # Observations coincident with the current estimate get the
            # estimate itself as their contribution (standard Weiszfeld fix).
            at_point = V[idx] & (d <= 1e-9)
            wsum = w.sum(axis=1)
            y_new = np.where(
                wsum[:, None] > 0,
                (w[:, :, None] * Xz[idx]).sum(axis=1) / np.maximum(wsum, 1e-12)[:, None],
                y[idx],
            )
            y_new = np.where(at_point.any(axis=1)[:, None] & (wsum[:, None] == 0), y[idx], y_new)
            shift = np.linalg.norm(y_new - y[idx], axis=1)
            y[idx] = y_new
            active[idx] = shift > tol

        out_block = np.full((block.shape[0], b), np.nan, dtype=work_dtype)
        out_block[has_data] = y
        result[start:start + pixel_chunk] = out_block
        progress.update()
        if low_mem:
            import gc
            del block, valid, X, V, Xz, y, out_block
            gc.collect()

    progress.finish()
    return result.reshape(ny, nx, b).transpose(2, 0, 1)


def aoi_geobox(aoi_geometry, scale_meters=30):
    """Builds an EPSG:4326 GeoBox over the AOI bounds at the given scale,
    mirroring how GEE's getDownloadURL gridded the historical composites."""
    from odc.geo.geobox import GeoBox
    from odc.geo.geom import Geometry

    resolution = scale_meters / METERS_PER_DEGREE
    geom = Geometry(aoi_geometry, crs="EPSG:4326")
    return GeoBox.from_geopolygon(geom, resolution=resolution, crs="EPSG:4326")


def write_geotiff(data, geobox, band_names, output_path, dtype, nodata=None, fill=0):
    """Writes a (band, y, x) array as a compressed GeoTIFF."""
    import rasterio
    from rasterio.transform import Affine

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    arr = np.asarray(data, dtype=np.float64)
    arr = np.where(np.isfinite(arr), arr, fill)
    if np.issubdtype(np.dtype(dtype), np.integer):
        info = np.iinfo(dtype)
        arr = np.clip(arr, info.min, info.max)  # saturate like GEE's toInt16
    transform = Affine(*geobox.transform[:6])
    profile = {
        "driver": "GTiff",
        "width": geobox.width,
        "height": geobox.height,
        "count": arr.shape[0],
        "dtype": dtype,
        "crs": str(geobox.crs),
        "transform": transform,
        "compress": "LZW",
        "nodata": nodata,
    }
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(arr.astype(dtype))
        for i, name in enumerate(band_names, start=1):
            dst.set_band_description(i, name)
