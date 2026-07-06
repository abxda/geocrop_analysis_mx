"""WASM-compatible COG loader (fallback for odc-stac).

odc-stac streams COG windows through GDAL's /vsicurl, which needs raw
network access in the C layer — unavailable inside WebAssembly (Pyodide).
This module provides the same "STAC items -> xarray stack on a target
GeoBox" step using only building blocks that DO work in Pyodide:

  - HTTP via `requests` (patched to the browser fetch API by pyodide-http),
  - tifffile (pure Python) to decode only the COG tiles intersecting the
    AOI, fetched with HTTP Range requests — a Sentinel-1 RTC scene is
    ~1.9 GB per band, but the AOI tiles are a few tens of MB,
  - rasterio.warp.reproject on in-memory arrays for the warp to the target
    grid (rasterio ships in Pyodide; only its network layer is missing).

If tifffile is not installed, each asset is fetched whole into memory
(acceptable for HLS bands, ~25 MB). The public entry point is `load_stack`.
"""

import math
import sys
import numpy as np


def is_emscripten():
    """True when running inside Pyodide/WebAssembly."""
    return sys.platform == "emscripten"


def enable_wasm_http():
    """Routes `requests` through the browser's fetch API when in Pyodide."""
    if is_emscripten():
        import pyodide_http
        pyodide_http.patch_all()


class HTTPRangeReader:
    """Read-only file-like object over HTTP Range requests.

    Small reads (headers, TIFF IFDs) are served from cached fixed-size
    blocks; large reads (tile data) fetch exactly the requested span."""

    SMALL_READ = 64 * 1024
    BLOCK_SIZE = 256 * 1024

    def __init__(self, url):
        import requests
        self.url = url
        self.name = url.rsplit("/", 1)[-1].split("?")[0]
        self._session = requests.Session()
        self._pos = 0
        self._blocks = {}
        head = self._session.head(url, timeout=120)
        head.raise_for_status()
        self._size = int(head.headers["Content-Length"])
        self.bytes_fetched = 0
        self.requests_made = 1

    def _fetch(self, start, end):
        """Fetches [start, end) from the server."""
        end = min(end, self._size)
        response = self._session.get(
            self.url, timeout=600,
            headers={"Range": f"bytes={start}-{end - 1}"})
        response.raise_for_status()
        self.bytes_fetched += end - start
        self.requests_made += 1
        return response.content

    def _read_cached(self, start, size):
        first = start // self.BLOCK_SIZE
        last = (start + size - 1) // self.BLOCK_SIZE
        parts = []
        for block_index in range(first, last + 1):
            if block_index not in self._blocks:
                block_start = block_index * self.BLOCK_SIZE
                self._blocks[block_index] = self._fetch(
                    block_start, block_start + self.BLOCK_SIZE)
            parts.append(self._blocks[block_index])
        blob = b"".join(parts)
        offset = start - first * self.BLOCK_SIZE
        return blob[offset:offset + size]

    def read(self, size=-1):
        if size is None or size < 0:
            size = self._size - self._pos
        size = max(0, min(size, self._size - self._pos))
        if size == 0:
            return b""
        if size <= self.SMALL_READ:
            data = self._read_cached(self._pos, size)
        else:
            data = self._fetch(self._pos, self._pos + size)
        self._pos += len(data)
        return data

    def seek(self, offset, whence=0):
        if whence == 0:
            self._pos = offset
        elif whence == 1:
            self._pos += offset
        else:
            self._pos = self._size + offset
        return self._pos

    def tell(self):
        return self._pos

    def seekable(self):
        return True

    def close(self):
        self._session.close()

    @property
    def closed(self):
        return False


def fetch_bytes(url, max_retries=3):
    """Downloads a URL fully into memory."""
    import requests

    last_error = None
    for _ in range(max_retries):
        try:
            response = requests.get(url, timeout=600)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as error:
            last_error = error
    raise last_error


def asset_grid(item, asset_key):
    """Returns (crs, transform, shape) of an asset from STAC proj metadata,
    or None if the item does not carry the projection extension."""
    from rasterio.crs import CRS
    from rasterio.transform import Affine

    asset = item.assets[asset_key]
    def prop(name):
        return asset.extra_fields.get(name, item.properties.get(name))

    epsg, transform, shape = prop("proj:epsg"), prop("proj:transform"), prop("proj:shape")
    if not transform or not shape:
        return None
    if epsg:
        crs = CRS.from_epsg(epsg)
    else:
        wkt = prop("proj:wkt2") or prop("proj:code")
        if not wkt:
            return None
        crs = CRS.from_string(str(wkt))
    return crs, Affine(*list(transform)[:6]), tuple(shape)


def _window_from_geobox(geobox, src_crs, src_transform, src_shape, margin=4):
    """Pixel window (row0, row1, col0, col1) of the source grid covering the
    GeoBox, expanded by a small margin. Returns None if disjoint."""
    from rasterio.warp import transform_bounds

    bounds = geobox.boundingbox
    left, bottom, right, top = transform_bounds(
        str(geobox.crs), src_crs, bounds.left, bounds.bottom, bounds.right, bounds.top)
    inv = ~src_transform
    cols, rows = [], []
    for x, y in [(left, bottom), (left, top), (right, bottom), (right, top)]:
        c, r = inv * (x, y)
        cols.append(c)
        rows.append(r)
    row0 = max(0, int(math.floor(min(rows))) - margin)
    row1 = min(src_shape[0], int(math.ceil(max(rows))) + margin)
    col0 = max(0, int(math.floor(min(cols))) - margin)
    col1 = min(src_shape[1], int(math.ceil(max(cols))) + margin)
    if row0 >= row1 or col0 >= col1:
        return None
    return row0, row1, col0, col1


def _decode_deflate_fp_predictor(data, tile_h, tile_w, itemsize=4):
    """Decodes a DEFLATE tile written with TIFF PREDICTOR=3 (floating point)
    in pure NumPy — imagecodecs (a C extension unavailable in Pyodide) is
    normally required for this predictor.

    Per row, the encoder splits the floats into big-endian byte planes and
    horizontally byte-differences the whole row; we invert both steps."""
    import zlib

    raw = np.frombuffer(zlib.decompress(data), dtype=np.uint8)
    rows = raw.reshape(tile_h, tile_w * itemsize)
    undiff = np.cumsum(rows, axis=1, dtype=np.uint8)
    planes = undiff.reshape(tile_h, itemsize, tile_w)
    interleaved = np.ascontiguousarray(planes.transpose(0, 2, 1))
    return interleaved.reshape(tile_h, tile_w * itemsize).view(">f4")


def _read_tiles_window(url, window, log=None):
    """Reads a pixel window from a tiled COG fetching only the intersecting
    tiles via HTTP Range requests (pure-Python decode through tifffile).

    Returns (array, nodata)."""
    import tifffile

    reader = HTTPRangeReader(url)
    try:
        tif = tifffile.TiffFile(reader)
        page = tif.pages[0]
        if not page.is_tiled:
            raise ValueError("asset is not a tiled COG")
        row0, row1, col0, col1 = window
        tile_h, tile_w = page.tilelength, page.tilewidth
        tiles_across = math.ceil(page.imagewidth / tile_w)
        out = np.zeros((row1 - row0, col1 - col0), dtype=page.dtype)
        nodata = page.tags.get("GDAL_NODATA")
        nodata = float(nodata.value) if nodata is not None else None
        if nodata is not None:
            out[:] = nodata

        for tile_row in range(row0 // tile_h, math.ceil(row1 / tile_h)):
            for tile_col in range(col0 // tile_w, math.ceil(col1 / tile_w)):
                index = tile_row * tiles_across + tile_col
                offset = page.dataoffsets[index]
                bytecount = page.databytecounts[index]
                if bytecount == 0:  # sparse tile: stays nodata
                    continue
                reader.seek(offset)
                data = reader.read(bytecount)
                if page.predictor == 3 and page.compression == 8 and page.dtype == np.float32:
                    tile = _decode_deflate_fp_predictor(data, tile_h, tile_w).astype(np.float32)
                else:
                    decoded = page.decode(data, index)[0]
                    tile = decoded[0, :, :, 0] if decoded.ndim == 4 else np.squeeze(decoded)
                # intersection of this tile with the requested window
                tr0, tc0 = tile_row * tile_h, tile_col * tile_w
                r0 = max(row0, tr0); r1 = min(row1, tr0 + tile_h)
                c0 = max(col0, tc0); c1 = min(col1, tc0 + tile_w)
                out[r0 - row0:r1 - row0, c0 - col0:c1 - col0] = \
                    tile[r0 - tr0:r1 - tr0, c0 - tc0:c1 - tc0]
        if log:
            log(f"    range-read {reader.name}: {reader.bytes_fetched/1e6:.1f} MB "
                f"in {reader.requests_made} requests")
        return out, nodata
    finally:
        reader.close()


def read_asset_onto_geobox(url, geobox, resampling="nearest", fill=np.nan,
                           grid=None, log=None):
    """Fetches one COG asset and warps it onto the target GeoBox.

    When `grid` (crs, transform, shape from STAC proj metadata) is given and
    tifffile is available, only the tiles intersecting the GeoBox are
    fetched via Range requests; otherwise the whole file is downloaded.
    Returns a float64 (y, x) array with `fill` outside the data."""
    from rasterio.warp import reproject
    from rasterio.enums import Resampling
    from rasterio.transform import Affine

    dst_transform = Affine(*geobox.transform[:6])
    dst = np.full((geobox.height, geobox.width), np.float64(fill))

    src_array = None
    if grid is not None:
        try:
            import tifffile  # noqa: F401
            src_crs, src_transform, src_shape = grid
            window = _window_from_geobox(geobox, src_crs, src_transform, src_shape)
            if window is None:
                return dst
            data, nodata = _read_tiles_window(url, window, log)
            row0, _, col0, _ = window
            src_array = data.astype(np.float64)
            if nodata is not None:
                src_array[data == nodata] = np.nan
            src_transform = src_transform * Affine.translation(col0, row0)
        except ImportError:
            src_array = None

    if src_array is None:
        # Full fetch fallback (no tifffile or no proj metadata)
        from rasterio.io import MemoryFile
        with MemoryFile(fetch_bytes(url)) as mem:
            with mem.open() as src:
                src_array = src.read(1, masked=True).astype(np.float64).filled(np.nan)
                src_transform, src_crs = src.transform, src.crs

    reproject(
        source=np.nan_to_num(src_array, nan=-1e30),
        destination=dst,
        src_transform=src_transform,
        src_crs=src_crs,
        src_nodata=-1e30,
        dst_transform=dst_transform,
        dst_crs=str(geobox.crs),
        dst_nodata=np.float64(fill),
        resampling=Resampling[resampling],
    )
    return dst


def load_stack(items, asset_map, geobox, resampling="nearest", fill=np.nan, log=None):
    """Loads STAC items onto a GeoBox as an xarray.Dataset (time, y, x).

    asset_map: {asset_key: variable_name}. Items are grouped by solar day
    (UTC date of the item datetime) like odc-stac's groupby="solar_day";
    where same-day items overlap, the first valid pixel wins.

    Reports progress per scene x asset, and — since this loader is what
    runs inside the browser — keeps the stack in float32 and collects
    garbage after every scene to hold peak RAM down.
    """
    import gc
    import pandas as pd
    import xarray as xr
    from . import stac_utils

    by_day = {}
    for item in items:
        day = str(item.datetime.date())
        by_day.setdefault(day, []).append(item)

    days = sorted(by_day)
    ny, nx = geobox.height, geobox.width
    stack_dtype = np.float32 if is_emscripten() else np.float64
    data = {var: np.full((len(days), ny, nx), fill, dtype=stack_dtype)
            for var in asset_map.values()}

    total_reads = sum(
        sum(1 for k in asset_map if k in item.assets)
        for its in by_day.values() for item in its)
    progress = stac_utils.Progress(
        f"fetching {total_reads} COG windows ({len(items)} scenes x "
        f"{len(asset_map)} assets)", total_reads, step_pct=10)

    for t, day in enumerate(days):
        for item in by_day[day]:
            for asset_key, var in asset_map.items():
                if asset_key not in item.assets:
                    continue
                layer = read_asset_onto_geobox(
                    item.assets[asset_key].href, geobox, resampling, fill,
                    grid=asset_grid(item, asset_key), log=log)
                current = data[var][t]
                empty = np.isnan(current) if np.isnan(fill) else current == fill
                current[empty] = layer[empty].astype(stack_dtype)
                del layer
                progress.update()
            gc.collect()
    progress.finish()

    transform = geobox.transform
    coords = {
        "time": pd.to_datetime(days),
        "y": transform.f + (np.arange(ny) + 0.5) * transform.e,
        "x": transform.c + (np.arange(nx) + 0.5) * transform.a,
    }
    return xr.Dataset(
        {var: (("time", "y", "x"), arr) for var, arr in data.items()},
        coords=coords,
    )
