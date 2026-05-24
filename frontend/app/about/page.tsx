'use client';

const PIPELINE_STEPS = [
    { num: '1', title: 'Ask a question', desc: 'Type any question about F1 regulations in natural language.' },
    { num: '2', title: 'Intent detection', desc: 'A local classifier (zero LLM calls) routes your query to the right pipeline.' },
    { num: '3', title: 'Search preparation', desc: 'One LLM call extracts year, section, and rewrites your query for retrieval.' },
    { num: '4', title: 'Hybrid retrieval', desc: 'Vector similarity + full-text search merged with Reciprocal Rank Fusion (RRF).' },
    { num: '5', title: 'Agentic reasoning', desc: 'Up to 3 search-reason loops until the LLM has enough context to answer.' },
    { num: '6', title: 'Answer with citations', desc: 'A grounded answer with exact article references you can verify.' },
];

const STACK = [
    { name: 'FastAPI', role: 'Backend' },
    { name: 'Next.js 14', role: 'Frontend' },
    { name: 'PostgreSQL + pgvector', role: 'Database' },
    { name: 'all-MiniLM-L6-v2', role: 'Embeddings' },
    { name: 'OpenRouter', role: 'LLM' },
    { name: 'Supabase', role: 'Hosting (DB)' },
    { name: 'Render', role: 'Hosting (API)' },
    { name: 'Vercel', role: 'Hosting (Web)' },
];

export default function AboutPage() {
    return (
        <div style={styles.page}>
            <div style={styles.container}>
                <div style={styles.header}>
                    <h1 style={styles.title}>How it works</h1>
                    <p style={styles.subtitle}>A RAG system for querying FIA Formula 1 regulations with natural language</p>
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
                    <div className="stack-grid" style={styles.stackGrid}>
                        {STACK.map(t => (
                            <div key={t.name} style={styles.stackCard}>
                                <span style={styles.stackName}>{t.name}</span>
                                <span style={styles.stackRole}>{t.role}</span>
                            </div>
                        ))}
                    </div>
                </section>

                <section style={styles.section}>
                    <h2 style={styles.sectionTitle}>Source</h2>
                    <p style={styles.sourceText}>
                        This project is open source.{' '}
                        <a href="https://github.com/alvaroherrera-33/f1-regulations-engine" target="_blank" rel="noopener noreferrer" style={styles.link}>
                            View on GitHub
                        </a>
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
    title: { fontSize: '1.4rem', fontWeight: 600, color: '#fff', letterSpacing: '-0.02em', marginBottom: '0.3rem' },
    subtitle: { fontSize: '0.85rem', color: '#666' },

    section: { marginBottom: '2.5rem' },
    sectionTitle: { fontSize: '0.72rem', color: '#666', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 500, marginBottom: '0.75rem' },

    steps: { display: 'flex', flexDirection: 'column', gap: '0.75rem' },
    step: { display: 'flex', gap: '0.75rem', alignItems: 'flex-start', padding: '0.75rem', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px' },
    stepNum: { color: '#eb0000', fontWeight: 700, fontSize: '0.82rem', flexShrink: 0, width: '1.5rem', textAlign: 'center', fontVariantNumeric: 'tabular-nums' },
    stepTitle: { fontSize: '0.9rem', color: '#ccc', fontWeight: 500, marginBottom: '0.2rem' },
    stepDesc: { fontSize: '0.82rem', color: '#666', lineHeight: 1.5 },

    stackGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.5rem' },
    stackCard: { display: 'flex', flexDirection: 'column', gap: '0.15rem', padding: '0.75rem', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px' },
    stackName: { fontSize: '0.85rem', color: '#ccc', fontWeight: 500 },
    stackRole: { fontSize: '0.72rem', color: '#666' },

    sourceText: { fontSize: '0.9rem', color: '#888', lineHeight: 1.6 },
    link: { color: '#eb0000', textDecoration: 'underline', textUnderlineOffset: '2px' },
};
