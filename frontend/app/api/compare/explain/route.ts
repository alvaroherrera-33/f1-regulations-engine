import { NextRequest, NextResponse } from 'next/server';

// C-02: Proxy to the backend instead of calling Supabase Edge Function directly.
// This eliminates the hardcoded Supabase project URL from the frontend bundle.
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const code    = searchParams.get('code')    ?? '';
    const year_a  = searchParams.get('year_a')  ?? '';
    const year_b  = searchParams.get('year_b')  ?? '';
    const section = searchParams.get('section');

    if (!code || !year_a || !year_b) {
        return NextResponse.json(
            { detail: 'Missing required params: code, year_a, year_b' },
            { status: 400 }
        );
    }

    let upstreamUrl = `${API_URL}/api/compare/explain?code=${encodeURIComponent(code)}&year_a=${year_a}&year_b=${year_b}`;
    if (section) upstreamUrl += `&section=${encodeURIComponent(section)}`;

    try {
        const res = await fetch(upstreamUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            cache: 'no-store',
        });
        const data = await res.json();
        return NextResponse.json(data, { status: res.status });
    } catch {
        return NextResponse.json(
            { detail: 'Upstream error' },
            { status: 502 }
        );
    }
}
