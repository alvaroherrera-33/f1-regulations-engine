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

    return (
        <div style={styles.container}>
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
};
