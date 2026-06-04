<script setup lang="ts">
import { ref } from "vue";
import { Upload } from "lucide-vue-next";

import { useFoldersStore } from "@/stores/folders";
import { useChatStore } from "@/stores/chat";

const folders = useFoldersStore();
const chat = useChatStore();

const over = ref(false);
const inputRef = ref<HTMLInputElement | null>(null);
const errorText = ref("");

function pickTargetFolder(): string | null {
  // Prefer the chat scope folder; fall back to first available folder.
  if (chat.scopeMode === "folder" && chat.scopeId) return chat.scopeId;
  if (folders.activeFolderId) return folders.activeFolderId;
  return folders.folders[0]?.id ?? null;
}

async function handleFiles(files: FileList | null) {
  if (!files || files.length === 0) return;
  errorText.value = "";

  let target = pickTargetFolder();
  if (!target) {
    try {
      await folders.createFolder("默认文件夹", "amber");
      target = folders.folders[0]?.id ?? null;
    } catch (e) {
      errorText.value = (e as Error).message;
      return;
    }
  }
  if (!target) return;

  for (const file of Array.from(files)) {
    try {
      await folders.upload(target, file);
    } catch (e) {
      errorText.value = `${file.name}: ${(e as Error).message}`;
    }
  }
}

function onDrop(e: DragEvent) {
  e.preventDefault();
  over.value = false;
  handleFiles(e.dataTransfer?.files ?? null);
}
</script>

<template>
  <div
    class="mx-[14px] mt-[14px] border-[1.5px] border-dashed border-line-l rounded-[10px] px-[14px] py-[22px] text-center cursor-pointer relative overflow-hidden shrink-0 transition-all duration-300"
    :class="over ? 'border-accent bg-bg-surface shadow-[0_0_28px_var(--accent-glow)]' : 'hover:border-accent hover:bg-bg-surface'"
    @click="inputRef?.click()"
    @dragover.prevent="over = true"
    @dragleave="over = false"
    @drop="onDrop"
  >
    <input
      ref="inputRef"
      type="file"
      multiple
      accept=".pdf,.md,.txt,.docx,.doc,.csv,.json,.xlsx,.xls,.xlsm"
      class="hidden"
      @change="(e) => handleFiles((e.target as HTMLInputElement).files)"
    />
    <div
      class="w-[38px] h-[38px] mx-auto mb-[10px] rounded-full bg-bg-elevated flex items-center justify-center transition-transform duration-300"
      :class="over ? '-translate-y-0.5' : ''"
    >
      <Upload :size="18" class="text-accent" />
    </div>
    <div class="text-xs font-semibold mb-[3px]">拖放文件至上传</div>
    <div class="text-[10px] text-text-3 font-mono">
      PDF / MD / TXT / DOCX / CSV / XLSX
    </div>
    <div v-if="errorText" class="text-[10px] text-bad font-mono mt-2">
      {{ errorText }}
    </div>
  </div>
</template>
