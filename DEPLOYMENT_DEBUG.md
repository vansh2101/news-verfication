# Deployment Checklist for TruthLens

## Environment Variables Setup

1. **In Vercel Dashboard:**
   - Go to your project settings
   - Navigate to Environment Variables
   - Add: `SERPAPI_KEY` with your actual SerpAPI key
   - Make sure it's set for Production, Preview, and Development environments

2. **Test Environment Variables:**
   - Visit: `https://your-app.vercel.app/api/test` after deployment
   - Check if `hasApiKey: true` in the response

## Debugging Steps

1. **Check Vercel Function Logs:**
   - Go to Vercel Dashboard > Functions tab
   - Look for errors in the `/api/news/headlines` function
   - Check for timeout errors or SerpAPI errors

2. **Test API Directly:**
   - Visit: `https://your-app.vercel.app/api/news/headlines?country=us&pageSize=5`
   - Should return JSON array of articles

3. **Check Browser Network Tab:**
   - Open Developer Tools > Network
   - Look for failed requests to `/api/news/headlines`
   - Check response status and error messages

## Common Issues & Solutions

### Issue 1: Environment Variable Not Set
- **Symptom:** API returns "SerpAPI key is not configured"
- **Solution:** Set SERPAPI_KEY in Vercel environment variables

### Issue 2: Function Timeout
- **Symptom:** Request hangs for 30+ seconds then fails
- **Solution:** SerpAPI is taking too long, try reducing pageSize parameter

### Issue 3: SerpAPI Package Compatibility
- **Symptom:** Function crashes or returns errors
- **Solution:** We've added better error handling and logging

### Issue 4: CORS Issues
- **Symptom:** Network errors in browser
- **Solution:** API routes should handle this, but check for browser blocks

## Fallback Mechanism

The app now includes:
- Automatic fallback to sample articles if API fails
- 35-second total timeout
- Better error logging
- Health check component (in development)

## Next Steps if Still Failing

1. Check Vercel function logs for specific errors
2. Test with reduced pageSize (try 10 instead of 50)
3. Consider switching to a different news API if SerpAPI continues to have issues
4. Implement static generation with ISR (Incremental Static Regeneration)
