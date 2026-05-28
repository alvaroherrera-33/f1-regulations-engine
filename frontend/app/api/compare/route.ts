import { NextRequest, NextResponse } from 'next/server';

// C-02: Call the backend instead of Supabase REST directly.
// This eliminates the hardcoded SUPABASE_ANON_KEY from the frontend bundle.
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ArticleVersion {
    article_code: string;
    title: string;
    content: string;
    year: number;
    section: string;
    issue: number;
}

async function fetchVersion(code: string, year: number, section?: string): Promise<ArticleVersion | null> {
    let url = `${API_URL}/api/articles?article_code=${encodeURIComponent(code)}&year=${year}&limit=1`;
    if (section) url += `&section=${encodeURIComponent(section)}`;
    try {
        const res = await fetch(url, { cache: 'no-store' });
        if (!res.ok) return null;
        const rows: ArticleVersion[] = await res.json();
        return rows[0] ?? null;
    } catch {
        return null;
    }
}

export async function GET(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const code    = searchParams.get('code')    ?? '';
    const year_a  = parseInt(searchParams.get('year_a') ?? '0', 10);
    const year_b  = parseInt(searchParams.get('year_b') ?? '0', 10);
    const section = searchParams.get('section') ?? undefined;

    if (!code || !year_a || !year_b) {
        return NextResponse.json({ detail: 'Missing required params: code, year_a, year_b' }, { status: 400 });
    }

    const [version_a, version_b] = await Promise.all([
        fetchVersion(code, year_a, section),
        fetchVersion(code, year_b, section),
    ]);

    if (!version_a && !version_b) {
        return NextResponse.json(
            { detail: `Article '${code}' not found for ${year_a} or ${year_b}.` },
            { status: 404 }
        );
    }

    return NextResponse.json({ version_a, version_b });
}
