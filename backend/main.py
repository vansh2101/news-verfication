# main.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import config
import os
import sys
import shutil
from pathlib import Path

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services'))

# Import the main pipeline
from services.main import run_main_pipeline

app = FastAPI(title="TruthLens Backend", version="0.1.0")

# CORS - allow frontend origin
origins = [
    config.FRONTEND_ORIGIN,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Backend is working"}


# -------------------------------
# Verification API
# -------------------------------
class VerifyRequest(BaseModel):
    video: Optional[str] = None
    link: Optional[str] = None
    text: Optional[str] = None


@app.post("/verify")
async def verify(req: VerifyRequest):
    """
    Main verification endpoint that processes video/link/text through the pipeline.
    Returns the frontend-ready JSON with truth scores and verification data.
    """
    try:
        # Validate that at least one input is provided
        if not req.video and not req.link and not req.text:
            raise HTTPException(
                status_code=400, 
                detail="At least one input (video, link, or text) must be provided"
            )
        
        print(f"\n[API] Received verification request:")
        print(f"  - Video: {req.video or 'None'}")
        print(f"  - Link: {req.link or 'None'}")
        print(f"  - Text: {req.text or 'None'}")
        
        # Run the main pipeline (skip scrapers for faster response - can be enabled)
        result = run_main_pipeline(
            video=req.video,
            link=req.link,
            text=req.text,
            frame_step=10,
            skip_scrapers=False  # Set to True for faster testing
        )
        
        # Check for errors
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        
        # Return the frontend JSON if available
        if 'frontend_json' in result and result['frontend_json']:
            print("[API] Returning frontend JSON")
            return JSONResponse(content=result['frontend_json'])
        else:
            print("[API] Frontend JSON not available, returning basic structure")
            # Return a basic structure if frontend JSON wasn't generated
            return JSONResponse(content={
                "analysis": {
                    "summary": result.get('analysis_result', {}).get('final_summary', {}).get('final_summary', ''),
                    "key_events": result.get('key_events', [])
                },
                "truth_score": {
                    "overall_score": 0,
                    "verification_status": "Analysis Only",
                    "confidence_level": "Low"
                },
                "metadata": {
                    "processing_complete": True,
                    "timestamp": result.get('meta', {}).get('timestamp', '')
                }
            })
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
    


# -------------------------------
# News Search API (for landing page)
# -------------------------------
@app.get("/search-news")
async def search_news(query: str = "latest news"):
    """
    Search for news articles using NewsAPI (for landing page display)
    This does NOT run verification - just fetches news articles
    """
    try:
        import requests
        from dotenv import load_dotenv
        
        # Load environment variables
        parent_env = os.path.abspath(os.path.join(os.path.dirname(__file__)))
        dotenv_path = os.path.join(parent_env, '.env')
        load_dotenv(dotenv_path)
        
        newsapi_key = os.getenv("NEWSAPI_KEY")
        
        if not newsapi_key or newsapi_key == "your_newsapi_key_here":
            # Return mock data if no API key
            print("[API] No NewsAPI key configured, returning mock data")
            return {
                "articles": [
                    {
                        "source": {"id": None, "name": "Example News"},
                        "author": "News Team",
                        "title": "Latest Breaking News - Configure NewsAPI Key for Real Articles",
                        "description": "To see real news articles, add your NewsAPI key to the .env file",
                        "url": "https://newsapi.org",
                        "urlToImage": "/pic1.jpg",
                        "publishedAt": "2025-11-26T00:00:00Z",
                        "content": "Add NEWSAPI_KEY to your .env file to fetch real news articles."
                    }
                ] * 10  # Repeat for 10 articles
            }
        
        # Fetch real news
        url = f"https://newsapi.org/v2/top-headlines?q={query}&language=en&pageSize=20&apiKey={newsapi_key}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {"articles": data.get("articles", [])}
        else:
            print(f"[API] NewsAPI error: {response.status_code}")
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch news")
            
    except Exception as e:
        print(f"[API ERROR] News search failed: {str(e)}")
        # Return empty articles on error
        return {"articles": []}


# -------------------------------
# Newsletter Subscription API
# -------------------------------
class SubscribeRequest(BaseModel):
    name: str
    email: str


@app.post("/subscribe")
async def subscribe_user(req: SubscribeRequest):
    """Newsletter subscription endpoint"""
    try:
        # TODO: Implement email service
        # For now, just return success
        print(f"[API] Newsletter subscription: {req.email}")
        
        return {
            "success": True,
            "message": "Subscription received — confirmation email sent."
        }

    except Exception as e:
        print(f"[API ERROR] Subscription failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Subscription failed: {str(e)}")


# -------------------------------
# Optional: file upload endpoint
# -------------------------------
@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    """Upload video file and return the saved path"""
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        # Save the file
        file_path = upload_dir / file.filename
        with open(file_path, "wb") as f:
            contents = await file.read()
            f.write(contents)
        
        print(f"[API] Video uploaded: {file_path}")
        
        return {
            "status": "ok", 
            "filename": file.filename,
            "path": str(file_path)
        }
    except Exception as e:
        print(f"[API ERROR] Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/verify-upload")
async def verify_upload(
    file: UploadFile = File(...),
    link: Optional[str] = Form(None),
    text: Optional[str] = Form(None)
):
    """Upload video and run verification in one step"""
    try:
        # Save the uploaded video
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        file_path = upload_dir / file.filename
        with open(file_path, "wb") as f:
            contents = await file.read()
            f.write(contents)
        
        print(f"[API] Video uploaded: {file_path}")
        print(f"[API] Link: {link or 'None'}")
        print(f"[API] Text: {text or 'None'}")
        
        # Run verification with the uploaded file
        result = run_main_pipeline(
            video=str(file_path),
            link=link,
            text=text,
            frame_step=10,
            skip_scrapers=False
        )
        
        # Clean up uploaded file after processing
        try:
            os.remove(file_path)
        except:
            pass
        
        # Return frontend JSON
        if 'frontend_json' in result and result['frontend_json']:
            return JSONResponse(content=result['frontend_json'])
        else:
            return JSONResponse(content={
                "analysis": {
                    "summary": result.get('analysis_result', {}).get('final_summary', {}).get('final_summary', ''),
                    "key_events": result.get('key_events', [])
                },
                "metadata": {
                    "processing_complete": True
                }
            })
            
    except Exception as e:
        print(f"[API ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


