'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getStatus, StatusResponse } from '@/lib/api';

export default function Home() {
    const [status, setStatus] = useState<StatusResponse | null>(null);

    useEffect(() => {
        getStatus().then(setStatus).catch(() => null);
    }, []);

    const fmt = (n: number | undefined) =>
        n === undefined ? '...' : n.toLocaleString();

    return (
        <main style={styles.main}>
            {/* Hero */}
            <div style={styles.hero}>
                <div style={styles.heroBadge}>2026 Ready</div>
                <h1 style={styles.title}>
                    F1 Regulations <span style={styles.titleAccent}>Engine</span>
                </h1>
                <p style={styles.subtitle}>
                    A legal-grade retrieval system for FIA Formula 1 Regulations.
                    Search across Technical, Sporting, and Financial rules with AI-driven precision.
                </p>
                <div style={styles.heroCTA}>
                    <Link href="/chat" style={styles.primaryButton}>Start Researching →</Link>
                    <Link href="/upload" style={styles.secondaryButton}>Upload Regulations</Link>
                </div>
            </div>

            {/* Feature Grid */}
            <div style={styles.grid}>
                <Link href="/chat" style={styles.card}>
                    <h2 style={styles.cardTitle}>Agentic Chat</h2>
                    <p style={styles.cardText}>Multistep reasoning to resolve complex regulatory cross-references automatically.</p>
                </Link>

                <div style={styles.card}>
                    <h2 style={styles.cardTitle}>Hybrid Search</h2>
                    <p style={styles.cardText}>Vector similarity + full-text search merged with Reciprocal Rank Fusion (RRF).</p>
                </div>

                <Link href="/upload" style={styles.card}>
                    <h2 style={styles.cardTitle}>PDF Ingestion</h2>
                    <p style={styles.cardText}>Upload any FIA regulation PDF and it's indexed and searchable in seconds.</p>
                </Link>
            </div>

            {/* Status Section with real metrics */}
            <div style={styles.statusSection}>
                <div style={styles.statusHeader}>
                    <span style={styles.statusDot} />
                    <h3 style={styles.statusTitle}>System Status: Operational</h3>
                </div>
                <div style={styles.statusMetrics}>
                    <div style={styles.metric}>
                        <span style={styles.metricValue}>{fmt(status?.documents_count)}</span>
                        <span style={styles.metricLabel}>Documents</span>
                    </div>
                    <div style={styles.metric}>
                        <span style={styles.metricValue}>{fmt(status?.articles_count)}</span>
                        <span style={styles.metricLabel}>Articles Indexed</span>
                    </div>
                    <div style={styles.metric}>
                        <span style={styles.metricValue}>{fmt(status?.embeddings_count)}</span>
                        <span style={styles.metricLabel}>Embeddings</span>
                    </div>
                </div>
            </div>
        </main>
    );
}

const styles: Record<string, React.CSSProperties> = {
    main: { padding: '3rem 2rem', maxWidth: '1200px', margin: '0 auto', minHeight: 'calc(100vh - 60px)' },
    hero: { textAlign: 'center', marginBottom: '4rem' },
    heroBadge: { background: 'rgba(235,0,0,0.1)', border: '1px solid #eb0000', color: '#eb0000', padding: '0.25rem 1rem', borderRadius: '20px', fontSize: '0.8rem', fontWeight: 'bold', display: 'inline-block', marginBottom: '1.5rem', textTransform: 'uppercase', letterSpacing: '0.1em' },
    title: { fontSize: 'clamp(2.2rem, 6vw, 4rem)', fontWeight: '900', marginBottom: '1.5rem', letterSpacing: '-0.02em', color: '#fff' },
    titleAccent: { background: 'linear-gradient(135deg, #eb0000 0%, #ff4d4d 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' },
    subtitle: { fontSize: '1.15rem', opacity: 0.7, marginBottom: '2.5rem', maxWidth: '700px', margin: '0 auto 2.5rem auto', lineHeight: '1.6' },
    heroCTA: { display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' },
    primaryButton: { background: '#eb0000', color: '#fff', padding: '0.9rem 2rem', borderRadius: '8px', fontSize: '1rem', fontWeight: 'bold', textDecoration: 'none', boxShadow: '0 8px 24px rgba(235,0,0,0.3)' },
    secondaryButton: { background: 'transparent', color: '#fff', padding: '0.9rem 2rem', borderRadius: '8px', fontSize: '1rem', fontWeight: '600', textDecoration: 'none', border: '1px solid #444' },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem', marginBottom: '4rem' },
    card: { padding: '2rem', background: '#111', border: '1px solid #222', borderRadius: '16px', textDecoration: 'none', color: 'inherit', display: 'block' },
    cardTitle: { fontSize: '1.3rem', marginBottom: '0.5rem', color: '#fff' },
    cardText: { fontSize: '0.9rem', opacity: 0.6, lineHeight: '1.5' },
    statusSection: { padding: '2rem', background: '#0a0a0a', border: '1px solid #222', borderRadius: '16px', display: 'flex', flexDirection: 'column', gap: '1.5rem' },
    statusHeader: { display: 'flex', alignItems: 'center', gap: '0.75rem' },
    statusDot: { width: '10px', height: '10px', borderRadius: '50%', background: '#22c55e', boxShadow: '0 0 8px #22c55e', flexShrink: 0 },
    statusTitle: { fontSize: '1rem', fontWeight: 'bold', color: '#22c55e' },
    statusMetrics: { display: 'flex', justifyContent: 'space-around', textAlign: 'center', flexWrap: 'wrap', gap: '1rem' },
    metric: { display: 'flex', flexDirection: 'column', gap: '0.25rem' },
    metricValue: { fontSize: '1.8rem', fontWeight: '900', color: '#fff' },
    metricLabel: { fontSize: '0.75rem', opacity: 0.5, textTransform: 'uppercase', letterSpacing: '0.05em' },
};
