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
    
    # List of libraries to check: (Display Name, Import Name)
    libraries_to_check = [
        ("GDAL", "osgeo.gdal"),
        ("RSGISLIB", "rsgislib"),
        ("GeoPandas", "geopandas"),
        ("Rasterio", "rasterio"),
        ("Earth Engine API", "ee"),
        ("PyYAML", "yaml")
    ]
    
    success_count = 0
    for name, import_name in libraries_to_check:
        if check_library(name, import_name):
            success_count += 1
    
    print("\n--- Validation Summary ---")
    if success_count == len(libraries_to_check):
        print("All critical libraries are installed correctly. Your environment is ready!")
    else:
        print("Some libraries are missing. Please review the [FAILURE] messages above and ensure the Conda environment was created successfully.")
        sys.exit(1) # Exit with an error code if validation fails

if __name__ == "__main__":
    main()
