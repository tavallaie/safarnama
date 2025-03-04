import os
import yaml
from loguru import logger

CONFIG_FILE = "config.yaml"
ENV_FILE = ".env"

DEFAULT_CONFIG = {
    "base_url": "https://www.techbend.io",
    "max_depth": 2,
    "delay": 1,
    "db_path": "python.db",
    "verbose": True,
    "save": True,
    "log_file": "techbend.log",
    "generate_sitemap": True,
    "recursive_crawl": True,
    "download_binaries": False,
    "download_specific_binaries": [],
    "find_images": False,
    "respect_robots": True,
    "exclude_url_patterns": [],
    "exclude_content_patterns": [],
    "depth_settings": {},
    "url_settings": {},
    "binary_extensions": [
        ".pdf",
        ".zip",
        ".exe",
        ".tar",
        ".tar.gz",
        ".tgz",
        ".rar",
        ".iso",
        ".bin",
        ".7z",
        ".dmg",
        ".tar.xz",
        ".pkg",
        ".bz2",
    ],
    "accepted_content_types": [
        "text/html",
        "application/xhtml+xml",
        "text/plain",
        "text/xml",
        "application/xml",
        "application/json",
    ],
    "llm": {
        "endpoint": "http://localhost:1234/v1/chat/completions",
        "model": "jinaai.readerlm-v2@q4_k_m",
        "max_tokens": 16529,
        "temperature": 0.7,
        "llm_prompt_template": (
            "Please summarize the following webpage content and extract a list of relevant tags. "
            "Return your answer as JSON with keys 'summary' and 'tags'."
        ),
        "system_prompt": "You are a helpful assistant that summarizes webpages and extracts tags.",
    },
    "connection_string": None,
}


def load_dotenv(env_file: str = ENV_FILE) -> None:
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def update_env(key: str, value: str, env_file: str = ENV_FILE) -> None:
    """
    Update or add a key/value pair in the .env file and set it in os.environ.
    """
    env_vars = {}
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
    env_vars[key] = value
    with open(env_file, "w") as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")
    os.environ[key] = value


def load_config(config_file: str = CONFIG_FILE) -> dict:
    load_dotenv()
    config = {}
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            config = yaml.safe_load(f) or {}
    updated = False
    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value
            updated = True
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if sub_key not in config[key]:
                    config[key][sub_key] = sub_value
                    updated = True
        elif isinstance(value, list):
            for item in value:
                if item not in config[key]:
                    config[key].append(item)
                    updated = True

    # Read the connection string from environment if available.
    db_connection = os.getenv("DB_CONNECTION_STRING")
    if db_connection:
        config["connection_string"] = db_connection
    else:
        config["connection_string"] = "sqlite:///python.db"

    if config.get("max_depth", 2) == 0:
        config["recursive_crawl"] = False

    if updated:
        with open(config_file, "w") as f:
            yaml.dump(config, f)
        logger.info(f"Updated configuration file {config_file} with missing keys.")
    return config
