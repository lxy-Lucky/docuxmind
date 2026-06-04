<script setup lang="ts">
import { ref, nextTick } from "vue";
import { Plus, Check, X } from "lucide-vue-next";

import { useFoldersStore } from "@/stores/folders";
import type { FolderColor } from "@/api/types";

import Folder from "./Folder.vue";

const folders = useFoldersStore();

const creating = ref(false);
const draft = ref("");
const inputRef = ref<HTMLInputElement | null>(null);

const colors: FolderColor[] = ["amber", "green", "blue", "purple", "red"];

async function startCreate() {
  if (creating.value) return;
  creating.value = true;
  draft.value = "";
  await nextTick();
  inputRef.value?.focus();
}

async function confirmCreate() {
  const name = draft.value.trim();
  if (!name) {
    creating.value = false;
    return;
  }
  const color = colors[folders.folders.length % colors.length];
  try {
    await folders.createFolder(name, color);
  } finally {
    creating.value = false;
    draft.value = "";
  }
}

function cancelCreate() {
  creating.value = false;
  draft.value = "";
}
</script>

<template>
  <div class="flex-1 overflow-y-auto px-2 pb-5 flex flex-col">
    <div class="flex items-center justify-between px-3 pt-2.5 pb-1.5 shrink-0">
      <div class="text-[10px] font-mono text-text-3 tracking-wider uppercase">
        文件夹
      </div>
      <button
        class="w-6 h-6 rounded-[5px] border border-line bg-bg-surface text-text-3 hover:border-accent hover:text-accent hover:bg-[var(--accent-glow)] flex items-center justify-center transition-all"
        title="新建文件夹"
        @click="startCreate"
      >
        <Plus :size="12" />
      </button>
    </div>

    <div
      v-if="creating"
      class="flex items-center gap-1.5 px-2.5 py-1.5 my-1 rounded-sm border border-accent bg-[var(--accent-glow)] mx-1"
    >
      <input
        ref="inputRef"
        v-model="draft"
        maxlength="20"
        placeholder="输入文件夹名称..."
        class="flex-1 bg-transparent border-none outline-none text-[12px] font-body text-text-1 placeholder:text-text-3"
        @keydown.enter="confirmCreate"
        @keydown.escape="cancelCreate"
      />
      <button
        class="w-[22px] h-[22px] border-none bg-accent text-bg-deep rounded flex items-center justify-center shrink-0"
        @click="confirmCreate"
      >
        <Check :size="12" />
      </button>
      <button
        class="w-[22px] h-[22px] border-none bg-transparent text-text-3 hover:text-bad rounded flex items-center justify-center shrink-0"
        @click="cancelCreate"
      >
        <X :size="13" />
      </button>
    </div>

    <div class="px-1">
      <Folder v-for="f in folders.folders" :key="f.id" :folder="f" />
      <div
        v-if="!folders.folders.length && !creating"
        class="text-[11px] text-text-3 py-6 text-center font-mono"
      >
        还没有文件夹 — 点击 + 新建
      </div>
    </div>
  </div>
</template>
