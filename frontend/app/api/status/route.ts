import { NextResponse } from 'next/server';

const SUPABASE_URL = 'https://nmftfbboxssonnvbjzef.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5tZnRmYmJveHNzb25udmJqemVmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgwNzQ5MDgsImV4cCI6MjA5MzY1MDkwOH0.EI7L8QhFUXvsSLr5EjAvauyvyw0a55txcxboM_HsyxQ';

async function getCount(table: string): Promise<number> {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}?select=id&limit=1`, {
        headers: {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
            'Prefer': 'count=exact',
        },
        cache: 'no-store',
    });
    if (!res.ok) return 0;
    const range = res.headers.get('content-range');
    if (!range) return 0;
    const match = range.match(/\/(\d+)$/);
    return match ? parseInt(match[1], 10) : 0;
}

export async function GET() {
    const [documents_count, articles_count, embeddings_count] = await Promise.all([
        getCount('documents'),
        getCount('articles'),
        getCount('article_embeddings'),
    ]);
    return NextResponse.json({ documents_count, articles_count, embeddings_count });
}
