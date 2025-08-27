import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

def load_config():
    """Loads the configuration file."""
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    return config

if __name__ == '__main__':
    # For testing purposes, print the loaded config
    config = load_config()
    import json
    print(json.dumps(config, indent=2))
