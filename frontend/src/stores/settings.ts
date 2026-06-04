import { defineStore } from "pinia";
import { ref } from "vue";

import { healthApi, settingsApi } from "@/api/client";
import type { SettingsView } from "@/api/types";

export const useSettingsStore = defineStore("settings", () => {
  const view = ref<SettingsView | null>(null);
  const llmReady = ref<boolean>(false);
  const llmModel = ref<string>("");
  const llmProvider = ref<string>("");
  const drawerOpen = ref<boolean>(false);
  const checking = ref<boolean>(false);
  const checkResult = ref<{
    ok: boolean;
    detail: string;
  } | null>(null);

  async function refresh() {
    try {
      const [v, h] = await Promise.all([settingsApi.view(), healthApi.get()]);
      view.value = v;
      llmReady.value = h.llm.ready;
      llmProvider.value = h.llm.provider;
      llmModel.value = h.llm.model;
    } catch (e) {
      llmReady.value = false;
    }
  }

  async function switchProvider(p: "mimo" | "lmstudio") {
    const r = await settingsApi.switch(p);
    llmProvider.value = r.current;
    llmModel.value = r.model;
    await refresh();
  }

  async function runCheck() {
    checking.value = true;
    checkResult.value = null;
    try {
      const r = await settingsApi.check();
      checkResult.value = {
        ok: r.ok,
        detail: r.ok
          ? `${r.model} ✓ 工具调用正常（共 ${r.tool_calls} 次）`
          : `${r.model} ✗ ${r.error || "未触发工具调用"}`,
      };
    } catch (e) {
      checkResult.value = {
        ok: false,
        detail: (e as Error).message,
      };
    } finally {
      checking.value = false;
    }
  }

  function openDrawer() {
    drawerOpen.value = true;
  }
  function closeDrawer() {
    drawerOpen.value = false;
  }

  return {
    view,
    llmReady,
    llmModel,
    llmProvider,
    drawerOpen,
    checking,
    checkResult,
    refresh,
    switchProvider,
    runCheck,
    openDrawer,
    closeDrawer,
  };
});
