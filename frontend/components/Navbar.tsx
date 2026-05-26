'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_LINKS = [
    { href: '/chat',    label: 'Chat' },
    { href: '/compare', label: 'Compare' },
    { href: '/about',   label: 'About' },
];

export default function Navbar() {
    const pathname = usePathname();

    return (
        <nav style={styles.nav}>
            <Link href="/" style={styles.logo}>
                <span style={styles.logoText}>
                    F1 Regs <span style={styles.logoAccent}>Engine</span>
                </span>
            </Link>

            <div style={styles.links}>
                {NAV_LINKS.map(({ href, label }) => {
                    const isActive = pathname.startsWith(href);
                    return (
                        <Link
                            key={href}
                            href={href}
                            style={{
                                ...styles.link,
                                ...(isActive ? styles.linkActive : {}),
                            }}
                        >
                            {label}
                        </Link>
                    );
                })}
            </div>
        </nav>
    );
}

const styles: Record<string, React.CSSProperties> = {
    nav: {
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: '52px',
        background: 'rgba(12,12,12,0.8)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 1.25rem',
        zIndex: 200,
    },
    logo: {
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        textDecoration: 'none',
    },
    logoText: {
        fontSize: '0.92rem',
        fontWeight: 700,
        color: '#fff',
        letterSpacing: '-0.01em',
    },
    logoAccent: {
        color: '#eb0000',
    },
    links: {
        display: 'flex',
        alignItems: 'center',
        gap: '0.15rem',
    },
    link: {
        padding: '0.35rem 0.75rem',
        fontSize: '0.82rem',
        color: '#666',
        textDecoration: 'none',
        borderRadius: '8px',
        transition: 'color 0.15s',
    },
    linkActive: {
        color: '#fff',
        fontWeight: 600,
        background: 'rgba(255,255,255,0.07)',
    },
};
