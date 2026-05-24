'use client';

import { Citation } from '@/lib/api';
import { useState } from 'react';

interface CitationCardProps {
    citation: Citation;
    index: number;
}

const VALIDITY_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
    unchanged: { label: 'Current',          color: '#4ade80', bg: 'rgba(74,222,128,0.08)' },
    minor:     { label: 'Minor updates',    color: '#facc15', bg: 'rgba(250,204,21,0.08)' },
    major:     { label: 'Changed',          color: '#fb923c', bg: 'rgba(251,146,60,0.08)' },
    removed:   { label: 'May be obsolete',  color: '#94a3b8', bg: 'rgba(148,163,184,0.08)' },
};

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

    const validityConf = citation.validity ? VALIDITY_CONFIG[citation.validity] : null;
    // Only show badge for non-current articles or when there's something to communicate
    const showValidity = validityConf && citation.validity !== 'unchanged';

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
                    {showValidity && validityConf && (
                        <span style={{
                            ...styles.validityBadge,
                            color: validityConf.color,
                            background: validityConf.bg,
                            borderColor: validityConf.color + '33',
                        }}
                            title={
                                citation.validity === 'removed'
                                    ? `This article does not appear in ${citation.latest_year || 2026} regulations`
                                    : citation.validity === 'major'
                                    ? `This article was significantly changed by ${citation.latest_year || 2026}`
                                    : `Minor updates were made through ${citation.latest_year || 2026}`
                            }
                        >
                            {validityConf.label}
                        </span>
                    )}
                    <button
                        onClick={handleCopy}
                        style={copied ? { ...styles.copyBtn, ...styles.copyBtnDone } : styles.copyBtn}
                        title="Copy citation"
                    >
                        {copied ? 'Copied!' : 'Copy'}
                    </button>
                </div>
            </div>

            {citation.title && !/^\d+$/.test(citation.title.trim()) && (
                <h4 style={styles.title}>{citation.title}</h4>
            )}
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
    validityBadge: { borderRadius: '4px', padding: '0.12rem 0.45rem', fontSize: '0.65rem', fontWeight: 600, letterSpacing: '0.03em', border: '1px solid transparent', cursor: 'default' },
    copyBtn: { background: 'transparent', border: 'none', color: '#444', padding: '0.1rem 0.3rem', fontSize: '0.68rem', cursor: 'pointer', whiteSpace: 'nowrap', transition: 'color 0.15s' },
    copyBtnDone: { color: '#22c55e' },
    title: { fontSize: '0.85rem', marginBottom: '0.35rem', color: '#ccc', fontWeight: 500, lineHeight: 1.4 },
    excerpt: { fontSize: '0.8rem', lineHeight: 1.6, color: '#888', marginBottom: '0.3rem' },
    toggleBtn: { background: 'transparent', border: 'none', color: '#eb0000', cursor: 'pointer', fontSize: '0.72rem', padding: 0, opacity: 0.7 },
};
