 # Safarnama
 
 Safarnama is named after the famous travel book [Safarnama](https://en.wikipedia.org/wiki/Safarnama) by [Nasir Khusraw](https://en.wikipedia.org/wiki/Nasir_Khusraw), a renowned Persian traveler, philosopher, and writer.
 Inspired by his journeys, Safarnama traverses the web, cleans up pages, and gathers useful information.
 
 In addition to standard web crawling and content processing, Safarnama now includes a search ability.
 You can perform searches (e.g., "open source tech books"), retrieve links from search results via Se​arxNG instances,
 and process those links with the crawler to, for example, download PDFs.
 
 ## Features
 
 - **Web Crawling:** Begins at a base URL and explores linked pages up to a specified depth.
 - **Content Processing:** Cleans HTML by removing scripts, styles, comments, and extraneous elements.
 - **LLM Integration:** Summarizes page content and extracts key tags via a Language Model endpoint.
 - **Search Integration:** Uses Se​arxNG to search for queries, fetch links, and feed them into the crawler.
 - **Data Storage:** Persists URL data, summaries, and tags in a SQLite database.
 - **Sitemap Generation:** Optionally generates an XML sitemap of crawled URLs.
 
 ## Installation
 
 Install Safarnama via pip:
 
 ```bash
 pip install safarnama
 ```
 
 ## Usage (Command-Line)
 
 Initialize the configuration file (interactive or quiet mode):
 ```bash
 safarnama init
 ```
 
 Start the crawler:
 ```bash
 safarnama start
 ```
 
 Test the LLM endpoint:
 ```bash
 safarnama test_llm
 ```
 
 **New:** Perform a search and process the results:
 ```bash
 safarnama search "open source tech books"
 ```
 This command uses Se​arxNG instances to search for the query, extracts links from the search results, and
 then feeds those links to the crawler for further processing (e.g., downloading PDFs).
 
 ## Sample Configuration File (`config.yaml`)
 
 ```yaml
 base_url: "https://www.techbend.io"
 max_depth: 2
 delay: 1
 db_path: "techbend.db"
 verbose: true
 save: true
 log_file: "techbend.log"
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
   llm_prompt_template: "Please summarize the following webpage content and extract a list of relevant tags. Return your answer as JSON with keys 'summary' and 'tags'."
   system_prompt: "You are a helpful assistant that summarizes webpages and extracts tags."
 ```
 
 **Note:** The LLM API key is managed via a separate `.env` file and is not stored in this configuration file.
 
 ## Programmatic Usage
 
 Safarnama can be used both as a CLI tool and as a library in your Python projects. For example:
 
 ```python
 from safarnama.config import load_config
 from safarnama.db import DBHandler
 from safarnama.searcher import SearxNGSearcher
 from safarnama.crawler import SiteCrawler
 
 # Load configuration from the YAML file
 config = load_config("config.yaml")
 
 # Create a DBHandler instance using the connection string from the config
 db = DBHandler(config.get("connection_string", "sqlite:///python.db"))
 
 # Create a SearxNGSearcher instance with a few retries
 searcher = SearxNGSearcher(db, retries=2)
 
 # Perform a search query (e.g., "open source tech books")
 result = searcher.search("open source tech books")
 
 if result:
     instance_used, data = result
     # Assume the search results contain a 'results' field with dictionaries that include a 'url'
     links = [item["url"] for item in data.get("results", []) if "url" in item]
     print(f"Found {len(links)} links.")
 
     # Create a crawler instance and add the search result links for processing
     crawler = SiteCrawler(config)
     for link in links:
         crawler.add_url(link, 0)
 
     # Start crawling and retrieve visited URLs
     visited_urls = crawler.crawl()
     print(f"Crawled {len(visited_urls)} URLs from search results.")
 
     # Optionally, generate an XML sitemap of the crawled URLs
     sitemap_tree = crawler.generate_sitemap(visited_urls)
     sitemap_tree.write("sitemap.xml", encoding="utf-8", xml_declaration=True)
 
     crawler.close()
 else:
     print("No healthy instance available to perform the search.")
 
 searcher.close()
 db.close()

 ```
 
 ## Contributing
 
 Contributions are welcome! Please:
 1. Fork the repository.
 2. Create a new branch for your feature or bugfix.
 3. Write your code and tests.
 4. Run tests to ensure everything works.
 5. Submit a pull request with a clear description.
 
 ## License
 
 This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
 
 ## ✨ Contributors
 
 <a href="https://github.com/tavallaie/safarnama/graphs/contributors">
   <img src="https://contrib.rocks/image?repo=tavallaie/safarnama" />
 </a>
