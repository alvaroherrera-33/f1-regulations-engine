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
        if (!file) { setError('Please select a file'); return; }
        setUploading(true);
        setError('');
        setMessage('');
        try {
            const response = await uploadPDF(file, year, section, issue);
            setMessage(response.message);
            setFile(null);
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
                    <input type="number" value={year} onChange={(e) => setYear(parseInt(e.target.value))} min="2000" max="2100" style={styles.input} disabled={uploading} />
                </div>
                <div style={styles.field}>
                    <label style={styles.label}>Section</label>
                    <select value={section} onChange={(e) => setSection(e.target.value)} style={styles.input} disabled={uploading}>
                        <option value="Technical">Technical</option>
                        <option value="Sporting">Sporting</option>
                        <option value="Financial">Financial</option>
                        <option value="Power Unit">Power Unit</option>
                    </select>
                </div>
                <div style={styles.field}>
                    <label style={styles.label}>Issue</label>
                    <input type="number" value={issue} onChange={(e) => setIssue(parseInt(e.target.value))} min="1" style={styles.input} disabled={uploading} />
                </div>
            </div>

            {error && <p style={styles.error}>{error}</p>}
            {message && <p style={styles.success}>{message}</p>}

            <button
                type="submit"
                disabled={uploading || !file}
                style={{ ...styles.button, opacity: uploading || !file ? 0.4 : 1, cursor: uploading || !file ? 'not-allowed' : 'pointer' }}
            >
                {uploading ? 'Uploading...' : 'Upload'}
            </button>
        </form>
    );
}

const styles: Record<string, React.CSSProperties> = {
    form: { border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px', padding: '1.5rem' },

    field: { marginBottom: '1rem', flex: 1 },
    row: { display: 'flex', gap: '0.75rem' },
    label: { display: 'block', marginBottom: '0.4rem', color: '#555', fontSize: '0.72rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.06em' },
    input: { width: '100%', padding: '0.5rem 0.75rem', background: '#111', border: '1px solid #222', borderRadius: '8px', color: '#e0e0e0', fontSize: '0.85rem', outline: 'none', transition: 'border-color 0.15s' },
    fileInput: { width: '100%', padding: '1.25rem', background: '#111', border: '1px dashed #222', borderRadius: '8px', color: '#666', fontSize: '0.85rem', cursor: 'pointer', transition: 'border-color 0.15s' },

    button: { width: '100%', padding: '0.6rem', background: '#eb0000', border: 'none', borderRadius: '8px', color: '#fff', fontSize: '0.85rem', fontWeight: 600, marginTop: '0.5rem', transition: 'opacity 0.15s' },

    error: { color: '#eb0000', fontSize: '0.82rem', marginTop: '0.75rem' },
    success: { color: '#4ade80', fontSize: '0.82rem', marginTop: '0.75rem' },
};
