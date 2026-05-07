'use client';

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { sendChatQuery, submitFeedback, ChatResponse } from '@/lib/api';
import CitationCard from './CitationCard';

const EXAMPLE_QUERIES = [
    'What is the minimum weight of an F1 car in 2026?',
    'How does the DRS system work?',
    'What are the power unit fuel flow limits?',
    'Explain the cost cap regulations',
    'What changed in 2026 technical regulations?',
    'How are points awarded after a race?',
];

const LOADING_MESSAGES = [
    'Analyzing query...',
    'Searching regulations...',
    'Reading articles...',
    'Generating answer...',
];

interface Message {
    role: 'user' | 'assistant';
    content: string;
    citations?: any[];
    researchSteps?: { step: number; thought: string; action: string; query: string; }[];
    timestamp: Date;
    queryId?: number;
    feedback?: 'up' | 'down';
}

interface ChatInterfaceProps {
    year: number | null;
    section: string | null;
    issue: number | null;
    viewSettings: { showMarkdown: boolean; density: 'standard' | 'compact'; fontSize: 'small' | 'medium' | 'large'; };
    onOpenSidebar?: () => void;
    showSidebarButton?: boolean;
}

export default function ChatInterface({ year, section, issue, viewSettings, onOpenSidebar, showSidebarButton }: ChatInterfaceProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [loadingMsgIdx, setLoadingMsgIdx] = useState(0);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loading]);

    // Cycle loading messages
    useEffect(() => {
        if (!loading) { setLoadingMsgIdx(0); return; }
        const t = setInterval(() => {
            setLoadingMsgIdx(i => (i + 1) % LOADING_MESSAGES.length);
        }, 1800);
        return () => clearInterval(t);
    }, [loading]);

    const getMessageStyle = (role: 'user' | 'assistant'): React.CSSProperties => ({
        ...styles.message,
        ...(role === 'user' ? styles.userMessage : styles.assistantMessage),
        padding: viewSettings.density === 'compact' ? '0.5rem 0.75rem' : undefined,
        fontSize: viewSettings.fontSize === 'small' ? '0.85rem' : viewSettings.fontSize === 'large' ? '1.1rem' : undefined,
    });

    const sendQuery = async (query: string) => {
        if (!query.trim() || loading) return;
        const userMessage: Message = { role: 'user', content: query, timestamp: new Date() };
        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setLoading(true);
        try {
            const response = await sendChatQuery({ query, year: year || undefined, section: section || undefined, issue: issue || undefined });
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: response.answer,
                citations: response.citations,
                researchSteps: response.research_steps,
                timestamp: new Date(),
                queryId: response.query_id,
            }]);
        } catch (error) {
            setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${error instanceof Error ? error.message : 'Failed to get response'}`, timestamp: new Date() }]);
        } finally {
            setLoading(false);
        }
    };

    const handleSend = () => sendQuery(input);

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
    };

    const handleFeedback = async (msgIndex: number, wasHelpful: boolean) => {
        const msg = messages[msgIndex];
        if (!msg.queryId || msg.feedback) return;
        setMessages(prev => prev.map((m, i) =>
            i === msgIndex ? { ...m, feedback: wasHelpful ? 'up' : 'down' } : m
        ));
        try { await submitFeedback(msg.queryId, wasHelpful); } catch { /* silent */ }
    };

    return (
        <div style={styles.container}>
            {/* Header */}
            <div style={styles.header}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    {showSidebarButton && (
                        <button onClick={onOpenSidebar} style={styles.hamburger} title="Open filters">
                            ☰
                        </button>
                    )}
                    <h2 style={styles.title}>💬 Chat with Regulations</h2>
                </div>
                {messages.length > 0 && (
                    <button onClick={() => setMessages([])} style={styles.clearButton}>Clear</button>
                )}
            </div>

            {/* Messages */}
            <div style={styles.messagesContainer}>
                {messages.length === 0 && (
                    <div style={styles.emptyState}>
                        <div style={styles.emptyIcon}>🏎️</div>
                        <h3 style={styles.emptyTitle}>Ask a question about F1 regulations</h3>
                        <p style={styles.emptyText}>Try one of these examples or type your own:</p>
                        <div style={styles.exampleGrid}>
                            {EXAMPLE_QUERIES.map(q => (
                                <button key={q} style={styles.exampleChip} onClick={() => sendQuery(q)}>
                                    {q}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((msg, i) => (
                    <div key={i} style={styles.messageWrapper}>
                        <div style={getMessageStyle(msg.role)}>
                            <div style={styles.messageHeader}>
                                <span style={styles.messageRole}>{msg.role === 'user' ? '👤 You' : '🤖 Assistant'}</span>
                                <span style={styles.messageTime}>{msg.timestamp.toLocaleTimeString()}</span>
                            </div>
                            <div style={styles.messageContent}>
                                {viewSettings.showMarkdown
                                    ? <ReactMarkdown>{msg.content}</ReactMarkdown>
                                    : msg.content}
                            </div>
                            {msg.researchSteps && msg.researchSteps.length > 0 && (
                                <div style={styles.researchContainer}>
                                    <h5 style={styles.researchTitle}>🔍 Research Process</h5>
                                    {msg.researchSteps.map((step, si) => (
                                        <div key={si} style={styles.researchStep}>
                                            <div style={styles.researchThought}><strong>Step {step.step}:</strong> {step.thought}</div>
                                            {step.action === 'SEARCH' && (
                                                <div style={styles.researchAction}>📡 Searching: <code>{step.query}</code></div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                            {msg.role === 'assistant' && msg.queryId && (
                                <div style={styles.feedbackRow}>
                                    {msg.feedback ? (
                                        <span style={styles.feedbackThanks}>
                                            {msg.feedback === 'up' ? '✅ Thanks for the feedback!' : '🙏 Thanks, we\'ll improve!'}
                                        </span>
                                    ) : (
                                        <>
                                            <span style={styles.feedbackLabel}>Was this helpful?</span>
                                            <button
                                                onClick={() => handleFeedback(i, true)}
                                                style={styles.feedbackBtn}
                                                title="Helpful"
                                            >👍</button>
                                            <button
                                                onClick={() => handleFeedback(i, false)}
                                                style={styles.feedbackBtn}
                                                title="Not helpful"
                                            >👎</button>
                                        </>
                                    )}
                                </div>
                            )}
                        </div>
                        {msg.citations && msg.citations.length > 0 && (
                            <div style={{ ...styles.citations, ...(viewSettings.density === 'compact' ? { gap: '0.25rem' } : {}) }}>
                                <h4 style={styles.citationsTitle}>📚 Sources ({msg.citations.length})</h4>
                                {msg.citations.map((c, ci) => <CitationCard key={ci} citation={c} index={ci + 1} />)}
                            </div>
                        )}
                    </div>
                ))}

                {/* Loading indicator */}
                {loading && (
                    <div style={styles.loadingWrapper}>
                        <div style={styles.loadingDots}>
                            {[0, 1, 2].map(i => (
                                <div key={i} style={{ ...styles.dot, animationDelay: `${i * 0.2}s` }} />
                            ))}
                        </div>
                        <span style={styles.loadingText}>{LOADING_MESSAGES[loadingMsgIdx]}</span>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div style={styles.inputContainer}>
                <textarea
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Ask a question about F1 regulations..."
                    style={styles.textarea}
                    rows={3}
                    disabled={loading}
                />
                <button
                    onClick={handleSend}
                    disabled={!input.trim() || loading}
                    style={{ ...styles.sendButton, opacity: !input.trim() || loading ? 0.5 : 1 }}
                >
                    {loading ? '...' : 'Send →'}
                </button>
            </div>
        </div>
    );
}

const styles: Record<string, React.CSSProperties> = {
    container: { display: 'flex', flexDirection: 'column', height: '100%' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.85rem 1rem', borderBottom: '1px solid #333', flexShrink: 0 },
    title: { fontSize: '1.1rem', margin: 0 },
    hamburger: { background: 'transparent', border: '1px solid #444', borderRadius: '6px', color: '#aaa', padding: '0.35rem 0.6rem', fontSize: '1rem', cursor: 'pointer' },
    clearButton: { background: 'transparent', border: '1px solid #444', borderRadius: '6px', color: '#aaa', padding: '0.4rem 0.9rem', fontSize: '0.82rem', cursor: 'pointer' },
    messagesContainer: { flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' },
    emptyState: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, textAlign: 'center', padding: '2rem' },
    emptyIcon: { fontSize: '3.5rem', marginBottom: '1rem' },
    emptyTitle: { fontSize: '1.2rem', marginBottom: '0.5rem' },
    emptyText: { fontSize: '0.9rem', color: '#aaa', marginBottom: '1.5rem' },
    exampleGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem', maxWidth: '700px', width: '100%' },
    exampleChip: { background: '#111', border: '1px solid #333', borderRadius: '8px', color: '#ccc', padding: '0.75rem 1rem', fontSize: '0.85rem', cursor: 'pointer', textAlign: 'left', lineHeight: '1.4', transition: 'border-color 0.15s' },
    messageWrapper: { display: 'flex', flexDirection: 'column', gap: '0.75rem' },
    message: { borderRadius: '12px', padding: '1rem', maxWidth: '88%' },
    userMessage: { alignSelf: 'flex-end', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', marginLeft: 'auto' },
    assistantMessage: { alignSelf: 'flex-start', background: '#1a1a1a', border: '1px solid #333' },
    messageHeader: { display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.82rem', opacity: 0.8 },
    messageRole: { fontWeight: 'bold' },
    messageTime: { fontSize: '0.72rem', opacity: 0.6 },
    messageContent: { lineHeight: '1.6', whiteSpace: 'pre-wrap' },
    researchContainer: { marginTop: '0.75rem', padding: '0.75rem', background: '#0d0d0d', borderRadius: '8px', border: '1px solid #222', fontSize: '0.88rem' },
    researchTitle: { margin: '0 0 0.5rem 0', color: '#888', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' },
    researchStep: { marginBottom: '0.5rem', paddingLeft: '0.5rem', borderLeft: '2px solid #444' },
    researchThought: { color: '#ccc', marginBottom: '0.25rem' },
    researchAction: { color: '#667eea', fontSize: '0.82rem', fontStyle: 'italic' },
    citations: { marginLeft: '1rem', paddingLeft: '1rem', borderLeft: '3px solid #667eea' },
    citationsTitle: { fontSize: '0.88rem', marginBottom: '0.75rem', color: '#667eea' },
    loadingWrapper: { display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.75rem 1rem', background: '#111', border: '1px solid #222', borderRadius: '12px', alignSelf: 'flex-start', animation: 'fadeIn 0.3s ease' },
    loadingDots: { display: 'flex', gap: '4px', alignItems: 'center' },
    dot: { width: '7px', height: '7px', borderRadius: '50%', background: '#667eea', animation: 'bounce 1.2s infinite ease-in-out' },
    loadingText: { fontSize: '0.85rem', color: '#888' },
    inputContainer: { padding: '0.75rem 1rem', borderTop: '1px solid #333', display: 'flex', gap: '0.75rem', flexShrink: 0 },
    textarea: { flex: 1, background: '#0a0a0a', border: '1px solid #333', borderRadius: '8px', padding: '0.75rem', color: '#fff', fontSize: '0.92rem', resize: 'none', fontFamily: 'inherit' },
    sendButton: { background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', border: 'none', borderRadius: '8px', color: '#fff', padding: '0.75rem 1.5rem', fontSize: '0.95rem', fontWeight: 'bold', cursor: 'pointer', alignSelf: 'flex-end' },
    feedbackRow: { display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.75rem', paddingTop: '0.6rem', borderTop: '1px solid #2a2a2a' },
    feedbackLabel: { fontSize: '0.78rem', color: '#666' },
    feedbackBtn: { background: 'transparent', border: '1px solid #333', borderRadius: '6px', cursor: 'pointer', fontSize: '1rem', padding: '0.2rem 0.5rem', lineHeight: 1, transition: 'border-color 0.15s' },
    feedbackThanks: { fontSize: '0.78rem', color: '#888', fontStyle: 'italic' },
};
