'use client';

export default function AboutPage() {
    return (
        <main style={styles.main}>
            <div style={styles.hero}>
                <h1 style={styles.title}>How It Works</h1>
                <p style={styles.subtitle}>
                    A Retrieval-Augmented Generation (RAG) system that lets you query
                    FIA Formula 1 regulations using natural language and get precise
                    answers with article-level citations.
                </p>
            </div>

            {/* Architecture Diagram */}
            <section style={styles.section}>
                <h2 style={styles.sectionTitle}>Query Pipeline</h2>
                <div style={styles.diagramContainer}>
                    <svg viewBox="0 0 800 360" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', maxWidth: '800px' }}>
                        {/* Arrows */}
                        <defs>
                            <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                                <polygon points="0 0, 8 3, 0 6" fill="#eb0000" />
                            </marker>
                        </defs>

                        {/* Step 1: User Query */}
                        <rect x="20" y="30" width="160" height="60" rx="10" fill="#1a1a1a" stroke="#333" strokeWidth="1.5" />
                        <text x="100" y="55" textAnchor="middle" fill="#fff" fontSize="13" fontWeight="bold">User Query</text>
                        <text x="100" y="73" textAnchor="middle" fill="#888" fontSize="10">"What is the min weight?"</text>

                        {/* Arrow 1→2 */}
                        <line x1="180" y1="60" x2="230" y2="60" stroke="#eb0000" strokeWidth="2" markerEnd="url(#arrowhead)" />

                        {/* Step 2: Intent Detection */}
                        <rect x="240" y="30" width="140" height="60" rx="10" fill="#1a1a1a" stroke="#eb0000" strokeWidth="1.5" />
                        <text x="310" y="55" textAnchor="middle" fill="#eb0000" fontSize="11" fontWeight="bold">Intent Detection</text>
                        <text x="310" y="73" textAnchor="middle" fill="#888" fontSize="10">Local (no LLM)</text>

                        {/* Arrow 2→3 */}
                        <line x1="380" y1="60" x2="430" y2="60" stroke="#eb0000" strokeWidth="2" markerEnd="url(#arrowhead)" />

                        {/* Step 3: Prepare Search */}
                        <rect x="440" y="30" width="140" height="60" rx="10" fill="#1a1a1a" stroke="#334155" strokeWidth="1.5" />
                        <text x="510" y="55" textAnchor="middle" fill="#94a3b8" fontSize="11" fontWeight="bold">Prepare Search</text>
                        <text x="510" y="73" textAnchor="middle" fill="#888" fontSize="10">LLM: year + section</text>

                        {/* Arrow 3→4 */}
                        <line x1="580" y1="60" x2="630" y2="60" stroke="#eb0000" strokeWidth="2" markerEnd="url(#arrowhead)" />

                        {/* Step 4: Hybrid Search */}
                        <rect x="640" y="20" width="140" height="80" rx="10" fill="#1a1a1a" stroke="#333" strokeWidth="1.5" />
                        <text x="710" y="45" textAnchor="middle" fill="#fff" fontSize="11" fontWeight="bold">Hybrid Search</text>
                        <text x="710" y="63" textAnchor="middle" fill="#eb0000" fontSize="10">Vector + FTS</text>
                        <text x="710" y="80" textAnchor="middle" fill="#888" fontSize="10">RRF Merge (k=60)</text>

                        {/* Arrow down from Hybrid Search */}
                        <line x1="710" y1="100" x2="710" y2="140" stroke="#eb0000" strokeWidth="2" markerEnd="url(#arrowhead)" />

                        {/* Step 5: Agentic Loop */}
                        <rect x="600" y="150" width="180" height="70" rx="10" fill="#1a1a1a" stroke="#eb0000" strokeWidth="2" strokeDasharray="6 3" />
                        <text x="690" y="175" textAnchor="middle" fill="#eb0000" fontSize="12" fontWeight="bold">Agentic Loop</text>
                        <text x="690" y="195" textAnchor="middle" fill="#888" fontSize="10">LLM decides: SEARCH or ANSWER</text>
                        <text x="690" y="210" textAnchor="middle" fill="#666" fontSize="9">Max 3 steps</text>

                        {/* Loop arrow */}
                        <path d="M 780 185 Q 800 185 800 100 Q 800 60 780 60" fill="none" stroke="#444" strokeWidth="1.5" strokeDasharray="4 3" markerEnd="url(#arrowhead)" />
                        <text x="795" y="130" textAnchor="middle" fill="#666" fontSize="9" transform="rotate(90, 795, 130)">retry</text>

                        {/* Arrow down from Agentic */}
                        <line x1="690" y1="220" x2="690" y2="260" stroke="#eb0000" strokeWidth="2" markerEnd="url(#arrowhead)" />

                        {/* Step 6: Response */}
                        <rect x="560" y="270" width="260" height="60" rx="10" fill="#1a1a1a" stroke="#22c55e" strokeWidth="1.5" />
                        <text x="690" y="295" textAnchor="middle" fill="#22c55e" fontSize="12" fontWeight="bold">Answer + Citations</text>
                        <text x="690" y="313" textAnchor="middle" fill="#888" fontSize="10">Article codes, content, confidence</text>

                        {/* Database */}
                        <ellipse cx="400" cy="280" rx="90" ry="35" fill="#0d0d0d" stroke="#334155" strokeWidth="1.5" />
                        <text x="400" y="276" textAnchor="middle" fill="#94a3b8" fontSize="11" fontWeight="bold">PostgreSQL</text>
                        <text x="400" y="293" textAnchor="middle" fill="#666" fontSize="10">pgvector + tsvector</text>

                        {/* Arrow DB→Hybrid */}
                        <path d="M 460 255 Q 550 200 640 180" fill="none" stroke="#334155" strokeWidth="1.5" strokeDasharray="4 2" markerEnd="url(#arrowhead)" />

                        {/* Embeddings label */}
                        <rect x="20" y="260" width="150" height="70" rx="10" fill="#0d0d0d" stroke="#333" strokeWidth="1" />
                        <text x="95" y="285" textAnchor="middle" fill="#888" fontSize="10" fontWeight="bold">all-MiniLM-L6-v2</text>
                        <text x="95" y="302" textAnchor="middle" fill="#666" fontSize="9">384-dim local embeddings</text>
                        <text x="95" y="317" textAnchor="middle" fill="#666" fontSize="9">Chunked (800 char overlap)</text>

                        {/* Arrow Embed→DB */}
                        <line x1="170" y1="290" x2="310" y2="280" stroke="#444" strokeWidth="1" strokeDasharray="3 2" />

                        {/* Legend */}
                        <rect x="20" y="155" width="10" height="10" rx="2" fill="transparent" stroke="#eb0000" strokeWidth="2" />
                        <text x="38" y="164" fill="#888" fontSize="9">LLM call</text>
                        <rect x="20" y="175" width="10" height="10" rx="2" fill="transparent" stroke="#333" strokeWidth="1.5" />
                        <text x="38" y="184" fill="#888" fontSize="9">Local / DB</text>
                    </svg>
                </div>
            </section>

            {/* How RAG Works */}
            <section style={styles.section}>
                <h2 style={styles.sectionTitle}>What is RAG?</h2>
                <p style={styles.text}>
                    Retrieval-Augmented Generation combines a search engine with a large language model.
                    Instead of relying solely on the LLM's training data (which may be outdated or imprecise),
                    the system first retrieves the most relevant regulation articles from the database,
                    then feeds them as context to the LLM. This means every answer is grounded in the
                    actual FIA documents, with exact article citations.
                </p>
            </section>

            {/* Hybrid Search */}
            <section style={styles.section}>
                <h2 style={styles.sectionTitle}>Hybrid Search + RRF</h2>
                <p style={styles.text}>
                    The retrieval layer runs two parallel searches: a semantic vector search (pgvector cosine
                    similarity) that understands meaning, and a keyword full-text search (PostgreSQL tsvector)
                    that catches exact terminology. Results are merged using Reciprocal Rank Fusion (RRF, k=60),
                    a parameter-free algorithm that combines ranked lists without needing score calibration.
                    Articles are deduplicated to always return the latest issue of each regulation.
                </p>
            </section>

            {/* Tech Stack */}
            <section style={styles.section}>
                <h2 style={styles.sectionTitle}>Tech Stack</h2>
                <div style={styles.stackGrid}>
                    {[
                        { label: 'Backend', tech: 'FastAPI (Python)', detail: 'Async, uvicorn' },
                        { label: 'Frontend', tech: 'Next.js 14', detail: 'App Router, TypeScript' },
                        { label: 'Database', tech: 'PostgreSQL + pgvector', detail: 'Supabase, 384-dim vectors' },
                        { label: 'Embeddings', tech: 'all-MiniLM-L6-v2', detail: 'Local, no external API' },
                        { label: 'LLM', tech: 'OpenRouter API', detail: 'Configurable model' },
                        { label: 'Deploy', tech: 'Render + Vercel', detail: 'Free tier, auto-deploy' },
                    ].map(({ label, tech, detail }) => (
                        <div key={label} style={styles.stackItem}>
                            <span style={styles.stackLabel}>{label}</span>
                            <span style={styles.stackTech}>{tech}</span>
                            <span style={styles.stackDetail}>{detail}</span>
                        </div>
                    ))}
                </div>
            </section>

            {/* Source */}
            <section style={{ ...styles.section, textAlign: 'center' }}>
                <a
                    href="https://github.com/alvaroherrera-33/f1-regulations-engine"
                    target="_blank"
                    rel="noopener noreferrer"
                    style={styles.githubLink}
                >
                    View Source on GitHub →
                </a>
            </section>
        </main>
    );
}

const styles: Record<string, React.CSSProperties> = {
    main: { padding: '2rem', maxWidth: '900px', margin: '0 auto', minHeight: 'calc(100vh - 60px)' },
    hero: { textAlign: 'center', marginBottom: '3rem' },
    title: { fontSize: '2.5rem', fontWeight: '900', marginBottom: '1rem', letterSpacing: '-0.02em' },
    subtitle: { fontSize: '1.1rem', opacity: 0.7, maxWidth: '650px', margin: '0 auto', lineHeight: '1.6' },
    section: { marginBottom: '3rem' },
    sectionTitle: { fontSize: '1.4rem', fontWeight: '800', marginBottom: '1rem', color: '#fff', letterSpacing: '-0.01em' },
    text: { fontSize: '0.95rem', lineHeight: '1.7', color: '#aaa' },
    diagramContainer: { background: '#0a0a0a', border: '1px solid #222', borderRadius: '16px', padding: '2rem', display: 'flex', justifyContent: 'center', overflow: 'auto' },
    stackGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' },
    stackItem: { background: '#111', border: '1px solid #222', borderRadius: '12px', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' },
    stackLabel: { fontSize: '0.7rem', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#eb0000' },
    stackTech: { fontSize: '1rem', fontWeight: '700', color: '#fff' },
    stackDetail: { fontSize: '0.82rem', color: '#666' },
    githubLink: { display: 'inline-block', color: '#eb0000', fontSize: '1rem', fontWeight: '600', textDecoration: 'none', padding: '0.75rem 2rem', border: '1px solid #eb0000', borderRadius: '8px' },
};
