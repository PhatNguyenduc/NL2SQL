import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Types matching backend API models
export interface SQLGenerationResponse {
  query: string;
  explanation: string;
  confidence: number;
  tables_used: string[];
  potential_issues?: string[];
}

export interface QueryExecutionResponse {
  success: boolean;
  rows?: Record<string, any>[];
  row_count: number;
  execution_time: number;
  columns?: string[];
  error_message?: string;
}

export interface ChatResponse {
  message_id: string;
  session_id: string;
  sql_generation: SQLGenerationResponse;
  execution?: QueryExecutionResponse;
  timestamp: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  execute_query?: boolean;
  temperature?: number;
}

export interface SchemaResponse {
  database_name: string;
  database_type: string;
  total_tables: number;
  tables: Record<string, any>;
}

export interface HealthResponse {
  status: string;
  database_connected: boolean;
  llm_configured: boolean;
  llm_provider?: string;
  llm_model?: string;
  tables?: number;
  timestamp: string;
}

// API functions
export const api = {
  // Health check
  async getHealth(): Promise<HealthResponse> {
    const response = await apiClient.get<HealthResponse>('/health');
    return response.data;
  },

  // Chat endpoint - main NL2SQL conversion
  async chat(request: ChatRequest): Promise<ChatResponse> {
    const response = await apiClient.post<ChatResponse>('/chat', request);
    return response.data;
  },

  // Get database schema
  async getSchema(): Promise<SchemaResponse> {
    const response = await apiClient.get<SchemaResponse>('/schema');
    return response.data;
  },

  // Get conversation history
  async getConversationHistory(sessionId: string, limit: number = 50) {
    const response = await apiClient.post('/conversation/history', {
      session_id: sessionId,
      limit,
    });
    return response.data;
  },

  // Analytics endpoints
  async getAnalyticsDashboard() {
    const response = await apiClient.get('/analytics/dashboard');
    return response.data;
  },

  async resetAnalytics() {
    const response = await apiClient.post('/analytics/reset');
    return response.data;
  },
};

export default api;

