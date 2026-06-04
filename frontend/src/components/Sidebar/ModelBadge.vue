<script setup lang="ts">
import { computed } from "vue";
import { Settings as SettingsIcon } from "lucide-vue-next";

import { useSettingsStore } from "@/stores/settings";

const s = useSettingsStore();

const label = computed(() => {
  if (!s.llmProvider) return "未连接";
  const p = s.llmProvider === "mimo" ? "云端" : "本地";
  return `${p} · ${s.llmModel || "未知模型"}`;
});

const dotClass = computed(() =>
  s.llmReady
    ? "bg-ok shadow-[0_0_5px_rgba(90,212,166,.4)] pulse-anim"
    : "bg-bad shadow-[0_0_5px_rgba(232,93,111,.4)]",
);
</script>

<template>
  <div class="px-[14px] py-3 border-t border-line shrink-0">
    <button
      class="w-full flex items-center gap-2 text-[10px] font-mono text-text-3 px-[11px] py-[7px] bg-bg-surface rounded-sm border border-line hover:border-line-l hover:bg-bg-elevated transition-all"
      @click="s.openDrawer()"
    >
      <span class="w-[5px] h-[5px] rounded-full shrink-0" :class="dotClass" />
      <span class="flex-1 text-left truncate">{{ label }}</span>
      <SettingsIcon :size="12" class="shrink-0 opacity-70" />
    </button>
  </div>
</template>
