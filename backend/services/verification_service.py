# services/verification_service.py
import time
from typing import List
from datetime import datetime

from models.verification_models import (
    Claim, CompleteVerificationResult,
    ProcessedInput, VerificationResultSummary
)

from services.webscraper_service import webscraper_service
from services.news_service import news_service
from services.gemini_service import extract_claims, verify_against_sources


async def process_input(input_type: str, content: str) -> ProcessedInput:
    if input_type == "text":
        return ProcessedInput(
            originalContent=content,
            extractedText=content,
            title="User Text"
        )

    elif input_type == "link":
        try:
            scraped = await webscraper_service.scrape_url(content)
            return ProcessedInput(
                originalContent=content,
                extractedText=scraped.get("content", ""),
                title=scraped.get("title"),
                url=scraped.get("url"),
                source=scraped.get("siteName")
            )
        except:
            return ProcessedInput(
                originalContent=content,
                extractedText=f"Content from: {content}",
                title="Link Content",
                url=content
            )

    elif input_type == "video":
        return ProcessedInput(
            originalContent=content,
            extractedText=f"Video content: {content}",
            title="Video Content"
        )

    raise ValueError("Invalid type")


async def verify_content(input_type: str, content: str) -> CompleteVerificationResult:
    start = time.time()

    processed = await process_input(input_type, content)

    # extract claims
    claims: List[Claim] = await extract_claims(processed.extractedText)

    # search news
    words = [w for w in processed.extractedText.split() if len(w) > 4][:8]
    query = " ".join(words) if words else "news"

    try:
        articles = await news_service.search_news(query, page_size=15)
    except:
        articles = []

    verification: VerificationResultSummary = await verify_against_sources(
        claims, articles, processed.extractedText
    )

    processing_time = int((time.time() - start) * 1000)
    print(  f"Verification processed in {processing_time} ms")
    print(  f"Claims extracted: {len(claims)}")
    print(  f"Articles considered: {len(articles)}")
    print(  f"Truth Score: {verification.truthScore}")
    
    return CompleteVerificationResult(
        claims=claims,
        verification=verification,
        input=processed,
        relatedArticles=articles[:10],
        processingTime=processing_time,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
