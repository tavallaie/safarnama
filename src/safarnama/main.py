import os
import re
import yaml
import sqlite3
import httpx
from bs4 import BeautifulSoup
import urllib.robotparser
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
import time
import sys
import json
from loguru import logger
import typer

CONFIG_FILE = "config.yaml"
ENV_FILE = ".env"

DEFAULT_CONFIG = {
    "base_url": "https://www.techbend.io",
    "max_depth": 2,
    "delay": 1,
    "db_path": "techbend.db",
    "verbose": True,
    "save": True,
    "log_file": "techbend.log",
    "generate_sitemap": True,  # Flag to enable/disable sitemap generation
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
    },
}


def load_dotenv(env_file: str = ENV_FILE) -> None:
    """Load variables from a .env file into os.environ if not already set."""
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def load_env(env_file: str = ENV_FILE) -> dict:
    """Return a dictionary of environment variables from the .env file."""
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
    return env_vars


def update_env(key: str, value: str, env_file: str = ENV_FILE) -> None:
    """Update (or add) a key/value pair in the .env file."""
    env_vars = load_env(env_file)
    env_vars[key] = value
    with open(env_file, "w") as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")
    os.environ[key] = value


# Load variables from .env early on
load_dotenv()


def load_config(config_file: str = CONFIG_FILE) -> dict:
    """
    Load configuration from a YAML file and update missing keys.
    If an environment variable 'LLM_API_KEY' is set, it overrides the API key.
    """
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

    # Override LLM API key from environment if available.
    env_api_key = os.getenv("LLM_API_KEY")
    if env_api_key:
        config["llm"]["api_key"] = env_api_key

    if updated:
        with open(config_file, "w") as f:
            yaml.dump(config, f)
        logger.info(f"Updated configuration file {config_file} with missing keys.")
    return config


def update_config_binary_extension(
    new_ext: str, config_file: str = CONFIG_FILE
) -> list:
    """
    Update the YAML config file with a new binary extension if it's not already present.
    """
    new_ext = new_ext.lower()
    config = load_config(config_file)
    if "binary_extensions" not in config:
        config["binary_extensions"] = DEFAULT_CONFIG["binary_extensions"].copy()
    if new_ext not in config["binary_extensions"]:
        config["binary_extensions"].append(new_ext)
        with open(config_file, "w") as f:
            yaml.dump(config, f)
        logger.info(f"Added new binary extension to config: {new_ext}")
    return config["binary_extensions"]


class HTMLCleaner:
    SCRIPT_PATTERN = r"<[ ]*script.*?\/[ ]*script[ ]*>"
    STYLE_PATTERN = r"<[ ]*style.*?\/[ ]*style[ ]*>"
    META_PATTERN = r"<[ ]*meta.*?>"
    COMMENT_PATTERN = r"<[ ]*!--.*?--[ ]*>"
    LINK_PATTERN = r"<[ ]*link.*?>"
    BASE64_IMG_PATTERN = r'<img[^>]+src="data:image/[^;]+;base64,[^"]+"[^>]*>'
    SVG_PATTERN = r"(<svg[^>]*>)(.*?)(<\/svg>)"

    @classmethod
    def replace_svg(cls, html: str, new_content: str = "this is a placeholder") -> str:
        return re.sub(
            cls.SVG_PATTERN,
            lambda match: f"{match.group(1)}{new_content}{match.group(3)}",
            html,
            flags=re.DOTALL,
        )

    @classmethod
    def replace_base64_images(cls, html: str, new_image_src: str = "#") -> str:
        return re.sub(cls.BASE64_IMG_PATTERN, f'<img src="{new_image_src}"/>', html)

    @classmethod
    def clean_html(
        cls, html: str, clean_svg: bool = False, clean_base64: bool = False
    ) -> str:
        html = re.sub(
            cls.SCRIPT_PATTERN, "", html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        html = re.sub(
            cls.STYLE_PATTERN, "", html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        html = re.sub(
            cls.META_PATTERN, "", html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        html = re.sub(
            cls.COMMENT_PATTERN,
            "",
            html,
            flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        html = re.sub(
            cls.LINK_PATTERN, "", html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        if clean_svg:
            html = cls.replace_svg(html)
        if clean_base64:
            html = cls.replace_base64_images(html)
        return html


class SiteCrawler:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.base_url = config.get("base_url")
        self.max_depth = config.get("max_depth", 2)
        self.delay = config.get("delay", 1)
        self.db_path = config.get("db_path", "python.db")
        self.verbose = config.get("verbose", True)
        self.save = config.get("save", True)
        self.log_file = config.get("log_file", "python.log")
        self.llm_config = config.get("llm", {})
        self.accepted_content_types = config.get("accepted_content_types")
        self.binary_extensions = config.get("binary_extensions", [])

        self.conn = None
        self.rp = None

        self.setup_logger()
        self.setup_db()
        self.rp = self.get_robots_parser(self.base_url)
        self.html_cleaner = HTMLCleaner

    def setup_logger(self) -> None:
        logger.remove()
        if not self.verbose and not self.save:
            logger.disable("crawler")
        else:
            if self.verbose:
                logger.add(sys.stdout, level="INFO", enqueue=True)
            if self.save:
                logger.add(self.log_file, rotation="10 MB", level="INFO", enqueue=True)

    def setup_db(self) -> None:
        self.conn = sqlite3.connect(self.db_path)
        c = self.conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                url TEXT PRIMARY KEY,
                depth INTEGER,
                status TEXT,
                content_type TEXT,
                summary TEXT,
                tags TEXT
            )
            """
        )
        self.conn.commit()

    def is_binary_url(self, url: str) -> bool:
        for ext in self.binary_extensions:
            if url.lower().endswith(ext):
                return True
        return False

    def add_url(
        self, url: str, depth: int, status: str = "to_visit", content_type: str = None
    ) -> None:
        if self.is_binary_url(url):
            logger.info(f"Skipping binary URL (pre-request): {url}")
            self.update_url_status(url, "ignored", "binary")
            return
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO urls (url, depth, status, content_type) VALUES (?, ?, ?, ?)",
                (url, depth, status, content_type),
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error adding URL {url}: {e}")

    def get_next_url(self) -> tuple:
        c = self.conn.cursor()
        c.execute(
            "SELECT url, depth FROM urls WHERE status = 'to_visit' AND depth <= ? ORDER BY depth LIMIT 1",
            (self.max_depth,),
        )
        row = c.fetchone()
        return (row[0], row[1]) if row else (None, None)

    def update_url_status(
        self, url: str, status: str, content_type: str = None
    ) -> None:
        self.conn.execute(
            "UPDATE urls SET status = ?, content_type = ? WHERE url = ?",
            (status, content_type, url),
        )
        self.conn.commit()

    def update_page_info(self, url: str, summary: str, tags: str) -> None:
        self.conn.execute(
            "UPDATE urls SET summary = ?, tags = ? WHERE url = ?",
            (summary, tags, url),
        )
        self.conn.commit()

    def get_robots_parser(self, base_url: str) -> urllib.robotparser.RobotFileParser:
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
        except Exception as e:
            logger.error(f"Error reading robots.txt from {robots_url}: {e}")
        return rp

    def is_allowed(self, url: str, user_agent: str = "*") -> bool:
        return self.rp.can_fetch(user_agent, url)

    def get_summary_and_tags(self, text: str) -> tuple:
        cleaned_text = self.html_cleaner.clean_html(
            text, clean_svg=True, clean_base64=True
        )
        prompt = (
            "Please summarize the following webpage content and extract a list "
            "of relevant tags. Return your answer as a JSON object with keys "
            "'summary' (a string) and 'tags' (an array of strings).\n\n" + cleaned_text
        )
        payload = {
            "model": self.llm_config.get("model", ""),
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes webpages and extracts tags.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.llm_config.get("max_tokens", 200000),
            "temperature": self.llm_config.get("temperature", 0.7),
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.llm_config.get('api_key', '')}",
        }
        timeout_config = httpx.Timeout(
            120.0, connect=120.0, read=120.0, write=120.0, pool=120.0
        )
        retries = 3
        for attempt in range(retries):
            try:
                endpoint = self.llm_config.get("endpoint", "")
                logger.info(f"Sending request to LLM endpoint: {endpoint}")
                response = httpx.post(
                    endpoint, json=payload, headers=headers, timeout=timeout_config
                )
                response.raise_for_status()
                response_json = response.json()
                if "error" in response_json:
                    logger.error(f"LLM returned error: {response_json['error']}")
                    return "", []
                choices = response_json.get("choices")
                if not choices:
                    logger.error(f"LLM response missing 'choices': {response_json}")
                    return "", []
                content = choices[0]["message"]["content"]
                if content.startswith("```json"):
                    content = content[len("```json") :].strip()
                if content.endswith("```"):
                    content = content[:-3].strip()
                result = json.loads(content)
                summary = result.get("summary", "")
                tags = result.get("tags", [])
                return summary, tags
            except httpx.TimeoutException as e:
                logger.error(f"LLM request timeout on attempt {attempt+1}: {e}")
                time.sleep(2)
            except Exception as e:
                logger.error(f"LLM request error on attempt {attempt+1}: {e}")
                break
        return "", []

    def crawl(self) -> set:
        self.add_url(self.base_url, 0, status="to_visit")
        visited_urls = set()

        with httpx.Client(timeout=10) as client:
            while True:
                current_url, depth = self.get_next_url()
                if not current_url:
                    break

                if self.is_binary_url(current_url):
                    logger.info(f"Skipping binary URL (pre-request): {current_url}")
                    self.update_url_status(current_url, "ignored", "binary")
                    continue

                logger.info(f"Processing {current_url} at depth {depth}")
                if not self.is_allowed(current_url):
                    logger.info(f"Skipping disallowed URL: {current_url}")
                    self.update_url_status(current_url, "ignored")
                    continue
                try:
                    response = client.get(current_url)
                except Exception as e:
                    logger.error(f"Error fetching {current_url}: {e}")
                    self.update_url_status(current_url, "ignored")
                    continue

                content_type = (
                    response.headers.get("Content-Type", "").split(";")[0].strip()
                )
                if content_type not in self.accepted_content_types:
                    logger.info(
                        f"Ignoring {current_url}: unsupported content type '{content_type}'"
                    )
                    self.update_url_status(current_url, "ignored", content_type)
                    if content_type == "application/octet-stream":
                        parsed = urlparse(current_url)
                        ext = os.path.splitext(parsed.path)[1]
                        if ext and ext not in self.binary_extensions:
                            self.binary_extensions = update_config_binary_extension(ext)
                            self.config = load_config()
                            self.binary_extensions = self.config.get(
                                "binary_extensions", []
                            )
                    continue

                self.update_url_status(current_url, "visited", content_type)
                visited_urls.add(current_url)

                if "html" in content_type.lower():
                    summary, tags = self.get_summary_and_tags(response.text)
                    logger.info(f"Summary for {current_url}: {summary}")
                    logger.info(f"Tags for {current_url}: {tags}")
                    tags_str = ", ".join(
                        (tag.get("name", "") if isinstance(tag, dict) else tag).replace(
                            "/", ""
                        )
                        for tag in tags
                    )
                    self.update_page_info(current_url, summary, tags_str)

                    soup = BeautifulSoup(response.text, "html.parser")
                    for link in soup.find_all("a", href=True):
                        href = link.get("href")
                        if href.startswith("#") or not href.strip():
                            continue
                        absolute_url = urljoin(current_url, href)
                        if (
                            urlparse(absolute_url).netloc
                            == urlparse(self.base_url).netloc
                        ):
                            self.add_url(absolute_url, depth + 1)
                time.sleep(self.delay)
        return visited_urls

    def generate_sitemap(self, urls: set) -> ET.ElementTree:
        urlset = ET.Element(
            "urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        )
        for url in urls:
            url_elem = ET.SubElement(urlset, "url")
            loc = ET.SubElement(url_elem, "loc")
            loc.text = url
        return ET.ElementTree(urlset)

    def close(self) -> None:
        if self.conn:
            self.conn.close()


def test_llm_endpoint() -> None:
    """
    A helper function to test connectivity to the LLM endpoint.
    """
    config = load_config()
    endpoint = config.get("llm", {}).get("endpoint", "")
    payload = {
        "model": config.get("llm", {}).get("model", ""),
        "messages": [{"role": "system", "content": "This is a test request."}],
        "max_tokens": config.get("llm", {}).get("max_tokens", 200000),
        "temperature": config.get("llm", {}).get("temperature", 0.7),
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.get('llm', {}).get('api_key', '')}",
    }
    try:
        logger.info(f"Testing LLM endpoint connectivity: {endpoint}")
        response = httpx.post(endpoint, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        logger.info(f"LLM test response: {response.json()}")
    except Exception as e:
        logger.error(f"LLM endpoint test failed: {e}")


app = typer.Typer()


@app.command()
def init(
    config_file: str = typer.Option(
        CONFIG_FILE, help="Path to configuration YAML file"
    ),
    interactive: bool = typer.Option(
        None, "-i", "--interactive", help="Run in interactive mode"
    ),
    quiet: bool = typer.Option(
        False, "-qq", "--quiet", help="Do not run interactively (use default config)"
    ),
):
    """
    Initialize a new configuration file.
    If no flag is provided, the user will be prompted to choose interactive mode.
    The LLM API key is not stored in the YAML file. Instead, if provided interactively,
    it is saved in a .env file as 'LLM_API_KEY'. If an API key is already set in the environment,
    the prompt is skipped.
    """
    if interactive and quiet:
        typer.echo(
            "Error: Interactive and quiet options cannot be used together. Please choose one."
        )
        raise typer.Exit(code=1)

    if quiet:
        interactive_mode = False
    elif interactive is None:
        interactive_mode = typer.confirm(
            "Do you want to create the configuration interactively?", default=True
        )
    else:
        interactive_mode = interactive

    if interactive_mode:
        base_url = typer.prompt("Base URL", default=DEFAULT_CONFIG["base_url"])
        max_depth = typer.prompt(
            "Max Depth", default=DEFAULT_CONFIG["max_depth"], type=int
        )
        delay = typer.prompt(
            "Delay (seconds)", default=DEFAULT_CONFIG["delay"], type=float
        )
        db_path = typer.prompt("Database Path", default=DEFAULT_CONFIG["db_path"])
        verbose = typer.confirm("Verbose logging?", default=DEFAULT_CONFIG["verbose"])
        save = typer.confirm("Save log to file?", default=DEFAULT_CONFIG["save"])
        log_file = typer.prompt("Log File", default=DEFAULT_CONFIG["log_file"])
        generate_sitemap = typer.confirm(
            "Generate sitemap?", default=DEFAULT_CONFIG["generate_sitemap"]
        )
        binary_ext_input = typer.prompt(
            "Binary Extensions (comma separated)",
            default=",".join(DEFAULT_CONFIG["binary_extensions"]),
        )
        binary_extensions = [
            ext.strip() for ext in binary_ext_input.split(",") if ext.strip()
        ]
        accepted_types_input = typer.prompt(
            "Accepted Content Types (comma separated)",
            default=",".join(DEFAULT_CONFIG["accepted_content_types"]),
        )
        accepted_content_types = [
            ctype.strip() for ctype in accepted_types_input.split(",") if ctype.strip()
        ]

        typer.echo("Configure LLM settings:")
        llm_endpoint = typer.prompt(
            "LLM Endpoint", default=DEFAULT_CONFIG["llm"]["endpoint"]
        )
        llm_model = typer.prompt("LLM Model", default=DEFAULT_CONFIG["llm"]["model"])
        llm_max_tokens = typer.prompt(
            "LLM Max Tokens", default=DEFAULT_CONFIG["llm"]["max_tokens"], type=int
        )
        llm_temperature = typer.prompt(
            "LLM Temperature", default=DEFAULT_CONFIG["llm"]["temperature"], type=float
        )

        # Check if LLM_API_KEY is already set in .env/environment.
        if os.getenv("LLM_API_KEY"):
            typer.echo("Found LLM_API_KEY in the environment. Skipping API key prompt.")
        else:
            llm_api_key = typer.prompt("LLM API Key", default="")
            update_env("LLM_API_KEY", llm_api_key)

        config = {
            "base_url": base_url,
            "max_depth": max_depth,
            "delay": delay,
            "db_path": db_path,
            "verbose": verbose,
            "save": save,
            "log_file": log_file,
            "generate_sitemap": generate_sitemap,
            "binary_extensions": binary_extensions,
            "accepted_content_types": accepted_content_types,
            "llm": {
                "endpoint": llm_endpoint,
                "model": llm_model,
                "max_tokens": llm_max_tokens,
                "temperature": llm_temperature,
            },
        }
    else:
        config = DEFAULT_CONFIG

    with open(config_file, "w") as f:
        yaml.dump(config, f)
    typer.echo(f"Configuration file created at {config_file}")


@app.command()
def start(
    config_file: str = typer.Option(
        CONFIG_FILE, help="Path to configuration YAML file"
    ),
):
    """
    Start crawling the website specified in the configuration.
    """
    config = load_config(config_file)
    crawler = SiteCrawler(config)
    logger.info(
        f"Starting crawl of {crawler.base_url} with max depth {crawler.max_depth}"
    )
    visited_urls = crawler.crawl()
    logger.info(f"Crawled {len(visited_urls)} URLs.")

    if config.get("generate_sitemap", True):
        sitemap_tree = crawler.generate_sitemap(visited_urls)
        sitemap_tree.write("sitemap.xml", encoding="utf-8", xml_declaration=True)
        logger.info("Sitemap generated as sitemap.xml")
    else:
        logger.info("Sitemap generation is disabled by configuration.")
    crawler.close()


@app.command()
def test_llm():
    """
    Test connectivity to the LLM endpoint.
    """
    test_llm_endpoint()


def run():
    if len(sys.argv) == 1:
        sys.argv.append("--help")
    app()


if __name__ == "__main__":
    # If no command-line arguments are provided, show the help message.
    run()
