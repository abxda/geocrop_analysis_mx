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
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config

if __name__ == '__main__':
    # For testing purposes, print the loaded config
    config = load_config()
    import json
    print(json.dumps(config, indent=2))
