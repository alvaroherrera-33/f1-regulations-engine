'use client';

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { sendChatQuery, submitFeedback } from '@/lib/api';
import CitationCard from './CitationCard';

const EXAMPLES = [
    'What is the minimum weight of an F1 car in 2026?',
    'How does DRS work under current regulations?',
    'Explain the cost cap rules',
    'What are the power unit fuel flow limits?',
];

const LOADING_MESSAGES = [
    'Searching regulations...',
    'Reading articles...',
    'Generating answer...',
];

interface Message {
    role: 'user' | 'assistant';
    content: string;
    citations?: any[];
    timestamp: Date;
    queryId?: number;
    feedback?: 'up' | 'down';
    retrievedCount?: number;
    stepCount?: number;
    timeMs?: number;
    confidence?: number;
}

interface Props {
    year: number | null;
    section: string | null;
    issue: number | null;
    onYearChange: (y: number | null) => void;
    onSectionChange: (s: string | null) => void;
    onIssueChange: (i: number | null) => void;
}

export default function ChatInterface({ year, section, issue, onYearChange, onSectionChange, onIssueChange }: Props) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [loadingIdx, setLoadingIdx] = useState(0);
    const [showFilters, setShowFilters] = useState(false);
    const endRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loading]);

    useEffect(() => {
        if (!loading) { setLoadingIdx(0); return; }
        const t = setInterval(() => setLoadingIdx(i => (i + 1) % LOADING_MESSAGES.length), 2000);
        return () => clearInterval(t);
    }, [loading]);

    // Reset textarea height when input is cleared
    useEffect(() => {
        if (!input && textareaRef.current) {
            textareaRef.current.style.height = 'auto';
        }
    }, [input]);

    const autoResize = () => {
        const el = textareaRef.current;
        if (!el) return;
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 150) + 'px';
    };

    const hasFilters = year || section || issue;

    const send = async (query: string) => {
        if (!query.trim() || loading) return;
        setMessages(prev => [...prev, { role: 'user', content: query, timestamp: new Date() }]);
        setInput('');
        setLoading(true);
        const t0 = Date.now();
        try {
            const res = await sendChatQuery({
                query,
                year: year || undefined,
                section: section || undefined,
                issue: issue || undefined,
            });
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: res.answer,
                citations: res.citations,
                timestamp: new Date(),
                queryId: res.query_id,
                retrievedCount: res.retrieved_count,
                stepCount: res.research_steps?.length || 1,
                timeMs: Date.now() - t0,
                confidence: res.confidence,
            }]);
        } catch (e: any) {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: 'Something went wrong: ' + (e.message || 'Unknown error'),
                timestamp: new Date(),
            }]);
        } finally {
            setLoading(false);
        }
    };

    const handleFeedback = async (idx: number, helpful: boolean) => {
        const msg = messages[idx];
        if (!msg.queryId || msg.feedback) return;
        setMessages(prev => prev.map((m, i) => i === idx ? { ...m, feedback: helpful ? 'up' : 'down' } : m));
        try { await submitFeedback(msg.queryId, helpful); } catch { /* silent */ }
    };

    return (
        <div style={styles.container}>
            {/* Messages */}
            <div style={styles.messages}>
                {messages.length === 0 && !loading && (
                    <div style={styles.empty}>
                        <h2 style={styles.emptyTitle}>What do you want to know?</h2>
                        <p style={styles.emptyHint}>Ask about any F1 regulation — Technical, Sporting, or Financial.</p>
                        <div style={styles.examples}>
                            {EXAMPLES.map(q => (
                                <button key={q} className="example-btn" onClick={() => send(q)} style={styles.exampleBtn}>{q}</button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((msg, i) => (
                    <div key={i} style={styles.msgWrap}>
                        <div style={msg.role === 'user' ? styles.userMsg : styles.asstMsg}>
                            {msg.role === 'user' ? (
                                <p style={styles.userText}>{msg.content}</p>
                            ) : (
                                <div className="prose" style={styles.asstContent}>
                                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                                </div>
                            )}

                            {/* Metrics + feedback for assistant */}
                            {msg.role === 'assistant' && msg.retrievedCount != null && (
                                <div style={styles.metaRow}>
                                    <span>{msg.retrievedCount} articles</span>
                                    <span style={styles.dot} />
                                    <span>{msg.stepCount} {msg.stepCount === 1 ? 'step' : 'steps'}</span>
                                    {msg.timeMs != null && (
                                        <>
                                            <span style={styles.dot} />
                                            <span>{(msg.timeMs / 1000).toFixed(1)}s</span>
                                        </>
                                    )}
                                    <span style={{ flex: 1 }} />
                                    {msg.queryId && !msg.feedback && (
                                        <>
                                            <button onClick={() => handleFeedback(i, true)} style={styles.fbBtn} title="Helpful">&#128077;</button>
                                            <button onClick={() => handleFeedback(i, false)} style={styles.fbBtn} title="Not helpful">&#128078;</button>
                                        </>
                                    )}
                                    {msg.feedback && (
                                        <span style={styles.fbThanks}>
                                            {msg.feedback === 'up' ? 'Thanks!' : 'Noted'}
                                        </span>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Low-confidence warning */}
                        {msg.role === 'assistant' && msg.confidence != null && msg.confidence < 0.55 && msg.citations && msg.citations.length > 0 && (
                            <div style={styles.confidenceWarn}>
                                <span style={styles.confidenceIcon}>⚠</span>
                                Low confidence — this topic may not be well covered in the indexed regulations. Verify with official FIA documents.
                            </div>
                        )}

                        {/* Citations */}
                        {msg.citations && msg.citations.length > 0 && (
                            <div style={styles.citations}>
                                <p style={styles.citLabel}>Sources ({msg.citations.length})</p>
                                {msg.citations.map((c, ci) => (
                                    <CitationCard key={ci} citation={c} index={ci + 1} />
                                ))}
                            </div>
                        )}
                    </div>
                ))}

                {loading && (
                    <div style={styles.loading}>
                        <div style={styles.dots}>
                            {[0, 1, 2].map(i => <div key={i} style={{ ...styles.dotAnim, animationDelay: i * 0.15 + 's' }} />)}
                        </div>
                        <span style={styles.loadingText}>{LOADING_MESSAGES[loadingIdx]}</span>
                    </div>
                )}

                <div ref={endRef} />
            </div>

            {/* Input area */}
            <div style={styles.inputArea}>
                <div style={styles.inputRow}>
                    <button
                        onClick={() => setShowFilters(!showFilters)}
                        style={{ ...styles.filterToggle, ...(hasFilters ? styles.filterToggleActive : {}) }}
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="11" y1="18" x2="13" y2="18"/></svg>
                        {hasFilters ? [year, section].filter(Boolean).join(' · ') : 'Filters'}
                    </button>
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={e => { setInput(e.target.value); autoResize(); }}
                        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input); } }}
                        placeholder="Ask about F1 regulations..."
                        style={styles.textarea}
                        rows={1}
                        disabled={loading}
                    />
                    <button
                        onClick={() => send(input)}
                        disabled={!input.trim() || loading}
                        style={{ ...styles.sendBtn, opacity: !input.trim() || loading ? 0.3 : 1 }}
                    >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                    </button>
                </div>

                {/* Filter dropdown */}
                {showFilters && (
                    <div style={styles.filterPanel}>
                        <select value={year || ''} onChange={e => onYearChange(e.target.value ? +e.target.value : null)} style={styles.filterSelect}>
                            <option value="">All years</option>
                            <option value="2026">2026</option>
                            <option value="2025">2025</option>
                            <option value="2024">2024</option>
                            <option value="2023">2023</option>
                        </select>
                        <select value={section || ''} onChange={e => onSectionChange(e.target.value || null)} style={styles.filterSelect}>
                            <option value="">All sections</option>
                            <option value="Technical">Technical</option>
                            <option value="Sporting">Sporting</option>
                            <option value="Financial">Financial</option>
                        </select>
                        <input
                            type="number"
                            placeholder="Issue #"
                            value={issue || ''}
                            onChange={e => onIssueChange(e.target.value ? +e.target.value : null)}
                            min={1}
                            style={{ ...styles.filterSelect, width: '80px' }}
                        />
                        {hasFilters && (
                            <button onClick={() => { onYearChange(null); onSectionChange(null); onIssueChange(null); }} style={styles.clearBtn}>
                                Clear
                            </button>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

const styles: Record<string, React.CSSProperties> = {
    container: { display: 'flex', flexDirection: 'column', height: '100%' },

    // Messages
    messages: { flex: 1, overflowY: 'auto', padding: '1.5rem 0', display: 'flex', flexDirection: 'column', gap: '1.5rem' },
    empty: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, textAlign: 'center', padding: '3rem 1rem' },
    emptyTitle: { fontSize: '1.4rem', fontWeight: 600, color: '#fff', marginBottom: '0.5rem', letterSpacing: '-0.02em' },
    emptyHint: { fontSize: '0.9rem', color: '#777', marginBottom: '2rem' },
    examples: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem', maxWidth: '580px', width: '100%' },
    exampleBtn: { background: 'transparent', border: '1px solid #2a2a2a', borderRadius: '8px', color: '#aaa', padding: '0.7rem 0.85rem', fontSize: '0.82rem', cursor: 'pointer', textAlign: 'left', lineHeight: 1.4, transition: 'border-color 0.15s, color 0.15s' },

    // Messages
    msgWrap: { display: 'flex', flexDirection: 'column', gap: '0.5rem', animation: 'fadeIn 0.25s ease' },
    userMsg: { alignSelf: 'flex-end', maxWidth: '75%' },
    userText: { background: '#1a1a1a', borderRadius: '16px 16px 4px 16px', padding: '0.7rem 1rem', fontSize: '0.9rem', color: '#e0e0e0', lineHeight: 1.5 },
    asstMsg: { alignSelf: 'flex-start', maxWidth: '100%' },
    asstContent: { fontSize: '0.9rem', lineHeight: 1.7, color: '#ccc' },

    // Meta & feedback
    metaRow: { display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.75rem', fontSize: '0.72rem', color: '#666', fontVariantNumeric: 'tabular-nums' },
    dot: { width: '2px', height: '2px', borderRadius: '50%', background: '#444', flexShrink: 0 },
    fbBtn: { background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '0.75rem', padding: '0.15rem 0.3rem', borderRadius: '4px', opacity: 0.5, transition: 'opacity 0.15s' },
    fbThanks: { fontSize: '0.72rem', color: '#666', fontStyle: 'italic' },

    // Citations
    citations: { paddingLeft: '0.75rem', borderLeft: '2px solid rgba(255,255,255,0.07)' },
    citLabel: { fontSize: '0.72rem', color: '#777', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 500 },

    // Loading
    loading: { display: 'flex', alignItems: 'center', gap: '0.75rem', animation: 'fadeIn 0.3s ease' },
    dots: { display: 'flex', gap: '3px' },
    dotAnim: { width: '5px', height: '5px', borderRadius: '50%', background: '#eb0000', animation: 'bounce 1.2s infinite ease-in-out' },
    loadingText: { fontSize: '0.82rem', color: '#666' },

    // Input
    inputArea: { borderTop: '1px solid rgba(255,255,255,0.06)', padding: '0.75rem 0' },
    inputRow: { display: 'flex', alignItems: 'flex-end', gap: '0.5rem' },
    filterToggle: { display: 'inline-flex', alignItems: 'center', gap: '0.35rem', background: 'transparent', border: '1px solid #222', borderRadius: '8px', color: '#666', padding: '0.55rem 0.75rem', fontSize: '0.78rem', cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0, transition: 'border-color 0.15s, color 0.15s', marginBottom: '2px' },
    filterToggleActive: { borderColor: '#eb0000', color: '#eb0000' },
    textarea: { flex: 1, background: 'transparent', border: 'none', color: '#e0e0e0', fontSize: '0.9rem', resize: 'none', outline: 'none', fontFamily: 'inherit', lineHeight: 1.5, padding: '0.5rem 0', overflowY: 'hidden', maxHeight: '150px' },
    sendBtn: { background: '#eb0000', border: 'none', borderRadius: '8px', color: '#fff', padding: '0.5rem', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'opacity 0.15s', marginBottom: '2px' },

    // Confidence warning
    confidenceWarn: { display: 'flex', alignItems: 'flex-start', gap: '0.4rem', background: 'rgba(250,204,21,0.06)', border: '1px solid rgba(250,204,21,0.2)', borderRadius: '6px', padding: '0.5rem 0.7rem', fontSize: '0.75rem', color: '#9ca3af', lineHeight: 1.5, marginTop: '0.5rem' },
    confidenceIcon: { color: '#facc15', flexShrink: 0, marginTop: '0.05rem' },

    // Filter panel
    filterPanel: { display: 'flex', gap: '0.5rem', padding: '0.5rem 0 0', flexWrap: 'wrap', animation: 'fadeIn 0.15s ease' },
    filterSelect: { background: '#111', border: '1px solid #222', borderRadius: '8px', color: '#ccc', padding: '0.4rem 0.6rem', fontSize: '0.78rem', outline: 'none', transition: 'border-color 0.15s' },
    clearBtn: { background: 'transparent', border: 'none', color: '#eb0000', fontSize: '0.78rem', cursor: 'pointer', padding: '0.4rem 0.6rem' },
};
