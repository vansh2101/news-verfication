#!/usr/bin/env python3
"""
Main Orchestrator Pipeline

Workflow:
1. Takes video/link/text inputs
2. Sends to input.py for analysis
3. Extracts key_events from the output JSON
4. For each key_event, runs sm_scrapers.py to collect related content
5. Saves all results in organized structure

Usage:
    python main.py --video "video.mp4" --link "https://url.com" --text "context"
    python main.py --video "video.mp4" --text "breaking news"
    python main.py --link "https://news.com" --text "event details"
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
import re

# Import the pipeline directly
from input import run_pipeline

# Import sm_scrapers functions
from sm_scrapers import collect_all

# Import Gemini for truth score computation
import google.generativeai as genai

# Load environment variables
from dotenv import load_dotenv
parent_env = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
dotenv_path = os.path.join(parent_env, '.env')
load_dotenv(dotenv_path)

# ---------- CONFIG ----------
OUTPUT_DIR = "final_outputs"
SCRAPERS_OUTPUT_DIR = "scrapers_outputs"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("[ERROR] GEMINI_API_KEY not found in environment variables")
    print("[ERROR] Please set GEMINI_API_KEY in your .env file")
    sys.exit(1)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
# ----------------------------


def sanitize_filename(s: str) -> str:
    """Sanitize string for use as filename"""
    s = (s or "").strip()
    s = re.sub(r"[^A-Za-z0-9 _-]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s[:30] or "output"


def extract_key_events(final_summary_dict: Dict) -> List[str]:
    """
    Extract key_events from the final_summary.
    
    Args:
        final_summary_dict: The final_summary dict from input.py output
    
    Returns:
        List of key event strings
    """
    print("\n" + "="*60)
    print("[EXTRACTION] Extracting Key Events")
    print("="*60)
    
    # Handle different possible formats
    if isinstance(final_summary_dict, dict):
        # Try to get key_events directly
        if "key_events" in final_summary_dict:
            key_events = final_summary_dict["key_events"]
            print(f"[INFO] Found {len(key_events)} key events directly")
            return key_events
        
        # Try to parse from final_summary text (if it's JSON string)
        if "final_summary" in final_summary_dict:
            final_text = final_summary_dict["final_summary"]
            
            # Try to extract JSON from the text
            try:
                # Look for JSON in the text
                json_match = re.search(r'\{.*\}', final_text, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    if "key_events" in parsed:
                        key_events = parsed["key_events"]
                        print(f"[INFO] Extracted {len(key_events)} key events from JSON in text")
                        return key_events
            except Exception as e:
                print(f"[WARN] Could not parse JSON from final_summary: {e}")
    
    # Fallback: return empty list
    print("[WARN] No key_events found in output")
    return []


def concatenate_news_sources(scraper_results: List[Dict]) -> str:
    """
    Concatenate all news articles from scraper results.
    
    Args:
        scraper_results: List of scraper result dicts
    
    Returns:
        Concatenated string of all news content
    """
    all_news = []
    
    for result in scraper_results:
        event_query = result.get('event_query', '')
        
        # Get news items
        news_items = result.get('news', [])
        
        for item in news_items:
            title = item.get('title', '')
            author = item.get('author', 'Unknown Source')
            link = item.get('link', '')
            
            news_entry = f"Source: {author}\nTitle: {title}\nLink: {link}\n"
            all_news.append(news_entry)
    
    return "\n---\n".join(all_news)


def compute_truth_score_with_gemini(analysis_summary: str, news_sources: str) -> Dict:
    """
    Use Gemini to compute truth score by comparing analysis with news sources.
    
    Args:
        analysis_summary: The final summary from input.py pipeline
        news_sources: Concatenated news sources from scrapers
    
    Returns:
        Dict with truth score and analysis
    """
    print("\n" + "="*60)
    print("[TRUTH SCORE] Computing with Gemini")
    print("="*60)
    
    prompt = f"""You are a fact-checking AI system. Your task is to evaluate the truthfulness of a claim/analysis by comparing it against verified news sources.

**Analysis/Claim to Verify:**
{analysis_summary}

**Verified News Sources (Ground Truth):**
{news_sources}

**Instructions:**
1. Compare the analysis/claim against the news sources
2. Calculate a truth score (0-100) based on:
   - How well the key facts are supported by news sources (50%)
   - Consistency across multiple sources (30%)
   - Absence of contradictory information (20%)
3. Identify which specific facts are verified, partially verified, or unverified
4. Provide reliability/credibility percentages for the main claims

**Output Format (JSON):**
{{
  "overall_truth_score": <0-100>,
  "confidence_level": "High|Medium|Low",
  "verification_status": "Verified|Partially Verified|Unverified|False",
  "fact_breakdown": [
    {{
      "claim": "specific claim from analysis",
      "truth_score": <0-100>,
      "verification": "Verified|Partially Verified|Unverified",
      "supporting_sources": ["source1", "source2"],
      "explanation": "brief explanation"
    }}
  ],
  "credibility_assessment": {{
    "factual_accuracy": <0-100>,
    "source_reliability": <0-100>,
    "consistency_score": <0-100>
  }},
  "summary": "Overall assessment of the analysis truthfulness",
  "recommendations": ["suggestion1", "suggestion2"]
}}

Provide ONLY the JSON output, no additional text.
"""
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        
        # Extract JSON from response
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        response_text = response_text.strip()
        
        truth_data = json.loads(response_text)
        
        print(f"[SUCCESS] Truth Score: {truth_data.get('overall_truth_score', 0)}%")
        print(f"[SUCCESS] Verification: {truth_data.get('verification_status', 'Unknown')}")
        
        return truth_data
        
    except Exception as e:
        print(f"[ERROR] Failed to compute truth score: {e}")
        import traceback
        traceback.print_exc()
        
        # Return default structure
        return {
            "overall_truth_score": 0,
            "confidence_level": "Low",
            "verification_status": "Error",
            "fact_breakdown": [],
            "credibility_assessment": {
                "factual_accuracy": 0,
                "source_reliability": 0,
                "consistency_score": 0
            },
            "summary": f"Error computing truth score: {str(e)}",
            "recommendations": []
        }


def select_top_items(scraper_results: List[Dict], count: int = 5) -> Dict:
    """
    Select top N items from each source across all scraper results.
    
    Args:
        scraper_results: List of scraper result dicts
        count: Number of items to select per source
    
    Returns:
        Dict with top items per source
    """
    all_youtube = []
    all_reddit = []
    all_twitter = []
    all_news = []
    
    for result in scraper_results:
        all_youtube.extend(result.get('youtube', []))
        all_reddit.extend(result.get('reddit', []))
        all_twitter.extend(result.get('twitter', []))
        all_news.extend(result.get('news', []))
    
    # Sort by likes/engagement (descending)
    all_youtube.sort(key=lambda x: x.get('likes', 0), reverse=True)
    all_reddit.sort(key=lambda x: x.get('likes', 0), reverse=True)
    all_twitter.sort(key=lambda x: x.get('likes', 0), reverse=True)
    all_news.sort(key=lambda x: x.get('likes', 0), reverse=True)
    
    # Extract top N with title, link, source
    def format_item(item):
        return {
            'title': item.get('title', ''),
            'link': item.get('link', ''),
            'source': item.get('author', 'Unknown'),
            'engagement': item.get('likes', 0)
        }
    
    return {
        'youtube': [format_item(item) for item in all_youtube[:count]],
        'reddit': [format_item(item) for item in all_reddit[:count]],
        'twitter': [format_item(item) for item in all_twitter[:count]],
        'news': [format_item(item) for item in all_news[:count]]
    }


def generate_frontend_json(analysis_result: Dict, scraper_results: List[Dict], 
                          truth_score_data: Dict, key_events: List[str],
                          video: str, link: str, text: str) -> Dict:
    """
    Generate the final JSON structure for frontend display.
    
    Args:
        analysis_result: Result from input.py pipeline
        scraper_results: Results from sm_scrapers
        truth_score_data: Truth score computation from Gemini
        key_events: List of key events
        video: Video path
        link: Link URL
        text: User text
    
    Returns:
        Frontend-ready JSON structure
    """
    print("\n" + "="*60)
    print("[FRONTEND JSON] Generating final output")
    print("="*60)
    
    # Get top 5 items from each source
    top_items = select_top_items(scraper_results, count=5)
    
    # Extract summary
    final_summary = analysis_result.get('final_summary', {}).get('final_summary', '')
    
    # Create frontend JSON
    frontend_data = {
        "input": {
            "video": video,
            "link": link,
            "text": text,
            "timestamp": datetime.now().isoformat()
        },
        
        "analysis": {
            "summary": final_summary,
            "key_events": key_events,
            "sources_analyzed": {
                "video_frames": analysis_result.get('video_analysis', {}).get('frames_analyzed', 0),
                "web_paragraphs": analysis_result.get('link_analysis', {}).get('paragraphs_extracted', 0),
                "total_scraped_items": sum([
                    len(r.get('youtube', [])) + len(r.get('reddit', [])) + 
                    len(r.get('twitter', [])) + len(r.get('news', []))
                    for r in scraper_results
                ])
            }
        },
        
        "truth_score": {
            "overall_score": truth_score_data.get('overall_truth_score', 0),
            "confidence_level": truth_score_data.get('confidence_level', 'Low'),
            "verification_status": truth_score_data.get('verification_status', 'Unknown'),
            
            "credibility": {
                "factual_accuracy": truth_score_data.get('credibility_assessment', {}).get('factual_accuracy', 0),
                "source_reliability": truth_score_data.get('credibility_assessment', {}).get('source_reliability', 0),
                "consistency_score": truth_score_data.get('credibility_assessment', {}).get('consistency_score', 0)
            },
            
            "fact_breakdown": truth_score_data.get('fact_breakdown', []),
            
            "summary": truth_score_data.get('summary', ''),
            "recommendations": truth_score_data.get('recommendations', [])
        },
        
        "supporting_evidence": {
            "youtube_videos": top_items['youtube'],
            "reddit_discussions": top_items['reddit'],
            "twitter_posts": top_items['twitter'],
            "news_articles": top_items['news']
        },
        
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_sources_checked": len(scraper_results),
            "processing_complete": True
        }
    }
    
    print(f"[SUCCESS] Frontend JSON generated")
    print(f"  - Overall Truth Score: {frontend_data['truth_score']['overall_score']}%")
    print(f"  - Verification Status: {frontend_data['truth_score']['verification_status']}")
    print(f"  - Top items selected: 5 per source (YouTube, Reddit, Twitter, News)")
    
    return frontend_data


def run_scrapers_for_event(event: str, event_idx: int, output_dir: str) -> Dict:
    """
    Run sm_scrapers.py for a single key event.
    
    Args:
        event: The key event query string
        event_idx: Index of the event
        output_dir: Directory to save scraper outputs
    
    Returns:
        Dict with scraper results
    """
    print(f"\n{'='*60}")
    print(f"[SCRAPER {event_idx+1}] Processing Event: '{event}'")
    print(f"{'='*60}\n")
    
    try:
        # Create subdirectory for this event (use short name to avoid path length issues)
        event_dir = os.path.join(output_dir, f"event_{event_idx+1}")
        os.makedirs(event_dir, exist_ok=True)
        
        # Run the scraper
        print(f"[INFO] Running sm_scrapers for: {event}")
        results = collect_all(event, outdir=event_dir)
        
        print(f"[SUCCESS] Scraping complete for event {event_idx+1}")
        
        # Get the data directly from results
        scraper_data = results.get('data', {})
        
        # Add metadata
        scraper_data['event_query'] = event
        scraper_data['event_index'] = event_idx + 1
        
        return scraper_data
        
    except Exception as e:
        print(f"[ERROR] Scraping failed for event {event_idx+1}: {e}")
        import traceback
        traceback.print_exc()
        return {
            'event_query': event,
            'event_index': event_idx + 1,
            'error': str(e),
            'youtube': [],
            'reddit': [],
            'twitter': [],
            'news': []
        }


def run_main_pipeline(video: Optional[str], link: Optional[str], text: Optional[str], 
                     frame_step: int = 10, skip_scrapers: bool = False) -> Dict:
    """
    Main orchestration function.
    
    Args:
        video: Path to video file
        link: URL to analyze
        text: User text/context
        frame_step: Frame sampling rate
        skip_scrapers: If True, skip the scraping phase
    
    Returns:
        Dict with complete results
    """
    print("\n" + "="*80)
    print("🚀 MAIN ORCHESTRATOR PIPELINE")
    print("="*80)
    print(f"\nInputs:")
    print(f"  - Video: {video or 'None'}")
    print(f"  - Link: {link or 'None'}")
    print(f"  - Text: {text or 'None'}")
    print(f"  - Frame Step: {frame_step}")
    print(f"  - Skip Scrapers: {skip_scrapers}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # ========================================
    # PHASE 1: Run input.py pipeline
    # ========================================
    print("\n" + "="*80)
    print("📊 PHASE 1: Running Video + Link + Text Analysis")
    print("="*80)
    
    try:
        analysis_result = run_pipeline(video, link, text, frame_step)
    except Exception as e:
        print(f"[ERROR] Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            'error': str(e),
            'phase': 'analysis',
            'timestamp': timestamp
        }
    
    # ========================================
    # PHASE 2: Extract key events
    # ========================================
    print("\n" + "="*80)
    print("🔍 PHASE 2: Extracting Key Events")
    print("="*80)
    
    final_summary_dict = analysis_result.get('final_summary', {})
    key_events = extract_key_events(final_summary_dict)
    
    if not key_events:
        print("\n[WARN] No key events found. Stopping pipeline.")
        print("[INFO] You can still find the analysis results in the analysis_outputs/ folder")
        
        # Save partial results
        output = {
            'meta': {
                'timestamp': timestamp,
                'video': video,
                'link': link,
                'text': text,
                'phase_completed': 'analysis_only'
            },
            'analysis_result': analysis_result,
            'key_events': [],
            'scraper_results': []
        }
        
        return output
    
    print(f"\n[SUCCESS] Extracted {len(key_events)} key events:")
    for i, event in enumerate(key_events, 1):
        print(f"  {i}. {event}")
    
    # ========================================
    # PHASE 3: Run scrapers for each event (optional)
    # ========================================
    scraper_results = []
    
    if skip_scrapers:
        print("\n" + "="*80)
        print("⏭️  PHASE 3: Skipping Scrapers (--skip-scrapers flag set)")
        print("="*80)
    else:
        print("\n" + "="*80)
        print(f"🔎 PHASE 3: Running Scrapers for {len(key_events)} Key Events")
        print("="*80)
        
        # Create scrapers output directory
        scrapers_dir = os.path.join(SCRAPERS_OUTPUT_DIR, f"run_{timestamp}")
        os.makedirs(scrapers_dir, exist_ok=True)
        
        for idx, event in enumerate(key_events):
            scraper_data = run_scrapers_for_event(event, idx, scrapers_dir)
            scraper_results.append(scraper_data)
        
        print(f"\n[SUCCESS] Completed scraping for all {len(key_events)} events")
    
    # ========================================
    # PHASE 4: Compute Truth Score
    # ========================================
    truth_score_data = {}
    
    if not skip_scrapers and scraper_results:
        print("\n" + "="*80)
        print("🎯 PHASE 4: Computing Truth Score with Gemini")
        print("="*80)
        
        # Get the analysis summary
        analysis_summary = analysis_result.get('final_summary', {}).get('final_summary', '')
        
        # Concatenate all news sources
        news_sources = concatenate_news_sources(scraper_results)
        
        if news_sources.strip():
            # Compute truth score
            truth_score_data = compute_truth_score_with_gemini(analysis_summary, news_sources)
        else:
            print("[WARN] No news sources found for truth score computation")
            truth_score_data = {
                "overall_truth_score": 0,
                "confidence_level": "Low",
                "verification_status": "Insufficient Data",
                "fact_breakdown": [],
                "credibility_assessment": {
                    "factual_accuracy": 0,
                    "source_reliability": 0,
                    "consistency_score": 0
                },
                "summary": "No news sources available for verification",
                "recommendations": ["Collect more news sources"]
            }
    else:
        print("\n[SKIP] Truth score computation (no scrapers run)")
    
    # ========================================
    # PHASE 5: Generate Frontend JSON
    # ========================================
    print("\n" + "="*80)
    print("📱 PHASE 5: Generating Frontend JSON")
    print("="*80)
    
    if not skip_scrapers and scraper_results and truth_score_data:
        frontend_json = generate_frontend_json(
            analysis_result=analysis_result,
            scraper_results=scraper_results,
            truth_score_data=truth_score_data,
            key_events=key_events,
            video=video or "",
            link=link or "",
            text=text or ""
        )
    else:
        print("[INFO] Generating basic output without truth scoring")
        frontend_json = None
    
    # ========================================
    # PHASE 6: Combine and save final output
    # ========================================
    print("\n" + "="*80)
    print("💾 PHASE 6: Saving Final Combined Results")
    print("="*80)
    
    # Create comprehensive output structure
    final_output = {
        'meta': {
            'timestamp': timestamp,
            'video': video,
            'link': link,
            'text': text,
            'frame_step': frame_step,
            'total_key_events': len(key_events),
            'scrapers_run': not skip_scrapers,
            'truth_score_computed': bool(truth_score_data),
            'generated_at': datetime.now().isoformat()
        },
        'analysis_result': {
            'video_analysis': analysis_result.get('video_analysis', {}),
            'link_analysis': analysis_result.get('link_analysis', {}),
            'final_summary': analysis_result.get('final_summary', {})
        },
        'key_events': key_events,
        'scraper_results': scraper_results,
        'truth_score': truth_score_data,
        'frontend_json': frontend_json
    }
    
    # Save ONLY frontend JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    safe_name = sanitize_filename(
        os.path.basename(video) if video else 
        link.split('//')[-1][:30] if link else 
        text[:30] if text else
        "pipeline"
    )
    
    # Save only frontend-ready JSON (if available)
    if frontend_json:
        frontend_file = os.path.join(OUTPUT_DIR, f"frontend_{safe_name}_{timestamp}.json")
        with open(frontend_file, 'w', encoding='utf-8') as f:
            json.dump(frontend_json, f, indent=2, ensure_ascii=False)
        print(f"\n[SUCCESS] ✓ Frontend JSON saved to: {frontend_file}")
        output_file = frontend_file
    else:
        # Fallback: save minimal output if frontend JSON not available
        output_file = os.path.join(OUTPUT_DIR, f"output_{safe_name}_{timestamp}.json")
        minimal_output = {
            'meta': final_output['meta'],
            'key_events': key_events,
            'error': 'Frontend JSON not generated'
        }
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(minimal_output, f, indent=2, ensure_ascii=False)
        print(f"\n[WARN] Frontend JSON not available, saved minimal output to: {output_file}")
    
    # Print summary
    print("\n" + "="*80)
    print("📋 PIPELINE SUMMARY")
    print("="*80)
    print(f"\n✅ Analysis Complete:")
    print(f"   - Video frames analyzed: {analysis_result.get('video_analysis', {}).get('frames_analyzed', 0)}")
    print(f"   - Link paragraphs extracted: {analysis_result.get('link_analysis', {}).get('paragraphs_extracted', 0)}")
    
    print(f"\n✅ Key Events Extracted: {len(key_events)}")
    for i, event in enumerate(key_events, 1):
        print(f"   {i}. {event}")
    
    if not skip_scrapers and scraper_results:
        print(f"\n✅ Scraper Results:")
        total_youtube = sum(len(r.get('youtube', [])) for r in scraper_results)
        total_reddit = sum(len(r.get('reddit', [])) for r in scraper_results)
        total_twitter = sum(len(r.get('twitter', [])) for r in scraper_results)
        total_news = sum(len(r.get('news', [])) for r in scraper_results)
        
        print(f"   - Total YouTube videos: {total_youtube}")
        print(f"   - Total Reddit posts: {total_reddit}")
        print(f"   - Total Twitter tweets: {total_twitter}")
        print(f"   - Total News articles: {total_news}")
        print(f"   - Total items scraped: {total_youtube + total_reddit + total_twitter + total_news}")
    
    if truth_score_data:
        print(f"\n✅ Truth Score Analysis:")
        print(f"   - Overall Truth Score: {truth_score_data.get('overall_truth_score', 0)}%")
        print(f"   - Verification Status: {truth_score_data.get('verification_status', 'Unknown')}")
        print(f"   - Confidence Level: {truth_score_data.get('confidence_level', 'Unknown')}")
        cred = truth_score_data.get('credibility_assessment', {})
        print(f"   - Factual Accuracy: {cred.get('factual_accuracy', 0)}%")
        print(f"   - Source Reliability: {cred.get('source_reliability', 0)}%")
        print(f"   - Consistency Score: {cred.get('consistency_score', 0)}%")
    
    print(f"\n📁 Output File:")
    print(f"   - Frontend JSON: {output_file}")
    print(f"   - This contains all analysis, truth scores, and supporting evidence")
    if not skip_scrapers:
        print(f"   - All data consolidated in single JSON file")
    
    print("\n" + "="*80)
    print("🎉 PIPELINE COMPLETE!")
    print("="*80 + "\n")
    
    return final_output


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(
        description="Main Orchestrator: Video+Link+Text Analysis → Key Events → Multi-Source Scraping",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline with video, link, and text
  python main.py --video "news.mp4" --link "https://news.com/article" --text "Breaking news"
  
  # Video only
  python main.py --video "video.mp4"
  
  # Link and text only
  python main.py --link "https://article.com" --text "Context about the event"
  
  # Skip scrapers (only run analysis)
  python main.py --video "video.mp4" --skip-scrapers
  
  # Custom frame sampling
  python main.py --video "video.mp4" --frame-step 5
        """
    )
    
    parser.add_argument("--video", type=str, help="Path to video file")
    parser.add_argument("--link", type=str, help="URL to extract content from")
    parser.add_argument("--text", type=str, help="User-provided text description")
    parser.add_argument("--frame-step", type=int, default=10, 
                        help="Sample every Nth frame from video (default: 10)")
    parser.add_argument("--skip-scrapers", action="store_true",
                        help="Skip the scraping phase (only run analysis)")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.video and not args.link and not args.text:
        print("[ERROR] At least one input (--video, --link, or --text) must be provided")
        parser.print_help()
        sys.exit(1)
    
    # Run the main pipeline
    result = run_main_pipeline(
        video=args.video,
        link=args.link,
        text=args.text,
        frame_step=args.frame_step,
        skip_scrapers=args.skip_scrapers
    )
    
    # Exit with appropriate code
    if 'error' in result:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
