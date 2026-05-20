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
            '[' + citation.article_code + '] ' + citation.title,
            citation.section + ' Regulations ' + citation.year + ' - Issue ' + citation.issue,
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
    card: { background: 'transparent', borderBottom: '1px solid rgba(255,255,255,0.06)', padding: '0.75rem 0', marginBottom: '0' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem', flexWrap: 'wrap', gap: '0.4rem' },
    headerLeft: { display: 'flex', alignItems: 'center', gap: '0.4rem' },
    headerRight: { display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' },
    number: { color: '#555', fontSize: '0.7rem', fontWeight: 500, flexShrink: 0, fontVariantNumeric: 'tabular-nums' },
    code: { fontFamily: 'monospace', fontSize: '0.82rem', color: '#eb0000', fontWeight: 600 },
    badge: { background: 'rgba(255,255,255,0.04)', borderRadius: '4px', padding: '0.12rem 0.4rem', fontSize: '0.68rem', color: '#666', fontWeight: 500, letterSpacing: '0.02em' },
    copyBtn: { background: 'transparent', border: 'none', color: '#444', padding: '0.1rem 0.3rem', fontSize: '0.68rem', cursor: 'pointer', whiteSpace: 'nowrap', transition: 'color 0.15s' },
    copyBtnDone: { color: '#22c55e' },
    title: { fontSize: '0.85rem', marginBottom: '0.35rem', color: '#ccc', fontWeight: 500, lineHeight: 1.4 },
    excerpt: { fontSize: '0.8rem', lineHeight: 1.6, color: '#888', marginBottom: '0.3rem' },
    toggleBtn: { background: 'transparent', border: 'none', color: '#eb0000', cursor: 'pointer', fontSize: '0.72rem', padding: 0, opacity: 0.7 },
};
