'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import ChatInterface from '@/components/ChatInterface';

function ChatPageInner() {
    const params = useSearchParams();
    const [year, setYear] = useState<number | null>(() => {
        const y = params.get('year');
        return y ? parseInt(y, 10) : null;
    });
    const [section, setSection] = useState<string | null>(() => params.get('section'));
    const [issue, setIssue] = useState<number | null>(null);
    const initialQuery = params.get('q') || undefined;
    const [showBeta, setShowBeta] = useState(true);

    return (
        <div style={styles.container}>
            {showBeta && (
                <div style={styles.betaBanner}>
                    <span style={styles.betaTag}>BETA v0.1</span>
                    <span style={styles.betaText}>
                        Early release — answers may contain errors. Always verify against the official FIA document.
                    </span>
                    <button
                        onClick={() => setShowBeta(false)}
                        style={styles.betaClose}
                        aria-label="Dismiss beta notice"
                    >
                        &times;
                    </button>
                </div>
            )}
            <ChatInterface
                year={year} section={section} issue={issue}
                onYearChange={setYear} onSectionChange={setSection} onIssueChange={setIssue}
                initialQuery={initialQuery}
            />
        </div>
    );
}

export default function ChatPage() {
    return (
        <Suspense fallback={<div style={styles.container} />}>
            <ChatPageInner />
        </Suspense>
    );
}

const styles: Record<string, React.CSSProperties> = {
    container: {
        maxWidth: '820px',
        margin: '0 auto',
        height: 'calc(100vh - 52px)',
        display: 'flex',
        flexDirection: 'column',
        padding: '0 1rem',
    },
    betaBanner: {
        display: 'flex',
        alignItems: 'center',
        gap: '0.6rem',
        margin: '0.75rem 0 0',
        padding: '0.55rem 0.85rem',
        background: 'rgba(235, 0, 0, 0.07)',
        border: '1px solid rgba(235, 0, 0, 0.22)',
        borderRadius: '8px',
        fontSize: '0.8rem',
        lineHeight: 1.4,
    },
    betaTag: {
        flexShrink: 0,
        fontWeight: 700,
        fontSize: '0.68rem',
        letterSpacing: '0.05em',
        color: '#eb0000',
        background: 'rgba(235, 0, 0, 0.12)',
        padding: '0.15rem 0.45rem',
        borderRadius: '5px',
    },
    betaText: {
        flex: 1,
        color: '#999',
    },
    betaClose: {
        flexShrink: 0,
        background: 'none',
        border: 'none',
        fontSize: '1.1rem',
        lineHeight: 1,
        color: '#999',
        cursor: 'pointer',
        padding: '0 0.2rem',
    },
};
