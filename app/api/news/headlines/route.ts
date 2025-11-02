import { NextRequest, NextResponse } from 'next/server';

async function getTopHeadlines(country: string = 'us', pageSize: number = 50) {
    const apiKey = process.env.NEWSAPI_KEY;
    if (!apiKey) {
      throw new Error('News API key is not configured. Please add NEWSAPI_KEY to your environment variables.');
    }
    const baseUrl = 'https://newsapi.org/v2';
    const url = `${baseUrl}/top-headlines?country=${country}&pageSize=${pageSize}&apiKey=${apiKey}`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        const errorBody = await response.text();
        console.error(`News API request failed: ${response.status} ${response.statusText}`, errorBody);
        throw new Error(`News API request failed: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (data.status !== 'ok') {
        throw new Error(`News API error: ${data.message || data.status}`);
      }

      return data.articles.filter((article: any) => 
        article.title &&
        article.description &&
        article.urlToImage &&
        article.url
      );
    } catch (error) {
      console.error('Error fetching top headlines:', error);
      throw error;
    }
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const country = searchParams.get('country') || 'us';
  const pageSize = searchParams.get('pageSize');

  try {
    const articles = await getTopHeadlines(country, pageSize ? parseInt(pageSize) : 50);
    return NextResponse.json(articles);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
