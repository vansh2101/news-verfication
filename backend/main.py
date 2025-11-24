# main.py
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from models.verification_models import CompleteVerificationResult
from services.verification_service import verify_content
from services.email_service import send_confirmation_email
from pydantic import BaseModel
from fastapi import Query
import config

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
    type: str  # "text" | "link" | "video"
    content: str


@app.post("/verify", response_model=CompleteVerificationResult)
async def verify(req: VerifyRequest):
    try:
        if req.type not in ("text", "link", "video"):
            raise HTTPException(status_code=400, detail="Invalid type")
        result = await verify_content(req.type, req.content)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@app.get("/search-news")
async def search_news(query: str):
    try:
        response = newsapi.get_everything(
            q=query,
            language="en",
            sort_by="publishedAt",
            page_size=20
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# -------------------------------
# Newsletter Subscription API
# -------------------------------
class SubscribeRequest(BaseModel):
    name: str
    email: str


@app.post("/subscribe")
async def subscribe_user(req: SubscribeRequest):
    try:
        success = await send_confirmation_email(req.email, req.name)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to send confirmation email")

        return {
            "success": True,
            "message": "Subscription received — confirmation email sent."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subscription failed: {str(e)}")


# -------------------------------
# Optional: file upload endpoint
# -------------------------------
@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        with open(f"/tmp/{file.filename}", "wb") as f:
            f.write(contents)
        return {"status": "ok", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
from services.news_service import news_service


