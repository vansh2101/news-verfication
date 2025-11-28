interface SerpAPIResponse {
  news_results?: SerpNewsResult[];
  error?: string;
}

interface SerpNewsResult {
  title: string;
  link: string;
  source: string;
  date: string;
  snippet?: string;
  thumbnail?: string;
}

export interface NewsArticle {
  source: {
    id: string | null;
    name: string;
  };
  author: string | null;
  title: string;
  description: string | null;
  url: string;
  urlToImage: string | null;
  publishedAt: string;
  content: string | null;
}

export class SerpAPIService {
  constructor() {}

  async searchNews(query: string, pageSize: number = 20): Promise<NewsArticle[]> {
    const url = `/api/news/search?query=${encodeURIComponent(query)}&pageSize=${pageSize}`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`SerpAPI request failed: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (data.error) {
        throw new Error(`SerpAPI error: ${data.error}`);
      }

      return data;
    } catch (error) {
      console.error('Error fetching news:', error);
      throw error;
    }
  }

  async getTopHeadlines(country: string = 'us', pageSize: number = 50): Promise<NewsArticle[]> {
    const url = `/api/news/headlines?country=${country}&pageSize=${pageSize}`;
    
    try {
      // Add timeout to prevent hanging requests
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
      
      const response = await fetch(url, {
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('API Response Error:', {
          status: response.status,
          statusText: response.statusText,
          body: errorText
        });
        throw new Error(`SerpAPI request failed: ${response.status} ${response.statusText}. ${errorText}`);
      }
      
      const data = await response.json();
      
      if (data.error) {
        console.error('SerpAPI Error:', data.error);
        throw new Error(`SerpAPI error: ${data.error}`);
      }

      if (!Array.isArray(data)) {
        console.error('Invalid response format:', data);
        throw new Error('Invalid response format from API');
      }

      return data;
    } catch (error: any) {
      console.error('Error fetching top headlines:', error);
      if (error.name === 'AbortError') {
        throw new Error('Request timeout - the news service took too long to respond');
      }
      throw error;
    }
  }

  async generateSearchQuery(content: string): Promise<string> {
    try {
      const response = await fetch('/api/news/keywords', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: content }),
      });

      if (!response.ok) {
        throw new Error(`API request failed: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      if (data.error) {
        throw new Error(`API error: ${data.error}`);
      }
      
      return data.searchQuery;
    } catch (error) {
      console.error('Error generating search query:', error);
      throw error;
    }
  }
}

let _serpApiService: SerpAPIService | null = null;

export const newsApiService = {
  get instance(): SerpAPIService {
    if (!_serpApiService) {
      _serpApiService = new SerpAPIService();
    }
    return _serpApiService;
  },
  
  // Proxy methods for easier access
  searchNews: (query: string, pageSize?: number) => newsApiService.instance.searchNews(query, pageSize),
  getTopHeadlines: (country?: string, pageSize?: number) => newsApiService.instance.getTopHeadlines(country, pageSize),
  generateSearchQuery: (content: string) => newsApiService.instance.generateSearchQuery(content)
};
