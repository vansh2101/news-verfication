// API client for TruthLens backend

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface VerifyRequest {
  video?: string;
  link?: string;
  text?: string;
}

export interface VerifyResponse {
  input: {
    video?: string;
    link?: string;
    text?: string;
    timestamp: string;
  };
  analysis: {
    summary: string;
    key_events: string[];
    sources_analyzed: {
      video_frames: number;
      web_paragraphs: number;
      total_scraped_items: number;
    };
  };
  truth_score: {
    overall_score: number;
    confidence_level: string;
    verification_status: string;
    credibility: {
      factual_accuracy: number;
      source_reliability: number;
      consistency_score: number;
    };
    fact_breakdown: Array<{
      claim: string;
      truth_score: number;
      verification: string;
      supporting_sources: string[];
      explanation: string;
    }>;
    summary: string;
    recommendations: string[];
  };
  supporting_evidence: {
    youtube_videos: Array<{
      title: string;
      link: string;
      source: string;
      engagement: number;
    }>;
    reddit_discussions: Array<{
      title: string;
      link: string;
      source: string;
      engagement: number;
    }>;
    twitter_posts: Array<{
      title: string;
      link: string;
      source: string;
      engagement: number;
    }>;
    news_articles: Array<{
      title: string;
      link: string;
      source: string;
      engagement: number;
    }>;
  };
  metadata: {
    generated_at: string;
    total_sources_checked: number;
    processing_complete: boolean;
  };
}

/**
 * Verify content using the backend pipeline
 */
export async function verifyContent(data: VerifyRequest): Promise<VerifyResponse> {
  console.log('[API] Sending verification request to:', `${API_BASE_URL}/verify`);
  console.log('[API] Request data:', data);
  
  try {
    const response = await fetch(`${API_BASE_URL}/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    console.log('[API] Response status:', response.status);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Verification failed' }));
      console.error('[API] Error response:', error);
      throw new Error(error.detail || 'Verification failed');
    }

    const result = await response.json();
    console.log('[API] Success response:', result);
    return result;
  } catch (error) {
    console.error('[API] Fetch error:', error);
    throw error;
  }
}

/**
 * Upload video file and verify
 */
export async function verifyWithUpload(
  file: File,
  link?: string,
  text?: string
): Promise<VerifyResponse> {
  console.log('[API] Uploading file to:', `${API_BASE_URL}/verify-upload`);
  console.log('[API] File:', file.name, 'Size:', file.size);
  
  const formData = new FormData();
  formData.append('file', file);
  if (link) formData.append('link', link);
  if (text) formData.append('text', text);

  try {
    const response = await fetch(`${API_BASE_URL}/verify-upload`, {
      method: 'POST',
      body: formData,
    });

    console.log('[API] Upload response status:', response.status);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload and verification failed' }));
      console.error('[API] Upload error:', error);
      throw new Error(error.detail || 'Upload and verification failed');
    }

    const result = await response.json();
    console.log('[API] Upload success:', result);
    return result;
  } catch (error) {
    console.error('[API] Upload fetch error:', error);
    throw error;
  }
}

/**
 * Subscribe to newsletter
 */
export async function subscribeNewsletter(name: string, email: string) {
  const response = await fetch(`${API_BASE_URL}/subscribe`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name, email }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Subscription failed' }));
    throw new Error(error.detail || 'Subscription failed');
  }

  return response.json();
}
