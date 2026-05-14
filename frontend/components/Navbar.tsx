'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_LINKS = [
    { href: '/',        label: 'Home' },
    { href: '/chat',    label: 'Chat' },
    { href: '/upload',  label: 'Upload' },
    { href: '/stats',   label: 'Stats' },
    { href: '/about',   label: 'About' },
    { href: '/docs',    label: 'API Docs', external: true },
];

export default function Navbar() {
    const pathname = usePathname();

    return (
        <nav style={styles.nav}>
            <Link href="/" style={styles.logo}>
                <span style={styles.logoIcon}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#eb0000" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 17h14M5 17l-1-4h16l-1 4M5 17H3v2h18v-2h-2M7 13l1.5-6h7L17 13M9 17v2M15 17v2"/></svg>
                </span>
                <span style={styles.logoText}>
                    F1 Regs <span style={styles.logoAccent}>Engine</span>
                </span>
            </Link>

            <div style={styles.links}>
                {NAV_LINKS.map(({ href, label, external }) => {
                    const isActive = href === '/'
                        ? pathname === '/'
                        : pathname.startsWith(href);

                    const linkProps = external
                        ? { target: '_blank', rel: 'noopener noreferrer' }
                        : {};

                    // External docs link points to the API backend
                    const resolvedHref = external
                        ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + href
                        : href;

                    return (
                        <Link
                            key={href}
                            href={resolvedHref}
                            style={{
                                ...styles.link,
                                ...(isActive ? styles.linkActive : {}),
                            }}
                            {...linkProps}
                        >
                            {label}
                            {isActive && <span style={styles.activeBar} />}
                        </Link>
                    );
                })}
            </div>
        </nav>
    );
}

const styles = {
    nav: {
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: '60px',
        background: '#0a0a0a',
        borderBottom: '1px solid #222',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 1.5rem',
        zIndex: 200,
    } as React.CSSProperties,

    logo: {
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        textDecoration: 'none',
    } as React.CSSProperties,

    logoIcon: {
        fontSize: '1.4rem',
    } as React.CSSProperties,

    logoText: {
        fontSize: '1rem',
        fontWeight: '700',
        color: '#fff',
        letterSpacing: '-0.01em',
    } as React.CSSProperties,

    logoAccent: {
        color: '#eb0000',
    } as React.CSSProperties,

    links: {
        display: 'flex',
        alignItems: 'center',
        gap: '0.25rem',
    } as React.CSSProperties,

    link: {
        position: 'relative',
        padding: '0.4rem 0.85rem',
        fontSize: '0.9rem',
        color: '#aaa',
        textDecoration: 'none',
        borderRadius: '6px',
        transition: 'color 0.15s',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
    } as React.CSSProperties,

    linkActive: {
        color: '#fff',
        fontWeight: '600',
    } as React.CSSProperties,

    activeBar: {
        position: 'absolute',
        bottom: '-1px',
        left: '0.85rem',
        right: '0.85rem',
        height: '2px',
        background: '#eb0000',
        borderRadius: '1px',
    } as React.CSSProperties,
};
