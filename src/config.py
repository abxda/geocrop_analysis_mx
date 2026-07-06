import yaml
from pathlib import Path

CONFIG_DIR = Path(__file__).parent.parent

def load_config(config_file="config.yaml"):
    """Loads the specified configuration file."""
    config_path = CONFIG_DIR / config_file
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    # Resolve relative data/output dirs against the repository root so the
    # pipeline behaves the same regardless of the current working directory.
    for key in ("data_dir", "output_dir"):
        if key in config and not Path(config[key]).is_absolute():
            config[key] = str((CONFIG_DIR / config[key]).resolve())
    return config

if __name__ == '__main__':
    # For testing purposes, print the loaded config
    config = load_config()
    import json
    print(json.dumps(config, indent=2))
