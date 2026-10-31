'use client';

import { useEffect, useRef, useState } from 'react';
import { Sparkles, X } from 'lucide-react';

interface SearchResult {
  name: string;
  type: string;
  access: string;
  distanceMeters: number;
  evidence: { state: string; label: string; observedAt: string | null };
  rate: { amount: number; unit: string; currency: string } | null;
  vehicles: string[];
  features: string[];
  hoursState: string;
  reasons: string[];
}

interface Props {
  results: SearchResult[];
  destinationName: string;
  vehicle: string;
  durationMinutes: number;
  searchKey: string; // changes each search to trigger re-fetch
}

export function AiSuggest({ results, destinationName, vehicle, durationMinutes, searchKey }: Props) {
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const lastKey = useRef('');

  useEffect(() => {
    if (!results.length || searchKey === lastKey.current || dismissed) return;
    lastKey.current = searchKey;
    setDismissed(false);
    setSuggestion(null);
    setLoading(true);

    const controller = new AbortController();

    fetch('/api/v1/ai-suggest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ results: results.slice(0, 3), destinationName, vehicle, durationMinutes }),
      signal: controller.signal,
    })
      .then(r => r.json() as Promise<{ suggestion?: string | null }>)
      .then((data: { suggestion?: string | null }) => {
        if (data.suggestion) setSuggestion(data.suggestion);
      })
      .catch(() => {})
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [searchKey, results.length]); // eslint-disable-line react-hooks/exhaustive-deps

  if (dismissed || (!loading && !suggestion)) return null;

  return (
    <div className="ai-suggest-bar" role="status" aria-live="polite">
      <span className="ai-suggest-icon" aria-hidden="true">
        <Sparkles size={15} />
      </span>
      <span className="ai-suggest-label">AI</span>
      {loading ? (
        <span className="ai-suggest-text ai-suggest-loading">Finding best option for you…</span>
      ) : (
        <span className="ai-suggest-text">{suggestion}</span>
      )}
      {!loading && suggestion && (
        <button
          className="ai-suggest-dismiss"
          aria-label="Dismiss AI suggestion"
          onClick={() => setDismissed(true)}
        >
          <X size={13} />
        </button>
      )}
    </div>
  );
}
