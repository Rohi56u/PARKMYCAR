export const dynamic = 'force-dynamic';

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

  const apiKey =
    process.env.GEMINI_API_KEY || process.env.NEXT_PUBLIC_GEMINI_API_KEY;

  if (!apiKey) {
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
      : 'price unknown';
    const status = r.evidence.state === 'AVAILABLE' ? 'reported available'
      : r.evidence.state === 'FULL' ? 'reported full'
      : r.evidence.state === 'LIMITED' ? 'limited spaces'
      : 'availability unknown';
    return `Option ${i + 1}: ${r.name} — ${r.type.replace('_', ' ')} parking, ${dist} away, ${price}, ${status}, hours: ${r.hoursState}`;
  }).join('\n');

  const vehicleLabel = vehicle === 'TWO_WHEELER' ? 'two-wheeler' : 'car';
  const stayLabel = durationMinutes >= 60
    ? `${Math.floor(durationMinutes / 60)}h${durationMinutes % 60 ? ` ${durationMinutes % 60}m` : ''}`
    : `${durationMinutes} minutes`;

  const prompt = `You are a smart parking assistant for Indian cities. A driver is heading to "${destinationName}" with a ${vehicleLabel} and plans to stay for ${stayLabel}.

Here are the top parking options nearby:
${top3}

Give a SHORT, helpful recommendation (2-3 sentences max). Be direct — tell them which option and why. If availability is unknown, mention that they should verify on arrival. Use plain language, no bullet points, no markdown. Focus on the most useful action they can take right now.`;

  try {
    const geminiRes = await fetch(`${GEMINI_API_URL}?key=${apiKey}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: {
          maxOutputTokens: 150,
          temperature: 0.4,
          topP: 0.9,
        },
        safetySettings: [
          { category: 'HARM_CATEGORY_HARASSMENT', threshold: 'BLOCK_MEDIUM_AND_ABOVE' },
          { category: 'HARM_CATEGORY_HATE_SPEECH', threshold: 'BLOCK_MEDIUM_AND_ABOVE' },
        ],
      }),
    });

    if (!geminiRes.ok) {
      return new Response(
        JSON.stringify({ suggestion: null, reason: 'AI_ERROR' }),
        { status: 200, headers }
      );
    }

    const data = await geminiRes.json() as {
      candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }>;
    };

    const text = data.candidates?.[0]?.content?.parts?.[0]?.text?.trim();

    if (!text) {
      return new Response(
        JSON.stringify({ suggestion: null, reason: 'AI_EMPTY' }),
        { status: 200, headers }
      );
    }

    return new Response(
      JSON.stringify({ suggestion: text }),
      { status: 200, headers }
    );
  } catch {
    return new Response(
      JSON.stringify({ suggestion: null, reason: 'AI_NETWORK_ERROR' }),
      { status: 200, headers }
    );
  }
}
