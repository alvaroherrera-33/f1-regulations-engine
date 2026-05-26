/** API client for backend communication. */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ChatRequest {
    query: string;
    year?: number;
    section?: string;
    issue?: number;
}

export interface Citation {
    article_code: string;
    title: string;
    excerpt: string;
    year: number;
    section: string;
    issue: number;
    validity?: 'unchanged' | 'minor' | 'major' | 'removed' | null;
    latest_year?: number | null;
}

export interface ChatResponse {
    answer: string;
    citations: Citation[];
    retrieved_count: number;
    research_steps?: {
        step: number;
        thought: string;
        action: string;
        query: string;
    }[];
    query_id?: number;
    confidence?: number;  // 0-1, retrieval confidence
}

export interface UploadResponse {
    job_id: string;
    status: string;
    message: string;
}

export interface HealthResponse {
    status: string;
    timestamp: string;
    database: string;
}

/**
 * Upload a PDF file for ingestion
 */
export async function uploadPDF(
    file: File,
    year: number,
    section: string,
    issue: number
): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('year', year.toString());
    formData.append('section', section);
    formData.append('issue', issue.toString());

    const response = await fetch(`${API_URL}/api/upload`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Upload failed');
    }

    return response.json();
}

/**
 * Send a chat query
 */
export async function sendChatQuery(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${API_URL}/api/chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Chat query failed');
    }

    return response.json();
}

/**
 * Check API health
 */
export async function checkHealth(): Promise<HealthResponse> {
    const response = await fetch(`${API_URL}/health`);

    if (!response.ok) {
        throw new Error('Health check failed');
    }

    return response.json();
}

export interface StatusResponse {
    documents_count: number;
    articles_count: number;
    embeddings_count: number;
}

export interface StatsResponse {
    total_queries: number;
    regulation_queries: number;
    conversational_queries: number;
    errors: number;
    avg_response_ms: number;
    positive_feedback: number;
    negative_feedback: number;
    last_query_at: string | null;
}

/**
 * Get system indexing status
 */
export async function getStatus(): Promise<StatusResponse> {
    const response = await fetch(`${API_URL}/status`);
    if (!response.ok) throw new Error('Status check failed');
    return response.json();
}

/**
 * Submit thumbs-up / thumbs-down feedback for a chat response
 */
export async function submitFeedback(queryId: number, wasHelpful: boolean): Promise<void> {
    await fetch(`${API_URL}/api/chat/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query_id: queryId, was_helpful: wasHelpful }),
    });
}

/**
 * Get aggregate query statistics
 */
export async function getStats(): Promise<StatsResponse> {
    const response = await fetch(`${API_URL}/api/stats`);
    if (!response.ok) throw new Error('Stats fetch failed');
    return response.json();
}

export interface ExplainDiffResponse {
    article_code: string;
    year_a: number;
    year_b: number;
    section: string | null;
    version_a: ArticleVersion | null;
    version_b: ArticleVersion | null;
    explanation: string;
}

export interface ArticleVersion {
    article_code: string;
    title: string;
    content: string;
    year: number;
    section: string;
    issue: number;
}

/**
 * AI-powered explanation of the differences between two versions of a regulation article
 */
export async function explainDiff(
    code: string,
    yearA: number,
    yearB: number,
    section?: string
): Promise<ExplainDiffResponse> {
    let url = `${API_URL}/api/compare/explain?code=${encodeURIComponent(code)}&year_a=${yearA}&year_b=${yearB}`;
    if (section) url += `&section=${encodeURIComponent(section)}`;
    const response = await fetch(url, { method: 'POST' });
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error((error as { detail?: string }).detail || 'Explain diff failed');
    }
    return response.json();
}

export interface SyncStatusResponse {
    last_checked: string | null;
    total_fia_docs: number;
    new_docs_found: number;
    last_error: string | null;
    db_total_docs: number;
}

/**
 * Get FIA sync status (last time we checked fia.com for new PDFs)
 */
export async function getSyncStatus(): Promise<SyncStatusResponse> {
    const response = await fetch(`${API_URL}/api/sync/status`);
    if (!response.ok) throw new Error('Sync status fetch failed');
    return response.json();
}
