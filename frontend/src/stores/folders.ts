import { defineStore } from "pinia";
import { ref, computed } from "vue";

import { folderApi, docApi, uploadFile } from "@/api/client";
import type { Doc, Folder, FolderColor } from "@/api/types";

export const useFoldersStore = defineStore("folders", () => {
  const folders = ref<Folder[]>([]);
  const docsByFolder = ref<Record<string, Doc[]>>({});
  const activeFolderId = ref<string | null>(null);
  const activeDocId = ref<string | null>(null);
  const loading = ref(false);

  const totalDocs = computed(() =>
    folders.value.reduce((s, f) => s + f.doc_count, 0),
  );
  const totalSegments = computed(() =>
    folders.value.reduce((s, f) => s + f.segment_count, 0),
  );

  async function refresh() {
    loading.value = true;
    try {
      const fs = await folderApi.list();
      // preserve `open` state
      const prevOpen: Record<string, boolean> = {};
      for (const f of folders.value) prevOpen[f.id] = !!f.open;
      folders.value = fs.map((f, idx) => ({
        ...f,
        open: prevOpen[f.id] ?? idx === 0,
      }));
    } finally {
      loading.value = false;
    }
  }

  async function loadDocs(folderId: string) {
    docsByFolder.value[folderId] = await docApi.list(folderId);
  }

  async function toggleFolder(id: string) {
    const f = folders.value.find((x) => x.id === id);
    if (!f) return;
    f.open = !f.open;
    activeFolderId.value = id;
    if (f.open && !docsByFolder.value[id]) {
      await loadDocs(id);
    }
  }

  async function createFolder(name: string, color: FolderColor = "amber") {
    const f = await folderApi.create(name, color);
    folders.value.unshift({ ...f, open: true });
    docsByFolder.value[f.id] = [];
    activeFolderId.value = f.id;
  }

  async function renameFolder(id: string, name: string) {
    await folderApi.update(id, { name });
    const f = folders.value.find((x) => x.id === id);
    if (f) f.name = name;
  }

  async function removeFolder(id: string) {
    await folderApi.remove(id);
    folders.value = folders.value.filter((f) => f.id !== id);
    delete docsByFolder.value[id];
    if (activeFolderId.value === id) activeFolderId.value = null;
  }

  async function removeDoc(folderId: string, docId: string) {
    await docApi.remove(docId);
    const list = docsByFolder.value[folderId];
    if (list) docsByFolder.value[folderId] = list.filter((d) => d.id !== docId);
    const f = folders.value.find((x) => x.id === folderId);
    if (f) f.doc_count = Math.max(0, f.doc_count - 1);
    if (activeDocId.value === docId) activeDocId.value = null;
  }

  async function reindexDoc(docId: string) {
    await docApi.reindex(docId);
  }

  /**
   * Upload + poll until ingest finishes. Returns the final Doc record.
   * Polling is short and cheap; we don't want to bring in WebSockets in v1.
   */
  async function upload(folderId: string, file: File): Promise<Doc> {
    const created = await uploadFile(folderId, file);
    if (!docsByFolder.value[folderId]) docsByFolder.value[folderId] = [];
    const existing = docsByFolder.value[folderId].find((d) => d.id === created.id);
    if (!existing) docsByFolder.value[folderId].unshift(created);

    const f = folders.value.find((x) => x.id === folderId);
    if (f) {
      f.open = true;
      if (!existing) f.doc_count += 1;
    }

    // Poll for ingestion result (every 1.2s, up to ~60s)
    for (let i = 0; i < 50; i++) {
      await new Promise((r) => setTimeout(r, 1200));
      try {
        const fresh = await docApi.list(folderId);
        docsByFolder.value[folderId] = fresh;
        const me = fresh.find((d) => d.id === created.id);
        if (me && (me.status === "ok" || me.status === "error")) {
          // refresh folder counts
          await refresh();
          return me;
        }
      } catch {
        /* keep polling */
      }
    }
    return created;
  }

  return {
    folders,
    docsByFolder,
    activeFolderId,
    activeDocId,
    loading,
    totalDocs,
    totalSegments,
    refresh,
    loadDocs,
    toggleFolder,
    createFolder,
    renameFolder,
    removeFolder,
    removeDoc,
    reindexDoc,
    upload,
  };
});
