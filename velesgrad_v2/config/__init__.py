# Velesgrad v2 – Config package
import os

def load_config():
    """Load config from TOML if available, else use defaults."""
    config_path = os.path.join(os.path.dirname(__file__), "default.toml")
    if os.path.exists(config_path):
        try:
            import tomllib
            with open(config_path, "rb") as f:
                return tomllib.load(f)
        except Exception:
            pass
    return {}
