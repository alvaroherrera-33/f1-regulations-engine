'use client';

import { useEffect, useState } from 'react';
import { getStats, getSyncStatus, StatsResponse, SyncStatusResponse } from '@/lib/api';

interface StatusResponse {
    documents_count: number;
    articles_count: number;
    embeddings_count: number;
}

export default function StatsPage() {
    const [stats, setStats] = useState<StatsResponse | null>(null);
    const [status, setStatus] = useState<StatusResponse | null>(null);
    const [syncStatus, setSyncStatus] = useState<SyncStatusResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        Promise.all([
            getStats(),
            fetch('/api/status').then(r => r.json() as Promise<StatusResponse>),
            getSyncStatus().catch(() => null),
        ])
            .then(([s, st, sync]) => { setStats(s); setStatus(st); setSyncStatus(sync); })
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    const helpfulRate = stats && (stats.positive_feedback + stats.negative_feedback) > 0
        ? Math.round((stats.positive_feedback / (stats.positive_feedback + stats.negative_feedback)) * 100)
        : null;

    const lastQuery = stats?.last_query_at
        ? new Date(stats.last_query_at).toLocaleDateString('en-GB', {
            day: 'numeric', month: 'short', year: 'numeric',
          })
        : 'No queries yet';

    const coverage = !status || status.articles_count === 0
        ? '—'
        : status.embeddings_count >= status.articles_count
            ? '100%'
            : Math.round((status.embeddings_count / status.articles_count) * 100) + '%';

    return (
        <div style={styles.page}>
            <div style={styles.container}>
                <div style={styles.header}>
                    <h1 style={styles.title}>System stats</h1>
                    <p style={styles.subtitle}>Live metrics from production</p>
                </div>

                {loading && <p style={styles.loading}>Loading stats...</p>}
                {error && <p style={styles.error}>Could not load stats: {error}</p>}

                {!loading && !error && stats && status && (
                    <>
                        <Section title="Knowledge Base">
                            <Stat label="Documents" value={status.documents_count} />
                            <Stat label="Articles" value={status.articles_count.toLocaleString()} />
                            <Stat label="Embeddings" value={status.embeddings_count.toLocaleString()} />
                            <Stat label="Coverage" value={coverage} accent={coverage === '100%'} />
                        </Section>

                        <Section title="Query Volume">
                            <Stat label="Total Queries" value={stats.total_queries} />
                            <Stat label="Regulations" value={stats.regulation_queries} />
                            <Stat label="Conversational" value={stats.conversational_queries} />
                            <Stat label="Errors" value={stats.errors} warn={stats.errors > 0} />
                        </Section>

                        <Section title="Performance">
                            <Stat
                                label="Avg Response"
                                value={stats.avg_response_ms > 0 ? (stats.avg_response_ms / 1000).toFixed(1) + 's' : '—'}
                                warn={stats.avg_response_ms > 15000}
                            />
                            <Stat label="Last Query" value={lastQuery} small />
                        </Section>

                        {syncStatus && (
                            <Section title="FIA Regulation Sync">
                                <Stat
                                    label="Last Checked"
                                    value={syncStatus.last_checked
                                        ? new Date(syncStatus.last_checked).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
                                        : 'Never'}
                                    small
                                />
                                <Stat label="FIA Docs" value={syncStatus.total_fia_docs || '—'} />
                                <Stat
                                    label="New Available"
                                    value={syncStatus.new_docs_found}
                                    warn={syncStatus.new_docs_found > 0}
                                    accent={syncStatus.new_docs_found === 0 && !!syncStatus.last_checked}
                                />
                                <Stat
                                    label="Status"
                                    value={syncStatus.last_error ? 'Error' : syncStatus.last_checked ? 'Up to date' : '—'}
                                    warn={!!syncStatus.last_error}
                                    accent={!syncStatus.last_error && !!syncStatus.last_checked}
                                    small
                                />
                            </Section>
                        )}

                        <Section title="Feedback">
                            <Stat label="Helpful" value={stats.positive_feedback} accent={stats.positive_feedback > 0} />
                            <Stat label="Not Helpful" value={stats.negative_feedback} warn={stats.negative_feedback > stats.positive_feedback} />
                            <Stat
                                label="Satisfaction"
                                value={helpfulRate !== null ? helpfulRate + '%' : '—'}
                                accent={helpfulRate !== null && helpfulRate >= 70}
                                warn={helpfulRate !== null && helpfulRate < 50}
                            />
                        </Section>
                    </>
                )}
            </div>
        </div>
    );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <section style={styles.section}>
            <h2 style={styles.sectionTitle}>{title}</h2>
            <div className="stack-grid" style={styles.grid}>{children}</div>
        </section>
    );
}

function Stat({ label, value, accent, warn, small }: {
    label: string; value: string | number; accent?: boolean; warn?: boolean; small?: boolean;
}) {
    return (
        <div style={styles.statCard}>
            <div style={styles.statLabel}>{label}</div>
            <div style={{
                ...styles.statValue,
                ...(small ? styles.statValueSmall : {}),
                ...(accent ? { color: '#4ade80' } : {}),
                ...(warn ? { color: '#f59e0b' } : {}),
            }}>
                {value}
            </div>
        </div>
    );
}

const styles: Record<string, React.CSSProperties> = {
    page: { minHeight: 'calc(100vh - 52px)', padding: '2rem 1rem' },
    container: { maxWidth: '720px', margin: '0 auto' },

    header: { marginBottom: '2rem' },
    title: { fontSize: '1.4rem', fontWeight: 600, color: '#fff', letterSpacing: '-0.02em', marginBottom: '0.3rem' },
    subtitle: { fontSize: '0.85rem', color: '#666' },

    loading: { color: '#666', textAlign: 'center', padding: '3rem 0', fontSize: '0.9rem' },
    error: { color: '#eb0000', fontSize: '0.85rem', padding: '1rem', border: '1px solid rgba(235,0,0,0.2)', borderRadius: '8px' },

    section: { marginBottom: '2rem' },
    sectionTitle: { fontSize: '0.72rem', color: '#666', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 500, marginBottom: '0.75rem' },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.6rem' },

    statCard: { border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px', padding: '1rem' },
    statLabel: { fontSize: '0.72rem', color: '#666', marginBottom: '0.4rem', letterSpacing: '0.06em', textTransform: 'uppercase' },
    statValue: { fontSize: '1.3rem', fontWeight: 600, color: '#ccc', fontVariantNumeric: 'tabular-nums' },
    statValueSmall: { fontSize: '0.88rem', fontWeight: 500, lineHeight: 1.4 },
};
