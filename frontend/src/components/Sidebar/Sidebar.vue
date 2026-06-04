<script setup lang="ts">
import Brand from "./Brand.vue";
import UploadZone from "./UploadZone.vue";
import Stats from "./Stats.vue";
import FolderTree from "./FolderTree.vue";
import ModelBadge from "./ModelBadge.vue";
</script>

<template>
  <aside
    class="row-span-2 bg-bg-main border-r border-line flex flex-col overflow-hidden relative sidebar-edge"
    :style="{ width: 'var(--sidebar-w)' }"
  >
    <Brand />
    <UploadZone />
    <Stats />
    <FolderTree />
    <ModelBadge />
  </aside>
</template>
