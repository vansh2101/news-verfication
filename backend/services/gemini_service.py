# services/gemini_service.py
import httpx
import json
import re
from typing import List, Dict, Any, Optional
from config import GEMINI_API_KEY, GEMINI_BASE_URL

from models.verification_models import Claim, SourceInfo, VerificationResultSummary

from utils.retries import retry_async

# Models to try in order
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-latest",
    "gemini-2.5-pro",
    "gemini-2.5-pro-latest",
]


async def _call_gemini_once(prompt: str, model: str, timeout: float = 30.0) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    url = f"{GEMINI_BASE_URL}/models/{model}:generateContent?key={GEMINI_API_KEY}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 8192,
        },
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=body)
        r.raise_for_status()
        data = r.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return json.dumps(data)


async def _call_gemini(prompt: str, models: Optional[List[str]] = None, retries_per_model: int = 2) -> str:
    models_to_try = models or GEMINI_MODELS
    last_err = None
    for model in models_to_try:
        try:
            # Use retry_async wrapper to allow transient network/model failures
            resp = await retry_async(lambda: _call_gemini_once(prompt, model), retries=retries_per_model, delay=1.0)
            # Basic sanity check
            if isinstance(resp, str) and len(resp.strip()) > 0:
                return resp
        except Exception as e:
            last_err = e
            # try next model
            continue
    raise RuntimeError(f"All Gemini attempts failed. Last error: {last_err}")


# -----------------------
# Claims extraction
# -----------------------
async def extract_claims(content: str) -> List[Claim]:
    """
    Use Gemini to extract up to 8 verifiable claims from text.
    Falls back to heuristic sentence-splitting if LLM fails.
    """
    prompt = f"""
Analyze the following text and extract verifiable claims. Focus on factual statements that can be fact-checked.

Text:
\"\"\"{content[:3000]}\"\"\"

For each claim, provide:
1. The exact claim text
2. Type (factual, opinion, prediction, or statistic)
3. Confidence level (0-100) that this is a verifiable claim
4. Context if needed

Return the result as a JSON array with this structure:
[
  {{
    "id": "claim_1",
    "text": "exact claim text",
    "type": "factual|opinion|prediction|statistic",
    "confidence": 85,
    "context": "optional context"
  }}
]

Limit to maximum 8 most important claims.
Only return JSON (no explanations).
"""
    try:
        raw = await _call_gemini(prompt)
        # cleanup
        txt = raw.strip().replace("```json", "").replace("```", "")
        match = re.search(r"(\[[\s\S]*\])", txt)
        json_str = match.group(1) if match else txt
        parsed = json.loads(json_str)
        claims: List[Claim] = []
        for i, item in enumerate(parsed):
            try:
                claim_id = item.get("id") or f"claim_{i+1}"
                text = (item.get("text") or "").strip()
                typ = item.get("type") if item.get("type") in ["factual", "opinion", "prediction", "statistic"] else "factual"
                confidence = int(item.get("confidence") or 70)
                context = item.get("context")
                if text:
                    claims.append(Claim(id=claim_id, text=text, type=typ, confidence=confidence, context=context))
            except Exception:
                continue
        if claims:
            return claims
    except Exception:
        pass

    # fallback: split by sentences, return top 3 sentences longer than 30 chars
    sents = [s.strip() for s in re.split(r'[.!?]\s+', content) if len(s.strip()) > 30][:3]
    fallback = []
    for i, s in enumerate(sents):
        fallback.append(Claim(id=f"fallback_{i+1}", text=s, type="factual", confidence=60, context="fallback"))
    print(fallback)
    print("Claims extraction fallback used.")
    return fallback


# -----------------------
# Verification against sources
# -----------------------
def _build_articles_text(articles: List[Dict[str, Any]]) -> str:
    lines = []
    for a in articles[:8]:
        src = (a.get("source") or {}).get("name", "Unknown")
        title = a.get("title") or ""
        desc = (a.get("description") or "")[:500]
        url = a.get("url") or ""
        lines.append(f"Source: {src}\nTitle: {title}\nDescription: {desc}\nURL: {url}\n")
    return "\n".join(lines)


async def verify_against_sources(claims: List[Claim], articles: List[Dict[str, Any]], original_content: str) -> VerificationResultSummary:
    """
    Use Gemini to evaluate claims vs articles and return a structured VerificationResultSummary.
    Falls back to conservative summary if LLM fails.
    """
    # If no articles found, short-circuit with "no evidence" style fallback
    if not articles:
        return VerificationResultSummary(
            truthScore=10,
            isLikelyMisinformation=True,
            reasons=["No matching news articles found for this claim."],
            supportingArticles=0,
            contradictingArticles=0,
            verificationSummary="No evidence found in trusted news sources. Claim appears unverified.",
            sources=[]
        )

    articles_text = _build_articles_text(articles)
    claims_text = "\n".join([f"{c.id}: {c.text} (type: {c.type}, conf: {c.confidence})" for c in claims])

    prompt = f"""
You are a fact-checking expert. Evaluate the following CLAIMS and ORIGINAL CONTENT against VERIFIED NEWS SOURCES. Return ONLY a JSON object with this exact structure (no extra keys):

{{
  "truthScore": 75,
  "isLikelyMisinformation": false,
  "reasons": ["..."],
  "supportingArticles": 3,
  "contradictingArticles": 0,
  "verificationSummary": "...",
  "sources": [
    {{"name":"BBC","url":"https://...","reliability":95,"stance":"supports"}}
  ]
}}

CLAIMS:
{claims_text}

ORIGINAL:
\"\"\"{original_content[:2000]}\"\"\"

SOURCES:
{articles_text}

Task:
- For each claim, determine if it is supported, contradicted, or not present in the provided sources.
- Count supporting and contradicting articles.
- Produce a concise verificationSummary and list the top sources (name, url, reliability 0-100, stance).
- Use a conservative scoring rubric (0-100) where lower means more likely misinformation.

Return JSON only.
"""
    try:
        raw = await _call_gemini(prompt)
        txt = raw.strip().replace("```json", "").replace("```", "")
        m = re.search(r"(\{[\s\S]*\})", txt)
        json_str = m.group(1) if m else txt
        parsed = json.loads(json_str)

        # parse sources
        sources_parsed: List[SourceInfo] = []
        for s in parsed.get("sources", [])[:8]:
            try:
                sources_parsed.append(SourceInfo(
                    name=s.get("name", "Unknown"),
                    url=s.get("url"),
                    reliability=int(s.get("reliability", 75)),
                    stance=s.get("stance", "neutral")
                ))
            except Exception:
                continue

        vs = VerificationResultSummary(
            truthScore=int(parsed.get("truthScore", 75)),
            isLikelyMisinformation=bool(parsed.get("isLikelyMisinformation", False)),
            reasons=parsed.get("reasons", [])[:5] if isinstance(parsed.get("reasons", []), list) else ["Analysis done"],
            supportingArticles=int(parsed.get("supportingArticles", 0)),
            contradictingArticles=int(parsed.get("contradictingArticles", 0)),
            verificationSummary=parsed.get("verificationSummary", "") or "",
            sources=sources_parsed
        )
        return vs
    except Exception:
        # final fallback: compute a conservative estimate based on article reliability heuristics
        avg_reliability = 75
        supporting = sum(1 for a in articles if a.get("title") and a.get("description")) // 2
        contradicting = max(0, len(articles) - supporting)
        sources_fallback = []
        for a in articles[:3]:
            try:
                name = (a.get("source") or {}).get("name", "Unknown")
                sources_fallback.append(SourceInfo(
                    name=name,
                    url=a.get("url"),
                    reliability=get_source_reliability(name),
                    stance="neutral"
                ))
            except Exception:
                continue

        return VerificationResultSummary(
            truthScore=min(90, max(20, int(avg_reliability))),
            isLikelyMisinformation=(avg_reliability < 60),
            reasons=["Fallback verification: limited or unstructured sources."],
            supportingArticles=supporting,
            contradictingArticles=contradicting,
            verificationSummary="Fallback: basic check against available sources.",
            sources=sources_fallback
        )


def get_source_reliability(name: str) -> int:
    mapping = {
        "BBC": 95, "Reuters": 93, "Associated Press": 94, "The Guardian": 90,
        "The New York Times": 92, "The Washington Post": 91, "Bloomberg": 89,
        "CNN": 88, "NPR": 87, "Al Jazeera": 85, "NDTV": 80,
        "Times of India": 78, "Hindustan Times": 75
    }
    return mapping.get(name, 75)


# Small helper to test API connectivity (useful for frontend tester)
async def test_api_key() -> Dict[str, Any]:
    try:
        resp = await _call_gemini("Say 'API key is working' if you can read this.")
        return {"success": True, "response": resp}
    except Exception as e:
        return {"success": False, "error": str(e)}
