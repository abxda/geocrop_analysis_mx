import ee
import math

def initialize_gee():
    """Authenticates and initializes the Earth Engine API."""
    try:
        ee.Initialize()
    except Exception:
        print("Earth Engine not initialized. Running authentication.")
        ee.Authenticate()
        ee.Initialize()

def hls_mask(image):
    """Masks clouds, shadows, and snow from HLS imagery."""
    fmask = image.select('Fmask')
    # Bit 0-3: Cloud mask (2: probable, 3: sure)
    cloud_mask = fmask.bitwiseAnd(0b11).gte(2)
    # Bit 4-5: Cloud shadow mask (2: probable, 3: sure)
    shadow_mask = fmask.bitwiseAnd(0b1100).gte(8)
    # Bit 6-7: Snow/ice mask (2: probable, 3: sure)
    snow_mask = fmask.bitwiseAnd(0b11000000).gte(192)
    # Bit 8-9: Cirrus mask
    cirrus_mask = fmask.bitwiseAnd(0b1100000000).gt(0)
    # Bit 14: Valid data mask
    valid_mask = fmask.bitwiseAnd(1 << 14).eq(0)

    # Combine masks to find clear pixels
    mask = (
        valid_mask
        .And(cloud_mask.Not())
        .And(shadow_mask.Not())
        .And(snow_mask.Not())
        .And(cirrus_mask.Not())
    )
    return image.updateMask(mask)

def add_variables(image):
    """Calculates and adds vegetation indices to an image."""
    return image \
        .addBands(
            image.normalizedDifference(['nir', 'red'])
                 .multiply(10000)
                 .int16()
                 .rename('NDVI')
        ) \
        .addBands(
            image.expression(
                '2.5 * ((nir - red) / (nir + 6 * red - 7.5 * blue + 1))',
                {'nir': image.select('nir'), 'red': image.select('red'), 'blue': image.select('blue')}
            ).multiply(10000).int16().rename('EVI')
        ) \
        .addBands(
            image.expression(
                'nir / green - 1',
                {'nir': image.select('nir'), 'green': image.select('green')}
            ).multiply(10000).int16().rename('GCVI')
        ) \
        .addBands(
            image.expression(
                '1 / 2 * (2 * nir + 1 - ((2 * nir + 1) ** 2 - 8 * (nir - red)) ** (1 / 2))',
                {'nir': image.select('nir'), 'red': image.select('red')}
            ).multiply(10000).int16().rename('MSAVI2')
        ) \
        .addBands(
            image.normalizedDifference(['nir', 'swir1'])
                 .multiply(10000)
                 .int16()
                 .rename('LSWI')
        ) \
        .addBands(
            image.normalizedDifference(['swir1', 'red'])
                 .multiply(10000)
                 .int16()
                 .rename('NDSVI')
        ) \
        .addBands(
            image.normalizedDifference(['swir1', 'swir2'])
                 .multiply(10000)
                 .int16()
                 .rename('NDTI')
        )

def scale_bands(image):
    """Scales spectral bands and combines with derived indices."""
    scaled_base = image.select(['blue','green','red','nir','swir1','swir2']) \
                       .multiply(10000).int16()
    derived = image.select(['NDVI','EVI','GCVI','MSAVI2','LSWI','NDSVI','NDTI'])
    return scaled_base.addBands(derived)

def split_geometry(geometry, max_dim=0.2):
    """Splits a larger geometry into a grid of smaller rectangles."""
    bounds = geometry.bounds().getInfo()['coordinates'][0]
    minX, minY = bounds[0]
    maxX, maxY = bounds[2]
    width = maxX - minX
    height = maxY - minY

    x_steps = math.ceil(width / max_dim)
    y_steps = math.ceil(height / max_dim)

    x_step_size = width / x_steps
    y_step_size = height / y_steps

    regions = []
    for i in range(x_steps):
        for j in range(y_steps):
            region = ee.Geometry.Rectangle(
                [minX + i * x_step_size,
                 minY + j * y_step_size,
                 minX + (i + 1) * x_step_size,
                 minY + (j + 1) * y_step_size])
            regions.append(region)
    return regions
