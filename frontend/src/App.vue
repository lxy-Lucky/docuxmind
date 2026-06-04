<script setup lang="ts">
import { onMounted, ref } from "vue";

import Sidebar from "@/components/Sidebar/Sidebar.vue";
import Header from "@/components/Header.vue";
import ChatArea from "@/components/ChatArea/ChatArea.vue";
import QABar from "@/components/QABar/QABar.vue";
import SettingsDrawer from "@/components/Settings/Drawer.vue";
import HistoryDrawer from "@/components/ChatHistory/Drawer.vue";

import { useFoldersStore } from "@/stores/folders";
import { useSettingsStore } from "@/stores/settings";
import { useChatStore } from "@/stores/chat";

const folders = useFoldersStore();
const settings = useSettingsStore();
const chat = useChatStore();

const historyOpen = ref(false);

onMounted(async () => {
  await folders.refresh();
  const first = folders.folders[0];
  if (first) await folders.loadDocs(first.id);
  await settings.refresh();
  await chat.restoreOnStartup();

  // Background heartbeat for the model badge
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
      <Header @open-history="historyOpen = true" />
      <ChatArea />
      <QABar />
    </main>
    <SettingsDrawer />
    <HistoryDrawer :open="historyOpen" @close="historyOpen = false" />
  </div>
</template>
