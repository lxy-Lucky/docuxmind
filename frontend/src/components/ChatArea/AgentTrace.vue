<script setup lang="ts">
import { ref, computed } from "vue";
import { ChevronDown, Wrench, FileText, Search, BookOpen, AlertTriangle } from "lucide-vue-next";

import type { ChatTraceEvent } from "@/api/types";

const props = defineProps<{ trace: ChatTraceEvent[]; streaming: boolean }>();
const open = ref(true);

interface ToolStep {
  name: string;
  args: Record<string, unknown>;
  result?: string;
}

const steps = computed<ToolStep[]>(() => {
  const out: ToolStep[] = [];
  for (const ev of props.trace) {
    if (ev.kind === "tool_call") {
      out.push({
        name: (ev.payload as any).name,
        args: (ev.payload as any).args || {},
      });
    } else if (ev.kind === "tool_result") {
      const last = out[out.length - 1];
      if (last && last.name === (ev.payload as any).name && !last.result) {
        last.result = (ev.payload as any).result || "";
      }
    }
  }
  return out;
});

const errorEvt = computed(() => props.trace.find((e) => e.kind === "error"));

function iconFor(name: string) {
  if (name.startsWith("list")) return FileText;
  if (name.startsWith("search")) return Search;
  if (name.startsWith("get_doc")) return BookOpen;
  if (name === "write_report") return FileText;
  return Wrench;
}
</script>

<template>
  <div
    v-if="steps.length || errorEvt"
    class="mt-3 mb-4 border border-line rounded-[7px] bg-bg-surface overflow-hidden"
  >
    <button
      class="w-full flex items-center gap-2 px-3 py-2 text-[11px] font-mono text-text-2 hover:bg-bg-elevated transition-colors"
      @click="open = !open"
    >
      <ChevronDown
        :size="12"
        class="text-text-3 transition-transform"
        :class="open ? '' : '-rotate-90'"
      />
      <Wrench :size="12" class="text-accent" />
      <span>思考过程 · {{ steps.length }} 步</span>
      <span
        v-if="streaming"
        class="ml-auto text-[9px] text-accent inline-flex items-center gap-1"
      >
        <span class="dot dot-a pulse-anim" /> 进行中
      </span>
      <AlertTriangle v-else-if="errorEvt" :size="12" class="ml-auto text-bad" />
    </button>
    <div v-if="open" class="border-t border-line divide-y divide-line/60">
      <div
        v-for="(s, i) in steps"
        :key="i"
        class="px-3 py-2 text-[11px] font-mono"
      >
        <div class="flex items-center gap-2 text-text-2">
          <component :is="iconFor(s.name)" :size="11" class="text-accent shrink-0" />
          <span class="text-text-1">{{ s.name }}</span>
          <span class="text-text-3 truncate">
            {{ Object.keys(s.args).length ? JSON.stringify(s.args) : "()" }}
          </span>
        </div>
        <pre
          v-if="s.result"
          class="mt-1 text-text-3 whitespace-pre-wrap break-words max-h-[120px] overflow-y-auto"
        >{{ s.result }}</pre>
      </div>
      <div
        v-if="errorEvt"
        class="px-3 py-2 text-[11px] font-mono text-bad bg-[var(--red-dim)]"
      >
        <AlertTriangle :size="11" class="inline mr-1 -mt-px" />
        {{ (errorEvt.payload as any).reason }}
        <span v-if="(errorEvt.payload as any).message">
          — {{ (errorEvt.payload as any).message }}
        </span>
      </div>
    </div>
  </div>
</template>
