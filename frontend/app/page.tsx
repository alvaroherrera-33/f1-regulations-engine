'use client';

import Link from 'next/link';

export default function Home() {
    return (
        <main style={styles.main}>
            <div style={styles.hero}>
                <p style={styles.tagline}>Formula 1 Regulation Search</p>
                <h1 style={styles.title}>
                    Ask anything about<br />
                    <span style={styles.accent}>F1 regulations</span>
                </h1>
                <p style={styles.subtitle}>
                    AI-powered search across Technical, Sporting, and Financial regulations.
                    Every answer backed by exact article citations.
                </p>
                <div style={styles.cta}>
                    <Link href="/chat" className="cta-btn" style={styles.primaryBtn}>
                        Start searching
                        <span className="cta-arrow" style={styles.arrow}>&rarr;</span>
                    </Link>
                </div>
                <p style={styles.meta}>
                    16,000+ articles indexed &middot; 2023–2026 seasons &middot; Free and open source
                </p>
            </div>
        </main>
    );
}

const styles: Record<string, React.CSSProperties> = {
    main: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - 52px)',
        padding: '2rem',
    },
    hero: {
        textAlign: 'center',
        maxWidth: '600px',
    },
    tagline: {
        fontSize: '0.78rem',
        color: '#eb0000',
        fontWeight: 500,
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        marginBottom: '1.25rem',
    },
    title: {
        fontSize: 'clamp(2rem, 5vw, 3.2rem)',
        fontWeight: 700,
        lineHeight: 1.15,
        color: '#fff',
        letterSpacing: '-0.03em',
        marginBottom: '1.5rem',
    },
    accent: {
        color: '#eb0000',
    },
    subtitle: {
        fontSize: '1.05rem',
        color: '#888',
        lineHeight: 1.6,
        marginBottom: '2.5rem',
    },
    cta: {
        marginBottom: '2rem',
    },
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
        transition: 'opacity 0.15s',
    },
    arrow: {
        fontSize: '1rem',
        transition: 'transform 0.15s',
        display: 'inline-block',
    },
    meta: {
        fontSize: '0.78rem',
        color: '#666',
    },
};
