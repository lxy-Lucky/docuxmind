<script setup lang="ts">
import { ref, computed, nextTick } from "vue";
import { ChevronRight, Folder as FolderIcon, Pencil, X } from "lucide-vue-next";

import type { Folder } from "@/api/types";
import { useFoldersStore } from "@/stores/folders";

import DocItem from "./DocItem.vue";

const props = defineProps<{ folder: Folder }>();
const store = useFoldersStore();

const isActive = computed(() => store.activeFolderId === props.folder.id);
const docs = computed(() => store.docsByFolder[props.folder.id] ?? []);

const renaming = ref(false);
const draftName = ref(props.folder.name);
const inputRef = ref<HTMLInputElement | null>(null);

const colorStyle = computed(() => {
  const c = props.folder.color;
  const map: Record<string, { bg: string; fg: string }> = {
    amber:  { bg: "var(--accent-glow)",  fg: "var(--accent)" },
    green:  { bg: "var(--green-dim)",    fg: "var(--green)" },
    blue:   { bg: "var(--blue-dim)",     fg: "var(--blue)" },
    purple: { bg: "var(--purple-dim)",   fg: "var(--purple)" },
    red:    { bg: "var(--red-dim)",      fg: "var(--red)" },
  };
  return map[c] ?? map.amber;
});

function onToggle() {
  store.toggleFolder(props.folder.id);
}

async function startRename(e: Event) {
  e.stopPropagation();
  renaming.value = true;
  draftName.value = props.folder.name;
  await nextTick();
  inputRef.value?.focus();
  inputRef.value?.select();
}

async function finishRename() {
  if (!renaming.value) return;
  renaming.value = false;
  const v = draftName.value.trim();
  if (v && v !== props.folder.name) {
    await store.renameFolder(props.folder.id, v);
  }
}

function cancelRename() {
  renaming.value = false;
  draftName.value = props.folder.name;
}

async function onDelete(e: Event) {
  e.stopPropagation();
  if (!confirm(`删除文件夹「${props.folder.name}」？其中的文档也会被移除。`)) return;
  await store.removeFolder(props.folder.id);
}
</script>

<template>
  <div class="mb-0.5">
    <div
      class="group flex items-center gap-1.5 px-2.5 py-2 rounded-sm cursor-pointer select-none relative transition-all"
      :class="isActive ? 'bg-bg-elevated' : 'hover:bg-bg-surface'"
      @click="onToggle"
    >
      <span
        v-if="isActive"
        class="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-[55%] bg-accent rounded-r-sm"
      />
      <ChevronRight
        :size="11"
        class="text-text-3 shrink-0 transition-transform duration-200"
        :class="folder.open ? 'rotate-90' : ''"
      />
      <div
        class="w-7 h-7 rounded-md flex items-center justify-center shrink-0"
        :style="{ background: colorStyle.bg, color: colorStyle.fg }"
      >
        <FolderIcon :size="14" />
      </div>
      <div v-if="!renaming" class="flex-1 text-[13px] font-medium truncate" :title="folder.name">
        {{ folder.name }}
      </div>
      <input
        v-else
        ref="inputRef"
        v-model="draftName"
        class="flex-1 bg-bg-deep border border-accent rounded px-1.5 py-0.5 text-[12px] font-body text-text-1 outline-none"
        @click.stop
        @keydown.enter="finishRename"
        @keydown.escape="cancelRename"
        @blur="finishRename"
      />
      <span
        class="text-[10px] font-mono text-text-3 bg-bg-deep px-1.5 py-px rounded-[10px] shrink-0"
      >
        {{ folder.doc_count }}
      </span>
      <div class="flex gap-0.5 ml-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <button
          class="w-5 h-5 border-none bg-transparent text-text-3 hover:text-text-1 hover:bg-bg-hover rounded flex items-center justify-center"
          title="重命名"
          @click="startRename"
        >
          <Pencil :size="11" />
        </button>
        <button
          class="w-5 h-5 border-none bg-transparent text-text-3 hover:text-bad hover:bg-[var(--red-dim)] rounded flex items-center justify-center"
          title="删除"
          @click="onDelete"
        >
          <X :size="12" />
        </button>
      </div>
    </div>

    <div
      class="overflow-hidden transition-[max-height] duration-300 ease-out"
      :style="{ maxHeight: folder.open ? '800px' : '0px' }"
    >
      <div class="pl-[18px] py-1">
        <DocItem
          v-for="d in docs"
          :key="d.id"
          :doc="d"
          :folder-id="folder.id"
        />
        <div
          v-if="!docs.length"
          class="text-[11px] text-text-3 py-2 text-center font-mono"
        >
          暂无文档
        </div>
      </div>
    </div>
  </div>
</template>
