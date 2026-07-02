import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

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
        ("GeoPandas", "geopandas"),
        ("Rasterio", "rasterio"),
        ("PySTAC Client", "pystac_client"),
        ("Planetary Computer", "planetary_computer"),
        ("ODC-STAC", "odc.stac"),
        ("Rioxarray", "rioxarray"),
        ("Shepherd-WASM", "shepherd_wasm"),
        ("ExactExtract", "exactextract"),
        ("TPOT", "tpot"),
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

    check_earthdata_token()

def check_earthdata_token():
    """Reports the NASA Earthdata token's presence and remaining validity,
    so an expired token is caught here instead of surfacing as a download
    failure mid-pipeline."""
    from data_download import stac_utils

    token = stac_utils.earthdata_token()
    if not token:
        print("\n[INFO] EARTHDATA_TOKEN not set: HLS optical downloads will "
              "use Planetary Computer (has archive gaps). See "
              "docs/manual_tokens_gratuitos.pdf to set up the free NASA token.")
        return

    expiry = stac_utils.earthdata_token_expiry(token)
    if expiry is None:
        print("\n[WARNING] EARTHDATA_TOKEN is set but could not be parsed as "
              "a token.")
        return

    from datetime import datetime, timezone
    days_left = (expiry - datetime.now(timezone.utc)).total_seconds() / 86400
    if days_left < 0:
        print(f"\n[FAILURE] EARTHDATA_TOKEN EXPIRED on {expiry:%Y-%m-%d}. "
              f"Generate a new one at "
              f"https://urs.earthdata.nasa.gov/profile/generate_token")
    elif days_left <= 14:
        print(f"\n[WARNING] EARTHDATA_TOKEN expires in {days_left:.0f} "
              f"day(s) ({expiry:%Y-%m-%d}). Renew soon at "
              f"https://urs.earthdata.nasa.gov/profile/generate_token")
    else:
        print(f"\n[SUCCESS] EARTHDATA_TOKEN valid until {expiry:%Y-%m-%d} "
              f"({days_left:.0f} days remaining).")

if __name__ == "__main__":
    main()