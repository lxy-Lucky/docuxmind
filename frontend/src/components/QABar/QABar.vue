<script setup lang="ts">
import ContextTags from "./ContextTags.vue";
import InputBox from "./InputBox.vue";
</script>

<template>
  <div class="border-t border-line bg-bg-main px-7 pt-3.5 pb-[18px] relative z-[1] shrink-0">
    <ContextTags />
    <InputBox />
    <div class="flex items-center justify-between mt-2 text-[10px] font-mono text-text-3">
      <span>
        <kbd
          class="inline-flex items-center gap-0.5 px-1.5 py-px bg-bg-surface border border-line rounded-[3px] text-[9px] mx-px"
        >Enter</kbd>
        发送 ·
        <kbd
          class="inline-flex items-center gap-0.5 px-1.5 py-px bg-bg-surface border border-line rounded-[3px] text-[9px] mx-px"
        >Shift</kbd>+<kbd
          class="inline-flex items-center gap-0.5 px-1.5 py-px bg-bg-surface border border-line rounded-[3px] text-[9px] mx-px"
        >Enter</kbd>
        换行
      </span>
      <span>数据仅在本地处理</span>
    </div>
  </div>
</template>
