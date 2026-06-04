<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import { useChatStore } from "@/stores/chat";
import Placeholder from "./Placeholder.vue";
import AnswerBlock from "./AnswerBlock.vue";

const chat = useChatStore();
const scrollRef = ref<HTMLElement | null>(null);

const hasMessages = computed(() => chat.messages.length > 0);

// Auto-scroll to bottom on new messages / streaming updates
watch(
  () => [chat.messages.length, chat.current?.content, chat.current?.trace.length],
  async () => {
    await nextTick();
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight;
    }
  },
);
</script>

<template>
  <div
    ref="scrollRef"
    class="flex-1 overflow-y-auto px-9 py-7 relative z-[1]"
  >
    <Placeholder v-if="!hasMessages" />
    <div v-else class="max-w-[720px] mx-auto">
      <AnswerBlock
        v-for="m in chat.messages"
        :key="m.id"
        :msg="m"
      />
    </div>
  </div>
</template>
