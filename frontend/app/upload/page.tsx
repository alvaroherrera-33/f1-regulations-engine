import UploadForm from '@/components/UploadForm';

export default function UploadPage() {
    return (
        <div style={styles.page}>
            <div style={styles.container}>
                <div style={styles.header}>
                    <h1 style={styles.title}>Upload regulations</h1>
                    <p style={styles.subtitle}>Upload FIA regulation PDFs for ingestion into the knowledge base</p>
                </div>
                <UploadForm />
            </div>
        </div>
    );
}

const styles: Record<string, React.CSSProperties> = {
    page: { minHeight: 'calc(100vh - 52px)', padding: '2rem 1rem' },
    container: { maxWidth: '560px', margin: '0 auto' },
    header: { marginBottom: '2rem' },
    title: { fontSize: '1.4rem', fontWeight: 600, color: '#fff', letterSpacing: '-0.02em', marginBottom: '0.3rem' },
    subtitle: { fontSize: '0.85rem', color: '#555' },
};
