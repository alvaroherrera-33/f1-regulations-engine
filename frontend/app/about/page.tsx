'use client';

import Link from 'next/link';

const COVERAGE_ROWS = [
    { type: 'Technical Regulations', desc: 'Car design, dimensions, aerodynamics, power unit, tyres, chassis, safety structures.' },
    { type: 'Sporting Regulations', desc: 'Race procedures, qualifying, points, penalties, pit stops, safety car, flags.' },
    { type: 'Financial Regulations', desc: 'Cost cap, budget limits, spending categories, auditing, reporting.' },
];

const YEARS = ['2023', '2024', '2025', '2026'];

const LIMITATIONS = [
    'The engine does not have access to race stewards decisions, technical directives, or FIA bulletins — only the core regulation PDFs.',
    'Answers are limited to what has been indexed. Very recent issues published after the last ingestion run may not appear.',
    'The system answers based on the text of the regulations. It does not interpret intent or precedent.',
    'For legally binding matters, always consult the official FIA documentation directly.',
];

export default function AboutPage() {
    return (
        <div style={styles.page}>
            <div style={styles.container}>

                <div style={styles.header}>
                    <h1 style={styles.title}>About F1 Regulations Engine</h1>
                    <p style={styles.subtitle}>
                        An AI-powered tool for searching official FIA Formula 1 regulations in plain language.
                    </p>
                </div>

                <section style={styles.section}>
                    <h2 style={styles.sectionTitle}>What it does</h2>
                    <p style={styles.body}>
                        F1 Regulations Engine lets you ask questions about the Formula 1 Technical, Sporting, and Financial
                        Regulations and receive precise answers grounded in the official FIA documents. Each answer
                        includes exact article citations so you can verify the source directly.
                    </p>
                    <p style={styles.body}>
                        The tool supports questions in English, Spanish, French, German, and Italian. Filters for year,
                        regulation type, and issue number are available when you need to narrow the scope of a search.
                    </p>
                </section>

                <section style={styles.section}>
                    <h2 style={styles.sectionTitle}>Regulation coverage</h2>
                    <p style={styles.body}>
                        All three main regulation types are indexed for the 2023 through 2026 seasons, including multiple
                        issues per year where published.
                    </p>
                    <div style={styles.coverageGrid}>
                        {COVERAGE_ROWS.map(row => (
                            <div key={row.type} style={styles.coverageCard}>
                                <div style={styles.coverageTop}>
                                    <span style={styles.coverageType}>{row.type}</span>
                                    <div style={styles.yearBadges}>
                                        {YEARS.map(y => (
                                            <span key={y} style={styles.yearBadge}>{y}</span>
                                        ))}
                                    </div>
                                </div>
                                <p style={styles.coverageDesc}>{row.desc}</p>
                            </div>
                        ))}
                    </div>
                </section>

                <section style={styles.section}>
                    <h2 style={styles.sectionTitle}>Limitations</h2>
                    <ul style={styles.limitationList}>
                        {LIMITATIONS.map((item, i) => (
                            <li key={i} style={styles.limitationItem}>{item}</li>
                        ))}
                    </ul>
                </section>

                <section style={styles.section}>
                    <h2 style={styles.sectionTitle}>Source</h2>
                    <p style={styles.body}>
                        This project is open source.{' '}
                        <a
                            href="https://github.com/alvaroherrera-33/f1-regulations-engine"
                            target="_blank"
                            rel="noopener noreferrer"
                            style={styles.link}
                        >
                            View on GitHub
                        </a>
                        {' '}to explore the code, report issues, or contribute.
                    </p>
                    <p style={styles.body}>
                        Curious how the search pipeline works under the hood?{' '}
                        <Link href="/about/technical" style={styles.link}>
                            See the technical overview
                        </Link>.
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

    coverageGrid: { display: 'flex', flexDirection: 'column', gap: '0.6rem' },
    coverageCard: {
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: '8px',
        padding: '0.9rem 1rem',
    },
    coverageTop: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem', flexWrap: 'wrap', gap: '0.5rem' },
    coverageType: { fontSize: '0.88rem', fontWeight: 500, color: '#ccc' },
    yearBadges: { display: 'flex', gap: '0.3rem' },
    yearBadge: {
        fontSize: '0.68rem',
        background: 'rgba(235,0,0,0.15)',
        color: '#eb0000',
        border: '1px solid rgba(235,0,0,0.25)',
        borderRadius: '4px',
        padding: '0.15rem 0.4rem',
        fontWeight: 500,
    },
    coverageDesc: { fontSize: '0.8rem', color: '#666', lineHeight: 1.5, margin: 0 },

    limitationList: { margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.6rem' },
    limitationItem: {
        fontSize: '0.85rem',
        color: '#777',
        lineHeight: 1.6,
        paddingLeft: '1rem',
        position: 'relative',
    },

    link: { color: '#eb0000', textDecoration: 'underline', textUnderlineOffset: '2px' },
};
