<script setup lang="ts">
import { useFoldersStore } from "@/stores/folders";

const folders = useFoldersStore();
</script>

<template>
  <div class="flex gap-1.5 px-[14px] pt-3 pb-2 shrink-0">
    <div class="chip">
      <span class="dot dot-g" /> {{ folders.totalDocs }} 文档
    </div>
    <div class="chip">
      <span class="dot dot-a" /> {{ folders.totalSegments }} 段
    </div>
  </div>
</template>
