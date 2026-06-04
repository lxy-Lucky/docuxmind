import { defineStore } from "pinia";
import { ref, computed } from "vue";

import { streamSSE, type SSESession } from "@/api/sse";
import type { ChatTraceEvent, ScopeMode } from "@/api/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  scope_name: string;
  scope_count: number;
  trace: ChatTraceEvent[];
  status: "streaming" | "done" | "error";
  error?: string;
  startedAt: number;
}

export const useChatStore = defineStore("chat", () => {
  const messages = ref<ChatMessage[]>([]);
  const scopeMode = ref<ScopeMode>("all");
  const scopeId = ref<string | null>(null);
  const scopeName = ref<string>("全部文档");
  const draft = ref<string>(
    sessionStorage.getItem("dxm_draft") || "",
  );

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
    if (v) sessionStorage.setItem("dxm_draft", v);
    else sessionStorage.removeItem("dxm_draft");
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

    const userMsg: ChatMessage = {
      id: "u_" + Date.now(),
      role: "user",
      content: question,
      scope_name: scopeName.value,
      scope_count: scopeCount,
      trace: [],
      status: "done",
      startedAt: Date.now(),
    };
    const aiMsgRaw: ChatMessage = {
      id: "a_" + Date.now(),
      role: "assistant",
      content: "",
      scope_name: scopeName.value,
      scope_count: scopeCount,
      trace: [],
      status: "streaming",
      startedAt: Date.now(),
    };
    messages.value.push(userMsg, aiMsgRaw);
    // IMPORTANT: pull the message back out of the reactive array so subsequent
    // mutations go through Vue's Proxy and trigger re-renders. Mutating the raw
    // local reference would bypass reactivity (the data updates but the UI
    // stays stuck on the typing indicator).
    const aiMsg = messages.value[messages.value.length - 1] as ChatMessage;

    isStreaming.value = true;
    active = streamSSE(
      "/api/chat",
      {
        question,
        scope_mode: scopeMode.value,
        scope_id: scopeId.value,
        scope_name: scopeName.value,
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
        },
      },
    );
  }

  function reset() {
    cancel();
    messages.value = [];
  }

  return {
    messages,
    current,
    scopeMode,
    scopeId,
    scopeName,
    draft,
    isStreaming,
    setScope,
    persistDraft,
    ask,
    cancel,
    reset,
  };
});
