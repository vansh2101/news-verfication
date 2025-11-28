'use client';

import { useState, useEffect } from 'react';

export function ApiHealthCheck() {
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [newsStatus, setNewsStatus] = useState<any>(null);

  useEffect(() => {
    // Test basic API health
    fetch('/api/test')
      .then(res => res.json())
      .then(data => setHealthStatus(data))
      .catch(err => setHealthStatus({ error: err.message }));

    // Test news API specifically
    fetch('/api/news/headlines?country=us&pageSize=5')
      .then(res => res.json())
      .then(data => setNewsStatus(data))
      .catch(err => setNewsStatus({ error: err.message }));
  }, []);

  if (process.env.NODE_ENV === 'production') {
    return null; // Don't show in production
  }

  return (
    <div className="fixed bottom-4 right-4 bg-gray-900 text-white p-4 rounded-lg shadow-lg max-w-sm z-50">
      <h3 className="font-bold mb-2">API Health Check</h3>
      
      <div className="mb-2">
        <strong>Basic API:</strong>
        <pre className="text-xs mt-1 overflow-auto max-h-20">
          {JSON.stringify(healthStatus, null, 2)}
        </pre>
      </div>

      <div>
        <strong>News API:</strong>
        <pre className="text-xs mt-1 overflow-auto max-h-20">
          {Array.isArray(newsStatus) 
            ? `${newsStatus.length} articles loaded`
            : JSON.stringify(newsStatus, null, 2)
          }
        </pre>
      </div>
    </div>
  );
}
