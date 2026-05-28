import { NextResponse } from 'next/server';

// C-02: Proxy to the backend instead of calling Supabase REST directly.
// This eliminates the hardcoded SUPABASE_ANON_KEY from the frontend bundle.
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function GET() {
    try {
        const res = await fetch(`${API_URL}/status`, { cache: 'no-store' });
        if (!res.ok) return NextResponse.json({ documents_count: 0, articles_count: 0, embeddings_count: 0 });
        const data = await res.json();
        return NextResponse.json(data);
    } catch {
        return NextResponse.json({ documents_count: 0, articles_count: 0, embeddings_count: 0 });
    }
}
