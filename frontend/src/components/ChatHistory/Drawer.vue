<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { X, MessageSquarePlus, MessageSquare, Trash2, Loader2 } from "lucide-vue-next";

import { useChatStore } from "@/stores/chat";

const chat = useChatStore();

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ (e: "close"): void }>();

const loading = ref(false);

async function refresh() {
  loading.value = true;
  try {
    await chat.refreshSessions();
  } finally {
    loading.value = false;
  }
}

onMounted(refresh);

const sorted = computed(() => chat.sessions);

async function pick(sid: string) {
  await chat.loadSession(sid);
  emit("close");
}

function start() {
  chat.newSession();
  emit("close");
}

async function remove(sid: string, e: Event) {
  e.stopPropagation();
  if (!confirm("删除这个会话？")) return;
  await chat.deleteSession(sid);
}

function relTime(iso: string | null) {
  if (!iso) return "—";
  const t = new Date(iso + "Z").getTime();
  if (!t) return iso;
  const diff = Date.now() - t;
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "刚刚";
  if (m < 60) return `${m} 分钟前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小时前`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d} 天前`;
  return new Date(iso + "Z").toLocaleDateString();
}
</script>

<template>
  <transition name="drawer">
    <div v-if="open" class="fixed inset-0 z-50 flex" @click.self="emit('close')">
      <div class="absolute inset-0 bg-bg-deep/70 backdrop-blur-sm" />

      <aside
        class="ml-auto w-[380px] max-w-[90vw] h-full bg-bg-main border-l border-line shadow-2xl relative flex flex-col"
        style="animation: slideInRight .35s cubic-bezier(.4,0,.2,1) forwards;"
      >
        <header class="flex items-center justify-between px-5 py-4 border-b border-line shrink-0">
          <div>
            <div class="font-display text-base font-semibold tracking-tight">
              历史会话
            </div>
            <div class="text-[10px] text-text-3 font-mono mt-0.5">
              {{ sorted.length }} 个对话
            </div>
          </div>
          <button
            class="w-8 h-8 rounded-md border border-line bg-bg-surface text-text-3 hover:text-text-1 hover:border-line-l flex items-center justify-center transition-all"
            @click="emit('close')"
          >
            <X :size="15" />
          </button>
        </header>

        <div class="px-4 py-3 border-b border-line shrink-0">
          <button
            class="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-[7px] border border-accent bg-[var(--accent-glow)] text-accent hover:bg-[var(--accent-glow-s)] transition-all text-[12px] font-medium"
            @click="start"
          >
            <MessageSquarePlus :size="14" />
            开启新会话
          </button>
        </div>

        <div class="flex-1 overflow-y-auto px-2 py-2">
          <div
            v-if="loading"
            class="flex items-center justify-center text-text-3 text-[12px] font-mono py-8"
          >
            <Loader2 :size="14" class="animate-spin mr-2" /> 加载中
          </div>
          <div
            v-else-if="!sorted.length"
            class="text-text-3 text-[12px] font-mono text-center py-10"
          >
            还没有历史会话
          </div>
          <div
            v-for="s in sorted"
            :key="s.id"
            class="group flex items-start gap-2 px-3 py-2.5 rounded-sm cursor-pointer transition-all mb-1"
            :class="
              chat.currentSessionId === s.id
                ? 'bg-bg-elevated border border-accent/40'
                : 'border border-transparent hover:bg-bg-surface'
            "
            @click="pick(s.id)"
          >
            <MessageSquare :size="14" class="text-text-3 shrink-0 mt-0.5" />
            <div class="flex-1 min-w-0">
              <div class="text-[12px] font-medium text-text-1 truncate">
                {{ s.title || "未命名" }}
              </div>
              <div class="text-[10px] font-mono text-text-3 mt-0.5 flex items-center gap-2">
                <span>{{ s.msg_count }} 条</span>
                <span>·</span>
                <span>{{ relTime(s.last_at || s.created_at) }}</span>
                <span v-if="s.scope_mode === 'folder'" class="text-accent">
                  · 文件夹
                </span>
              </div>
            </div>
            <button
              class="opacity-0 group-hover:opacity-100 text-text-3 hover:text-bad transition-all shrink-0 p-1"
              title="删除"
              @click="remove(s.id, $event)"
            >
              <Trash2 :size="12" />
            </button>
          </div>
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
