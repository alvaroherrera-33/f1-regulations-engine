import UploadForm from '@/components/UploadForm';

export default function UploadPage() {
    return (
        <main style={styles.main}>
            <div style={styles.header}>
                <h1 style={styles.title}>
                    📄 Upload Regulations
                </h1>
                <p style={styles.subtitle}>
                    Upload FIA Formula 1 regulation PDFs for ingestion
                </p>
            </div>

            <UploadForm />

            <div style={styles.info}>
                <h3 style={styles.infoTitle}>Instructions</h3>
                <ul style={styles.list}>
                    <li>Select a PDF file containing FIA regulations</li>
                    <li>Specify the year, section, and issue number</li>
                    <li>Click Upload to begin processing</li>
                    <li>The system will parse articles and generate embeddings</li>
                </ul>
            </div>
        </main>
    );
}

const styles = {
    main: {
        padding: '2rem',
        maxWidth: '800px',
        margin: '0 auto',
    } as React.CSSProperties,

    header: {
        marginBottom: '2rem',
    } as React.CSSProperties,

    title: {
        fontSize: '2.5rem',
        marginBottom: '0.5rem',
    } as React.CSSProperties,

    subtitle: {
        fontSize: '1.1rem',
        opacity: 0.7,
    } as React.CSSProperties,

    info: {
        marginTop: '3rem',
        padding: '1.5rem',
        background: '#1a1a1a',
        border: '1px solid #333',
        borderRadius: '12px',
    } as React.CSSProperties,

    infoTitle: {
        marginBottom: '1rem',
        fontSize: '1.2rem',
    } as React.CSSProperties,

    list: {
        paddingLeft: '1.5rem',
        lineHeight: '1.8',
        opacity: 0.8,
    } as React.CSSProperties,
};
