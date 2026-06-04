<script setup lang="ts">
import { onMounted } from "vue";

import Sidebar from "@/components/Sidebar/Sidebar.vue";
import ChatArea from "@/components/ChatArea/ChatArea.vue";
import QABar from "@/components/QABar/QABar.vue";
import SettingsDrawer from "@/components/Settings/Drawer.vue";

import { useFoldersStore } from "@/stores/folders";
import { useSettingsStore } from "@/stores/settings";

const folders = useFoldersStore();
const settings = useSettingsStore();

onMounted(async () => {
  await folders.refresh();
  // Eagerly load docs for the first folder so the tree shows them when expanded.
  const first = folders.folders[0];
  if (first) await folders.loadDocs(first.id);
  await settings.refresh();

  // Background heartbeat so the model badge stays fresh.
  setInterval(() => settings.refresh(), 20_000);
});
</script>

<template>
  <div
    class="grid h-screen overflow-hidden"
    :style="{
      gridTemplateColumns: 'var(--sidebar-w) 1fr',
      gridTemplateRows: '1fr auto',
    }"
  >
    <Sidebar />
    <main class="flex flex-col overflow-hidden bg-bg-deep relative main-glow">
      <ChatArea />
      <QABar />
    </main>
    <SettingsDrawer />
  </div>
</template>
