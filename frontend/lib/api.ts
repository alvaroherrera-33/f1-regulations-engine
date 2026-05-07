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
