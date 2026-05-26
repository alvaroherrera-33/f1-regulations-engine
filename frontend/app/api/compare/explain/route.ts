import { NextRequest, NextResponse } from 'next/server';

// Proxies to Supabase Edge Function — no backend env vars needed
const EDGE_FN_URL = 'https://nmftfbboxssonnvbjzef.supabase.co/functions/v1/compare-explain';

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

    let upstreamUrl = `${EDGE_FN_URL}?code=${encodeURIComponent(code)}&year_a=${year_a}&year_b=${year_b}`;
    if (section) upstreamUrl += `&section=${encodeURIComponent(section)}`;

    try {
        const res = await fetch(upstreamUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        const data = await res.json();
        return NextResponse.json(data, { status: res.status });
    } catch (err) {
        return NextResponse.json(
            { detail: err instanceof Error ? err.message : 'Upstream error' },
            { status: 502 }
        );
    }
}
