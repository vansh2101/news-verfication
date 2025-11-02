import { NextRequest, NextResponse } from 'next/server';

async function searchNews(query: string, pageSize: number = 20) {
    const apiKey = process.env.NEWSAPI_KEY;
    if (!apiKey) {
      throw new Error('News API key is not configured. Please add NEWSAPI_KEY to your environment variables.');
    }
    const baseUrl = 'https://newsapi.org/v2';
    const url = `${baseUrl}/everything?q=${encodeURIComponent(query)}&language=en&sortBy=publishedAt&pageSize=${pageSize}&apiKey=${apiKey}`;
    
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
        (article.content || article.description) &&
        article.url
      );
    } catch (error) {
      console.error('Error fetching news:', error);
      throw error;
    }
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get('query');
  const pageSize = searchParams.get('pageSize');

  if (!query) {
    return NextResponse.json({ error: 'Query parameter is required' }, { status: 400 });
  }

  try {
    const articles = await searchNews(query, pageSize ? parseInt(pageSize) : 20);
    return NextResponse.json(articles);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
