<script setup lang="ts">
import { computed } from "vue";
import { Info } from "lucide-vue-next";

import { useChatStore } from "@/stores/chat";

const chat = useChatStore();
const tip = computed(() =>
  chat.scopeMode === "all"
    ? "选择左侧文件夹作为上下文范围，在下方输入问题，AI 将检索对应文档并整合回答。"
    : `当前检索范围：「${chat.scopeName}」文件夹。输入问题开始提问。`,
);
</script>

<template>
  <div
    class="h-full flex flex-col items-center justify-center text-center px-6"
    style="animation: fadeUp .6s ease forwards;"
  >
    <div
      class="w-[72px] h-[72px] mb-[22px] rounded-full bg-bg-surface border border-line flex items-center justify-center relative"
    >
      <span
        class="absolute -inset-[5px] rounded-full border border-dashed border-line-l"
        style="animation: spin 18s linear infinite;"
      />
      <Info :size="28" class="text-accent" stroke-width="1.5" />
    </div>
    <h2 class="font-display text-[20px] font-semibold mb-1.5 tracking-tight">
      基于文档提问
    </h2>
    <p class="text-[13px] text-text-3 max-w-[340px] leading-relaxed">
      {{ tip }}
    </p>
  </div>
</template>
