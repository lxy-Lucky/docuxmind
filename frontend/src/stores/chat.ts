import { defineStore } from "pinia";
import { ref, computed } from "vue";

import { sessionApi } from "@/api/client";
import { streamSSE, type SSESession } from "@/api/sse";
import type { ChatSession, ChatTraceEvent, ScopeMode } from "@/api/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  scope_name: string;
  scope_count: number;
  trace: ChatTraceEvent[];
  status: "streaming" | "done" | "error";
  error?: string;
  report_file?: string | null;
  startedAt: number;
}

const SESSION_KEY = "dxm_session_id";
const DRAFT_KEY = "dxm_draft";

function newId(prefix: string) {
  return prefix + "_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
}

export const useChatStore = defineStore("chat", () => {
  const messages = ref<ChatMessage[]>([]);
  const sessions = ref<ChatSession[]>([]);
  const currentSessionId = ref<string | null>(
    localStorage.getItem(SESSION_KEY),
  );

  const scopeMode = ref<ScopeMode>("all");
  const scopeId = ref<string | null>(null);
  const scopeName = ref<string>("全部文档");
  const draft = ref<string>(sessionStorage.getItem(DRAFT_KEY) || "");

  let active: SSESession | null = null;
  const isStreaming = ref(false);

  const current = computed(() => messages.value[messages.value.length - 1]);

  function setScope(mode: ScopeMode, id: string | null, name: string) {
    scopeMode.value = mode;
    scopeId.value = id;
    scopeName.value = name;
  }

  function persistDraft(v: string) {
    draft.value = v;
    if (v) sessionStorage.setItem(DRAFT_KEY, v);
    else sessionStorage.removeItem(DRAFT_KEY);
  }

  async function refreshSessions() {
    try {
      sessions.value = await sessionApi.list();
    } catch (e) {
      // non-fatal
    }
  }

  async function loadSession(sid: string) {
    cancel();
    const detail = await sessionApi.detail(sid);
    currentSessionId.value = sid;
    localStorage.setItem(SESSION_KEY, sid);
    scopeMode.value = (detail.session.scope_mode as ScopeMode) || "all";
    scopeId.value = detail.session.scope_id;
    scopeName.value =
      detail.session.scope_mode === "folder"
        ? detail.session.title || "文件夹"
        : "全部文档";

    // Hydrate UI messages from stored rows
    const hydrated: ChatMessage[] = detail.messages.map((m) => {
      let report_file: string | null = null;
      if (m.trace_json) {
        try {
          const t = JSON.parse(m.trace_json);
          report_file = t.report_file || null;
        } catch {
          /* ignore */
        }
      }
      return {
        id: m.id,
        role: m.role,
        content: m.content,
        scope_name: scopeName.value,
        scope_count: 0,
        trace: [],
        status: "done",
        report_file,
        startedAt: new Date(m.created_at + "Z").getTime() || Date.now(),
      };
    });
    messages.value = hydrated;
  }

  async function restoreOnStartup() {
    await refreshSessions();
    const sid = currentSessionId.value;
    if (sid && sessions.value.some((s) => s.id === sid)) {
      try {
        await loadSession(sid);
        return;
      } catch {
        // session gone — fall through
      }
    }
    // No restorable session — fresh state
    currentSessionId.value = null;
    localStorage.removeItem(SESSION_KEY);
    messages.value = [];
  }

  function newSession() {
    cancel();
    messages.value = [];
    currentSessionId.value = null;
    localStorage.removeItem(SESSION_KEY);
  }

  async function deleteSession(sid: string) {
    await sessionApi.remove(sid);
    sessions.value = sessions.value.filter((s) => s.id !== sid);
    if (currentSessionId.value === sid) newSession();
  }

  function cancel() {
    if (active) {
      active.abort();
      active = null;
    }
    const cur = current.value;
    if (cur && cur.status === "streaming") {
      cur.status = "error";
      cur.error = "已取消";
    }
    isStreaming.value = false;
  }

  async function ask(question: string, scopeCount: number) {
    if (!question.trim() || isStreaming.value) return;
    persistDraft("");

    // Lazy-create session_id on the first message so refresh restores work.
    if (!currentSessionId.value) {
      currentSessionId.value = newId("s");
      localStorage.setItem(SESSION_KEY, currentSessionId.value);
    }
    const sid = currentSessionId.value;

    const userMsg: ChatMessage = {
      id: newId("u"),
      role: "user",
      content: question,
      scope_name: scopeName.value,
      scope_count: scopeCount,
      trace: [],
      status: "done",
      startedAt: Date.now(),
    };
    const aiMsgRaw: ChatMessage = {
      id: newId("a"),
      role: "assistant",
      content: "",
      scope_name: scopeName.value,
      scope_count: scopeCount,
      trace: [],
      status: "streaming",
      startedAt: Date.now(),
    };
    messages.value.push(userMsg, aiMsgRaw);
    // Pull the proxied element back out so mutations trigger reactivity.
    const aiMsg = messages.value[messages.value.length - 1] as ChatMessage;

    isStreaming.value = true;
    active = streamSSE(
      "/api/chat",
      {
        question,
        scope_mode: scopeMode.value,
        scope_id: scopeId.value,
        scope_name: scopeName.value,
        session_id: sid,
      },
      {
        onEvent: (event, data) => {
          aiMsg.trace.push({
            kind: event as ChatTraceEvent["kind"],
            payload: data,
            at: Date.now(),
          });
          if (event === "answer" && typeof (data as any).content === "string") {
            aiMsg.content = (data as any).content;
            aiMsg.report_file = (data as any).report_file ?? null;
          } else if (event === "error") {
            aiMsg.status = "error";
            aiMsg.error =
              (data as any)?.reason || (data as any)?.message || "未知错误";
          } else if (event === "done") {
            aiMsg.status = "done";
          }
        },
        onError: (err) => {
          aiMsg.status = "error";
          aiMsg.error = (err as Error)?.message || "连接失败";
          isStreaming.value = false;
        },
        onDone: () => {
          if (aiMsg.status === "streaming") aiMsg.status = "done";
          isStreaming.value = false;
          active = null;
          // refresh session list so the new session bubbles to top
          refreshSessions();
        },
      },
    );
  }

  return {
    messages,
    sessions,
    currentSessionId,
    current,
    scopeMode,
    scopeId,
    scopeName,
    draft,
    isStreaming,
    setScope,
    persistDraft,
    refreshSessions,
    loadSession,
    restoreOnStartup,
    newSession,
    deleteSession,
    ask,
    cancel,
  };
});
