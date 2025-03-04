import sys
import os
import typer
from loguru import logger

from safarnama.config import load_config, update_env, CONFIG_FILE, DEFAULT_CONFIG
from safarnama.crawler import SiteCrawler
from safarnama.logger_setup import setup_logger
from safarnama.searcher import SearxNGSearcher
from safarnama.db import DBHandler

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
            "Max Depth (0 means no recursion)",
            default=DEFAULT_CONFIG["max_depth"],
            type=int,
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
        recursive_crawl = max_depth != 0
        download_binaries = typer.confirm(
            "Download binary files (instead of skipping)?",
            default=DEFAULT_CONFIG["download_binaries"],
        )
        download_specific_binaries_input = typer.prompt(
            "Specific binary extensions to download (comma separated)",
            default=",".join(DEFAULT_CONFIG["download_specific_binaries"])
            if DEFAULT_CONFIG["download_specific_binaries"]
            else "",
        )
        download_specific_binaries = [
            ext.strip()
            for ext in download_specific_binaries_input.split(",")
            if ext.strip()
        ]
        find_images = typer.confirm(
            "Find and download images?", default=DEFAULT_CONFIG["find_images"]
        )
        respect_robots = typer.confirm(
            "Respect robots.txt rules?", default=DEFAULT_CONFIG["respect_robots"]
        )
        exclude_url_input = typer.prompt(
            "Exclude URL patterns (comma separated)",
            default=",".join(DEFAULT_CONFIG["exclude_url_patterns"])
            if DEFAULT_CONFIG["exclude_url_patterns"]
            else "",
        )
        exclude_url_patterns = [
            pattern.strip()
            for pattern in exclude_url_input.split(",")
            if pattern.strip()
        ]
        exclude_content_input = typer.prompt(
            "Exclude content patterns (comma separated)",
            default=",".join(DEFAULT_CONFIG["exclude_content_patterns"])
            if DEFAULT_CONFIG["exclude_content_patterns"]
            else "",
        )
        exclude_content_patterns = [
            pattern.strip()
            for pattern in exclude_content_input.split(",")
            if pattern.strip()
        ]
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
        llm_prompt_template = typer.prompt(
            "LLM Prompt Template", default=DEFAULT_CONFIG["llm"]["llm_prompt_template"]
        )
        system_prompt = typer.prompt(
            "LLM System Prompt", default=DEFAULT_CONFIG["llm"]["system_prompt"]
        )

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
            "recursive_crawl": recursive_crawl,
            "download_binaries": download_binaries,
            "download_specific_binaries": download_specific_binaries,
            "find_images": find_images,
            "respect_robots": respect_robots,
            "exclude_url_patterns": exclude_url_patterns,
            "exclude_content_patterns": exclude_content_patterns,
            "binary_extensions": binary_extensions,
            "accepted_content_types": accepted_content_types,
            "llm": {
                "endpoint": llm_endpoint,
                "model": llm_model,
                "max_tokens": llm_max_tokens,
                "temperature": llm_temperature,
                "llm_prompt_template": llm_prompt_template,
                "system_prompt": system_prompt,
            },
        }
    else:
        config = DEFAULT_CONFIG

    import yaml

    with open(config_file, "w") as f:
        yaml.dump(config, f)
    typer.echo(f"Configuration file created at {config_file}")


@app.command()
def start(
    config_file: str = typer.Option(
        CONFIG_FILE, help="Path to configuration YAML file"
    ),
):
    config = load_config(config_file)
    setup_logger(
        config.get("verbose", True),
        config.get("save", True),
        config.get("log_file", "python.log"),
    )
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
def search(
    query: str,
    config_file: str = typer.Option(
        CONFIG_FILE, help="Path to configuration YAML file"
    ),
):
    """
    Search for a query using SearxNG instances and process the resulting links with the crawler.
    """
    config = load_config(config_file)
    db = DBHandler(config.get("connection_string", "sqlite:///python.db"))
    searcher = SearxNGSearcher(db, retries=2)
    result = searcher.search(query)
    if result:
        instance_used, data = result
        # Assume search JSON contains a "results" field with link dictionaries.
        links = [item["url"] for item in data.get("results", []) if "url" in item]
        typer.echo(f"Found {len(links)} links. Processing with crawler...")
        crawler = SiteCrawler(config)
        for link in links:
            crawler.add_url(link, 0)
        visited = crawler.crawl()
        typer.echo(f"Crawled {len(visited)} URLs from search results.")
        crawler.close()
    else:
        typer.echo("No healthy instance available to perform the search.")
    searcher.close()
    db.close()


@app.command()
def test_llm():
    config = load_config()
    crawler = SiteCrawler(config)
    logger.info("Testing LLM endpoint...")
    summary, tags = crawler.get_summary_and_tags("This is a test request.")
    logger.info(f"LLM test summary: {summary}")
    logger.info(f"LLM test tags: {tags}")


def run():
    if len(sys.argv) == 1:
        sys.argv.append("--help")
    app()


if __name__ == "__main__":
    run()
