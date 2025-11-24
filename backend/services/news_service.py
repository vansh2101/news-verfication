# services/news_service.py
import httpx
from typing import List, Dict, Any
from config import NEWSAPI_KEY

BASE_URL = "https://newsapi.org/v2"

class NewsAPIService:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search_news(self, query: str, page_size: int = 20) -> List[Dict[str, Any]]:
        if not self.api_key:
            raise RuntimeError("NEWSAPI_KEY is not configured")

        url = f"{BASE_URL}/everything"
        params = {
            "q": query,
            "pageSize": page_size,
            "language": "en",
            "sortBy": "relevancy",
            "apiKey": self.api_key
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            articles = data.get("articles", [])
            # filter minimal required fields
            return [a for a in articles if a.get("title") and a.get("url")]

    async def top_headlines(self, country="us", page_size=20):
        if not self.api_key:
            raise RuntimeError("NEWSAPI_KEY is not configured")
        url = f"{BASE_URL}/top-headlines"
        params = {"country": country, "pageSize": page_size, "apiKey": self.api_key}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json().get("articles", [])

# singleton
news_service = NewsAPIService(NEWSAPI_KEY)
