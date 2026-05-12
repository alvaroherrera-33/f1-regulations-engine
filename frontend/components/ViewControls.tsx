'use client';

interface ViewSettings {
    showMarkdown: boolean;
    density: 'standard' | 'compact';
    fontSize: 'small' | 'medium' | 'large';
}

interface ViewControlsProps {
    settings: ViewSettings;
    onSettingsChange: (settings: ViewSettings) => void;
}

export default function ViewControls({ settings, onSettingsChange }: ViewControlsProps) {
    return (
        <div style={styles.container}>
            <h3 style={styles.title}>View Settings</h3>
            
            <div style={styles.controlGroup}>
                <label style={styles.label}>
                    <input
                        type="checkbox"
                        checked={settings.showMarkdown}
                        onChange={(e) => onSettingsChange({ ...settings, showMarkdown: e.target.checked })}
                        style={styles.checkbox}
                    />
                    Render Markdown
                </label>
            </div>

            <div style={styles.controlGroup}>
                <span style={styles.label}>Density</span>
                <div style={styles.buttonGroup}>
                    {(['standard', 'compact'] as const).map((d) => (
                        <button
                            key={d}
                            onClick={() => onSettingsChange({ ...settings, density: d })}
                            style={{
                                ...styles.button,
                                ...(settings.density === d ? styles.activeButton : {}),
                            }}
                        >
                            {d.charAt(0).toUpperCase() + d.slice(1)}
                        </button>
                    ))}
                </div>
            </div>

            <div style={styles.controlGroup}>
                <span style={styles.label}>Text Size</span>
                <div style={styles.buttonGroup}>
                    {(['small', 'medium', 'large'] as const).map((s) => (
                        <button
                            key={s}
                            onClick={() => onSettingsChange({ ...settings, fontSize: s })}
                            style={{
                                ...styles.button,
                                ...(settings.fontSize === s ? styles.activeButton : {}),
                            }}
                        >
                            {s.charAt(0).toUpperCase() + s.slice(1)}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}

const styles = {
    container: {
        background: '#0a0a0a',
        border: '1px solid #222',
        borderRadius: '12px',
        padding: '1.25rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
    } as React.CSSProperties,

    title: {
        fontSize: '0.75rem',
        margin: 0,
        marginBottom: '0.5rem',
        color: '#666',
        fontWeight: 'bold',
        textTransform: 'uppercase' as const,
        letterSpacing: '0.05em',
    } as React.CSSProperties,

    controlGroup: {
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
    } as React.CSSProperties,

    label: {
        fontSize: '0.75rem',
        color: '#aaa',
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        fontWeight: '500',
    } as React.CSSProperties,

    checkbox: {
        cursor: 'pointer',
        accentColor: '#eb0000',
    } as React.CSSProperties,

    buttonGroup: {
        display: 'flex',
        gap: '2px',
        background: '#1a1a1a',
        padding: '2px',
        borderRadius: '8px',
        border: '1px solid #333',
    } as React.CSSProperties,

    button: {
        flex: 1,
        background: 'transparent',
        border: 'none',
        borderRadius: '6px',
        color: '#666',
        padding: '0.5rem',
        fontSize: '0.75rem',
        fontWeight: 'bold',
        cursor: 'pointer',
        transition: 'all 0.2s',
    } as React.CSSProperties,

    activeButton: {
        background: '#eb0000',
        color: '#fff',
    } as React.CSSProperties,
};
