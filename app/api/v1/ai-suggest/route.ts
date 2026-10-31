export const dynamic = 'force-dynamic';

const GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions';
const GEMINI_API_URL =
  'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent';

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

export async function POST(request: Request): Promise<Response> {
  const headers = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  };

  const groqApiKey =
    process.env.GROQ_API_KEY || process.env.NEXT_PUBLIC_GROQ_API_KEY;
  const geminiApiKey =
    process.env.GEMINI_API_KEY || process.env.NEXT_PUBLIC_GEMINI_API_KEY;

  if (!groqApiKey && !geminiApiKey) {
    return new Response(
      JSON.stringify({ suggestion: null, reason: 'AI_NOT_CONFIGURED' }),
      { status: 200, headers }
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify({ error: { code: 'INVALID_JSON', message: 'Send JSON data.' } }),
      { status: 400, headers }
    );
  }

  const { results, destinationName, vehicle, durationMinutes } = body as {
    results: SearchResult[];
    destinationName: string;
    vehicle: string;
    durationMinutes: number;
  };

  if (!results?.length || !destinationName) {
    return new Response(
      JSON.stringify({ suggestion: null, reason: 'NO_RESULTS' }),
      { status: 200, headers }
    );
  }

  const top3 = results.slice(0, 3).map((r, i) => {
    const dist = r.distanceMeters < 1000
      ? `${Math.round(r.distanceMeters / 10) * 10}m`
      : `${(r.distanceMeters / 1000).toFixed(1)}km`;
    const price = r.rate
      ? `₹${r.rate.amount}/${r.rate.unit === 'PER_HOUR' ? 'hr' : r.rate.unit === 'PER_ENTRY' ? 'entry' : 'day'}`
      : 'tariff unlisted';
    const status = r.evidence.state === 'AVAILABLE' ? 'reported space available'
      : r.evidence.state === 'FULL' ? 'reported full'
      : r.evidence.state === 'LIMITED' ? 'limited space'
      : 'live status not confirmed';
    return `Option ${i + 1}: ${r.name} — ${r.type.replace('_', ' ')} parking, ${dist} away, ${price}, ${status}, ${r.hoursState === 'open' ? 'currently open' : 'hours unlisted'}`;
  }).join('\n');

  const vehicleLabel = vehicle === 'TWO_WHEELER' ? 'two-wheeler' : 'car';
  const stayLabel = durationMinutes >= 60
    ? `${Math.floor(durationMinutes / 60)}h${durationMinutes % 60 ? ` ${durationMinutes % 60}m` : ''}`
    : `${durationMinutes} minutes`;

  const prompt = `You are a smart arrival-first parking intelligence assistant for Indian urban mobility. A driver is heading to "${destinationName}" with a ${vehicleLabel} planning a ${stayLabel} stay.

Top parking options nearby:
${top3}

Provide a direct, authoritative 1-2 sentence recommendation on which option to pick and why (weighing pedestrian walk distance, facility shelter/security, and verified availability). Do NOT use bullet points, markdown bolding, or generic greetings. Keep it natural and concise.`;

  // 1. Try Groq first if key is present
  if (groqApiKey) {
    try {
      const groqRes = await fetch(GROQ_API_URL, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${groqApiKey}`,
          'Content-Type': 'application/json',
          'User-Agent': 'ParkMyCar/1.1'
        },
        body: JSON.stringify({
          model: 'qwen/qwen3.8-27b',
          messages: [
            {
              role: 'system',
              content: 'You are a decisive parking intelligence assistant for Indian cities. Give a concise, actionable 1-2 sentence recommendation.'
            },
            {
              role: 'user',
              content: prompt
            }
          ],
          max_tokens: 110,
          temperature: 0.3
        })
      });

      if (groqRes.ok) {
        const groqData = await groqRes.json() as {
          choices?: Array<{ message?: { content?: string } }>;
        };
        const text = groqData.choices?.[0]?.message?.content?.trim();
        if (text) {
          return new Response(
            JSON.stringify({ suggestion: text, engine: 'ai' }),
            { status: 200, headers }
          );
        }
      }
    } catch {
      // Fall through to Gemini fallback
    }
  }

  // 2. Gemini fallback
  if (geminiApiKey) {
    try {
      const geminiRes = await fetch(`${GEMINI_API_URL}?key=${geminiApiKey}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: {
            maxOutputTokens: 120,
            temperature: 0.3,
            topP: 0.9,
          },
        }),
      });

      if (geminiRes.ok) {
        const data = await geminiRes.json() as {
          candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }>;
        };
        const text = data.candidates?.[0]?.content?.parts?.[0]?.text?.trim();
        if (text) {
          return new Response(
            JSON.stringify({ suggestion: text, engine: 'ai' }),
            { status: 200, headers }
          );
        }
      }
    } catch {
      // Fall through
    }
  }

  return new Response(
    JSON.stringify({ suggestion: null, reason: 'AI_UNAVAILABLE' }),
    { status: 200, headers }
  );
}
