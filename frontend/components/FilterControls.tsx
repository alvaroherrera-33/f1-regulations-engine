'use client';

interface FilterControlsProps {
    year: number | null;
    section: string | null;
    issue: number | null;
    onYearChange: (year: number | null) => void;
    onSectionChange: (section: string | null) => void;
    onIssueChange: (issue: number | null) => void;
    onClear: () => void;
}

export default function FilterControls({
    year,
    section,
    issue,
    onYearChange,
    onSectionChange,
    onIssueChange,
    onClear,
}: FilterControlsProps) {
    return (
        <div style={styles.container}>
            <div style={styles.filters}>
                <div style={styles.filter}>
                    <label style={styles.label}>Year</label>
                    <select
                        value={year || ''}
                        onChange={(e) => onYearChange(e.target.value ? parseInt(e.target.value) : null)}
                        style={styles.select}
                    >
                        <option value="">All Years</option>
                        <option value="2026">2026</option>
                        <option value="2025">2025</option>
                        <option value="2024">2024</option>
                    </select>
                </div>

                <div style={styles.filter}>
                    <label style={styles.label}>Section</label>
                    <select
                        value={section || ''}
                        onChange={(e) => onSectionChange(e.target.value || null)}
                        style={styles.select}
                    >
                        <option value="">All Sections</option>
                        <option value="Technical">Technical</option>
                        <option value="Sporting">Sporting</option>
                        <option value="Financial">Financial</option>
                        <option value="Power Unit">Power Unit</option>
                    </select>
                </div>

                <div style={styles.filter}>
                    <label style={styles.label}>Issue</label>
                    <input
                        type="number"
                        value={issue || ''}
                        onChange={(e) => onIssueChange(e.target.value ? parseInt(e.target.value) : null)}
                        placeholder="All"
                        min="1"
                        style={styles.input}
                    />
                </div>
            </div>

            <button onClick={onClear} style={styles.clearButton}>
                Clear Filters
            </button>
        </div>
    );
}

const styles = {
    container: {
        background: '#0a0a0a',
        border: '1px solid #222',
        borderRadius: '12px',
        padding: '1.25rem',
        marginBottom: '1rem',
    } as React.CSSProperties,

    filters: {
        display: 'flex',
        flexDirection: 'column' as const,
        gap: '1.25rem',
        marginBottom: '1.5rem',
    } as React.CSSProperties,

    filter: {
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
    } as React.CSSProperties,

    label: {
        fontSize: '0.75rem',
        color: '#666',
        fontWeight: 'bold',
        textTransform: 'uppercase' as const,
        letterSpacing: '0.05em',
    } as React.CSSProperties,

    select: {
        background: '#111',
        border: '1px solid #333',
        borderRadius: '8px',
        padding: '0.75rem',
        color: '#fff',
        fontSize: '0.9rem',
        outline: 'none',
        transition: 'border-color 0.2s',
    } as React.CSSProperties,

    input: {
        background: '#111',
        border: '1px solid #333',
        borderRadius: '8px',
        padding: '0.75rem',
        color: '#fff',
        fontSize: '0.9rem',
        outline: 'none',
        transition: 'border-color 0.2s',
    } as React.CSSProperties,

    clearButton: {
        background: 'transparent',
        border: '1px solid #333',
        borderRadius: '8px',
        color: '#888',
        padding: '0.75rem 1rem',
        fontSize: '0.85rem',
        fontWeight: 'bold',
        cursor: 'pointer',
        transition: 'all 0.2s',
        width: '100%',
    } as React.CSSProperties,
};
