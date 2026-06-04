<script setup lang="ts">
import { computed } from "vue";
import { History, MessageSquarePlus, User } from "lucide-vue-next";

import { useChatStore } from "@/stores/chat";
import { useSettingsStore } from "@/stores/settings";

const chat = useChatStore();
const settings = useSettingsStore();

const title = computed(() => {
  if (!chat.currentSessionId) return "新会话";
  const s = chat.sessions.find((x) => x.id === chat.currentSessionId);
  return s?.title || "新会话";
});

defineEmits<{ (e: "open-history"): void }>();
</script>

<template>
  <header
    class="flex items-center gap-3 px-6 h-[52px] border-b border-line bg-bg-deep/80 backdrop-blur-sm relative z-[2] shrink-0"
  >
    <div class="min-w-0 flex-1">
      <div
        class="text-[13px] font-medium text-text-1 truncate font-display tracking-tight"
        :title="title"
      >
        {{ title }}
      </div>
      <div class="text-[10px] font-mono text-text-3 truncate">
        {{
          chat.scopeMode === "all"
            ? "全部文档"
            : `检索范围 · ${chat.scopeName}`
        }}
      </div>
    </div>

    <button
      class="w-9 h-9 rounded-md border border-line bg-bg-surface text-text-3 hover:text-accent hover:border-accent hover:bg-[var(--accent-glow)] flex items-center justify-center transition-all"
      title="新会话"
      @click="chat.newSession()"
    >
      <MessageSquarePlus :size="15" />
    </button>

    <button
      class="w-9 h-9 rounded-md border border-line bg-bg-surface text-text-3 hover:text-text-1 hover:border-line-l flex items-center justify-center transition-all"
      title="历史会话"
      @click="$emit('open-history')"
    >
      <History :size="15" />
    </button>

    <button
      class="w-9 h-9 rounded-full text-bg-deep font-bold font-display flex items-center justify-center shadow-accent transition-transform hover:-translate-y-0.5"
      style="background: linear-gradient(135deg, var(--accent), var(--accent-dim));"
      title="设置"
      @click="settings.openDrawer()"
    >
      <User :size="15" />
    </button>
  </header>
</template>
