<script setup lang="ts">
import { computed } from "vue";
import { Folder as FolderIcon, Layers } from "lucide-vue-next";

import { useFoldersStore } from "@/stores/folders";
import { useChatStore } from "@/stores/chat";

const folders = useFoldersStore();
const chat = useChatStore();

const colorVar = (color: string) => {
  const map: Record<string, string> = {
    amber: "var(--accent)",
    green: "var(--green)",
    blue: "var(--blue)",
    purple: "var(--purple)",
    red: "var(--red)",
  };
  return map[color] ?? "var(--text-3)";
};

const allActive = computed(() => chat.scopeMode === "all");

function pickAll() {
  chat.setScope("all", null, "全部文档");
}
function pickFolder(id: string, name: string) {
  chat.setScope("folder", id, name);
  folders.activeFolderId = id;
}
</script>

<template>
  <div class="flex items-center gap-1.5 mb-2 text-[10px] font-mono text-text-3 flex-wrap">
    <span class="mr-0.5">检索范围：</span>
    <button
      class="flex items-center gap-1 px-2.5 py-[3px] rounded-full border transition-all"
      :class="
        allActive
          ? 'border-accent bg-[var(--accent-glow)] text-accent'
          : 'border-line bg-bg-surface hover:border-line-l hover:bg-bg-elevated'
      "
      @click="pickAll"
    >
      <Layers :size="11" :stroke="allActive ? 'var(--accent)' : 'var(--text-3)'" />
      全部文档
    </button>
    <div class="w-px h-3.5 bg-line mx-0.5" />
    <button
      v-for="f in folders.folders"
      :key="f.id"
      class="flex items-center gap-1 px-2.5 py-[3px] rounded-full border transition-all"
      :class="
        chat.scopeMode === 'folder' && chat.scopeId === f.id
          ? 'border-accent bg-[var(--accent-glow)] text-accent'
          : 'border-line bg-bg-surface hover:border-line-l hover:bg-bg-elevated'
      "
      @click="pickFolder(f.id, f.name)"
    >
      <FolderIcon :size="11" :stroke="colorVar(f.color)" />
      {{ f.name }} ({{ f.doc_count }})
    </button>
  </div>
</template>
