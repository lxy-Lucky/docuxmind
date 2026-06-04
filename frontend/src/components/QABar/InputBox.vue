<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from "vue";
import { Send, X } from "lucide-vue-next";

import { useChatStore } from "@/stores/chat";
import { useFoldersStore } from "@/stores/folders";

const chat = useChatStore();
const folders = useFoldersStore();

const textareaRef = ref<HTMLTextAreaElement | null>(null);
const value = ref(chat.draft || "");

const scopeCount = computed(() => {
  if (chat.scopeMode === "all") return folders.totalDocs;
  const f = folders.folders.find((x) => x.id === chat.scopeId);
  return f ? f.doc_count : 0;
});

const canSend = computed(
  () => value.value.trim().length > 0 && !chat.isStreaming,
);

function autoSize() {
  const el = textareaRef.value;
  if (!el) return;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

watch(value, (v) => {
  chat.persistDraft(v);
  nextTick(autoSize);
});

onMounted(autoSize);

async function send() {
  if (!canSend.value) return;
  const q = value.value;
  value.value = "";
  await nextTick();
  autoSize();
  chat.ask(q, scopeCount.value);
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
}
</script>

<template>
  <div class="flex items-end gap-2.5">
    <div class="flex-1 relative">
      <textarea
        ref="textareaRef"
        v-model="value"
        rows="1"
        placeholder="选择文件夹后在此提问，例如：这个版本的认证方案具体是怎样设计的？"
        class="w-full bg-bg-surface border-[1.5px] border-line rounded-[10px] px-4 py-[13px] text-[13.5px] font-body text-text-1 outline-none resize-none leading-relaxed min-h-[48px] max-h-[120px] transition-all placeholder:text-text-3 focus:border-accent focus:bg-bg-elevated focus:shadow-[0_0_0_3px_var(--accent-glow)]"
        @keydown="onKeydown"
      />
    </div>
    <button
      v-if="chat.isStreaming"
      class="w-12 h-12 rounded-[10px] bg-bg-elevated border border-line text-text-2 cursor-pointer flex items-center justify-center shrink-0 hover:text-bad hover:border-bad transition-all"
      title="取消"
      @click="chat.cancel()"
    >
      <X :size="19" />
    </button>
    <button
      v-else
      class="w-12 h-12 rounded-[10px] border-none cursor-pointer flex items-center justify-center shrink-0 shadow-accent hover:-translate-y-px hover:shadow-accentLg active:scale-[.96] transition-all disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-accent disabled:cursor-not-allowed"
      style="background: linear-gradient(135deg, var(--accent), var(--accent-dim));"
      :disabled="!canSend"
      title="发送"
      @click="send"
    >
      <Send :size="19" :stroke="'var(--bg-deep)'" stroke-width="2.5" />
    </button>
  </div>
</template>
