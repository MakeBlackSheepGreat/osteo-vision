import { onBeforeUnmount, onMounted, ref } from "vue";

export function useFullscreenPanel() {
  const expanded = ref(false);

  async function open() {
    expanded.value = true;

    // 全屏请求必须紧跟用户点击触发；失败时仍保留 fixed 覆盖层作为兜底。
    await document.documentElement.requestFullscreen?.().catch(() => undefined);
  }

  async function close() {
    expanded.value = false;
    if (document.fullscreenElement) {
      await document.exitFullscreen().catch(() => undefined);
    }
  }

  function syncState() {
    if (expanded.value && !document.fullscreenElement) {
      expanded.value = false;
    }
  }

  onMounted(() => document.addEventListener("fullscreenchange", syncState));
  onBeforeUnmount(() => document.removeEventListener("fullscreenchange", syncState));

  return {
    expanded,
    open,
    close,
  };
}
