import { NextRequest, NextResponse } from 'next/server';
const { getJson } = require("serpapi");

async function searchNews(query: string, pageSize: number = 20) {
    const apiKey = process.env.SERPAPI_KEY;
    if (!apiKey) {
      throw new Error('SerpAPI key is not configured. Please add SERPAPI_KEY to your environment variables.');
    }
    
    try {
      const searchResults = await new Promise((resolve, reject) => {
        getJson({
          api_key: apiKey,
          engine: "google_news",
          q: query,
          hl: "en",
          gl: "us",
          num: pageSize
        }, (json: any) => {
          if (json.error) {
            reject(new Error(`SerpAPI error: ${json.error}`));
          } else {
            resolve(json);
          }
        });
      });

      const data = searchResults as any;
      
      if (!data.news_results) {
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
