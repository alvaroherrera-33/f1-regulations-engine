'use client';

import Link from 'next/link';

const FEATURES = [
    {
        title: 'Instant answers with citations',
        desc: 'Every response is grounded in the official FIA regulation text, with exact article codes you can verify.',
    },
    {
        title: 'Compare across years',
        desc: 'Query 2023 through 2026 side by side. The engine flags articles that have changed, been added, or removed.',
    },
    {
        title: '16,000+ articles indexed',
        desc: 'Full coverage of Technical, Sporting, and Financial regulations across four seasons.',
    },
];

const COVERAGE = [
    { type: 'Technical', y2023: true, y2024: true, y2025: true, y2026: true },
    { type: 'Sporting',  y2023: true, y2024: true, y2025: true, y2026: true },
    { type: 'Financial', y2023: true, y2024: true, y2025: true, y2026: true },
];

const EXAMPLE = {
    question: 'What is the minimum car weight in 2026?',
    answer: 'According to [Article 4.1] of the 2026 Technical Regulations (Issue 3), the minimum weight of the car, inclusive of the driver and all fluids, is 800 kg. This represents a 2 kg reduction from the 2025 limit of 802 kg as specified in [Article 4.1] of the 2025 Technical Regulations.',
    citations: ['Article 4.1 — Weight (Technical Regulations 2026, Issue 3)', 'Article 4.1 — Weight (Technical Regulations 2025, Issue 2)'],
};

export default function Home() {
    return (
        <main style={styles.main}>

            {/* Hero */}
            <section style={styles.hero}>
                <p style={styles.tagline}>Formula 1 Regulation Search</p>
                <h1 style={styles.title}>
                    Search F1 regulations with<br />
                    <span style={styles.accent}>AI-powered precision</span>
                </h1>
                <p style={styles.subtitle}>
                    Ask anything in plain language. Get exact answers backed by official FIA article citations — no guessing, no hallucinations.
                </p>
                <div style={styles.cta}>
                    <Link href="/chat" style={styles.primaryBtn}>
                        Start searching
                        <span style={styles.arrow}>&rarr;</span>
                    </Link>
                </div>
            </section>

            {/* Features */}
            <section style={styles.section}>
                <div style={styles.features}>
                    {FEATURES.map(f => (
                        <div key={f.title} style={styles.featureCard}>
                            <h3 style={styles.featureTitle}>{f.title}</h3>
                            <p style={styles.featureDesc}>{f.desc}</p>
                        </div>
                    ))}
                </div>
            </section>

            {/* Coverage */}
            <section style={styles.section}>
                <h2 style={styles.sectionTitle}>Regulation coverage</h2>
                <table style={styles.table}>
                    <thead>
                        <tr>
                            <th style={styles.th}>Regulation type</th>
                            <th style={styles.th}>2023</th>
                            <th style={styles.th}>2024</th>
                            <th style={styles.th}>2025</th>
                            <th style={styles.th}>2026</th>
                        </tr>
                    </thead>
                    <tbody>
                        {COVERAGE.map(row => (
                            <tr key={row.type}>
                                <td style={styles.td}>{row.type}</td>
                                {[row.y2023, row.y2024, row.y2025, row.y2026].map((v, i) => (
                                    <td key={i} style={{ ...styles.td, ...styles.tdCenter }}>
                                        {v ? <span style={styles.check}>&#10003;</span> : <span style={styles.cross}>&#8212;</span>}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </section>

            {/* Example Q&A */}
            <section style={styles.section}>
                <h2 style={styles.sectionTitle}>Example</h2>
                <div style={styles.example}>
                    <div style={styles.exQuestion}>
                        <span style={styles.exLabel}>Question</span>
                        <p style={styles.exText}>{EXAMPLE.question}</p>
                    </div>
                    <div style={styles.exAnswer}>
                        <span style={styles.exLabel}>Answer</span>
                        <p style={styles.exText}>{EXAMPLE.answer}</p>
                        <div style={styles.exCitations}>
                            {EXAMPLE.citations.map(c => (
                                <span key={c} style={styles.citationTag}>{c}</span>
                            ))}
                        </div>
                    </div>
                </div>
            </section>

            {/* Footer */}
            <footer style={styles.footer}>
                <span>Built by&nbsp;
                    <a href="https://github.com/alvaroherrera-33" target="_blank" rel="noopener noreferrer" style={styles.footerLink}>
                        Alvaro Herrera
                    </a>
                </span>
                <span style={styles.footerDot}>&middot;</span>
                <a href="https://github.com/alvaroherrera-33/f1-regulations-engine" target="_blank" rel="noopener noreferrer" style={styles.footerLink}>
                    GitHub
                </a>
                <span style={styles.footerDot}>&middot;</span>
                <span>Data: FIA official regulations</span>
            </footer>
        </main>
    );
}

const styles: Record<string, React.CSSProperties> = {
    main: {
        maxWidth: '760px',
        margin: '0 auto',
        padding: '4rem 1.5rem 3rem',
    },

    // Hero
    hero: { textAlign: 'center', marginBottom: '4rem' },
    tagline: {
        fontSize: '0.72rem',
        color: '#eb0000',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.12em',
        marginBottom: '1.25rem',
    },
    title: {
        fontSize: 'clamp(1.9rem, 4.5vw, 3rem)',
        fontWeight: 700,
        lineHeight: 1.15,
        color: '#fff',
        letterSpacing: '-0.03em',
        marginBottom: '1.25rem',
    },
    accent: { color: '#eb0000' },
    subtitle: {
        fontSize: '1rem',
        color: '#888',
        lineHeight: 1.65,
        maxWidth: '560px',
        margin: '0 auto 2.5rem',
    },
    cta: { display: 'flex', justifyContent: 'center' },
    primaryBtn: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.5rem',
        background: '#fff',
        color: '#000',
        padding: '0.75rem 1.75rem',
        borderRadius: '8px',
        fontSize: '0.92rem',
        fontWeight: 600,
        textDecoration: 'none',
    },
    arrow: { fontSize: '1rem' },

    // Sections
    section: { marginBottom: '3.5rem' },
    sectionTitle: {
        fontSize: '0.72rem',
        color: '#555',
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        fontWeight: 600,
        marginBottom: '1.25rem',
    },

    // Features
    features: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '1rem',
    },
    featureCard: {
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: '10px',
        padding: '1.25rem',
    },
    featureTitle: {
        fontSize: '0.88rem',
        fontWeight: 600,
        color: '#e0e0e0',
        marginBottom: '0.5rem',
        letterSpacing: '-0.01em',
    },
    featureDesc: { fontSize: '0.82rem', color: '#666', lineHeight: 1.55 },

    // Coverage table
    table: {
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: '0.85rem',
    },
    th: {
        textAlign: 'left',
        color: '#555',
        fontWeight: 500,
        fontSize: '0.75rem',
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        padding: '0.5rem 0.75rem',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
    },
    td: {
        padding: '0.6rem 0.75rem',
        color: '#aaa',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
    },
    tdCenter: { textAlign: 'center' },
    check: { color: '#22c55e', fontWeight: 700 },
    cross: { color: '#444' },

    // Example Q&A
    example: {
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: '10px',
        overflow: 'hidden',
    },
    exQuestion: {
        padding: '1.25rem',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(255,255,255,0.02)',
    },
    exAnswer: { padding: '1.25rem' },
    exLabel: {
        display: 'block',
        fontSize: '0.68rem',
        color: '#555',
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        fontWeight: 600,
        marginBottom: '0.5rem',
    },
    exText: { fontSize: '0.88rem', color: '#ccc', lineHeight: 1.65, margin: 0 },
    exCitations: { display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.85rem' },
    citationTag: {
        fontSize: '0.72rem',
        color: '#777',
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '4px',
        padding: '0.2rem 0.5rem',
    },

    // Footer
    footer: {
        display: 'flex',
        gap: '0.5rem',
        justifyContent: 'center',
        alignItems: 'center',
        fontSize: '0.78rem',
        color: '#555',
        paddingTop: '2rem',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        flexWrap: 'wrap',
    },
    footerLink: { color: '#777', textDecoration: 'none' },
    footerDot: { color: '#333' },
};
