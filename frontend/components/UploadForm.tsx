'use client';

import { useState } from 'react';
import { uploadPDF } from '@/lib/api';

export default function UploadForm() {
    const [file, setFile] = useState<File | null>(null);
    const [year, setYear] = useState<number>(2024);
    const [section, setSection] = useState<string>('Technical');
    const [issue, setIssue] = useState<number>(1);
    const [uploading, setUploading] = useState(false);
    const [message, setMessage] = useState<string>('');
    const [error, setError] = useState<string>('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!file) {
            setError('Please select a file');
            return;
        }

        setUploading(true);
        setError('');
        setMessage('');

        try {
            const response = await uploadPDF(file, year, section, issue);
            setMessage(response.message);
            setFile(null);
            // Reset form
            const fileInput = document.getElementById('file') as HTMLInputElement;
            if (fileInput) fileInput.value = '';
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Upload failed');
        } finally {
            setUploading(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} style={styles.form}>
            <h2 style={styles.title}>Upload Regulation PDF</h2>

            <div style={styles.field}>
                <label style={styles.label}>PDF File</label>
                <input
                    id="file"
                    type="file"
                    accept=".pdf"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    style={styles.fileInput}
                    disabled={uploading}
                />
            </div>

            <div style={styles.row}>
                <div style={styles.field}>
                    <label style={styles.label}>Year</label>
                    <input
                        type="number"
                        value={year}
                        onChange={(e) => setYear(parseInt(e.target.value))}
                        min="2000"
                        max="2100"
                        style={styles.input}
                        disabled={uploading}
                    />
                </div>

                <div style={styles.field}>
                    <label style={styles.label}>Section</label>
                    <select
                        value={section}
                        onChange={(e) => setSection(e.target.value)}
                        style={styles.input}
                        disabled={uploading}
                    >
                        <option value="Technical">Technical</option>
                        <option value="Sporting">Sporting</option>
                        <option value="Financial">Financial</option>
                        <option value="Power Unit">Power Unit</option>
                    </select>
                </div>

                <div style={styles.field}>
                    <label style={styles.label}>Issue</label>
                    <input
                        type="number"
                        value={issue}
                        onChange={(e) => setIssue(parseInt(e.target.value))}
                        min="1"
                        style={styles.input}
                        disabled={uploading}
                    />
                </div>
            </div>

            {error && (
                <div style={styles.error}>
                    ⚠️ {error}
                </div>
            )}

            {message && (
                <div style={styles.success}>
                    ✅ {message}
                </div>
            )}

            <button
                type="submit"
                disabled={uploading || !file}
                style={{
                    ...styles.button,
                    opacity: uploading || !file ? 0.5 : 1,
                    cursor: uploading || !file ? 'not-allowed' : 'pointer'
                }}
            >
                {uploading ? 'Uploading...' : 'Upload PDF'}
            </button>
        </form>
    );
}

const styles = {
    form: {
        background: '#0a0a0a',
        border: '1px solid #222',
        borderRadius: '20px',
        padding: '2.5rem',
        maxWidth: '650px',
        width: '100%',
        boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
    } as React.CSSProperties,

    title: {
        fontSize: '1.75rem',
        fontWeight: '900',
        marginBottom: '2rem',
        color: '#fff',
        letterSpacing: '-0.02em',
    } as React.CSSProperties,

    field: {
        marginBottom: '1.5rem',
        flex: '1',
    } as React.CSSProperties,

    row: {
        display: 'flex',
        gap: '1.25rem',
    } as React.CSSProperties,

    label: {
        display: 'block',
        marginBottom: '0.6rem',
        color: '#666',
        fontSize: '0.75rem',
        fontWeight: 'bold',
        textTransform: 'uppercase' as const,
        letterSpacing: '0.05em',
    } as React.CSSProperties,

    input: {
        width: '100%',
        padding: '0.85rem',
        background: '#111',
        border: '1px solid #333',
        borderRadius: '10px',
        color: '#fff',
        fontSize: '0.95rem',
        outline: 'none',
        transition: 'border-color 0.2s',
    } as React.CSSProperties,

    fileInput: {
        width: '100%',
        padding: '2rem',
        background: '#111',
        border: '2px dashed #333',
        borderRadius: '12px',
        color: '#888',
        fontSize: '0.9rem',
        textAlign: 'center' as const,
        cursor: 'pointer',
        transition: 'border-color 0.2s, background 0.2s',
    } as React.CSSProperties,

    button: {
        width: '100%',
        padding: '1.1rem',
        background: '#eb0000',
        border: 'none',
        borderRadius: '10px',
        color: '#fff',
        fontSize: '1rem',
        fontWeight: '900',
        marginTop: '1.5rem',
        textTransform: 'uppercase' as const,
        letterSpacing: '0.1em',
        transition: 'all 0.2s',
        boxShadow: '0 10px 30px rgba(235, 0, 0, 0.2)',
    } as React.CSSProperties,

    error: {
        padding: '1rem',
        background: 'rgba(239, 68, 68, 0.1)',
        border: '1px solid rgba(239, 68, 68, 0.3)',
        borderRadius: '10px',
        color: '#ef4444',
        marginTop: '1.5rem',
        fontSize: '0.9rem',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
    } as React.CSSProperties,

    success: {
        padding: '1rem',
        background: 'rgba(34, 197, 94, 0.1)',
        border: '1px solid rgba(34, 197, 94, 0.3)',
        borderRadius: '10px',
        color: '#22c55e',
        marginTop: '1.5rem',
        fontSize: '0.9rem',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
    } as React.CSSProperties,
};
