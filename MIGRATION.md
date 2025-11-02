# Migration from News API to SerpAPI

## Summary of Changes

This document outlines the migration from News API to SerpAPI for fetching news data in the TruthLens application.

## Files Modified

### 1. Package Dependencies
- **Added**: `serpapi` package
- **Removed**: Direct News API dependencies

### 2. Core Service Layer
- **File**: `lib/newsApi.ts`
  - Renamed `NewsAPIService` class to `SerpAPIService`
  - Updated interfaces to handle SerpAPI response structure
  - Maintained the same public API interface for backward compatibility

### 3. API Routes
- **File**: `app/api/news/search/route.ts`
  - Replaced News API fetch calls with SerpAPI `getJson` calls
  - Updated data transformation to handle SerpAPI's nested structure (highlights and stories)
  - Changed environment variable from `NEWSAPI_KEY` to `SERPAPI_KEY`

- **File**: `app/api/news/headlines/route.ts`
  - Similar updates as search route
  - Handles both highlight stories and regular articles

### 4. Frontend Pages
- **File**: `app/page.tsx`
  - Updated imports to use the new service
  - Replaced direct API calls with service calls

- **Files**: `app/news-text/page.tsx`, `app/news-video/page.tsx`, `app/news-link/page.tsx`
  - Removed direct News API calls
  - Updated to use the centralized service

### 5. Components
- **File**: `app/components/ApiKeyTester.tsx`
  - Updated labels and links to reflect SerpAPI instead of News API

### 6. Configuration
- **File**: `.env.example`
  - Updated to show `SERPAPI_KEY` instead of `NEXT_PUBLIC_NEWSAPI_KEY`

- **File**: `README.md`
  - Added setup instructions for SerpAPI key

## API Key Migration

### Old Configuration
```env
NEXT_PUBLIC_NEWSAPI_KEY=your_newsapi_key_here
```

### New Configuration
```env
SERPAPI_KEY=your_serpapi_key_here
```

## Data Structure Changes

### SerpAPI Response Structure
SerpAPI returns data in a different format than News API:

1. **Highlight Stories**: Main stories with nested related articles
2. **Regular Articles**: Simple article structure
3. **Rich Metadata**: Additional information like thumbnails, authors, etc.

### Transformation Logic
The service now handles both structures and normalizes them to match the existing `NewsArticle` interface, ensuring backward compatibility.

## Benefits of Migration

1. **Better Data Quality**: SerpAPI provides more comprehensive news data from Google News
2. **Real-time Updates**: More current news information
3. **Rich Media**: Better thumbnail and image support
4. **Reliability**: More stable API with better uptime

## Setup Instructions

1. Get a SerpAPI key from [https://serpapi.com/](https://serpapi.com/)
2. Add `SERPAPI_KEY=your_key_here` to your `.env.local` file
3. Restart your development server
4. The application will now use SerpAPI for all news data

## Testing

All existing functionality remains the same from a user perspective. The API key tester component has been updated to reflect the new service.
