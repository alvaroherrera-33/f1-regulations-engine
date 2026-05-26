'use client';

import { useState, useRef } from 'react';
import { uploadPDF } from '@/lib/api';

type Stage = 'idle' | 'uploading' | 'ingesting' | 'done' | 'error';

const STEPS = [
    { id: 'upload',  label: 'Upload PDF' },
    { id: 'ingest',  label: 'Parse & embed' },
    { id: 'done',    label: 'Complete' },
];

function stageToStep(stage: Stage): number {
    if (stage === 'idle' || stage === 'error') return 0;
    if (stage === 'uploading') return 1;
    if (stage === 'ingesting') return 2;
    return 3; // done
}

export default function UploadForm() {
    const [file, setFile] = useState<File | null>(null);
    const [year, setYear] = useState<number>(2024);
    const [section, setSection] = useState<string>('Technical');
    const [issue, setIssue] = useState<number>(1);
    const [stage, setStage] = useState<Stage>('idle');
    const [message, setMessage] = useState<string>('');
    const [error, setError] = useState<string>('');
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFile(e.target.files?.[0] || null);
        setError('');
        setMessage('');
        setStage('idle');
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!file) { setError('Please select a file'); return; }
        setStage('uploading');
        setError('');
        setMessage('');
        try {
            // Stage 1: upload the file
            const response = await uploadPDF(file, year, section, issue);

            // Stage 2: ingestion runs async on the backend — show intermediate state
            setStage('ingesting');
            await new Promise(resolve => setTimeout(resolve, 1800));

            // Stage 3: done
            setStage('done');
            setMessage(response.message);
            setFile(null);
            if (fileInputRef.current) fileInputRef.current.value = '';
        } catch (err) {
            setStage('error');
            setError(err instanceof Error ? err.message : 'Upload failed');
        }
    };

    const reset = () => {
        setStage('idle');
        setError('');
        setMessage('');
    };

    const uploading = stage === 'uploading' || stage === 'ingesting';
    const activeStep = stageToStep(stage);

    return (
        <form onSubmit={handleSubmit} style={styles.form}>
            {/* Step indicator */}
            <div style={styles.steps}>
                {STEPS.map((step, i) => {
                    const done = activeStep > i + 1;
                    const active = activeStep === i + 1;
                    return (
                        <div key={step.id} style={styles.stepItem}>
                            <div style={{
                                ...styles.stepCircle,
                                background: done ? '#eb0000' : active ? 'rgba(235,0,0,0.12)' : 'transparent',
                                border: `1.5px solid ${done || active ? '#eb0000' : '#2a2a2a'}`,
                                color: done ? '#fff' : active ? '#eb0000' : '#444',
                            }}>
                                {done ? (
                                    <svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                        <polyline points="2 6 5 9 10 3" />
                                    </svg>
                                ) : (
                                    <span style={{ fontSize: '0.6rem', fontWeight: 700 }}>{i + 1}</span>
                                )}
                            </div>
                            <span style={{
                                ...styles.stepLabel,
                                color: done || active ? (done ? '#888' : '#ccc') : '#333',
                            }}>{step.label}</span>
                            {i < STEPS.length - 1 && (
                                <div style={{
                                    ...styles.stepLine,
                                    background: done ? '#eb0000' : '#1e1e1e',
                                }} />
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Custom file input */}
            <div style={styles.field}>
                <label style={styles.label}>PDF File</label>
                <input
                    ref={fileInputRef}
                    id="file"
                    type="file"
                    accept=".pdf"
                    onChange={handleFileChange}
                    style={styles.hiddenInput}
                    disabled={uploading}
                />
                <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                    style={styles.fileArea}
                >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, opacity: 0.5 }}>
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="17 8 12 3 7 8"/>
                        <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                    <span style={file ? styles.fileName : styles.filePlaceholder}>
                        {file ? file.name : 'Click to select a PDF file'}
                    </span>
                </button>
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

            {error && (
                <div style={styles.errorBox}>
                    <p style={styles.errorText}>{error}</p>
                    <button type="button" onClick={reset} style={styles.retryBtn}>Try again</button>
                </div>
            )}

            {stage === 'done' && message && (
                <div style={styles.successBox}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <div>
                        <p style={styles.successText}>{message}</p>
                        <p style={styles.successNote}>Articles will be searchable within a few seconds.</p>
                    </div>
                    <button type="button" onClick={reset} style={styles.uploadAnotherBtn}>Upload another</button>
                </div>
            )}

            {stage !== 'done' && (
                <button
                    type="submit"
                    disabled={uploading || !file}
                    style={{ ...styles.button, opacity: uploading || !file ? 0.4 : 1, cursor: uploading || !file ? 'not-allowed' : 'pointer' }}
                >
                    {stage === 'uploading' && (
                        <><span style={styles.spinner} />Uploading…</>
                    )}
                    {stage === 'ingesting' && (
                        <><span style={styles.spinner} />Parsing &amp; embedding…</>
                    )}
                    {(stage === 'idle' || stage === 'error') && 'Upload'}
                </button>
            )}
        </form>
    );
}

const styles: Record<string, React.CSSProperties> = {
    form: { border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px', padding: '1.5rem' },

    // Step indicator
    steps: { display: 'flex', alignItems: 'center', marginBottom: '1.75rem' },
    stepItem: { display: 'flex', alignItems: 'center', flex: 1, gap: '0.4rem' },
    stepCircle: {
        width: '22px', height: '22px', borderRadius: '50%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0, transition: 'all 0.2s',
    },
    stepLabel: { fontSize: '0.7rem', fontWeight: 500, whiteSpace: 'nowrap', transition: 'color 0.2s' },
    stepLine: { flex: 1, height: '1px', marginLeft: '0.4rem', transition: 'background 0.2s' },

    field: { marginBottom: '1rem', flex: 1 },
    row: { display: 'flex', gap: '0.75rem' },
    label: { display: 'block', marginBottom: '0.4rem', color: '#666', fontSize: '0.72rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.06em' },

    hiddenInput: { display: 'none' },
    fileArea: {
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        padding: '1rem 1.25rem',
        background: '#111',
        border: '1px dashed #2a2a2a',
        borderRadius: '8px',
        cursor: 'pointer',
        transition: 'border-color 0.15s',
        textAlign: 'left',
    } as React.CSSProperties,
    filePlaceholder: { fontSize: '0.85rem', color: '#666' },
    fileName: { fontSize: '0.85rem', color: '#ccc', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } as React.CSSProperties,

    input: { width: '100%', padding: '0.5rem 0.75rem', background: '#111', border: '1px solid #222', borderRadius: '8px', color: '#e0e0e0', fontSize: '0.85rem', outline: 'none', transition: 'border-color 0.15s' },

    button: {
        width: '100%', padding: '0.6rem', background: '#eb0000', border: 'none',
        borderRadius: '8px', color: '#fff', fontSize: '0.85rem', fontWeight: 600,
        marginTop: '0.5rem', transition: 'opacity 0.15s',
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem',
    },
    spinner: {
        display: 'inline-block', width: '10px', height: '10px',
        border: '1.5px solid rgba(255,255,255,0.3)', borderTopColor: '#fff',
        borderRadius: '50%', animation: 'spin 0.7s linear infinite',
    },

    errorBox: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', background: 'rgba(235,0,0,0.06)', border: '1px solid rgba(235,0,0,0.2)', borderRadius: '8px', padding: '0.75rem 1rem', marginTop: '0.75rem' },
    errorText: { color: '#eb0000', fontSize: '0.82rem', margin: 0 },
    retryBtn: { background: 'transparent', border: '1px solid rgba(235,0,0,0.3)', borderRadius: '6px', color: '#eb0000', padding: '0.25rem 0.6rem', fontSize: '0.72rem', cursor: 'pointer', whiteSpace: 'nowrap' },

    successBox: { display: 'flex', alignItems: 'flex-start', gap: '0.6rem', background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.2)', borderRadius: '8px', padding: '0.75rem 1rem', marginTop: '0.75rem' },
    successText: { color: '#4ade80', fontSize: '0.82rem', margin: 0, marginBottom: '0.15rem' },
    successNote: { color: '#555', fontSize: '0.75rem', margin: 0 },
    uploadAnotherBtn: { background: 'transparent', border: '1px solid rgba(74,222,128,0.3)', borderRadius: '6px', color: '#4ade80', padding: '0.25rem 0.6rem', fontSize: '0.72rem', cursor: 'pointer', whiteSpace: 'nowrap', marginLeft: 'auto', flexShrink: 0 },

    error: { color: '#eb0000', fontSize: '0.82rem', marginTop: '0.75rem' },
    success: { color: '#4ade80', fontSize: '0.82rem', marginTop: '0.75rem' },
};
