# Safarnama

Safarnama is named after the famous travel book [Safarnama](https://en.wikipedia.org/wiki/Safarnama) by [Nasir Khusraw](https://en.wikipedia.org/wiki/Nasir_Khusraw), a well-known Persian traveler, philosopher, and writer.
In his book, Nasir Khusraw shared his adventures and experiences as he traveled far and wide.
Inspired by this classic work, our tool sets out on a journey across the internet, visiting websites and gathering useful information.

As it explores, Safarnama cleans up web pages by removing unnecessary parts like scripts and styles. It also uses a language model to create easy-to-read summaries and extract key tags.

Whether you are a developer looking to add web crawling to your project or a user who enjoys a simple command-line tool, Safarnama is designed for both.
It works both from the command line and programmatically in your own Python code.

Join Safarnama on its adventure as it writes its own digital story—one website at a time.


## Features

- **Web Crawling:** Starts at a base URL and explores linked pages up to a specified depth.
- **Content Processing:** Cleans HTML content by removing scripts, styles, comments, and other extraneous elements.
- **LLM Integration:** Summarizes page content and extracts relevant tags by communicating with a Language Model endpoint.
- **Data Storage:** Saves discovered URL data, summaries, and tags in a SQLite database.
- **Sitemap Generation:** Optionally creates an XML sitemap of all crawled URLs.

## Installation

Install Safarnama via pip:

```bash
pip install safarnama
```

## Usage (Command-Line)

Begin your digital expedition from the command line:

```bash
safarnama init      # Initialize the configuration file (interactive or quiet mode)
safarnama start     # Start crawling based on the configuration
safarnama test_llm  # Test connectivity to the LLM endpoint
```

Running the tool without any arguments will automatically display the help message.

## Sample Configuration File (`config.yaml`)

```yaml
base_url: "https://www.python.org"
max_depth: 2
delay: 1
db_path: "python.db"
verbose: true
save: true
log_file: "python.log"
generate_sitemap: true
binary_extensions:
  - ".pdf"
  - ".zip"
  - ".exe"
  - ".tar"
  - ".tar.gz"
  - ".tgz"
  - ".rar"
  - ".iso"
  - ".bin"
  - ".7z"
  - ".dmg"
  - ".tar.xz"
  - ".pkg"
  - ".bz2"
accepted_content_types:
  - "text/html"
  - "application/xhtml+xml"
  - "text/plain"
  - "text/xml"
  - "application/xml"
  - "application/json"
llm:
  endpoint: "http://localhost:1234/v1/chat/completions"
  model: "jinaai.readerlm-v2@q4_k_m"
  max_tokens: 16529
  temperature: 0.7
```

**Note:** The LLM API key is managed via a separate `.env` file and is not stored in this configuration file.

## Programmatic Usage

Safarnama is not only a command-line tool but can also be used programmatically in your Python projects. Below is an example of how to integrate its crawling capabilities:

```python
from safarnama import load_config, SiteCrawler

# Load configuration from the YAML file
config = load_config("config.yaml")

# Create a crawler instance with the loaded configuration
crawler = SiteCrawler(config)

# Start crawling and retrieve a set of visited URLs
visited_urls = crawler.crawl()

# Display the number of URLs crawled
print(f"Crawled {len(visited_urls)} URLs.")

# Optionally, generate an XML sitemap of the crawled URLs
sitemap_tree = crawler.generate_sitemap(visited_urls)
sitemap_tree.write("sitemap.xml", encoding="utf-8", xml_declaration=True)

# Close the crawler's database connection
crawler.close()
```

## Contributing

Contributions are welcome! Please follow these steps to contribute:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Write your code and tests.
4. Run the tests to make sure everything is working.
5. Submit a pull request with a clear description of your changes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

## ✨ Contributors

<!-- Thanks goes to these incredible people: -->

<a href="https://github.com/tavallaie/safarnama/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=tavallaie/safarnama" />
</a>