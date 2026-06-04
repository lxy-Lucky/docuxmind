<script setup lang="ts">
import { computed, onMounted } from "vue";
import { X, Cloud, Cpu, CheckCircle2, XCircle, Loader2 } from "lucide-vue-next";

import { useSettingsStore } from "@/stores/settings";

const s = useSettingsStore();

onMounted(() => {
  if (s.drawerOpen && !s.view) s.refresh();
});

const isMimo = computed(() => s.llmProvider === "mimo");

async function switchTo(p: "mimo" | "lmstudio") {
  if (s.llmProvider === p) return;
  await s.switchProvider(p);
}
</script>

<template>
  <transition name="drawer">
    <div
      v-if="s.drawerOpen"
      class="fixed inset-0 z-50 flex"
      @click.self="s.closeDrawer()"
    >
      <!-- backdrop -->
      <div class="absolute inset-0 bg-bg-deep/70 backdrop-blur-sm" />

      <!-- drawer panel -->
      <aside
        class="ml-auto w-[420px] max-w-[90vw] h-full bg-bg-main border-l border-line shadow-2xl relative flex flex-col"
        style="animation: slideInRight .35s cubic-bezier(.4,0,.2,1) forwards;"
      >
        <header class="flex items-center justify-between px-5 py-4 border-b border-line shrink-0">
          <div>
            <div class="font-display text-base font-semibold tracking-tight">设置</div>
            <div class="text-[10px] text-text-3 font-mono mt-0.5">LLM 提供商与诊断</div>
          </div>
          <button
            class="w-8 h-8 rounded-md border border-line bg-bg-surface text-text-3 hover:text-text-1 hover:border-line-l flex items-center justify-center transition-all"
            @click="s.closeDrawer()"
          >
            <X :size="15" />
          </button>
        </header>

        <div class="flex-1 overflow-y-auto px-5 py-5 space-y-6">
          <!-- Provider switch -->
          <section>
            <div class="text-[10px] font-mono text-text-3 tracking-wider uppercase mb-2.5">
              模型提供商
            </div>
            <div class="grid grid-cols-2 gap-2.5">
              <button
                class="flex flex-col items-start gap-1.5 px-3.5 py-3 rounded-[10px] border-[1.5px] transition-all text-left"
                :class="
                  isMimo
                    ? 'border-accent bg-[var(--accent-glow)]'
                    : 'border-line bg-bg-surface hover:border-line-l'
                "
                @click="switchTo('mimo')"
              >
                <Cloud
                  :size="16"
                  :class="isMimo ? 'text-accent' : 'text-text-3'"
                />
                <div class="text-[13px] font-medium">云端</div>
                <div class="text-[10px] text-text-3 font-mono truncate w-full">
                  {{ s.view?.mimo_model || "mimo-v2.5-pro" }}
                </div>
              </button>
              <button
                class="flex flex-col items-start gap-1.5 px-3.5 py-3 rounded-[10px] border-[1.5px] transition-all text-left"
                :class="
                  !isMimo
                    ? 'border-accent bg-[var(--accent-glow)]'
                    : 'border-line bg-bg-surface hover:border-line-l'
                "
                @click="switchTo('lmstudio')"
              >
                <Cpu
                  :size="16"
                  :class="!isMimo ? 'text-accent' : 'text-text-3'"
                />
                <div class="text-[13px] font-medium">本地 LM Studio</div>
                <div class="text-[10px] text-text-3 font-mono truncate w-full">
                  {{ s.view?.lmstudio_model || "qwen2.5-7b-instruct" }}
                </div>
              </button>
            </div>
          </section>

          <!-- Endpoints (read-only; reflects .env) -->
          <section>
            <div class="text-[10px] font-mono text-text-3 tracking-wider uppercase mb-2.5">
              接口地址（来自 .env）
            </div>
            <div class="space-y-2">
              <div class="bg-bg-surface border border-line rounded-sm px-3 py-2">
                <div class="text-[10px] text-text-3 font-mono">MIMO_BASE_URL</div>
                <div class="text-[11px] font-mono text-text-1 break-all">
                  {{ s.view?.mimo_base_url || "—" }}
                </div>
              </div>
              <div class="bg-bg-surface border border-line rounded-sm px-3 py-2">
                <div class="text-[10px] text-text-3 font-mono">LMSTUDIO_BASE_URL</div>
                <div class="text-[11px] font-mono text-text-1 break-all">
                  {{ s.view?.lmstudio_base_url || "—" }}
                </div>
              </div>
            </div>
          </section>

          <!-- Capability self-test -->
          <section>
            <div class="text-[10px] font-mono text-text-3 tracking-wider uppercase mb-2.5">
              工具调用能力自检
            </div>
            <p class="text-[12px] text-text-2 mb-3 leading-relaxed">
              发送一个最小测试 prompt，看当前模型是否能正确触发 tool-calling。
              本地小模型常在这步翻车，云端 mimo 应稳定通过。
            </p>
            <button
              class="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-[7px] border border-accent bg-[var(--accent-glow)] text-accent hover:bg-[var(--accent-glow-s)] transition-all text-[12px] font-medium"
              :disabled="s.checking"
              @click="s.runCheck()"
            >
              <Loader2 v-if="s.checking" :size="14" class="animate-spin" />
              {{ s.checking ? "检测中..." : "开始自检" }}
            </button>
            <div
              v-if="s.checkResult"
              class="mt-3 flex items-start gap-2 px-3 py-2.5 rounded-sm border text-[12px] font-mono"
              :class="
                s.checkResult.ok
                  ? 'border-ok/40 bg-[var(--green-dim)] text-ok'
                  : 'border-bad/40 bg-[var(--red-dim)] text-bad'
              "
            >
              <CheckCircle2 v-if="s.checkResult.ok" :size="14" class="shrink-0 mt-0.5" />
              <XCircle v-else :size="14" class="shrink-0 mt-0.5" />
              <span class="break-all">{{ s.checkResult.detail }}</span>
            </div>
          </section>

          <!-- Tips -->
          <section
            class="text-[11px] text-text-3 leading-relaxed font-mono bg-bg-surface border border-line rounded-sm px-3 py-2.5"
          >
            提示：要修改 API key 或模型名，请编辑 backend/.env 后重启服务。运行时切换只在内存中生效。
          </section>
        </div>
      </aside>
    </div>
  </transition>
</template>

<style scoped>
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.2s;
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
</style>
