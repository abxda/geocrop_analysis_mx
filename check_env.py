import sys

def check_library(name, import_name):
    """Attempts to import a library and prints a success or failure message."""
    try:
        __import__(import_name)
        print(f"[SUCCESS] {name} library found and is importable.")
        return True
    except ImportError:
        print(f"[FAILURE] {name} library not found. Please check your environment installation.")
        return False

def main():
    """Runs validation checks for all critical libraries."""
    print("--- Running Environment Validation Check ---")
    
    libraries_to_check = [
        ("GDAL", "osgeo.gdal"),
        ("GeoPandas", "geopandas"),
        ("Rasterio", "rasterio"),
        ("Earth Engine API", "ee"),
        ("PyShepSeg", "pyshepseg"),
        ("ExactExtract", "exactextract"),
        ("Scikit-Image", "skimage"),
        ("Scikit-Learn", "sklearn")
    ]
    
    success_count = 0
    for name, import_name in libraries_to_check:
        if check_library(name, import_name):
            success_count += 1
    
    print("\n--- Validation Summary ---")
    if success_count == len(libraries_to_check):
        print("All critical libraries are installed correctly. Your environment is ready!")
    else:
        print("Some libraries are missing. Please review the [FAILURE] messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()