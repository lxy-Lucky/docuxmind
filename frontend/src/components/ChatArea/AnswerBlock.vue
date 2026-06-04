<script setup lang="ts">
import { computed } from "vue";
import { FileText, Copy, ThumbsUp, ThumbsDown, Check } from "lucide-vue-next";
import MarkdownIt from "markdown-it";
import DOMPurify from "dompurify";

import type { ChatMessage } from "@/stores/chat";
import AgentTrace from "./AgentTrace.vue";
import { ref } from "vue";

const props = defineProps<{ msg: ChatMessage }>();

// Allow inline HTML in answers so the agent can emit the original design's
// citation badges (<span class="sr">...) and highlights (<span class="hl">...).
// DOMPurify strips anything dangerous; we just permit the design's class names.
const md = new MarkdownIt({ html: true, breaks: true, linkify: true });

const rendered = computed(() => {
  if (!props.msg.content) return "";
  return DOMPurify.sanitize(md.render(props.msg.content), {
    ADD_ATTR: ["class"],
  });
});

const copied = ref(false);
async function copy() {
  try {
    await navigator.clipboard.writeText(props.msg.content);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1400);
  } catch {}
}
</script>

<template>
  <div class="mb-8" style="animation: fadeUp .4s ease forwards;">
    <!-- User question -->
    <div v-if="msg.role === 'user'" class="mb-3 text-[13px] text-text-2">
      <div class="font-mono text-[10px] text-text-3 mb-1">你</div>
      <div class="text-text-1 whitespace-pre-wrap">{{ msg.content }}</div>
    </div>

    <!-- AI answer -->
    <div v-else>
      <div class="flex items-center gap-2.5 mb-[18px] pb-[14px] border-b border-line">
        <div
          class="w-8 h-8 rounded-[9px] flex items-center justify-center text-bg-deep font-bold font-display text-[13px] shrink-0"
          style="background: linear-gradient(135deg, var(--accent), var(--accent-dim));"
        >
          AI
        </div>
        <div class="text-[11px] font-mono text-text-3">
          <b class="text-text-1 font-medium">DocuMind</b> · 检索「{{ msg.scope_name }}」· {{ msg.scope_count }} 个文档
        </div>
        <div
          class="ml-auto flex items-center gap-1.5 text-[10px] font-mono text-text-3 bg-bg-surface px-[9px] py-[3px] rounded-full border border-line"
        >
          <FileText :size="11" />
          {{ msg.scope_count }} 来源
        </div>
      </div>

      <AgentTrace :trace="msg.trace" :streaming="msg.status === 'streaming'" />

      <div v-if="msg.status === 'streaming' && !msg.content" class="mb-3">
        <div class="text-text-3 text-[12px] font-mono mb-2">
          正在从「{{ msg.scope_name }}」中检索相关片段...
        </div>
        <div class="typing">
          <span /><span /><span />
        </div>
      </div>

      <div
        v-else-if="msg.content"
        class="ans-body"
        v-html="rendered"
      />

      <div
        v-if="msg.status === 'done' && msg.report_file"
        class="mt-4 inline-flex items-center gap-1.5 text-[10px] font-mono text-text-3 bg-bg-surface border border-line px-2.5 py-1 rounded-full"
        :title="`已保存到 data/reports/${msg.report_file}`"
      >
        <FileText :size="11" />
        已存档 · {{ msg.report_file }}
      </div>

      <div
        v-if="msg.status === 'error'"
        class="mt-3 text-[12px] font-mono text-bad bg-[var(--red-dim)] border border-bad/30 rounded-sm px-3 py-2"
      >
        ✗ {{ msg.error }}
      </div>

      <div
        v-if="msg.status === 'done' && msg.content"
        class="flex gap-[7px] mt-5 pt-[14px] border-t border-line"
      >
        <button
          class="flex items-center gap-1.5 text-[11px] font-mono text-text-3 bg-bg-surface border border-line px-3 py-1.5 rounded-full hover:text-text-1 hover:border-line-l hover:bg-bg-elevated transition-all"
          @click="copy"
        >
          <Check v-if="copied" :size="13" class="text-ok" />
          <Copy v-else :size="13" />
          {{ copied ? "已复制" : "复制" }}
        </button>
        <button
          class="flex items-center gap-1.5 text-[11px] font-mono text-text-3 bg-bg-surface border border-line px-3 py-1.5 rounded-full hover:text-text-1 hover:border-line-l hover:bg-bg-elevated transition-all"
        >
          <ThumbsUp :size="13" /> 有帮助
        </button>
        <button
          class="flex items-center gap-1.5 text-[11px] font-mono text-text-3 bg-bg-surface border border-line px-3 py-1.5 rounded-full hover:text-text-1 hover:border-line-l hover:bg-bg-elevated transition-all"
        >
          <ThumbsDown :size="13" /> 需改进
        </button>
      </div>
    </div>
  </div>
</template>
