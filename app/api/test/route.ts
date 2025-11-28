import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  return NextResponse.json({
    status: 'API is working',
    timestamp: new Date().toISOString(),
    environment: {
      nodeEnv: process.env.NODE_ENV,
      hasApiKey: !!process.env.SERPAPI_KEY,
      vercel: !!process.env.VERCEL,
      vercelEnv: process.env.VERCEL_ENV,
      region: process.env.VERCEL_REGION
    }
  });
}
