import React from 'react';
import { ExternalLink, Youtube, MessageSquare, Twitter, Newspaper } from 'lucide-react';

interface EvidenceItem {
  title: string;
  link: string;
  source: string;
  engagement: number;
}

interface SupportingEvidenceProps {
  youtube_videos?: EvidenceItem[];
  reddit_discussions?: EvidenceItem[];
  twitter_posts?: EvidenceItem[];
  news_articles?: EvidenceItem[];
}

export function SupportingEvidenceGrid({
  youtube_videos = [],
  reddit_discussions = [],
  twitter_posts = [],
  news_articles = []
}: SupportingEvidenceProps) {
  const formatEngagement = (count: number) => {
    if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
    if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
    return count.toString();
  };

  const renderSection = (
    title: string,
    items: EvidenceItem[],
    icon: React.ReactNode,
    color: string
  ) => {
    if (!items || items.length === 0) return null;

    // Show only top 6 items for cleaner display
    const displayItems = items.slice(0, 6);

    return (
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {icon}
            <h3 className="text-base font-bold text-gray-900">{title}</h3>
            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
              {items.length}
            </span>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {displayItems.map((item, index) => (
            <a
              key={index}
              href={item.link}
              target="_blank"
              rel="noopener noreferrer"
              className={`block bg-white border-2 ${color} rounded-lg p-3 hover:shadow-md transition-all group`}
            >
              <div className="flex justify-between items-start mb-2">
                <span className="text-xs font-semibold text-gray-500 uppercase truncate max-w-[150px]">
                  {item.source}
                </span>
                <ExternalLink className="w-3 h-3 text-gray-400 group-hover:text-gray-600 flex-shrink-0" />
              </div>
              <h4 className="text-sm font-medium text-gray-900 line-clamp-2 mb-2 group-hover:text-blue-600">
                {item.title.length > 80 ? item.title.substring(0, 80) + '...' : item.title}
              </h4>
              {item.engagement > 0 && (
                <div className="flex items-center gap-1 text-xs text-gray-500">
                  <span className="font-semibold">{formatEngagement(item.engagement)}</span>
                  <span>views</span>
                </div>
              )}
            </a>
          ))}
        </div>
        {items.length > 6 && (
          <p className="text-xs text-gray-500 mt-2 text-center">
            +{items.length - 6} more sources available
          </p>
        )}
      </div>
    );
  };

  const hasAnyEvidence = 
    youtube_videos.length > 0 ||
    reddit_discussions.length > 0 ||
    twitter_posts.length > 0 ||
    news_articles.length > 0;

  if (!hasAnyEvidence) {
    return (
      <div className="text-center py-8 text-gray-500">
        No supporting evidence available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Supporting Evidence</h2>
      
      {renderSection(
        'News Articles',
        news_articles,
        <Newspaper className="w-4 h-4 text-blue-600" />,
        'border-blue-200 hover:border-blue-400'
      )}

      {renderSection(
        'YouTube Videos',
        youtube_videos,
        <Youtube className="w-4 h-4 text-red-600" />,
        'border-red-200 hover:border-red-400'
      )}

      {renderSection(
        'Reddit Discussions',
        reddit_discussions,
        <MessageSquare className="w-4 h-4 text-orange-600" />,
        'border-orange-200 hover:border-orange-400'
      )}

      {renderSection(
        'Twitter Posts',
        twitter_posts,
        <Twitter className="w-4 h-4 text-sky-600" />,
        'border-sky-200 hover:border-sky-400'
      )}
    </div>
  );
}

export default SupportingEvidenceGrid;
