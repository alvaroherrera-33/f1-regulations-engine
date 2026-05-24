import { NextRequest, NextResponse } from 'next/server';

const SUPABASE_URL = 'https://nmftfbboxssonnvbjzef.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5tZnRmYmJveHNzb25udmJqemVmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgwNzQ5MDgsImV4cCI6MjA5MzY1MDkwOH0.EI7L8QhFUXvsSLr5EjAvauyvyw0a55txcxboM_HsyxQ';
const OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions';

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
        headers: { 'apikey': SUPABASE_ANON_KEY, 'Authorization': `Bearer ${SUPABASE_ANON_KEY}` },
        cache: 'no-store',
    });
    if (!res.ok) return null;
    const rows: ArticleVersion[] = await res.json();
    return rows[0] ?? null;
}

async function callLLM(code: string, vA: ArticleVersion | null, vB: ArticleVersion | null): Promise<string> {
    const apiKey = process.env.OPENROUTER_API_KEY;
    if (!apiKey) throw new Error('OPENROUTER_API_KEY not configured');

    const contentA = vA?.content ?? 'Not available';
    const contentB = vB?.content ?? 'Not available';
    const yearA = vA?.year ?? '?';
    const yearB = vB?.year ?? '?';
    const issueA = vA?.issue ?? '?';
    const issueB = vB?.issue ?? '?';

    const prompt = `You are an expert in FIA Formula 1 regulations. Compare these two versions of Article ${code}:

---VERSION A (${yearA}, Issue ${issueA})---
${contentA.slice(0, 2000)}

---VERSION B (${yearB}, Issue ${issueB})---
${contentB.slice(0, 2000)}

Provide a concise explanation (3-5 sentences) covering:
1. What specifically changed between the two versions
2. Whether the change is TECHNICAL (affects car design/performance) or EDITORIAL (clarification/wording)
3. The practical impact for F1 teams

Be specific and factual. If the content is identical or very similar, say so.`;

    const model = process.env.LLM_MODEL ?? 'openai/gpt-4o-mini';
    const res = await fetch(OPENROUTER_URL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiKey}`,
            'HTTP-Referer': 'https://f1-regulations-engine-project.vercel.app',
            'X-Title': 'F1 Regulations Engine',
        },
        body: JSON.stringify({
            model,
            messages: [{ role: 'user', content: prompt }],
            max_tokens: 400,
            temperature: 0.2,
        }),
    });
    if (!res.ok) {
        const err = await res.text();
        throw new Error(`LLM error ${res.status}: ${err.slice(0, 200)}`);
    }
    const data = await res.json();
    return data.choices[0].message.content.trim();
}

export async function POST(request: NextRequest) {
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

    try {
        const explanation = await callLLM(code, version_a, version_b);
        return NextResponse.json({
            article_code: code,
            year_a,
            year_b,
            section: section ?? null,
            version_a,
            version_b,
            explanation,
        });
    } catch (err) {
        return NextResponse.json(
            { detail: err instanceof Error ? err.message : 'LLM service error' },
            { status: 502 }
        );
    }
}
