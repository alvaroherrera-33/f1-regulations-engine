'use client';

import { useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const COMPARE_API = `${API_BASE}/api/compare`;
interface ArticleVersion {
    article_code: string;
    title: string;
    content: string;
    year: number;
    section: string;
    issue: number;
}

export default function ComparePage() {
    const [code, setCode] = useState('');
    const [yearA, setYearA] = useState(2025);
    const [yearB, setYearB] = useState(2026);
    const [section, setSection] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<{ a: ArticleVersion | null; b: ArticleVersion | null } | null>(null);
    const [error, setError] = useState('');
    const [explanation, setExplanation] = useState<string | null>(null);
    const [explainLoading, setExplainLoading] = useState(false);
    const [explainError, setExplainError] = useState('');

    const compare = async (overrideCode?: string) => {
        const target = (overrideCode ?? code).trim();
        if (!target) return;
        setLoading(true);
        setError('');
        setResult(null);
        setExplanation(null);
        setExplainError('');
        try {
            let url = `${COMPARE_API}?code=${encodeURIComponent(target)}&year_a=${yearA}&year_b=${yearB}`;
            if (section) url += `&section=${encodeURIComponent(section)}`;
            const res = await fetch(url);
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error((err as { detail?: string }).detail || 'Not found');
            }
            const data = await res.json();
            setResult({ a: data.version_a, b: data.version_b });
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Could not find that article. Check the code and try again.');
        } finally {
            setLoading(false);
        }
    };

    const explainDiff = async () => {
        if (!result || !code.trim()) return;
        setExplainLoading(true);
        setExplainError('');
        setExplanation(null);
        try {
            let url = `${API_BASE}/api/compare/explain?code=${encodeURIComponent(code.trim())}&year_a=${yearA}&year_b=${yearB}`;
            if (section) url += `&section=${encodeURIComponent(section)}`;
            const res = await fetch(url, { method: 'POST' });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error((err as { detail?: string }).detail || 'AI explanation failed');
            }
            const data = await res.json();
            setExplanation(data.explanation ?? null);
        } catch (err) {
            setExplainError(err instanceof Error ? err.message : 'Could not generate explanation.');
        } finally {
            setExplainLoading(false);
        }
    };

    const CHIPS = ['1.1', '2.1', '3.1', '5.1', '10.1', '22.1'];

    return (
        <div style={styles.page}>
            <div style={styles.container}>
                <div style={styles.header}>
                    <h1 style={styles.title}>Compare regulations</h1>
                    <p style={styles.subtitle}>See how a specific article changed between years</p>
                </div>

                <div style={styles.controls}>
                    <select value={yearA} onChange={e => setYearA(+e.target.value)} style={styles.select}>
                        <option value={2026}>2026</option>
                        <option value={2025}>2025</option>
                        <option value={2024}>2024</option>
                        <option value={2023}>2023</option>
                    </select>
                    <span style={styles.vs}>vs</span>
                    <select value={yearB} onChange={e => setYearB(+e.target.value)} style={styles.select}>
                        <option value={2026}>2026</option>
                        <option value={2025}>2025</option>
                        <option value={2024}>2024</option>
                        <option value={2023}>2023</option>
                    </select>
                    <select value={section} onChange={e => setSection(e.target.value)} style={styles.select}>
                        <option value="">All sections</option>
                        <option value="Technical">Technical</option>
                        <option value="Sporting">Sporting</option>
                        <option value="Financial">Financial</option>
                    </select>
                    <input
                        value={code}
                        onChange={e => setCode(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') compare(); }}
                        placeholder="Article code (e.g. 3.1)"
                        style={styles.input}
                    />
                    <button onClick={() => compare()} disabled={loading || !code.trim()} style={{ ...styles.btn, opacity: loading || !code.trim() ? 0.3 : 1 }}>
                        {loading ? 'Loading...' : 'Compare'}
                    </button>
                </div>

                <div style={styles.chips}>
                    {CHIPS.map(c => (
                        <button key={c} className="example-btn" onClick={() => { setCode(c); compare(c); }} style={styles.chip}>{c}</button>
                    ))}
                </div>

                {error && <p style={styles.error}>{error}</p>}

                {result && (
                    <>
                        <div className="diff-grid" style={styles.diffGrid}>
                            <VersionPanel version={result.a} year={yearA} />
                            <VersionPanel version={result.b} year={yearB} />
                        </div>

                        <div style={styles.explainRow}>
                            <button
                                onClick={explainDiff}
                                disabled={explainLoading}
                                style={{ ...styles.explainBtn, opacity: explainLoading ? 0.5 : 1 }}
                            >
                                {explainLoading ? (
                                    <>
                                        <span style={styles.spinner} />
                                        Analysing changes…
                                    </>
                                ) : (
                                    <>
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                                            <circle cx="12" cy="12" r="10" />
                                            <path d="M12 16v-4M12 8h.01" />
                                        </svg>
                                        Explain changes with AI
                                    </>
                                )}
                            </button>
                        </div>

                        {explainError && <p style={styles.error}>{explainError}</p>}

                        {explanation && (
                            <div style={styles.explanationBox}>
                                <div style={styles.explanationHeader}>
                                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#eb0000" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <circle cx="12" cy="12" r="10" />
                                        <path d="M12 16v-4M12 8h.01" />
                                    </svg>
                                    <span style={styles.explanationLabel}>AI Analysis</span>
                                    <span style={styles.explanationMeta}>{yearA} → {yearB} · Article {code.trim()}</span>
                                </div>
                                <p style={styles.explanationText}>{explanation}</p>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}

function VersionPanel({ version, year }: { version: ArticleVersion | null; year: number }) {
    if (!version) {
        return (
            <div style={styles.panel}>
                <p style={styles.panelEmpty}>No data for {year}</p>
            </div>
        );
    }
    return (
        <div style={styles.panel}>
            <div style={styles.panelHeader}>
                <span style={styles.panelYear}>{version.year}</span>
                <span style={styles.panelCode}>{version.article_code}</span>
                <span style={styles.panelBadge}>{version.section}</span>
                <span style={{ ...styles.panelBadge, marginLeft: 'auto' }}>Issue {version.issue}</span>
            </div>
            <h3 style={styles.panelTitle}>{version.title}</h3>
            <p style={styles.panelContent}>{version.content}</p>
        </div>
    );
}

const styles: Record<string, React.CSSProperties> = {
    page: { minHeight: 'calc(100vh - 52px)', padding: '2rem 1rem' },
    container: { maxWidth: '960px', margin: '0 auto' },
    header: { marginBottom: '2rem' },
    title: { fontSize: '1.4rem', fontWeight: 600, color: '#fff', letterSpacing: '-0.02em', marginBottom: '0.3rem' },
    subtitle: { fontSize: '0.85rem', color: '#666' },
    controls: { display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' },
    select: { background: '#111', border: '1px solid #222', borderRadius: '8px', color: '#ccc', padding: '0.5rem 0.75rem', fontSize: '0.85rem', outline: 'none', transition: 'border-color 0.15s' },
    vs: { color: '#666', fontSize: '0.78rem', fontWeight: 500 },
    input: { flex: 1, minWidth: '160px', background: '#111', border: '1px solid #222', borderRadius: '8px', color: '#e0e0e0', padding: '0.5rem 0.75rem', fontSize: '0.85rem', outline: 'none', transition: 'border-color 0.15s' },
    btn: { background: '#eb0000', border: 'none', borderRadius: '8px', color: '#fff', padding: '0.5rem 1.25rem', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', transition: 'opacity 0.15s' },
    chips: { display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '1.5rem' },
    chip: { background: 'transparent', border: '1px solid #222', borderRadius: '8px', color: '#666', padding: '0.3rem 0.6rem', fontSize: '0.72rem', cursor: 'pointer', transition: 'border-color 0.15s, color 0.15s' },
    error: { color: '#eb0000', fontSize: '0.85rem', marginBottom: '1rem' },
    diffGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' },
    panel: { border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px', padding: '1.25rem' },
    panelEmpty: { color: '#666', fontSize: '0.85rem', textAlign: 'center', padding: '2rem 0' },
    panelHeader: { display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' },
    panelYear: { fontSize: '0.72rem', color: '#eb0000', fontWeight: 600 },
    panelCode: { fontFamily: 'monospace', fontSize: '0.82rem', color: '#ccc', fontWeight: 600 },
    panelBadge: { background: 'rgba(255,255,255,0.04)', borderRadius: '4px', padding: '0.12rem 0.4rem', fontSize: '0.68rem', color: '#666', fontWeight: 500 },
    panelTitle: { fontSize: '0.9rem', color: '#ccc', fontWeight: 500, marginBottom: '0.75rem', lineHeight: 1.4 },
    panelContent: { fontSize: '0.82rem', color: '#888', lineHeight: 1.7, whiteSpace: 'pre-line' },

    explainRow: { display: 'flex', justifyContent: 'center', marginTop: '1.25rem', marginBottom: '0.5rem' },
    explainBtn: {
        display: 'flex', alignItems: 'center', gap: '0.4rem',
        background: 'rgba(235,0,0,0.08)', border: '1px solid rgba(235,0,0,0.25)',
        borderRadius: '8px', color: '#eb0000', padding: '0.45rem 1rem',
        fontSize: '0.82rem', fontWeight: 500, cursor: 'pointer', transition: 'opacity 0.15s',
    },
    spinner: {
        display: 'inline-block', width: '10px', height: '10px',
        border: '1.5px solid rgba(235,0,0,0.3)', borderTopColor: '#eb0000',
        borderRadius: '50%', animation: 'spin 0.7s linear infinite',
    },

    explanationBox: {
        marginTop: '1rem', padding: '1.1rem 1.25rem',
        background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: '8px',
    },
    explanationHeader: { display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.65rem' },
    explanationLabel: { fontSize: '0.72rem', color: '#eb0000', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' },
    explanationMeta: { fontSize: '0.7rem', color: '#444', marginLeft: 'auto' },
    explanationText: { fontSize: '0.85rem', color: '#aaa', lineHeight: 1