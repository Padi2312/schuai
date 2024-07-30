from duckduckgo_search import DDGS
from goose3 import Goose


class WebScraper:
    def __init__(self, max_results=3):
        self.ddgs = DDGS()
        self.max_results = max_results
        self.goose = Goose()

    def search_and_scrape(self, keywords):
        # Search for the keywords
        results = self.ddgs.text(
            keywords,
            max_results=self.max_results,
            safesearch="off",
        )
        scraped_content = []

        for result in results:
            try:
                # Scrape the content using Goose
                article = self.goose.extract(url=result["href"])
                scraped_content.append(
                    {
                        "title": article.title,
                        "url": result["href"],
                        "content": article.cleaned_text,
                    }
                )
            except Exception as e:
                print(f"Error scraping {result['href']}: {e}")

        return scraped_content
