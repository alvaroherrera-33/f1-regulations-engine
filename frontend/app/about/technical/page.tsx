'use client';

import Link from 'next/link';

const PIPELINE_STEPS = [
    { num: '1', title: 'Ask a question', desc: 'Type any question about F1 regulations in natural language.' },
    { num: '2', title: 'Intent detection', desc: 'A local classifier (zero LLM calls) routes your query to the regulations pipeline or returns a direct conversational response.' },
    { num: '3', title: 'Search preparation', desc: 'One LLM call extracts the year, section, and rewrites your query using precise FIA regulatory terminology.' },
    { num: '4', title: 'Hybrid retrieval', desc: 'Vector similarity (pgvector cosine distance) and full-text search (PostgreSQL tsvector) are merged with Reciprocal Rank Fusion (RRF). Duplicates are resolved to the latest issue.' },
    { num: '5', title: 'Agentic reasoning', desc: 'Up to three search-reason cycles: the LLM decides whether to perform another search (to resolve cross-references) or to commit to an answer.' },
    { num: '6', title: 'Answer with citations', desc: 'A grounded answer is returned with exact article codes, section, year, and issue number. Only cited articles appear as citation cards.' },
];

const STACK = [
    { name: 'FastAPI', role: 'Backend', note: 'Python 3.11, async, uvicorn' },
    { name: 'Next.js 14', role: 'Frontend', note: 'TypeScript, App Router' },
    { name: 'PostgreSQL + pgvector', role: 'Database', note: '384-dim vectors, hybrid search' },
    { name: 'all-MiniLM-L6-v2', role: 'Embeddings', note: 'Runs locally on backend' },
    { name: 'OpenRouter', role: 'LLM', note: 'Configurable model' },
    { name: 'Supabase', role: 'DB hosting', note: 'Session Pooler for IPv4' },
    { name: 'Render', role: 'API hosting', note: 'Free tier' },
    { name: 'Vercel', role: 'Web hosting', note: 'Hobby plan' },
];

export default function TechnicalPage() {
    return (
        <div style={styles.page}>
            <div style={styles.container}>

                <div style={styles.header}>
                    <Link href="/about" style={styles.back}>&larr; About</Link>
                    <h1 style={styles.title}>How it works</h1>
                    <p style={styles.subtitle}>
                        A RAG (Retrieval-Augmented Generation) system for querying FIA Formula 1 regulations with natural language.
                    </p>
                </div>

                <section style={styles.section}>
                    <h2 style={styles.sectionTitle}>Pipeline</h2>
                    <div style={styles.steps}>
                        {PIPELINE_STEPS.map(s => (
                            <div key={s.num} style={styles.step}>
                                <span style={styles.stepNum}>{s.num}</span>
                                <div>
                                    <h3 style={styles.stepTitle}>{s.title}</h3>
                                    <p style={styles.stepDesc}>{s.desc}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </section>

                <section style={styles.section}>
                    <h2 style={styles.sectionTitle}>Tech stack</h2>
                    <div style={styles.stackGrid}>
                        {STACK.map(t => (
                            <div key={t.name} style={styles.stackCard}>
                                <span style={styles.stackName}>{t.name}</span>
                                <span style={styles.stackRole}>{t.role}</span>
                                <span style={styles.stackNote}>{t.note}</span>
                            </div>
                        ))}
                    </div>
                </section>

                <section style={styles.section}>
                    <h2 style={styles.sectionTitle}>Source code</h2>
                    <p style={styles.body}>
                        The full source is available on{' '}
                        <a
                            href="https://github.com/alvaroherrera-33/f1-regulations-engine"
                            target="_blank"
                            rel="noopener noreferrer"
                            style={styles.link}
                        >
                            GitHub
                        </a>
                        , including the ingestion pipeline, hybrid retriever, and prompt engineering.
                    </p>
                </section>

            </div>
        </div>
    );
}

const styles: Record<string, React.CSSProperties> = {
    page: { minHeight: 'calc(100vh - 52px)', padding: '2rem 1rem' },
    container: { maxWidth: '720px', margin: '0 auto' },

    header: { marginBottom: '2.5rem' },
    back: { display: 'inline-block', fontSize: '0.78rem', color: '#555', textDecoration: 'none', marginBottom: '1rem' },
    title: { fontSize: '1.4rem', fontWeight: 600, color: '#fff', letterSpacing: '-0.02em', marginBottom: '0.4rem' },
    subtitle: { fontSize: '0.88rem', color: '#666', lineHeight: 1.6 },

    section: { marginBottom: '2.5rem' },
    sectionTitle: {
        fontSize: '0.72rem',
        color: '#555',
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        fontWeight: 600,
        marginBottom: '0.85rem',
    },
    body: { fontSize: '0.88rem', color: '#999', lineHeight: 1.7, marginBottom: '0.75rem' },

    steps: { display: 'flex', flexDirection: 'column', gap: '0.65rem' },
    step: {
        display: 'flex',
        gap: '0.85rem',
        alignItems: 'flex-start',
        padding: '0.85rem',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: '8px',
    },
    stepNum: {
        color: '#eb0000',
        fontWeight: 700,
        fontSize: '0.82rem',
        flexShrink: 0,
        width: '1.5rem',
        textAlign: 'center',
        fontVariantNumeric: 'tabular-nums',
        paddingTop: '0.1rem',
    },
    stepTitle: { fontSize: '0.88rem', color: '#ccc', fontWeight: 500, marginBottom: '0.2rem' },
    stepDesc: { fontSize: '0.82rem', color: '#666', lineHeight: 1.55 },

    stackGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.5rem' },
    stackCard: {
        display: 'flex',
        flexDirection: 'column',
        gap: '0.1rem',
        padding: '0.75rem',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: '8px',
    },
    stackName: { fontSize: '0.85rem', color: '#ccc', fontWeight: 500 },
    stackRole: { fontSize: '0.72rem', color: '#666' },
    stackNote: { fontSize: '0.72rem', color: '#444' },

    link: { color: '#eb0000', textDecoration: 'underline', textUnderlineOffset: '2px' },
};
