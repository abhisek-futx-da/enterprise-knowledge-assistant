export type AnswerType = "grounded" | "refused" | "unverified" | "tool" | "direct";
export type SearchMode = "vector" | "bm25" | "hybrid";

export interface User {
  id: string;
  email: string;
  role: string;
  created_at: string;
}

export interface Doc {
  id: string;
  filename: string;
  content_type: string;
  status: "pending" | "ready" | "failed";
  error: string | null;
  num_pages: number;
  num_chunks: number;
  created_at: string;
}

export interface Citation {
  id: string;
  document_id: string;
  filename: string;
  page: number;
  chunk_index: number;
  snippet: string;
}

export interface ChatResult {
  answer: string;
  answer_type: AnswerType;
  route: string | null;
  grounded: boolean | null;
  citations: Citation[];
  tool_calls: { tool: string; args: Record<string, unknown> }[];
  trace: string[];
  conversation_id: string;
  cached: boolean;
}

export type StreamEvent =
  | { type: "start"; conversation_id: string }
  | { type: "step"; node: string; trace: string[] }
  | ({ type: "final" } & ChatResult)
  | { type: "error"; detail: string };

export interface SearchHit {
  chunk_id: string;
  document_id: string;
  filename: string;
  page: number;
  chunk_index: number;
  text: string;
  score: number;
  vector_score: number | null;
  bm25_score: number | null;
  ranks: Record<string, number>;
}

export interface Conversation {
  id: string;
  title: string;
  questions: number;
  created_at: string;
}

export interface StoredMessage {
  role: "user" | "assistant";
  content: string;
  answer_type: AnswerType | null;
  citations: Citation[] | null;
  created_at: string;
}

export interface WorkspaceStats {
  documents: number;
  documents_by_status: Record<string, number>;
  pages: number;
  chunks: number;
  conversations: number;
  questions: number;
  answers_by_type: Partial<Record<AnswerType, number>>;
}
