'use client';

import { Citation } from '@/lib/api';
import { useState } from 'react';

interface CitationCardProps {
    citation: Citation;
    index: number;
}

export default function CitationCard({ citation, index }: CitationCardProps) {
    const [expanded, setExpanded] = useState(false);
    const [copied, setCopied] = useState(false);

    const excerpt = expanded
        ? citation.excerpt
        : citation.excerpt.slice(0, 200) + (citation.excerpt.length > 200 ? '...' : '');

    const handleCopy = async () => {
        const text = [
            `[${citation.article_code}] ${citation.title}`,
            `${citation.section} Regulations ${citation.year} -- Issue ${citation.issue}`,
            '',
            citation.excerpt,
        ].join('\n');
        try {
            await navigator.clipboard.writeText(text);
        } catch {
            const el = document.createElement('textarea');
            el.value = text;
            document.body.appendChild(el);
            el.select();
            document.execCommand('copy');
            document.body.removeChild(el);
        }
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div style={styles.card}>
            <div style={styles.header}>
                <div style={styles.headerLeft}>
                    <span style={styles.number}>{index}</span>
                    <span style={styles.code}>{citation.article_code}</span>
                </div>
                <div style={styles.headerRight}>
                    <span style={styles.badge}>{citation.section}</span>
                    <span style={styles.badge}>{citation.year}</span>
                    <span style={{ ...styles.badge, opacity: 0.7 }}>Issue {citation.issue}</span>
                    <button
                        onClick={handleCopy}
                        style={copied ? { ...styles.copyBtn, ...styles.copyBtnDone } : styles.copyBtn}
                        title="Copy citation"
                    >
                        {copied ? 'Copied!' : 'Copy'}
                    </button>
                </div>
            </div>

            <h4 style={styles.title}>{citation.title}</h4>
            <p style={styles.excerpt}>{excerpt}</p>

            {citation.excerpt.length > 200 && (
                <button onClick={() => setExpanded(!expanded)} style={styles.toggleBtn}>
                    {expanded ? 'Show less' : 'Show more'}
                </button>
            )}
        </div>
    );
}

const styles: Record<string, React.CSSProperties> = {
    card: { background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: '10px', padding: '1rem', marginBottom: '0.75rem' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem', flexWrap: 'wrap', gap: '0.5rem' },
    headerLeft: { display: 'flex', alignItems: 'center', gap: '0.5rem' },
    headerRight: { display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' },
    number: { background: '#667eea', color: '#fff', borderRadius: '50%', width: '22px', height: '22px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.72rem', fontWeight: 'bold', flexShrink: 0 },
    code: { fontFamily: 'monospace', fontSize: '0.9rem', color: '#eb0000', fontWeight: 'bold' },
    badge: { background: 'rgba(235,0,0,0.07)', border: '1px solid rgba(235,0,0,0.18)', borderRadius: '4px', padding: '0.15rem 0.45rem', fontSize: '0.68rem', color: '#ff6666', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em' },
    copyBtn: { background: 'transparent', border: '1px solid #444', borderRadius: '4px', color: '#888', padding: '0.15rem 0.5rem', fontSize: '0.7rem', cursor: 'pointer', whiteSpace: 'nowrap' },
    copyBtnDone: { borderColor: '#22c55e', color: '#22c55e' },
    title: { fontSize: '0.95rem', marginBottom: '0.6rem', color: '#e8e8e8', fontWeight: '600', lineHeight: '1.4' },
    excerpt: { fontSize: '0.87rem', lineHeight: '1.65', color: '#bbb', marginBottom: '0.5rem', paddingLeft: '0.85rem', borderLeft: '2px solid #333' },
    toggleBtn: { background: 'transparent', border: 'none', color: '#667eea', cursor: 'pointer', fontSize: '0.78rem', padding: 0 },
};
