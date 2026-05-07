'use client';

import { useEffect, useState } from 'react';
import { getStats, getStatus, StatsResponse, StatusResponse } from '@/lib/api';

export default function StatsPage() {
    const [stats, setStats] = useState<StatsResponse | null>(null);
    const [status, setStatus] = useState<StatusResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        Promise.all([getStats(), getStatus()])
            .then(([s, st]) => { setStats(s); setStatus(st); })
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    const helpfulRate = stats && (stats.positive_feedback + stats.negative_feedback) > 0
        ? Math.round((stats.positive_feedback / (stats.positive_feedback + stats.negative_feedback)) * 100)
        : null;

    const lastQuery = stats?.last_query_at
        ? new Date(stats.last_query_at).toLocaleString()
        : 'No queries yet';

    return (
        <div style={styles.page}>
            <div style={styles.container}>
                <div style={styles.header}>
                    <a href="/chat" style={styles.backLink}>← Back to Chat</a>
                    <h1 style={styles.title}>📊 System Stats</h1>
                    <p style={styles.subtitle}>Live metrics from production</p>
                </div>

                {loading && <div style={styles.loading}>Loading stats...</div>}
                {error && <div style={styles.error}>Could not load stats: {error}</div>}

                {!loading && !error && stats && status && (
                    <>
                        {/* DB Coverage */}
                        <section style={styles.section}>
                            <h2 style={styles.sectionTitle}>📚 Knowledge Base</h2>
                            <div style={styles.grid}>
                                <Stat label="Documents" value={status.documents_count} />
                                <Stat label="Articles" value={status.articles_count.toLocaleString()} />
                                <Stat label="Embeddings" value={status.embeddings_count.toLocaleString()} />
                                <Stat label="Coverage" value={status.embeddings_count === status.articles_count ? '100%' : `${Math.round((status.embeddings_count / status.articles_count) * 100)}%`} highlight />
                            </div>
                        </section>

                        {/* Query Volume */}
                        <section style={styles.section}>
                            <h2 style={styles.sectionTitle}>💬 Query Volume</h2>
                            <div style={styles.grid}>
                                <Stat label="Total Queries" value={stats.total_queries} />
                                <Stat label="Regulations" value={stats.regulation_queries} />
                                <Stat label="Conversational" value={stats.conversational_queries} />
                                <Stat label="Errors" value={stats.errors} warn={stats.errors > 0} />
                            </div>
                        </section>

                        {/* Performance */}
                        <section style={styles.section}>
                            <h2 style={styles.sectionTitle}>⚡ Performance</h2>
                            <div style={styles.grid}>
                                <Stat
                                    label="Avg Response Time"
                                    value={stats.avg_response_ms > 0 ? `${(stats.avg_response_ms / 1000).toFixed(1)}s` : '—'}
                                    warn={stats.avg_response_ms > 15000}
                                />
                                <Stat label="Last Query" value={lastQuery} wide />
                            </div>
                        </section>

                        {/* Feedback */}
                        <section style={styles.section}>
                            <h2 style={styles.sectionTitle}>👍 User Feedback</h2>
                            <div style={styles.grid}>
                                <Stat label="Helpful" value={stats.positive_feedback} highlight={stats.positive_feedback > 0} />
                                <Stat label="Not Helpful" value={stats.negative_feedback} warn={stats.negative_feedback > stats.positive_feedback} />
                                <Stat
                                    label="Satisfaction Rate"
                                    value={helpfulRate !== null ? `${helpfulRate}%` : 'No feedback yet'}
                                    highlight={helpfulRate !== null && helpfulRate >= 70}
                                    warn={helpfulRate !== null && helpfulRate < 50}
                                />
                            </div>
                        </section>
                    </>
                )}
            </div>
        </div>
    );
}

function Stat({ label, value, highlight, warn, wide }: {
    label: string;
    value: string | number;
    highlight?: boolean;
    warn?: boolean;
    wide?: boolean;
}) {
    return (
        <div style={{ ...styles.statCard, ...(wide ? styles.wideCard : {}) }}>
            <div style={styles.statLabel}>{label}</div>
            <div style={{
                ...styles.statValue,
                ...(highlight ? styles.statHighlight : {}),
                ...(warn ? styles.statWarn : {}),
            }}>
                {value}
            </div>
        </div>
    );
}

const styles: Record<string, React.CSSProperties> = {
    page: { minHeight: '100vh', background: '#0a0a0a', color: '#e0e0e0', fontFamily: 'system-ui, sans-serif', padding: '2rem 1rem' },
    container: { maxWidth: '800px', margin: '0 auto' },
    header: { marginBottom: '2rem' },
    backLink: { color: '#667eea', textDecoration: 'none', fontSize: '0.9rem' },
    title: { fontSize: '1.8rem', margin: '0.5rem 0 0.25rem', color: '#fff' },
    subtitle: { color: '#666', margin: 0, fontSize: '0.9rem' },
    loading: { color: '#666', textAlign: 'center', padding: '3rem' },
    error: { color: '#e05c5c', background: '#1a0a0a', border: '1px solid #4a1a1a', borderRadius: '8px', padding: '1rem' },
    section: { marginBottom: '2rem' },
    sectionTitle: { fontSize: '1rem', color: '#888', textTransform: 'uppercase' as const, letterSpacing: '0.08em', marginBottom: '1rem', fontWeight: 600 },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem' },
    statCard: { background: '#111', border: '1px solid #222', borderRadius: '10px', padding: '1.25rem 1rem' },
    wideCard: { gridColumn: 'span 2' },
    statLabel: { fontSize: '0.78rem', color: '#666', marginBottom: '0.5rem', textTransform: 'uppercase' as const, letterSpacing: '0.05em' },
    statValue: { fontSize: '1.5rem', fontWeight: 700, color: '#ccc' },
    statHighlight: { color: '#4ade80' },
    statWarn: { color: '#f59e0b' },
};
