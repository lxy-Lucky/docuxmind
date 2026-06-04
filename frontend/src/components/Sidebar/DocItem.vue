<script setup lang="ts">
import { computed } from "vue";
import { X, RefreshCw, AlertTriangle } from "lucide-vue-next";

import type { Doc } from "@/api/types";
import { useFoldersStore } from "@/stores/folders";

const props = defineProps<{ doc: Doc; folderId: string }>();
const folders = useFoldersStore();

const sizeLabel = computed(() => {
  const b = props.doc.size_bytes;
  if (b > 1024 * 1024) return (b / (1024 * 1024)).toFixed(1) + " MB";
  if (b > 1024) return (b / 1024).toFixed(0) + " KB";
  return b + " B";
});

const dotClass = computed(() => {
  switch (props.doc.status) {
    case "ok": return "bg-ok shadow-[0_0_5px_rgba(90,212,166,.4)]";
    case "error": return "bg-bad shadow-[0_0_5px_rgba(232,93,111,.4)]";
    default: return "bg-accent shadow-[0_0_5px_var(--accent-glow-s)] pulse-anim";
  }
});

const typeClass = computed(() => {
  const t = props.doc.type;
  if (t === "pdf") return "bg-[var(--red-dim)] text-bad";
  if (t === "md") return "bg-[var(--green-dim)] text-ok";
  if (t === "csv") return "bg-[var(--purple-dim)] text-purple";
  if (t === "docx") return "bg-[var(--blue-dim)] text-info";
  if (t === "xlsx") return "bg-[var(--green-dim)] text-ok";
  return "bg-[var(--blue-dim)] text-info";
});

const isActive = computed(() => folders.activeDocId === props.doc.id);

function onClick() {
  folders.activeDocId = props.doc.id;
  folders.activeFolderId = props.folderId;
}

async function onDelete(e: Event) {
  e.stopPropagation();
  await folders.removeDoc(props.folderId, props.doc.id);
}

async function onReindex(e: Event) {
  e.stopPropagation();
  await folders.reindexDoc(props.doc.id);
  await folders.loadDocs(props.folderId);
}
</script>

<template>
  <div
    class="group flex items-center gap-2 px-2.5 py-[7px] rounded-sm cursor-pointer transition-all relative mb-px"
    :class="isActive ? 'bg-bg-elevated' : 'hover:bg-bg-surface'"
    @click="onClick"
  >
    <span
      v-if="isActive"
      class="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-[55%] bg-ok rounded-r-sm"
    />
    <div
      class="w-7 h-7 rounded-[5px] flex items-center justify-center text-[9px] font-semibold font-mono shrink-0 uppercase tracking-wide"
      :class="typeClass"
    >
      {{ doc.type }}
    </div>
    <div class="flex-1 min-w-0">
      <div class="text-[12px] font-medium truncate" :title="doc.name">
        {{ doc.name }}
      </div>
      <div class="text-[10px] text-text-3 font-mono mt-px flex items-center gap-1">
        {{ sizeLabel }} · {{ doc.segment_count }} 段
        <span v-if="doc.status === 'error'" class="text-bad inline-flex items-center gap-0.5">
          · <AlertTriangle :size="9" /> 失败
        </span>
      </div>
    </div>
    <span class="w-[7px] h-[7px] rounded-full shrink-0" :class="dotClass" />
    <button
      v-if="doc.status === 'error'"
      class="opacity-0 group-hover:opacity-100 bg-transparent border-none text-text-3 hover:text-accent rounded-[3px] transition-opacity shrink-0 p-1"
      title="重新索引"
      @click="onReindex"
    >
      <RefreshCw :size="12" />
    </button>
    <button
      class="opacity-0 group-hover:opacity-100 bg-transparent border-none text-text-3 hover:text-bad hover:bg-[var(--red-dim)] rounded-[3px] transition-all shrink-0 p-1"
      title="删除"
      @click="onDelete"
    >
      <X :size="13" />
    </button>
  </div>
</template>
