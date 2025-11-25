#!/usr/bin/env python3
"""
multi_source_with_serpapi.py

Combined YouTube + Reddit + Twitter + GoogleNews (SerpApi) scraper
Outputs:
 - combined CSV (all sources)
 - cleaned JSON with structure:
   {
     "query": "...",
     "youtube": [{title, link, author, likes, time}, ...],
     "reddit": [...],
     "twitter": [...],
     "news": [...]
   }
"""

import os
import re
import time
import json
import base64
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

import pandas as pd
from dateutil import parser as dateparser

# YouTube imports
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi

# Reddit import
import praw
# HTTP
import requests

# SerpApi (Google News)
from serpapi import GoogleSearch
import ast
# Gemini AI
import google.generativeai as genai
# Load env
from dotenv import load_dotenv
parent_env = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
dotenv_path = os.path.join(parent_env, '.env')
load_dotenv(dotenv_path)

# -----------------
# === CONFIG ===
# -----------------
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")

# Twitter/X credentials
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")

# SerpApi (Google News) key
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

# Limits & caps
TOP_LIMIT_PER_SOURCE = 10       # number of items to retrieve per source
MAX_YT_RESULTS_PER_SEARCH = 20
MAX_TOTAL_YT_RESULTS = TOP_LIMIT_PER_SOURCE

# Requests
REQUEST_TIMEOUT = 20

# -----------------
# === HELPERS ===
# -----------------
def sanitize_for_filename(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^A-Za-z0-9 _-]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s[:40] or "results"

def iso_to_dt(s: Optional[str]):
    if not s:
        return None
    try:
        return dateparser.parse(s)
    except Exception:
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None

def safe_gemini_call(prompt_parts, model_name="gemini-2.5-flash", max_retries=3, retry_delay=2):
    """
    Safely calls Gemini with retries.
    
    Args:
        prompt_parts: list of strings or dicts for images {"mime_type": "...", "data": bytes}
        model_name: gemini model to use
        max_retries: retry attempts
        retry_delay: seconds between retries
        
    Returns:
        Gemini response object OR None if failed
    """

    model = genai.GenerativeModel(model_name)

    for attempt in range(1, max_retries + 1):
        try:
            # Gemini expects parts in a specific structure
            response = model.generate_content(prompt_parts)
            return response

        except Exception as e:
            print(f"[safe_gemini_call] ERROR on attempt {attempt}/{max_retries}: {e}")

            if attempt == max_retries:
                print("[safe_gemini_call] All retries failed.")
                return None

            print(f"[safe_gemini_call] Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)

    return None

def _extract_json_from_text(text: str) -> Optional[dict]:
    """
    Robustly extract a JSON object from `text`.

    Strategy (in order):
      1. If there's a ```json ... ``` fence, extract its inner content and try to json.loads().
      2. Trim leading/trailing quotes and whitespace and try direct json.loads().
      3. Find the first '{' then scan forward to the matching '}' (balanced braces) and try json.loads() on that slice.
      4. Try to unescape obvious escapes (e.g. '\"', '\\n') and json.loads() again.
      5. Try ast.literal_eval (last resort).
      6. Return None if parsing fails.

    Returns parsed dict on success, else None.
    """
    if not text:
        return None
    s = text.strip()

    # 1) Code-fence extraction (```json ... ``` or ``` ... ```)
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, flags=re.DOTALL | re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except Exception:
            # fall through to other strategies using candidate as the base string
            s = candidate

    # Remove surrounding quotes if the whole thing is quoted (e.g. starts with " or ')
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        # remove only one layer of surrounding quotes
        s_unq = s[1:-1].strip()
        # also unescape escaped quotes inside
        s = s_unq.replace('\\"', '"').replace("\\'", "'")

    # 2) Try direct json.loads
    try:
        return json.loads(s)
    except Exception:
        pass

    # 3) Balanced-brace scan: find the first '{' then the matching closing '}'.
    start = s.find('{')
    if start != -1:
        depth = 0
        end = -1
        for i in range(start, len(s)):
            ch = s[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end != -1:
            candidate = s[start:end+1]
            # Try json loads directly
            try:
                return json.loads(candidate)
            except Exception:
                pass

            # 4) Try unescaping common escape sequences and retry
            try:
                # Replace escaped newlines and tabs and escaped quotes, common when JSON was double-serialized
                cand2 = candidate.encode('utf-8').decode('unicode_escape')
                # also remove Unicode NUL if any
                cand2 = cand2.replace('\x00', '')
                return json.loads(cand2)
            except Exception:
                pass

            # 5) Last resort: ast.literal_eval (accepts Python dicts with single quotes)
            try:
                pyobj = ast.literal_eval(candidate)
                if isinstance(pyobj, dict):
                    return pyobj
            except Exception:
                pass

    # Nothing worked
    return None

# -----------------
# === YOUTUBE ===
# -----------------
def build_youtube_client():
    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_API_KEY)

def search_youtube(youtube, query: str, order: str = None, max_results: int = MAX_YT_RESULTS_PER_SEARCH, region_code: str = 'IN', videoDuration: Optional[str]=None):
    params = dict(part='snippet', q=query, type='video', maxResults=max_results, regionCode=region_code)
    if order:
        params['order'] = order
    if videoDuration:
        params['videoDuration'] = videoDuration
    try:
        resp = youtube.search().list(**params).execute()
        return resp.get('items', [])
    except Exception as e:
        print("[youtube] search error:", e)
        return []

def get_video_details(youtube, video_ids: List[str]):
    if not video_ids:
        return {}
    result = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        try:
            resp = youtube.videos().list(part='snippet,statistics,contentDetails', id=','.join(batch)).execute()
            for item in resp.get('items', []):
                result[item['id']] = item
        except Exception as e:
            print("[youtube] videos.list batch error:", e)
    return result

def parse_iso8601_duration(duration: str) -> int:
    try:
        hours = minutes = seconds = 0
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
        if not m:
            return 0
        h, mnt, sec = m.groups()
        if h: hours = int(h)
        if mnt: minutes = int(mnt)
        if sec: seconds = int(sec)
        return hours*3600 + minutes*60 + seconds
    except Exception:
        return 0

def is_short(duration_seconds: int, title: str) -> bool:
    if duration_seconds and duration_seconds <= 60: return True
    return 'shorts' in (title or "").lower()

def get_transcript_for_video(video_id: str):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en','hi'])
        return " ".join([t['text'] for t in transcript_list])
    except Exception:
        return None

def rows_for_youtube_query(youtube, query: str, cap: int = MAX_TOTAL_YT_RESULTS):
    rows = []
    # popular + recent + shorts
    popular = search_youtube(youtube, query, order='viewCount', max_results=MAX_YT_RESULTS_PER_SEARCH)
    recent = search_youtube(youtube, query, order='date', max_results=MAX_YT_RESULTS_PER_SEARCH)
    shorts = search_youtube(youtube, query + " shorts", order='date', max_results=MAX_YT_RESULTS_PER_SEARCH, videoDuration='short')

    video_ids = []
    for it in (popular + recent + shorts):
        vid = None
        if isinstance(it.get('id'), dict):
            vid = it['id'].get('videoId')
        else:
            vid = it.get('id')
        if vid and vid not in video_ids:
            video_ids.append(vid)
    video_ids = video_ids[:cap]

    details = get_video_details(youtube, video_ids)
    for vid in video_ids:
        d = details.get(vid)
        if not d:
            continue
        sn = d.get('snippet', {})
        stats = d.get('statistics', {})
        content = d.get('contentDetails', {})
        duration = parse_iso8601_duration(content.get('duration',''))
        transcript = get_transcript_for_video(vid)
        # choose likes if present else views
        likes = None
        try:
            likes = int(stats.get('likeCount')) if stats.get('likeCount') is not None else None
        except Exception:
            likes = None
        if likes is None:
            try:
                likes = int(stats.get('viewCount')) if stats.get('viewCount') is not None else 0
            except Exception:
                likes = 0
        row = {
            'source': 'youtube',
            'title': sn.get('title'),
            'link': f"https://www.youtube.com/watch?v={vid}",
            'author': sn.get('channelTitle'),
            'likes': likes,
            'time': sn.get('publishedAt'),
        }
        rows.append(row)
        if len(rows) >= cap:
            break
    return rows

# -----------------
# === REDDIT ===
# -----------------
def build_reddit_client():
    return praw.Reddit(client_id=REDDIT_CLIENT_ID, client_secret=REDDIT_CLIENT_SECRET, user_agent=REDDIT_USER_AGENT)

def rows_for_reddit_query(reddit, query: str, cap: int = TOP_LIMIT_PER_SOURCE):
    out = []
    try:
        submissions = list(reddit.subreddit('all').search(query, sort='relevance', limit=cap))
    except Exception:
        try:
            submissions = list(reddit.subreddit('india').search(query, sort='relevance', limit=cap))
        except Exception as e:
            print("[reddit] search error:", e)
            submissions = []
    for sub in submissions[:cap]:
        try:
            created = datetime.utcfromtimestamp(sub.created_utc).isoformat() if getattr(sub,'created_utc',None) else None
        except Exception:
            created = None
        out.append({
            'source': 'reddit',
            'title': sub.title,
            'link': sub.shortlink,
            'author': str(sub.author) if sub.author else None,
            'likes': int(sub.score) if getattr(sub,'score',None) is not None else 0,
            'time': created
        })
    return out

# -----------------
# === TWITTER/X ===
# -----------------
class TwitterRetrieval:
    def __init__(self, bearer_token: Optional[str] = None, api_key: Optional[str] = None, api_secret: Optional[str] = None, rate_limit_wait: int = 60):
        self.bearer_token = bearer_token or X_BEARER_TOKEN
        self.api_key = api_key or X_API_KEY
        self.api_secret = api_secret or X_API_SECRET
        self.rate_limit_wait = rate_limit_wait
        self.min_interval = 1.0
        if not self.bearer_token and (not self.api_key or not self.api_secret):
            raise ValueError("Set X_BEARER_TOKEN or X_API_KEY & X_API_SECRET in env")

    def ensure_bearer(self):
        if self.bearer_token:
            return self.bearer_token
        credentials = f"{self.api_key}:{self.api_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        url = "https://api.twitter.com/oauth2/token"
        headers = {"Authorization": f"Basic {encoded}", "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
        data = {"grant_type": "client_credentials"}
        resp = requests.post(url, headers=headers, data=data, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        self.bearer_token = resp.json().get('access_token')
        return self.bearer_token

    def search_tweets(self, query: str, max_results: int = TOP_LIMIT_PER_SOURCE):
        token = self.ensure_bearer()
        url = "https://api.twitter.com/2/tweets/search/recent"
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "query": query,
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,public_metrics,author_id",
            "expansions": "author_id",
            "user.fields": "username,name"
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print("[twitter] search error:", e)
            return []
        users = {}
        for u in data.get('includes', {}).get('users', []):
            users[u['id']] = u
        out = []
        for tweet in data.get('data', [])[:max_results]:
            uid = tweet.get('author_id')
            user = users.get(uid, {})
            metrics = tweet.get('public_metrics', {})
            likes = metrics.get('like_count', 0)
            out.append({
                'source': 'twitter',
                'title': (tweet.get('text')[:120] + '...') if tweet.get('text') and len(tweet.get('text'))>120 else tweet.get('text'),
                'link': f"https://twitter.com/{user.get('username','i')}/status/{tweet.get('id')}",
                'author': user.get('name') or user.get('username'),
                'likes': int(likes),
                'time': tweet.get('created_at')
            })
        return out

# -----------------
# === SERPAPI (Google News) ===
# -----------------
def rows_for_serpapi_news_query(query: str, cap: int = TOP_LIMIT_PER_SOURCE):
    key = SERPAPI_API_KEY
    if not key:
        print("[news] SERPAPI_API_KEY not set — skipping news fetch.")
        return []
    params = {
        "api_key": key,
        "engine": "google_news",
        "q": query,
        "hl": "en",
        "gl": "us",
        "num": min(cap, 10)  # serpapi returns pages; we'll iterate if needed
    }
    out = []
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        # results['news_results'] holds articles usually
        news_results = results.get('news_results') or results.get('articles') or []
        for art in news_results[:cap]:
            # SerpApi fields: 'title', 'link', 'source' (may be dict/string), 'published' or 'snippet'
            title = art.get('title') or art.get('news_title') or art.get('headline')
            link = art.get('link') or art.get('url')
            # author/source
            author = None
            if art.get('source'):
                if isinstance(art['source'], dict):
                    author = art['source'].get('name') or art['source'].get('title')
                else:
                    author = art['source']
            # SerpApi may provide 'published' or 'date' or 'snippet_time'
            time_str = art.get('published') or art.get('date') or art.get('snippet_time') or art.get('time') or art.get('published_on')
            # SerpApi doesn't have likes - set 0
            out.append({
                'source': 'news',
                'title': title,
                'link': link,
                'author': author,
                'likes': 0,
                'time': time_str
            })
        # If we didn't get enough results and serpapi supports 'start' or pagination, you could paginate here.
    except Exception as e:
        print("[serpapi] error:", e)
    return out

def summarize_news_via_gemini(query: str, cap: int = 10, model_name: str = "gemini-2.5-flash") -> Dict:
    """
    Fetch up to `cap` news articles via SerpApi, send them collectively to Gemini-2.5-Flash,
    and return the parsed JSON summary (final_summary + key_events) plus debug fields.

    Returns dict:
      {
        "articles": [ ... ],               # the list of article dicts used
        "final_summary": "...",            # model-parsed summary (or None on parse failure)
        "key_events": [...],               # list (may be empty)
        "raw_model_output": "...",         # raw text from Gemini
        "error": null or "error message"
      }
    """
    # 1) fetch articles (uses your existing function)
    articles = rows_for_serpapi_news_query(query, cap=cap)[:cap]
    if not articles:
        return {"articles": [], "final_summary": None, "key_events": [], "raw_model_output": None, "error": "No news articles found or SERPAPI key missing."}

    # 2) Build a compact combined content string for the model
    # include index, title, snippet (if present in raw), link, author, time
    lines = []
    for i, art in enumerate(articles, start=1):
        title = art.get("title") or ""
        link = art.get("link") or ""
        author = art.get("author") or ""
        time_str = art.get("time") or ""
        # try to include snippet/description if present in raw (SerpApi uses 'snippet' or 'snippet_time' etc.)
        snippet = None
        raw = art.get("raw") or {}
        snippet = raw.get("snippet") or raw.get("summary") or raw.get("abstract") or raw.get("news_snippet")
        if not snippet:
            # sometimes SerpApi returns 'snippet' at top-level in results (we didn't copy it before) — try safe access
            snippet = art.get("raw", {}).get("snippet")
        header = f"[{i}] Title: {title}\nAuthor: {author}\nTime: {time_str}\nLink: {link}"
        if snippet:
            header += f"\nSnippet: {snippet}"
        lines.append(header)

    combined_content = "\n\n".join(lines)

    # 3) Build final prompt (force JSON-only output)
    final_prompt = f"""
You are a high-quality summarization assistant. You are given up to {len(articles)} news articles about the same topic (listed below).
Task:
  1) Produce a concise but comprehensive unified summary that integrates facts across these articles.
  2) Extract a chronological list of key events (short bullet phrases) mentioned across the articles.
  3) Note any contradictions or significant uncertainties (briefly) if present.

Input Articles:
{combined_content}

Output format (STRICT JSON ONLY):
{{
  "final_summary": "<A single coherent summary that integrates the articles — 5-10 sentences>",
  "key_events": [
    "Event 1",
    "Event 2",
    "..."
  ]
}}

Rules:
- Return **only** the JSON object above and nothing else.
- Do not hallucinate: use only the information present in the provided articles.
- If an article lacks a field (author/time/snippet), ignore that missing piece.
"""

    # 4) Call Gemini via safe_gemini_call (text-only -> pass single text part)
    prompt_parts = [final_prompt]
    try:
        response = safe_gemini_call(prompt_parts)
        # small pause for safety/backoff (use your global var)
        time.sleep(globals().get("API_SLEEP_BETWEEN_REQS", 0.12))

        if response is None:
            return {"articles": articles, "final_summary": None, "key_events": [], "raw_model_output": None, "error": "safe_gemini_call returned None (failed/timeout)."}

        raw_output = getattr(response, "text", None) or (response if isinstance(response, str) else None)
        if raw_output is None:
            return {"articles": articles, "final_summary": None, "key_events": [], "raw_model_output": None, "error": "No text in Gemini response."}

        raw_output = raw_output.strip()

        # 5) Parse JSON robustly using your helper
        parsed = _extract_json_from_text(raw_output)
        if not parsed:
            # parsing failed — return raw output for debugging
            return {
                "articles": articles,
                "final_summary": None,
                "key_events": [],
                "raw_model_output": raw_output,
                "error": "Model output could not be parsed as JSON. See raw_model_output."
            }

        # normalize keys
        final_summary = parsed.get("final_summary") or parsed.get("summary") or parsed.get("finalSummary") or ""
        key_events = parsed.get("key_events") or parsed.get("keyEvents") or parsed.get("events") or []
        if isinstance(key_events, str):
            key_events = [ln.strip() for ln in key_events.splitlines() if ln.strip()]

        return {
            "articles": articles,
            "final_summary": final_summary,
            "key_events": key_events,
            "raw_model_output": raw_output,
            "error": None
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"articles": articles, "final_summary": None, "key_events": [], "raw_model_output": None, "error": str(e)}


# -----------------
# === ORCHESTRATION & OUTPUT ===
# -----------------
def collect_all(query: str, outdir: str = '.'):
    os.makedirs(outdir, exist_ok=True)
    youtube = build_youtube_client()
    reddit = build_reddit_client()

    results = {'youtube': [], 'reddit': [], 'twitter': [], 'news': []}

    # Run the four fetchers in parallel
    def run_youtube():
        try:
            return rows_for_youtube_query(youtube, query, cap=MAX_TOTAL_YT_RESULTS)[:TOP_LIMIT_PER_SOURCE]
        except Exception as e:
            print("[MAIN] youtube error:", e)
            return []

    def run_reddit():
        try:
            return rows_for_reddit_query(reddit, query, cap=TOP_LIMIT_PER_SOURCE)
        except Exception as e:
            print("[MAIN] reddit error:", e)
            return []

    def run_twitter():
        try:
            tr = TwitterRetrieval()
            return tr.search_tweets(query, max_results=TOP_LIMIT_PER_SOURCE)
        except Exception as e:
            print("[MAIN] twitter error:", e)
            return []

    def run_news():
        try:
            return rows_for_serpapi_news_query(query, cap=TOP_LIMIT_PER_SOURCE)
        except Exception as e:
            print("[MAIN] news error:", e)
            return []

    tasks = {
        'youtube': run_youtube,
        'reddit': run_reddit,
        'twitter': run_twitter,
        'news': run_news
    }

    with ThreadPoolExecutor(max_workers=4) as exe:
        future_to_name = {exe.submit(func): name for name, func in tasks.items()}
        print(f"[MAIN] Submitted {len(future_to_name)} workers")
        for fut in as_completed(future_to_name):
            name = future_to_name[fut]
            try:
                data = fut.result()
                results[name] = data or []
                print(f"[MAIN] {name} finished: {len(results[name])} items")
            except Exception as e:
                print(f"[MAIN] {name} failed:", e)
                results[name] = []

    # Normalize each source array to desired cleaned form
    def normalize_item(it):
        title = it.get('title')
        link = it.get('link')
        author = it.get('author')
        likes = it.get('likes') or 0
        time_str = it.get('time')
        dt = iso_to_dt(time_str)
        time_iso = dt.isoformat() if dt else (time_str or None)
        return {'title': title, 'link': link, 'author': author, 'likes': int(likes), 'time': time_iso}

    cleaned = {}
    for src in ['youtube','reddit','twitter','news']:
        cleaned[src] = [normalize_item(it) for it in results.get(src, [])]

    # Sort per-source: likes desc, then time desc
    def sort_list(li):
        def keyfn(x):
            likes = x.get('likes') or 0
            dt = iso_to_dt(x.get('time'))
            ts = dt.timestamp() if dt else 0
            return (-likes, -ts)
        return sorted(li, key=keyfn)

    for src in cleaned:
        cleaned[src] = sort_list(cleaned[src])

    # Combined CSV rows
    combined_rows = []
    for src in ['youtube','reddit','twitter','news']:
        for it in cleaned[src]:
            combined_rows.append({
                'source': src,
                'title': it['title'],
                'link': it['link'],
                'author': it['author'],
                'likes': it['likes'],
                'time': it['time']
            })

    # Sort combined rows: likes desc then newest first
    combined_rows = sorted(combined_rows, key=lambda x: (-(x.get('likes') or 0), -(iso_to_dt(x.get('time')).timestamp() if iso_to_dt(x.get('time')) else 0)))

    print(f"[MAIN] Scraping completed: {len(combined_rows)} total items")

    # Return data without saving intermediate files
    out_json = {
        'query': query,
        'youtube': cleaned['youtube'],
        'reddit': cleaned['reddit'],
        'twitter': cleaned['twitter'],
        'news': cleaned['news']
    }

    return {'combined_rows': combined_rows, 'per_source': cleaned, 'data': out_json}

# -----------------
# === CLI ===
# -----------------
def main():
    parser = argparse.ArgumentParser(description="Scrape YouTube + Reddit + Twitter + Google News (SerpApi) and save combined CSV + JSON")
    parser.add_argument('query', type=str, help='Query text (wrap in quotes)')
    parser.add_argument('--outdir', type=str, default='.', help='Output folder')
    args = parser.parse_args()
    collect_all(args.query, args.outdir)

if __name__ == "__main__":
    main()
