import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type ThemeListener = (event: MediaQueryListEvent) => void;

function installMatchMedia(initialMatches: boolean) {
  let matches = initialMatches;
  const listeners = new Set<ThemeListener>();
  const mediaQuery = {
    get matches() {
      return matches;
    },
    media: "(prefers-color-scheme: dark)",
    onchange: null,
    addEventListener: (_type: string, listener: ThemeListener) => listeners.add(listener),
    removeEventListener: (_type: string, listener: ThemeListener) => listeners.delete(listener),
    addListener: (listener: ThemeListener) => listeners.add(listener),
    removeListener: (listener: ThemeListener) => listeners.delete(listener),
    dispatchEvent: () => true,
  } as MediaQueryList;

  vi.stubGlobal("matchMedia", vi.fn(() => mediaQuery));

  return {
    change(nextMatches: boolean) {
      matches = nextMatches;
      const event = { matches, media: mediaQuery.media } as MediaQueryListEvent;
      listeners.forEach((listener) => listener(event));
    },
  };
}

describe("ThemeToggle", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.style.removeProperty("color-scheme");
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("follows the dark system preference when no preference is stored", async () => {
    installMatchMedia(true);
    const { default: ThemeToggle } = await import("../src/components/ThemeToggle.vue");
    const wrapper = mount(ThemeToggle);

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(wrapper.get("button").attributes("title")).toBe("切换到日间模式");
    expect(wrapper.get("button").attributes("aria-label")).toBe("切换到日间模式");
    expect(wrapper.find(".app-icon--sun").exists()).toBe(true);
  });

  it("persists a manual choice and ignores later system changes", async () => {
    const systemPreference = installMatchMedia(true);
    const { default: ThemeToggle } = await import("../src/components/ThemeToggle.vue");
    const { THEME_STORAGE_KEY } = await import("../src/composables/useTheme");
    const wrapper = mount(ThemeToggle);

    await wrapper.get("button").trigger("click");

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(wrapper.get("button").attributes("aria-label")).toBe("切换到夜间模式");
    expect(wrapper.find(".app-icon--moon").exists()).toBe(true);

    systemPreference.change(true);
    await flushPromises();
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("responds to system changes until the user makes a choice", async () => {
    const systemPreference = installMatchMedia(false);
    const { default: ThemeToggle } = await import("../src/components/ThemeToggle.vue");
    const wrapper = mount(ThemeToggle);

    expect(document.documentElement.dataset.theme).toBe("light");
    systemPreference.change(true);
    await flushPromises();

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(wrapper.find(".app-icon--sun").exists()).toBe(true);
  });

  it("restores a stored choice ahead of the system preference", async () => {
    window.localStorage.setItem("osteo-vision-theme", "light");
    const systemPreference = installMatchMedia(true);
    const { default: ThemeToggle } = await import("../src/components/ThemeToggle.vue");
    const wrapper = mount(ThemeToggle);

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(wrapper.get("button").attributes("aria-pressed")).toBe("false");

    systemPreference.change(false);
    await flushPromises();
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
