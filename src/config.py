import os
import yaml
from pathlib import Path

CONFIG_DIR = Path(__file__).parent.parent

def load_env_file(env_path=None):
    """Loads KEY=VALUE lines from a plain env file into os.environ, without
    overriding variables already set in the real environment (e.g. by a
    CI system or an explicit `export`). Keeps secrets like EARTHDATA_TOKEN
    out of shell history/rc files: create an `env` file next to config.yaml
    (already gitignored) with `EARTHDATA_TOKEN=...` and it's picked up
    automatically.

    Public and safe to call on its own (e.g. from check_env.py) without a
    config.yaml present — it only touches os.environ."""
    if env_path is None:
        env_path = CONFIG_DIR / "env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

def load_config(config_file="config.yaml"):
    """Loads the specified configuration file."""
    load_env_file()
    config_path = CONFIG_DIR / config_file
    if not config_path.exists():
        raise SystemExit(
            f"\n[CONFIG] Configuration file not found: {config_path}\n"
            f"Run the pipeline from the repository root, and pass the file "
            f"name with --config (e.g. --config config.test.yaml).")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    _validate_config(config, config_file)
    return config


def _validate_config(config, config_file):
    """Checks the configuration up front and explains problems in plain
    language, so users see one clear message instead of a traceback three
    phases later."""
    problems = []

    for key in ("data_dir", "output_dir", "aoi_file", "study_period", "output_names"):
        if key not in config:
            problems.append(f"Missing required setting '{key}:'.")

    period = config.get("study_period") or {}
    start, end = period.get("start_date"), period.get("end_date")
    if start and end:
        from datetime import datetime
        try:
            d0 = datetime.strptime(str(start), "%Y-%m-%d")
            d1 = datetime.strptime(str(end), "%Y-%m-%d")
            if d1 < d0:
                problems.append(
                    f"study_period end_date ({end}) is earlier than "
                    f"start_date ({start}).")
        except ValueError:
            problems.append(
                f"study_period dates must look like YYYY-MM-DD "
                f"(got start_date: {start!r}, end_date: {end!r}).")

    backend = config.get("download_backend", "stac")
    if backend not in ("stac", "gee"):
        problems.append(
            f"download_backend must be \"stac\" (default, no account needed) "
            f"or \"gee\" (optional Google Earth Engine); got {backend!r}.")

    provider = config.get("hls_provider", "auto")
    if provider not in ("auto", "nasa", "mpc", "earthsearch"):
        problems.append(
            f"hls_provider must be one of auto/nasa/mpc/earthsearch; "
            f"got {provider!r}.")

    layers = config.get("extra_layers")
    if layers is not None and not isinstance(layers, list):
        problems.append(
            "extra_layers must be a list. Example:\n"
            "    extra_layers:\n"
            "      - path: \"../data/dem.tif\"\n"
            "        prefix: \"dem_\"")

    if problems:
        bullet_list = "\n".join(f"  - {p}" for p in problems)
        raise SystemExit(
            f"\n[CONFIG] {config_file} has {len(problems)} problem(s):\n"
            f"{bullet_list}\n\nFix the file and run again.")

if __name__ == '__main__':
    # For testing purposes, print the loaded config
    config = load_config()
    import json
    print(json.dumps(config, indent=2))
