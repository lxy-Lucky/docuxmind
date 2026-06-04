import type {
  ChatSession,
  Doc,
  Folder,
  FolderColor,
  ScopeMode,
  SessionDetail,
  SettingsView,
} from "./types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

// Folders
export const folderApi = {
  list: () => request<Folder[]>("/folders"),
  create: (name: string, color: FolderColor) =>
    request<Folder>("/folders", {
      method: "POST",
      body: JSON.stringify({ name, color }),
    }),
  update: (id: string, patch: { name?: string; color?: FolderColor }) =>
    request<{ ok: true }>(`/folders/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  remove: (id: string) =>
    request<{ ok: true }>(`/folders/${id}`, { method: "DELETE" }),
};

// Docs
export const docApi = {
  list: (folderId: string) => request<Doc[]>(`/folders/${folderId}/docs`),
  remove: (id: string) =>
    request<{ ok: true }>(`/docs/${id}`, { method: "DELETE" }),
  reindex: (id: string) =>
    request<{ ok: true }>(`/docs/${id}/reindex`, { method: "POST" }),
};

// Upload — multipart, doesn't use the json wrapper
export async function uploadFile(folderId: string, file: File): Promise<Doc> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${BASE}/folders/${folderId}/upload`, {
    method: "POST",
    body: fd,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

// Sessions
export const sessionApi = {
  list: () => request<ChatSession[]>("/sessions"),
  detail: (id: string) => request<SessionDetail>(`/sessions/${id}/messages`),
  create: (scope_mode: ScopeMode, scope_id: string | null, title?: string) =>
    request<{ id: string; title: string | null }>("/sessions", {
      method: "POST",
      body: JSON.stringify({ scope_mode, scope_id, title }),
    }),
  rename: (id: string, title: string) =>
    request<{ ok: true }>(`/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  remove: (id: string) =>
    request<{ ok: true }>(`/sessions/${id}`, { method: "DELETE" }),
};

// Settings
export const settingsApi = {
  view: () => request<SettingsView>("/settings"),
  switch: (provider: "mimo" | "lmstudio") =>
    request<{ ok: true; current: string; model: string }>(
      "/settings/provider",
      { method: "POST", body: JSON.stringify({ provider }) },
    ),
  check: () =>
    request<{ ok: boolean; tool_calls?: number; model: string; error?: string }>(
      "/settings/llm_check",
      { method: "POST" },
    ),
};

// Health
export const healthApi = {
  get: () =>
    request<{
      ok: boolean;
      llm: { provider: string; model: string; ready: boolean };
    }>("/health"),
};
