import { NextRequest, NextResponse } from 'next/server';
const { getJson } = require("serpapi");

async function getTopHeadlines(country: string = 'us', pageSize: number = 50) {
    const apiKey = process.env.SERPAPI_KEY;
    if (!apiKey) {
      console.error('Environment variables:', {
        hasApiKey: !!process.env.SERPAPI_KEY,
        nodeEnv: process.env.NODE_ENV,
        vercel: !!process.env.VERCEL,
        allEnvKeys: Object.keys(process.env).filter(key => key.includes('SERP'))
      });
      throw new Error('SerpAPI key is not configured. Please add SERPAPI_KEY to your environment variables.');
    }
    
    console.log('Starting SerpAPI request with params:', { country, pageSize });
    
    try {
      const searchResults = await new Promise((resolve, reject) => {
        const params = {
          api_key: apiKey,
          engine: "google_news",
          hl: "en",
          gl: country,
          num: Math.min(pageSize, 100) // Limit to prevent timeouts
        };
        
        console.log('SerpAPI request params:', { ...params, api_key: '[REDACTED]' });
        
        getJson(params, (json: any) => {
          if (json.error) {
            console.error('SerpAPI returned error:', json.error);
            reject(new Error(`SerpAPI error: ${json.error}`));
          } else {
            console.log('SerpAPI response received, news_results count:', json.news_results?.length || 0);
            resolve(json);
          }
        });
      });

      const data = searchResults as any;
      
      if (!data.news_results || !Array.isArray(data.news_results)) {
        console.warn('No news results found in response:', data);
        return [];
      }

      // Transform SerpAPI results to match NewsArticle interface
      const articles: any[] = [];
      
      data.news_results.forEach((result: any) => {
        // Handle highlight structure (main story)
        if (result.highlight) {
          const highlight = result.highlight;
          articles.push({
            source: {
              id: null,
              name: highlight.source?.name || 'Unknown'
            },
            author: highlight.source?.authors?.[0] || null,
            title: highlight.title,
            description: null, // SerpAPI doesn't provide description for highlights
            url: highlight.link,
            urlToImage: highlight.thumbnail || null,
            publishedAt: highlight.date || new Date().toISOString(),
            content: null
          });
          
          // Add related stories
          if (result.stories) {
            result.stories.forEach((story: any) => {
              articles.push({
                source: {
                  id: null,
                  name: story.source?.name || 'Unknown'
                },
                author: story.source?.authors?.[0] || null,
                title: story.title,
                description: null,
                url: story.link,
                urlToImage: story.thumbnail || null,
                publishedAt: story.date || new Date().toISOString(),
                content: null
              });
            });
          }
        } else {
          // Handle simple article structure
          articles.push({
            source: {
              id: null,
              name: result.source?.name || result.source || 'Unknown'
            },
            author: result.source?.authors?.[0] || null,
            title: result.title,
            description: result.snippet || null,
            url: result.link,
            urlToImage: result.thumbnail || null,
            publishedAt: result.date || new Date().toISOString(),
            content: result.snippet || null
          });
        }
      });
      
      return articles.filter((article: any) => 
        article.title &&
        article.url &&
        article.source.name
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

  // Log environment for debugging
  console.log('API Route Environment Check:', {
    hasApiKey: !!process.env.SERPAPI_KEY,
    nodeEnv: process.env.NODE_ENV,
    vercel: !!process.env.VERCEL
  });

  try {
    const articles = await getTopHeadlines(country, pageSize ? parseInt(pageSize) : 50);
    
    console.log(`Successfully fetched ${articles.length} articles`);
    
    return NextResponse.json(articles, {
      status: 200,
      headers: {
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600', // Cache for 5 minutes
      }
    });
  } catch (error: any) {
    console.error('API Route Error:', {
      message: error.message,
      stack: error.stack,
      name: error.name
    });
    
    return NextResponse.json({ 
      error: error.message,
      details: process.env.NODE_ENV === 'development' ? error.stack : undefined 
    }, { status: 500 });
  }
}
