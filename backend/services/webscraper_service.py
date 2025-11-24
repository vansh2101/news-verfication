# services/webscraper_service.py
import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any
from urllib.parse import urlparse

class WebScraperService:
    async def fetch_html(self, url: str) -> str:
        # Simple fetch, set a browser-like user-agent
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; TruthLensBot/1.0; +https://example.com/bot)"
        }
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.text

    def clean_text(self, text: str) -> str:
        text = " ".join(text.split())
        return text

    def extract_content(self, html: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")

        # Try Open Graph title/description
        og_title = soup.find("meta", property="og:title")
        og_description = soup.find("meta", property="og:description")
        og_site = soup.find("meta", property="og:site_name")

        title = (og_title["content"] if og_title and og_title.get("content") else None) or \
                (soup.title.string if soup.title else None) or ""

        description = (og_description["content"] if og_description and og_description.get("content") else "")

        # Try common article selectors
        selectors = [
            "article",
            '[role="main"]',
            ".article-content",
            ".post-content",
            ".entry-content",
            ".content",
            "main",
            ".story-body",
            ".article-body"
        ]
        content = ""
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                content = el.get_text(separator=" ", strip=True)
                if len(content) > 150:
                    break

        # Fallback to large <p> tags
        if not content or len(content) < 120:
            paragraphs = [p.get_text(separator=" ", strip=True) for p in soup.find_all("p")]
            paragraphs = [p for p in paragraphs if len(p) > 60]
            content = " ".join(paragraphs[:20])

        content = self.clean_text(" ".join([t for t in [title, description, content] if t]))
        site = og_site["content"] if og_site and og_site.get("content") else urlparse(url).hostname
        return {
            "title": title,
            "content": content[:8000],
            "url": url,
            "siteName": site
        }

    async def scrape_url(self, url: str):
        html = await self.fetch_html(url)
        return self.extract_content(html, url)

webscraper_service = WebScraperService()
