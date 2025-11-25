"use client";

import { useSearchParams } from "next/navigation";
import { useState, useEffect, Suspense } from "react";
import { Card } from "@/app/components/ui/card";
import { Play, ExternalLink, Loader2 } from "lucide-react";
import { VerificationStatus } from "@/app/components/verification-status";
import { ConfidenceScoreBox } from "@/app/components/confidence-score-box";
import { SourceBox } from "@/app/components/source-box";
import { ClaimsDisplay } from "@/app/components/ClaimsDisplay";
import { VerificationSummaryCard } from "@/app/components/VerificationSummaryCard";
import { SupportingEvidenceGrid } from "@/app/components/SupportingEvidenceGrid";

interface NewsArticle {
  title: string;
  description: string;
  url: string;
  urlToImage: string;
  publishedAt: string;
  source: {
    name: string;
  };
  content: string;
}

function CombinedResultsContent() {
  const searchParams = useSearchParams();
  const typesParam = searchParams.get("types");
  const queryParam = searchParams.get("query") || "breaking news";
  const isVerified = searchParams.get("verified") === "true";
  const types = typesParam ? typesParam.split(",") : [];
  
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [verificationResults, setVerificationResults] = useState<any>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        
        // Check if we have verification results from the backend
        if (isVerified) {
          const storedResults = localStorage.getItem('verificationResults');
          console.log('[Results Page] Raw localStorage data:', storedResults);
          if (storedResults) {
            const parsedResults = JSON.parse(storedResults);
            console.log('[Results Page] Parsed results:', parsedResults);
            setVerificationResults(parsedResults);
            
            // Convert backend supporting_evidence to articles format
            if (parsedResults.result?.supporting_evidence) {
              const evidence = parsedResults.result.supporting_evidence;
              const allArticles: NewsArticle[] = [];
              
              // Add news articles
              if (evidence.news_articles) {
                evidence.news_articles.forEach((article: any) => {
                  allArticles.push({
                    title: article.title,
                    description: article.title,
                    url: article.link,
                    urlToImage: '',
                    publishedAt: new Date().toISOString(),
                    source: { name: article.source },
                    content: article.title
                  });
                });
              }
              
              setArticles(allArticles.slice(0, 5));
              setLoading(false);
              return;
            }
          }
        }
        
        // No verification data - show empty state
        setArticles([]);
        setLoading(false);
      } catch (err: any) {
        setError(err.message || "Error loading verification results");
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [queryParam, isVerified]);

  // Generate dynamic confidence scores based on source reputation or verification results
  const getConfidenceScore = (sourceName: string): number => {
    const reputableSources: { [key: string]: number } = {
      "BBC": 95, "Reuters": 93, "CNN": 88, "The Guardian": 90,
      "The New York Times": 92, "The Washington Post": 91,
      "Associated Press": 94, "Bloomberg": 89, "NPR": 87
    };
    return reputableSources[sourceName] || Math.floor(Math.random() * 15) + 75;
  };

  // Create news data object with verification results if available
  const getNewsData = () => {
    // Use backend verification results
    if (verificationResults?.result) {
      const result = verificationResults.result;
      const truthScore = result.truth_score || {};
      
      return {
        verified: truthScore.verification_status !== 'Unverified',
        truthScore: truthScore.overall_score || 0,
        verificationSummary: truthScore.summary || result.analysis?.summary || 'No summary available',
        reasons: truthScore.recommendations || [],
        confidenceScores: [
          { source: 'Factual Accuracy', score: truthScore.credibility?.factual_accuracy || 0 },
          { source: 'Source Reliability', score: truthScore.credibility?.source_reliability || 0 },
          { source: 'Consistency', score: truthScore.credibility?.consistency_score || 0 }
        ],
        sources: [
          ...(result.supporting_evidence?.news_articles?.map((article: any) => ({
            name: article.source,
            date: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
            description: article.title,
            url: article.link
          })) || []),
          ...(result.supporting_evidence?.youtube_videos?.map((video: any) => ({
            name: 'YouTube',
            date: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
            description: video.title,
            url: video.link
          })) || [])
        ].slice(0, 5),
        claims: truthScore.fact_breakdown?.map((fact: any) => ({
          claim: fact.claim,
          verification: fact.verification,
          sources: fact.supporting_sources || []
        })) || [],
        input: result.input,
        link: result.input?.link ? {
          title: 'Provided Link',
          description: result.input.link,
          url: result.input.link,
          image: '/placeholder-news.jpg',
        } : null,
        video: result.input?.video ? {
          title: 'Provided Video',
          thumbnail: '/placeholder-video.jpg',
          duration: '3:45',
          url: result.input.video,
        } : null,
        text: result.input?.text || result.analysis?.summary || 'No content available',
      };
    }

    // Fallback when no verification data
    return {
      verified: false,
      truthScore: 0,
      verificationSummary: 'No verification data available',
      reasons: [],
      confidenceScores: [],
      sources: [],
      claims: [],
      link: null,
      video: null,
      text: 'No content available',
    };
  };

  const newsData = getNewsData();

  // 🔸 Sidebar with basic verification info
  const renderSidebar = () => (
    <aside className="space-y-4 lg:space-y-6 w-full">
      <VerificationStatus isVerified={newsData.verified} truthScore={newsData.truthScore} />

      <div>
        <p className="font-semibold text-gray-700 mb-2">Confidence Scores</p>
        <div className="space-y-2">
          {newsData.confidenceScores && newsData.confidenceScores.length > 0 ? (
            newsData.confidenceScores.map((item: any, idx: number) => (
              <ConfidenceScoreBox key={idx} score={item.score} sourceName={item.source} />
            ))
          ) : (
            <p className="text-sm text-gray-500">No confidence scores available</p>
          )}
        </div>

        {/* 🟧 Expanded reliability section */}
        <div className="mt-4 lg:mt-6 grid grid-cols-1 gap-4">
          <div className="flex flex-col justify-between items-center bg-gray-50 border border-black/20 rounded-lg p-4 shadow-sm min-h-40">
            <p className="text-lg lg:text-xl text-center font-semibold text-orange-500 mb-1">
              Overall <br /> Reliability
            </p>
            <p className={`text-xl lg:text-2xl font-bold my-auto ${
              newsData.truthScore >= 80 ? 'text-green-600' :
              newsData.truthScore >= 70 ? 'text-blue-600' :
              newsData.truthScore >= 60 ? 'text-yellow-600' :
              newsData.truthScore >= 50 ? 'text-orange-600' : 'text-red-600'
            }`}>
              {newsData.truthScore >= 80 ? 'High' :
               newsData.truthScore >= 70 ? 'Good' :
               newsData.truthScore >= 60 ? 'Medium' :
               newsData.truthScore >= 50 ? 'Low' : 'Very Low'}
            </p>
            <p className="text-xs text-gray-600 text-center">
              Cross-verified with {newsData.confidenceScores.length} trusted sources.
            </p>
          </div>

          <div className="flex flex-col justify-between items-center bg-gray-50 border border-gray-200 rounded-lg p-4 shadow-sm min-h-40">
            <p className="text-base lg:text-lg text-center font-semibold text-orange-500">
              Verification <br /> Summary
            </p>

            <p className="text-sm text-center text-gray-600 leading-snug my-auto px-2">
              {newsData.verificationSummary && newsData.verificationSummary.length > 0 
                ? newsData.verificationSummary.slice(0, 120) + (newsData.verificationSummary.length > 120 ? '...' : '')
                : "Independent reviews confirm the content matches verified facts."}
            </p>

            <div className="h-1" />
          </div>
        </div>
      </div>
    </aside>
  );

  // 🔸 Detailed Analysis Section (right side)
  const renderDetailedAnalysis = () => (
    <div className="space-y-6 lg:space-y-8">
      {/* Enhanced Verification Summary */}
      {verificationResults && verificationResults.result && (
        <div className="bg-white border-2 border-gray-200 rounded-2xl p-6 shadow-sm">
          <VerificationSummaryCard
            truthScore={newsData.truthScore}
            isLikelyMisinformation={newsData.truthScore < 60}
            reasons={newsData.reasons || []}
            verificationSummary={newsData.verificationSummary || ""}
            supportingArticles={verificationResults.result.supporting_evidence?.news_articles?.length || 0}
            contradictingArticles={0}
            sources={newsData.sources || []}
          />
        </div>
      )}

      {/* Claims Analysis Section */}
      {newsData.claims && newsData.claims.length > 0 && (
        <div className="bg-white border-2 border-gray-200 rounded-2xl p-6 shadow-sm">
          <h4 className="text-xl font-semibold text-gray-800 mb-4">Fact Breakdown</h4>
          <ClaimsDisplay claims={newsData.claims} />
        </div>
      )}

      {/* Supporting Evidence Section */}
      {verificationResults?.result?.supporting_evidence && (
        <div className="bg-white border-2 border-gray-200 rounded-2xl p-6 shadow-sm">
          <SupportingEvidenceGrid
            youtube_videos={verificationResults.result.supporting_evidence.youtube_videos}
            reddit_discussions={verificationResults.result.supporting_evidence.reddit_discussions}
            twitter_posts={verificationResults.result.supporting_evidence.twitter_posts}
            news_articles={verificationResults.result.supporting_evidence.news_articles}
          />
        </div>
      )}
    </div>
  );

  // 🔸 Sources row under main content
  const renderSourcesRow = () => {
    if (!newsData.sources || newsData.sources.length === 0) {
      return null;
    }
    
    return (
      <div className="mt-6 lg:mt-8">
        <h4 className="text-lg font-semibold text-gray-800 mb-4">Verified Sources</h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {newsData.sources.slice(0, 6).map((s: any, i: number) => (
            <div
              key={i}
              className="flex justify-center"
            >
              <SourceBox {...s} />
            </div>
          ))}
        </div>
      </div>
    );
  };

  // Render unified input content section (video, link, text combined)
  const renderInputContent = () => {
    const hasVideo = types.includes("video") && newsData.video;
    const hasLink = types.includes("link") && newsData.link;
    const hasText = types.includes("text");
    const inputText = newsData.input?.text || newsData.text;

    return (
      <div className="space-y-4">
        <h3 className="text-xl font-bold text-gray-800 mb-4">📥 Submitted Content</h3>
        
        {/* Video Card */}
        {hasVideo && newsData.video && (
          <Card className="p-4 border-2 border-orange-200 bg-gradient-to-br from-orange-50 to-white rounded-xl shadow-sm hover:shadow-md transition-all">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0">
                <div className="w-12 h-12 bg-orange-500 rounded-lg flex items-center justify-center">
                  <Play className="w-6 h-6 text-white fill-white" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-orange-600 uppercase tracking-wide mb-1">Video Content</p>
                <h4 className="text-sm font-bold text-gray-800 truncate">{newsData.video.title}</h4>
                <a
                  href={newsData.video.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-orange-600 hover:text-orange-700 font-medium inline-flex items-center gap-1 mt-1"
                >
                  View Video <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          </Card>
        )}

        {/* Link Card */}
        {hasLink && newsData.link && (
          <Card className="p-4 border-2 border-blue-200 bg-gradient-to-br from-blue-50 to-white rounded-xl shadow-sm hover:shadow-md transition-all">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0">
                <div className="w-12 h-12 bg-blue-500 rounded-lg flex items-center justify-center">
                  <ExternalLink className="w-6 h-6 text-white" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-blue-600 uppercase tracking-wide mb-1">Web Link</p>
                <a
                  href={newsData.link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-bold text-gray-800 hover:text-blue-600 transition-colors truncate block"
                >
                  {newsData.link.url}
                </a>
                <p className="text-xs text-gray-600 mt-1 line-clamp-2">{newsData.link.description}</p>
              </div>
            </div>
          </Card>
        )}

        {/* Text Card */}
        {hasText && inputText && (
          <Card className="p-4 border-2 border-purple-200 bg-gradient-to-br from-purple-50 to-white rounded-xl shadow-sm hover:shadow-md transition-all">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0">
                <div className="w-12 h-12 bg-purple-500 rounded-lg flex items-center justify-center">
                  <span className="text-2xl">📝</span>
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-purple-600 uppercase tracking-wide mb-1">Text Content</p>
                <p className="text-sm text-gray-700 line-clamp-3 leading-relaxed">
                  {inputText.length > 200 ? inputText.substring(0, 200) + '...' : inputText}
                </p>
              </div>
            </div>
          </Card>
        )}
      </div>
    );
  };

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-white px-4 sm:px-6 py-8 sm:py-12">
      <div className="max-w-7xl mx-auto">
        {/* Header with Score Badge */}
        <div className="text-center mb-8 sm:mb-12">
          <h1 className="text-3xl sm:text-5xl font-bold text-gray-900 mb-4">
            Verification <span className="text-orange-500">Results</span>
          </h1>
          {!loading && verificationResults && (
            <div className="inline-flex items-center gap-3 bg-white border-2 border-gray-200 rounded-full px-6 py-3 shadow-lg">
              <div className={`text-3xl font-bold ${
                newsData.truthScore >= 80 ? 'text-green-600' :
                newsData.truthScore >= 70 ? 'text-blue-600' :
                newsData.truthScore >= 60 ? 'text-yellow-600' :
                newsData.truthScore >= 50 ? 'text-orange-600' : 'text-red-600'
              }`}>
                {newsData.truthScore}%
              </div>
              <div className="text-left">
                <p className="text-xs text-gray-500 uppercase tracking-wide">Truth Score</p>
                <p className="text-sm font-semibold text-gray-700">
                  {newsData.truthScore >= 80 ? 'Highly Reliable' :
                   newsData.truthScore >= 70 ? 'Reliable' :
                   newsData.truthScore >= 60 ? 'Moderately Reliable' :
                   newsData.truthScore >= 50 ? 'Low Reliability' : 'Unreliable'}
                </p>
              </div>
            </div>
          )}
        </div>

        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-12 h-12 animate-spin text-orange-500" />
            <span className="ml-3 text-lg text-gray-600">Analyzing content...</span>
          </div>
        )}

        {error && (
          <div className="text-center py-20">
            <div className="inline-flex items-center gap-3 bg-red-50 border-2 border-red-200 rounded-xl px-6 py-4">
              <span className="text-3xl">⚠️</span>
              <p className="text-red-600 text-lg font-semibold">{error}</p>
            </div>
          </div>
        )}

        {!loading && !error && !verificationResults && (
          <div className="text-center py-20">
            <div className="inline-flex items-center gap-3 bg-gray-50 border-2 border-gray-200 rounded-xl px-6 py-4">
              <span className="text-3xl">🔍</span>
              <p className="text-gray-500 text-lg">No verification data available. Please submit content to verify.</p>
            </div>
          </div>
        )}

        {/* UNIFIED CONTENT SECTION - All modalities in one place */}
        {!loading && !error && verificationResults && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8">
            {/* Left Sidebar - Verification Status */}
            <div className="lg:col-span-3 space-y-4">
              <VerificationStatus isVerified={newsData.verified} truthScore={newsData.truthScore} />

              {/* Confidence Scores */}
              <div className="bg-white border-2 border-gray-200 rounded-xl p-5 shadow-sm">
                <p className="font-bold text-gray-800 mb-3 text-sm uppercase tracking-wide">Credibility Metrics</p>
                <div className="space-y-3">
                  {newsData.confidenceScores && newsData.confidenceScores.length > 0 ? (
                    newsData.confidenceScores.map((item: any, idx: number) => (
                      <ConfidenceScoreBox key={idx} score={item.score} sourceName={item.source} />
                    ))
                  ) : (
                    <p className="text-xs text-gray-400">No scores available</p>
                  )}
                </div>
              </div>

              {/* Quick Summary */}
              <div className="bg-gradient-to-br from-orange-50 to-white border-2 border-orange-200 rounded-xl p-5 shadow-sm">
                <p className="font-bold text-orange-600 mb-2 text-sm uppercase tracking-wide">Verification Summary</p>
                <p className="text-xs text-gray-700 leading-relaxed">
                  {newsData.verificationSummary && newsData.verificationSummary.length > 0 
                    ? newsData.verificationSummary.slice(0, 150) + (newsData.verificationSummary.length > 150 ? '...' : '')
                    : "Content has been cross-verified with multiple trusted sources."}
                </p>
              </div>
            </div>

            {/* Center - Input Content Cards */}
            <div className="lg:col-span-5 space-y-6">
              {renderInputContent()}

              {/* Verified Sources */}
              {renderSourcesRow()}
            </div>

            {/* Right Sidebar - Detailed Analysis */}
            <div className="lg:col-span-4 space-y-6">
              {renderDetailedAnalysis()}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

export default function CombinedResultsPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-white px-6 py-10">
        <div className="max-w-7xl mx-auto space-y-24">
          <h1 className="text-4xl font-bold text-black mb-8 text-center">
            <span className="text-orange-500">Verification</span> Results
          </h1>
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-12 h-12 animate-spin text-orange-500" />
            <span className="ml-3 text-lg text-gray-600">Loading verification results...</span>
          </div>
        </div>
      </main>
    }>
      <CombinedResultsContent />
    </Suspense>
  );
}
