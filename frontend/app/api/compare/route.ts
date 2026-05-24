import { NextRequest, NextResponse } from 'next/server';

const SUPABASE_URL = 'https://nmftfbboxssonnvbjzef.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5tZnRmYmJveHNzb25udmJqemVmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgwNzQ5MDgsImV4cCI6MjA5MzY1MDkwOH0.EI7L8QhFUXvsSLr5EjAvauyvyw0a55txcxboM_HsyxQ';

interface ArticleVersion {
    article_code: string;
    title: string;
    content: string;
    year: number;
    section: string;
    issue: number;
}

async function fetchVersion(code: string, year: number, section?: string): Promise<ArticleVersion | null> {
    let url = `${SUPABASE_URL}/rest/v1/articles?article_code=eq.${encodeURIComponent(code)}&year=eq.${year}&select=article_code,title,content,year,section,issue&order=issue.desc&limit=1`;
    if (section) url += `&section=eq.${encodeURIComponent(section)}`;
    const res = await fetch(url, {
        headers: {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
        },
        cache: 'no-store',
    });
    if (!res.ok) return null;
    const rows: ArticleVersion[] = await res.json();
    return rows[0] ?? null;
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
