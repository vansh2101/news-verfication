#!/usr/bin/env python3
"""
Video + Link + Text Analysis Pipeline

Inputs:
 - --video : local path to video file (mp4 suggested)
 - --link  : URL to extract content from using links_scraper
 - --text  : user text description (optional)

Outputs:
 - combined JSON with detailed video summary, link content summary, and concatenated final summary

Workflow:
1. Video: Sample every 10th frame, send all frames at once to Gemini-2.5-Pro for detailed analysis
2. Link: Extract content using links_scraper and summarize
3. Final: Create concatenated summary from video_summary + link_summary + text
"""
import re
import os
import ast
import sys
import io
import json
import time
import argparse
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from serpapi import GoogleSearch
import time
import urllib.request
import cv2
from PIL import Image
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add paths for imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# ---------- CONFIG ----------
FRAME_SAMPLE_RATE = 10           # sample every 10th frame
OUTPUT_DIR = "analysis_outputs"
API_SLEEP_BETWEEN_REQS = 1.0     # sleep between API calls to avoid rate limits
# ----------------------------

# Load environment variables
parent_env = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
dotenv_path = os.path.join(parent_env, '.env')
load_dotenv(dotenv_path)

# Initialize Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("[ERROR] GEMINI_API_KEY not found in environment variables")
    print("[ERROR] Please set GEMINI_API_KEY in your .env file or environment")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)


# ---------- UTILITY FUNCTIONS ----------

class NewsLinkExtractor:
    def __init__(self):
        """Initializes the NewsLinkExtractor with environment variables and API setup."""
        dotenv_path = find_dotenv()
        load_dotenv(dotenv_path)
        self.params = {
            "engine": "google_news",
            "gl": "us",
            "hl": "en",
            "api_key": os.getenv("SERP_API_KEY")
        }

    def extract_links(self, query):
        """Extracts news links based on the query provided using SerpAPI."""
        self.params["q"] = query
        search = GoogleSearch(self.params)
        results = search.get_dict()
        news_results = results.get("news_results", [])
        return [news_result["link"] for news_result in news_results]

    def fallback_extract_links(self, query):
        """Fallback to GNews API for extracting links."""
        apikey = os.getenv("gnews_api_key")
        url = f"https://gnews.io/api/v4/search?q={query}&lang=en&country=us&max=10&apikey={apikey}"
        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode("utf-8"))
                articles = data.get("articles", [])
                return [article["url"] for article in articles]
        except Exception as e:
            print(f"Error with GNews API: {e}")
            return []

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

def sanitize_filename(s: str) -> str:
    """Sanitize string for use as filename"""
    import re
    s = (s or "").strip()
    s = re.sub(r"[^A-Za-z0-9 _-]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s[:100] or "output"


def sample_video_frames(video_path: str, frame_step: int = FRAME_SAMPLE_RATE) -> List[Dict]:
    """
    Sample frames from video at specified interval.
    
    Args:
        video_path: Path to video file
        frame_step: Sample every Nth frame
    
    Returns:
        List of dicts with frame_idx, timestamp_s, image_bytes, pil_image
    """
    if not video_path or not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    
    print(f"[VIDEO] Total frames: {total_frames}, FPS: {fps:.2f}")
    print(f"[VIDEO] Sampling every {frame_step} frames...")
    
    sampled = []
    frame_idx = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Sample every Nth frame
        if frame_idx % frame_step == 0:
            # Convert BGR to RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            
            # Resize if too large (Gemini has size limits)
            max_dim = 1024
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            
            # Convert to bytes for storage
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85)
            
            sampled.append({
                "frame_idx": frame_idx,
                "timestamp_s": frame_idx / fps,
                "image_bytes": buf.getvalue(),
                "pil_image": img  # Keep PIL image for Gemini
            })
        
        frame_idx += 1
    
    cap.release()
    print(f"[VIDEO] Sampled {len(sampled)} frames (every {frame_step} frames)")
    return sampled


# ---------- GEMINI API FUNCTIONS ----------

def analyze_video_with_gemini(video_path: str, frame_step: int = FRAME_SAMPLE_RATE) -> Dict:
    """
    Analyze video by sending all sampled frames to Gemini-2.5-Pro at once.
    
    Args:
        video_path: Path to video file
        frame_step: Sample every Nth frame (default: 10)
    
    Returns:
        Dict with video_summary and frames_analyzed count
    """
    print(f"\n{'='*60}")
    print("[STAGE 1] Video Analysis with Gemini-2.5-Pro")
    print(f"{'='*60}\n")
    
    # Sample frames
    frames = sample_video_frames(video_path, frame_step)
    
    if not frames:
        return {
            "video_summary": "No frames could be extracted from video",
            "frames_analyzed": 0,
            "error": "Frame extraction failed"
        }
    
    # Build prompt for detailed analysis
    prompt = f"""You are analyzing a video by examining {len(frames)} frames sampled at regular intervals.

Your task is to provide a COMPREHENSIVE and DETAILED summary of everything happening in this video.

Please include:
1. **Main Events**: Describe all significant events, actions, and activities in chronological order
2. **People**: Identify and describe people, their actions, expressions, and interactions
3. **Objects**: Note important objects, items, products, or things visible in the frames
4. **Scene Details**: Describe locations, settings, environments, and background elements
5. **Visual Details**: Colors, lighting, composition, camera angles, and visual style
6. **Text/Graphics**: Any text, signs, labels, or graphics visible in the frames
7. **Timeline**: Approximate timing of key events based on frame progression
8. **Context**: Overall theme, purpose, or narrative of the video

Be as detailed as possible. Include small details that might be important. 
Provide a rich, comprehensive description that captures the full essence of the video.

Total frames: {len(frames)}
Frame sampling rate: Every {frame_step} frames
"""
    
    try:
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        # Build content: prompt + all frames
        content_parts = [prompt]
        
        for i, frame_data in enumerate(frames):
            content_parts.append(frame_data["pil_image"])
            if (i + 1) % 10 == 0:
                print(f"  Adding frame {i+1}/{len(frames)} (timestamp: {frame_data['timestamp_s']:.2f}s)")
        
        print(f"\n[GEMINI] Sending {len(frames)} frames to Gemini-2.5-Pro for analysis...")
        print("[GEMINI] This may take a moment for the model to process all frames...")
        
        response = model.generate_content(content_parts)
        time.sleep(API_SLEEP_BETWEEN_REQS)
        
        video_summary = response.text
        
        print(f"\n[SUCCESS] Video analysis complete!")
        print(f"[INFO] Summary length: {len(video_summary)} characters")
        
        return {
            "video_summary": video_summary,
            "frames_analyzed": len(frames),
            "frame_step": frame_step,
            "video_path": video_path
        }
        
    except Exception as e:
        print(f"\n[ERROR] Gemini video analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "video_summary": f"Error during video analysis: {str(e)}",
            "frames_analyzed": len(frames),
            "error": str(e)
        }


def extract_and_summarize_link(url: str) -> Dict:
    """
    Extract content from link using links_scraper and create summary.
    
    Args:
        url: URL to extract content from
    
    Returns:
        Dict with link_content and link_summary
    """
    print(f"\n{'='*60}")
    print("[STAGE 2] Link Content Extraction")
    print(f"{'='*60}\n")
    
    try:
        # Use NewsLinkExtractor to get content
        # Note: NewsLinkExtractor extracts news links based on query
        # For direct URL scraping, we'll use a simple approach
        import requests
        from bs4 import BeautifulSoup
        
        print(f"[LINK] Fetching content from: {url}")
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract main content
        # Look for article content or main text
        content_tags = soup.find_all(['p', 'article', 'div'])
        paragraphs = []
        
        for tag in content_tags:
            text = tag.get_text(separator=' ', strip=True)
            if len(text) > 50:  # Filter out short texts
                paragraphs.append(text)
        
        link_content = "\n\n".join(paragraphs[:50])  # Limit to first 50 paragraphs
        
        print(f"[LINK] Extracted {len(paragraphs)} paragraphs")
        print(f"[LINK] Total content length: {len(link_content)} characters")
        
        # Summarize with Gemini
        if link_content:
            print("[GEMINI] Generating link content summary...")
            
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            summary_prompt = f"""Summarize the following article/web content in detail. 
Capture all key points, facts, events, and important information:

{link_content}

Provide a comprehensive summary that preserves important details."""
            
            response = model.generate_content(summary_prompt)
            time.sleep(API_SLEEP_BETWEEN_REQS)
            
            link_summary = response.text
            print(f"[SUCCESS] Link summary generated ({len(link_summary)} chars)")
        else:
            link_summary = "No content extracted from link"
        
        return {
            "link_content": link_content[:5000],  # Store first 5000 chars
            "link_summary": link_summary,
            "url": url,
            "paragraphs_extracted": len(paragraphs)
        }
        
    except Exception as e:
        print(f"[ERROR] Link extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "link_content": f"Error: {str(e)}",
            "link_summary": f"Could not extract content from link: {str(e)}",
            "error": str(e),
            "url": url
        }


def create_final_summary(video_summary: str, link_summary: str, user_text: str = "") -> Dict:
    """
    Create concatenated final summary from video, link, and text using safe_gemini_call(prompt_parts).
    Returns a structured dict with parsed JSON (or raw output + error if parsing failed).
    """
    print("\n" + "="*60)
    print("[STAGE 3] Final Summary Generation")
    print("="*60 + "\n")

    # Prepare sections and flags
    sections = []
    video_ok = bool(video_summary and "Error" not in video_summary)
    link_ok = bool(link_summary and "Error" not in link_summary)
    user_ok = bool(user_text and user_text.strip())

    if video_ok:
        sections.append("VIDEO ANALYSIS:\n" + video_summary.strip())
    if link_ok:
        sections.append("LINK CONTENT:\n" + link_summary.strip())
    if user_ok:
        sections.append("USER NOTES:\n" + user_text.strip())

    if not sections:
        return {
            "final_summary": "No content available to summarize",
            "error": "All sources failed or empty",
            "sources_used": {"video": video_ok, "link": link_ok, "user_text": user_ok}
        }

    # Build the combined content with clear separators
    separator = "\n" + ("=" * 60) + "\n\n"
    combined_content = "\n\n" + separator.join(sections)

    # Build the final prompt (single text prompt)
    final_prompt = f"""Below is your **one-shot version** of the prompt (fully compressed, globally coherent, aggressive instruction-locking, and ready to paste into Gemini).
After that, I generate **a sample set of 4–5 short key events (6–10 words)** based on a **global violence scene** exactly as you requested.

---

# ✅ **ONE-SHOT MASTER PROMPT (COPY–PASTE READY)**

```
You are an advanced reasoning system that receives information about the same topic from multiple modalities:
- Video analysis summaries
- Webpage/blog extracted text
- User-provided notes or descriptions

Below is the combined content gathered from all sources:

{combined_content}

----------------------------
### 🎯 Your Task
Produce ONE unified, exhaustive, coherent summary that merges all sources into a single narrative without losing ANY important detail.

----------------------------
### 🧠 STRICT RULES
1. Integrate and merge all facts from video, webpage, and user text.
2. Create a smooth, logically structured narrative that reads like a complete report.
3. Include all critical facts, timelines, actors, locations, causes, and consequences.
4. Highlight contradictions or cross-source confirmations explicitly.
5. Do NOT hallucinate — rely ONLY on provided content.
6. Do NOT repeat identical facts; merge overlapping information.
7. Maintain clarity, chronology, and conceptual coherence.
8. **Output ONLY JSON** — no text before or after it.
9. Every key event must:
   - be a standalone bullet point
   - be 6–10 words long
   - contain at least one proper noun
   - be grammatically independent from other events
   - summarize a major event/action, not fluff
10. Final summary MUST be exhaustive but readable.

----------------------------
### 📌 REQUIRED OUTPUT FORMAT (STRICT)

{{
  "final_summary": "<Deep, complete, merged narrative integrating all sources>",
  "key_events": [
      "Event 1 (6–10 words, with proper noun)",
      "Event 2",
      "Event 3",
      "Event 4",
      "Event 5"
  ]
}}
```

---

# **EXAMPLE**
{{
  "final_summary": "A coordinated militant attack occurs in a major city, involving bombings, armed assaults, and hostage situations. Multiple intelligence agencies respond. International condemnation follows.
",
  "key_events": [
      "ISIS militants detonate explosives near Damascus Central Station",
      "UN Peacekeepers secure civilians trapped inside Aleppo Mall",
      "NATO drones identify fleeing attackers near Raqqa highway",
      "Red Crescent medics rescue wounded at Homs Hospital",
      "Event 5"
  ]
}}
"""

    # Prepare prompt_parts just like your other use case (list with only text)
    # safe_gemini_call expects a list (images + prompt), so pass a single-item list for text-only call.
    prompt_parts = [final_prompt]

    try:
        print("[GEMINI] Sending prompt to safe_gemini_call(...)")
        response = safe_gemini_call(prompt_parts)   # uses same interface as your other example
        time.sleep(API_SLEEP_BETWEEN_REQS)

        # Response may be an object with .text, or a raw string — handle both
        raw_output = None
        if response is None:
            raw_output = None
        else:
            raw_output = getattr(response, "text", None) or (response if isinstance(response, str) else None)

        if not raw_output:
            return {
                "final_summary": None,
                "key_events": [],
                "sources_used": {"video": video_ok, "link": link_ok, "user_text": user_ok},
                "raw_model_output": raw_output,
                "error": "No response text returned by safe_gemini_call"
            }

        # Clean whitespace
        raw_output = raw_output.strip()
        print("[GEMINI] Raw output length:", len(raw_output))

        # Try to extract JSON
        parsed = _extract_json_from_text(raw_output)
        if not parsed:
            # parsing failed — return raw output for later debugging
            return {
                "final_summary": None,
                "key_events": [],
                "sources_used": {"video": video_ok, "link": link_ok, "user_text": user_ok},
                "raw_model_output": raw_output,
                "error": "Model output could not be parsed as JSON. See raw_model_output for details."
            }

        # Extract canonical fields (support alternate keys)
        final_summary = parsed.get("final_summary") or parsed.get("summary") or parsed.get("finalSummary") or ""
        key_events = parsed.get("key_events") or parsed.get("events") or parsed.get("keyEvents") or []
        if isinstance(key_events, str):
            # split by newline if model returned a newline-separated string
            key_events = [ln.strip() for ln in key_events.splitlines() if ln.strip()]

        # Return well-formed dict
        result = {
            "final_summary": final_summary,
            "key_events": key_events,
            "sources_used": {"video": video_ok, "link": link_ok, "user_text": user_ok},
            "raw_model_output": raw_output
        }
        print("[SUCCESS] Parsed final summary and key events.")
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "final_summary": None,
            "error": str(e),
            "sources_used": {"video": video_ok, "link": link_ok, "user_text": user_ok}
        }

# ---------- MAIN PIPELINE ----------

def run_pipeline(video: Optional[str], link: Optional[str], text: Optional[str], frame_step: int = FRAME_SAMPLE_RATE) -> Dict:
    """
    Main pipeline orchestration with parallel processing.
    
    Args:
        video: Path to video file
        link: URL to extract content from
        text: User-provided text
        frame_step: Frame sampling rate
    
    Returns:
        Dict with all results
    """
    print("\n" + "="*60)
    print("VIDEO + LINK + TEXT ANALYSIS PIPELINE (PARALLEL)")
    print("="*60)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Prepare tasks for parallel execution
    tasks = {}
    video_result = {}
    link_result = {}
    
    print("\n[INFO] Starting parallel processing of inputs...")
    print(f"  - Video: {'✓' if video else '✗'}")
    print(f"  - Link: {'✓' if link else '✗'}")
    print(f"  - Text: {'✓' if text else '✗'}")
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit tasks for video and link processing
        if video:
            print(f"\n[PARALLEL] Submitting video analysis task...")
            tasks['video'] = executor.submit(analyze_video_with_gemini, video, frame_step)
        
        if link:
            print(f"[PARALLEL] Submitting link extraction task...")
            tasks['link'] = executor.submit(extract_and_summarize_link, link)
        
        # Wait for all tasks to complete
        print(f"\n[PARALLEL] Waiting for {len(tasks)} tasks to complete...\n")
        
        for task_name, future in tasks.items():
            try:
                result = future.result()
                if task_name == 'video':
                    video_result = result
                    print(f"[PARALLEL] ✓ Video analysis completed")
                elif task_name == 'link':
                    link_result = result
                    print(f"[PARALLEL] ✓ Link extraction completed")
            except Exception as e:
                print(f"[PARALLEL] ✗ {task_name} task failed: {e}")
                if task_name == 'video':
                    video_result = {"video_summary": f"Error: {str(e)}", "frames_analyzed": 0, "error": str(e)}
                elif task_name == 'link':
                    link_result = {"link_summary": f"Error: {str(e)}", "link_content": "", "error": str(e)}
    
    # Handle cases where inputs were not provided
    if not video:
        print("\n[SKIP] No video provided")
        video_result = {"video_summary": "", "frames_analyzed": 0}
    
    if not link:
        print("[SKIP] No link provided")
        link_result = {"link_summary": "", "link_content": ""}
    
    print(f"\n[PARALLEL] All parallel tasks completed!")
    print(f"{'='*60}\n")
    
    # Stage 3: Final Summary (sequential, depends on video and link results)
    final_result = create_final_summary(
        video_result.get("video_summary", ""),
        link_result.get("link_summary", ""),
        text or ""
    )
    
    # Combine all results
    output = {
        "meta": {
            "timestamp": timestamp,
            "video": video,
            "link": link,
            "user_text": text,
            "frame_step": frame_step
        },
        "video_analysis": video_result,
        "link_analysis": link_result,
        "final_summary": final_result,
        "generated_at": datetime.now().isoformat()
    }
    
    # Don't save intermediate files, just return the data
    print(f"\n{'='*60}")
    print("[COMPLETE] Analysis pipeline finished successfully!")
    print(f"{'='*60}")
    
    return output


# ---------- CLI ----------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Video + Link + Text Analysis Pipeline using Gemini-2.5-Pro"
    )
    parser.add_argument("--video", type=str, help="Path to video file")
    parser.add_argument("--link", type=str, help="URL to extract content from")
    parser.add_argument("--text", type=str, help="User-provided text description")
    parser.add_argument("--frame_step", type=int, default=FRAME_SAMPLE_RATE, 
                        help=f"Sample every Nth frame (default: {FRAME_SAMPLE_RATE})")
    
    args = parser.parse_args()
    
    if not args.video and not args.link and not args.text:
        print("[ERROR] At least one input (--video, --link, or --text) must be provided")
        parser.print_help()
        sys.exit(1)
    
    result = run_pipeline(args.video, args.link, args.text, args.frame_step)
    
    # Print final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    print(result["final_summary"]["final_summary"])
