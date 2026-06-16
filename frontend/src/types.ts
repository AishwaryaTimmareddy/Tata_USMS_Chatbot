export type Citation = {
  title: string;
  source: string;
  page_number?: number | null;
  excerpt: string;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  grounded?: boolean;
  latency?: number;
};

export type IndexerStatus = {
  status: string;
  last_result?: string | null;
  processed: number;
  failed: number;
  errors: string[];
  warnings: string[];
};

export type ChatResponse = {
  session_id: string;
  answer: string;
  citations: Citation[];
  grounded: boolean;
  latency_ms: number;
};

export type DocumentItem = {
  name: string;
  size: number;
  content_type?: string;
  last_modified: string;
  url: string;
};

export type Health = {
  ready: boolean;
  services: Record<string, { configured: boolean; missing: string[] }>;
};

export type UserProfile = {
  id: string;
  email: string;
  display_name: string;
  role: "user" | "admin";
};

export type AuthSession = {
  access_token: string;
  token_type: "bearer";
  user: UserProfile;
};

export type ConversationSummary = {
  session_id: string;
  title: string;
  updated_at: string;
  message_count: number;
};

export type ConversationTurn = {
  id: string;
  created_at: string;
  question: string;
  answer: string;
  citations: Citation[];
  grounded: boolean;
  latency_ms: number;
};

export type ConversationDetail = {
  session_id: string;
  turns: ConversationTurn[];
};
