'use client';

import { useState } from 'react';
import ChatInterface from '@/components/ChatInterface';

export default function ChatPage() {
    const [year, setYear] = useState<number | null>(null);
    const [section, setSection] = useState<string | null>(null);
    const [issue, setIssue] = useState<number | null>(null);

    return (
        <div style={styles.container}>
            <ChatInterface
                year={year} section={section} issue={issue}
                onYearChange={setYear} onSectionChange={setSection} onIssueChange={setIssue}
            />
        </div>
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
