interface NewsAPIResponse {
  status: string;
  totalResults: number;
  articles: NewsArticle[];
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

export class NewsAPIService {
  constructor() {}

  async searchNews(query: string, pageSize: number = 20): Promise<NewsArticle[]> {
    const url = `/api/news/search?query=${encodeURIComponent(query)}&pageSize=${pageSize}`;
    
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`API request failed: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (data.error) {
        throw new Error(`API error: ${data.error}`);
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
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`API request failed: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (data.error) {
        throw new Error(`API error: ${data.error}`);
      }

      return data;
    } catch (error) {
      console.error('Error fetching top headlines:', error);
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

let _newsApiService: NewsAPIService | null = null;

export const newsApiService = {
  get instance(): NewsAPIService {
    if (!_newsApiService) {
      _newsApiService = new NewsAPIService();
    }
    return _newsApiService;
  },
  
  // Proxy methods for easier access
  searchNews: (query: string, pageSize?: number) => newsApiService.instance.searchNews(query, pageSize),
  getTopHeadlines: (country?: string, pageSize?: number) => newsApiService.instance.getTopHeadlines(country, pageSize),
  generateSearchQuery: (content: string) => newsApiService.instance.generateSearchQuery(content)
};
