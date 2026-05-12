'use client';

import { useState, useEffect } from 'react';
import ChatInterface from '@/components/ChatInterface';
import FilterControls from '@/components/FilterControls';
import ViewControls from '@/components/ViewControls';

export default function ChatPage() {
    const [year, setYear] = useState<number | null>(null);
    const [section, setSection] = useState<string | null>(null);
    const [issue, setIssue] = useState<number | null>(null);
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [isMobile, setIsMobile] = useState(false);

    const [viewSettings, setViewSettings] = useState<{
        showMarkdown: boolean;
        density: 'standard' | 'compact';
        fontSize: 'small' | 'medium' | 'large';
    }>({ showMarkdown: true, density: 'standard', fontSize: 'medium' });

    useEffect(() => {
        const check = () => setIsMobile(window.innerWidth < 768);
        check();
        window.addEventListener('resize', check);
        return () => window.removeEventListener('resize', check);
    }, []);

    // Close sidebar when switching from mobile to desktop
    useEffect(() => {
        if (!isMobile) setSidebarOpen(false);
    }, [isMobile]);

    const clearFilters = () => { setYear(null); setSection(null); setIssue(null); };

    const sidebarVisible = !isMobile || sidebarOpen;

    return (
        <div style={styles.container}>
            {/* Overlay (mobile) */}
            {isMobile && sidebarOpen && (
                <div style={styles.overlay} onClick={() => setSidebarOpen(false)} />
            )}

            {/* Sidebar */}
            {sidebarVisible && (
                <div style={{
                    ...styles.sidebar,
                    ...(isMobile ? styles.sidebarMobile : {}),
                }}>
                    {isMobile && (
                        <button style={styles.closeSidebar} onClick={() => setSidebarOpen(false)}>
                            ✕ Close
                        </button>
                    )}
                    <div style={styles.sidebarHeader}>
                        <h2 style={styles.sidebarTitle}>Controls</h2>
                        <p style={styles.sidebarSubtitle}>Manage search and display preferences</p>
                    </div>
                    <FilterControls
                        year={year} section={section} issue={issue}
                        onYearChange={setYear} onSectionChange={setSection}
                        onIssueChange={setIssue} onClear={clearFilters}
                    />
                    <ViewControls settings={viewSettings} onSettingsChange={setViewSettings} />
                    <div style={styles.info}>
                        <h3 style={styles.infoTitle}>Tips</h3>
                        <ul style={styles.infoList}>
                            <li>Be specific in your questions</li>
                            <li>Autofilter detects year/section automatically</li>
                            <li>Check citations for exact references</li>
                        </ul>
                    </div>
                    <a href="/stats" style={styles.statsLink}>View System Stats</a>
                </div>
            )}

            {/* Main chat area */}
            <div style={styles.main}>
                <ChatInterface
                    year={year} section={section} issue={issue}
                    viewSettings={viewSettings}
                    onOpenSidebar={isMobile ? () => setSidebarOpen(true) : undefined}
                    showSidebarButton={isMobile}
                />
            </div>
        </div>
    );
}

const styles: Record<string, React.CSSProperties> = {
    container: { display: 'flex', height: 'calc(100vh - 60px)', overflow: 'hidden', position: 'relative' },
    overlay: { position: 'fixed', inset: 0, top: '60px', background: 'rgba(0,0,0,0.6)', zIndex: 99 },
    sidebar: { width: '300px', background: '#0a0a0a', borderRight: '1px solid #333', padding: '1.25rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1.25rem', flexShrink: 0 },
    sidebarMobile: { position: 'fixed', top: '60px', left: 0, bottom: 0, zIndex: 100, boxShadow: '4px 0 20px rgba(0,0,0,0.8)' },
    closeSidebar: { background: 'transparent', border: '1px solid #444', borderRadius: '6px', color: '#aaa', padding: '0.4rem 0.75rem', fontSize: '0.8rem', cursor: 'pointer', alignSelf: 'flex-end' },
    sidebarHeader: { marginBottom: '0.25rem' },
    sidebarTitle: { fontSize: '1.1rem', marginBottom: '0.4rem' },
    sidebarSubtitle: { fontSize: '0.8rem', color: '#aaa', lineHeight: '1.4' },
    info: { background: '#1a1a1a', border: '1px solid #333', borderRadius: '8px', padding: '1rem' },
    infoTitle: { fontSize: '0.9rem', marginBottom: '0.6rem' },
    infoList: { fontSize: '0.82rem', lineHeight: '1.8', color: '#aaa', paddingLeft: '1.1rem', margin: 0 },
    statsLink: { display: 'block', textAlign: 'center' as const, color: '#eb0000', fontSize: '0.82rem', textDecoration: 'none', padding: '0.5rem', border: '1px solid #222', borderRadius: '6px' },
    main: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 },
};
