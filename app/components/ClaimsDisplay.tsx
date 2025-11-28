import React from 'react';
import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react';

interface Claim {
  claim: string;
  truth_score?: number;
  verification?: string;
  supporting_sources?: string[];
  explanation?: string;
  // Legacy format support
  id?: string;
  type?: string;
  text?: string;
  confidence?: number;
  context?: string;
}

interface ClaimsDisplayProps {
  claims: Claim[];
}

export function ClaimsDisplay({ claims }: ClaimsDisplayProps) {
  if (!claims || claims.length === 0) {
    return null;
  }

  const getVerificationColor = (verification: string) => {
    switch (verification?.toLowerCase()) {
      case 'verified':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'partially verified':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'unverified':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'false':
        return 'bg-red-100 text-red-800 border-red-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getVerificationIcon = (verification: string) => {
    switch (verification?.toLowerCase()) {
      case 'verified':
        return <CheckCircle className="w-4 h-4 text-green-600" />;
      case 'partially verified':
        return <AlertTriangle className="w-4 h-4 text-yellow-600" />;
      case 'unverified':
      case 'false':
        return <XCircle className="w-4 h-4 text-red-600" />;
      default:
        return <AlertTriangle className="w-4 h-4 text-gray-600" />;
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-3">
      {claims.map((claim, index) => {
        // Support both new backend format and legacy format
        const claimText = claim.claim || claim.text || '';
        const truthScore = claim.truth_score ?? claim.confidence ?? 0;
        const verification = claim.verification || 'Unknown';
        const sources = claim.supporting_sources || [];
        const explanation = claim.explanation || claim.context || '';

        return (
          <div key={claim.id || index} className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm hover:shadow-md transition-all">
            {/* Header with verification status and score */}
            <div className="flex justify-between items-start mb-2">
              <div className="flex items-center gap-2">
                {getVerificationIcon(verification)}
                <span className={`px-3 py-1 text-sm rounded-full font-medium border ${getVerificationColor(verification)}`}>
                  {verification}
                </span>
              </div>
              <div className="text-right">
                {/* <div className="text-xs text-gray-500">Truth Score</div>
                <div className={`text-lg font-bold ${getScoreColor(truthScore)}`}>
                  {truthScore}%
                </div> */}
              </div>
            </div>

            {/* Claim text - Truncated */}
            <p className="text-sm text-gray-800 leading-relaxed mb-2 font-medium line-clamp-2">
              "{claimText.length > 150 ? claimText.substring(0, 150) + '...' : claimText}"
            </p>

            {/* Explanation - Truncated */}
            {explanation && (
              <div className="bg-gray-50 border-l-4 border-l-blue-400 pl-2 py-1.5 mb-2 rounded">
                <p className="text-xs text-gray-700 line-clamp-2">
                  <span className="font-semibold">Explanation:</span> {explanation.length > 120 ? explanation.substring(0, 120) + '...' : explanation}
                </p>
              </div>
            )}

            {/* Supporting Sources - Show max 4 */}
            {sources.length > 0 && (
              <div className="mt-2 pt-2 border-t border-gray-200">
                <p className="text-xs font-semibold text-gray-600 mb-2">Supporting Sources ({sources.length}):</p>
                <div className="flex flex-wrap gap-2">
                  {sources.slice(0, 4).map((source, idx) => (
                    <span key={idx} className="px-2 py-1 text-xs bg-blue-50 text-blue-700 rounded-md border border-blue-200 truncate max-w-[200px]">
                      {source}
                    </span>
                  ))}
                  {sources.length > 4 && (
                    <span className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-md border border-gray-200">
                      +{sources.length - 4} more
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default ClaimsDisplay;
