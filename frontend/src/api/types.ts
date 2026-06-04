export type FolderColor = "amber" | "green" | "blue" | "purple" | "red";

export interface Folder {
  id: string;
  name: string;
  color: FolderColor;
  position?: number;
  doc_count: number;
  segment_count: number;
  open?: boolean; // UI-only
  created_at?: string;
}

export type DocType = "pdf" | "docx" | "md" | "txt" | "csv" | "xlsx";
export type DocStatus = "pending" | "indexing" | "ok" | "error";

export interface Doc {
  id: string;
  folder_id: string;
  name: string;
  type: DocType;
  size_bytes: number;
  status: DocStatus;
  error_reason?: string | null;
  segment_count: number;
  language?: string | null;
  created_at?: string;
}

export type ScopeMode = "all" | "folder";

export interface ChatTraceEvent {
  kind:
    | "start"
    | "step"
    | "tool_call"
    | "tool_result"
    | "token"
    | "answer"
    | "done"
    | "error";
  payload: Record<string, unknown>;
  at: number; // epoch ms
}

export interface SettingsView {
  llm_provider: "mimo" | "lmstudio";
  mimo_model: string;
  lmstudio_model: string;
  mimo_base_url: string;
  lmstudio_base_url: string;
}
