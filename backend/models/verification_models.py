# models/verification_models.py
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Literal


class Claim(BaseModel):
    id: str
    text: str
    type: Literal["factual", "opinion", "prediction", "statistic"]
    confidence: int = Field(..., ge=0, le=100)
    context: Optional[str] = None


class SourceInfo(BaseModel):
    name: str
    url: Optional[HttpUrl] = None
    reliability: int = Field(..., ge=0, le=100)
    stance: Literal["supports", "contradicts", "neutral"]


class VerificationResultSummary(BaseModel):
    truthScore: int = Field(..., ge=0, le=100)
    isLikelyMisinformation: bool
    reasons: List[str]
    supportingArticles: int
    contradictingArticles: int
    verificationSummary: str
    sources: List[SourceInfo]


class ProcessedInput(BaseModel):
    originalContent: str
    extractedText: str
    title: Optional[str] = None
    url: Optional[HttpUrl] = None
    source: Optional[str] = None


class CompleteVerificationResult(BaseModel):
    claims: List[Claim]
    verification: VerificationResultSummary
    input: ProcessedInput
    relatedArticles: List[dict]
    processingTime: int
    timestamp: str
