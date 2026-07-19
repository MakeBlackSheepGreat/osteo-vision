import { computed, readonly, ref } from "vue";

export type ThemeName = "light" | "dark";

export const THEME_STORAGE_KEY = "osteo-vision-theme";

const theme = ref<ThemeName>("light");
const hasUserPreference = ref(false);

let initialized = false;
let systemThemeQuery: MediaQueryList | null = null;

function isThemeName(value: string | null): value is ThemeName {
  return value === "light" || value === "dark";
}

function readStoredTheme(): ThemeName | null {
  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (isThemeName(storedTheme)) {
      return storedTheme;
    }
    if (storedTheme !== null) {
      window.localStorage.removeItem(THEME_STORAGE_KEY);
    }
  } catch {
    // The theme still follows the system when browser storage is unavailable.
  }
  return null;
}

function systemTheme(): ThemeName {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return "light";
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(nextTheme: ThemeName): void {
  theme.value = nextTheme;
  if (typeof document === "undefined") {
    return;
  }

  document.documentElement.dataset.theme = nextTheme;
  document.documentElement.style.colorScheme = nextTheme;
}

function handleSystemThemeChange(event: MediaQueryListEvent): void {
  if (!hasUserPreference.value) {
    applyTheme(event.matches ? "dark" : "light");
  }
}

function listenForSystemThemeChanges(): void {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function" || systemThemeQuery) {
    return;
  }

  systemThemeQuery = window.matchMedia("(prefers-color-scheme: dark)");
  if (typeof systemThemeQuery.addEventListener === "function") {
    systemThemeQuery.addEventListener("change", handleSystemThemeChange);
  } else {
    systemThemeQuery.addListener(handleSystemThemeChange);
  }
}

export function initializeTheme(): void {
  if (initialized || typeof window === "undefined") {
    return;
  }

  const storedTheme = readStoredTheme();
  hasUserPreference.value = storedTheme !== null;
  applyTheme(storedTheme ?? systemTheme());
  listenForSystemThemeChanges();
  initialized = true;
}

export function setTheme(nextTheme: ThemeName): void {
  hasUserPreference.value = true;
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  } catch {
    // Keep the in-memory preference for this browser session.
  }
  applyTheme(nextTheme);
}

export function clearThemePreference(): void {
  hasUserPreference.value = false;
  try {
    window.localStorage.removeItem(THEME_STORAGE_KEY);
  } catch {
    // The system preference still applies when browser storage is unavailable.
  }
  applyTheme(systemTheme());
}

export function useTheme() {
  initializeTheme();

  const isDark = computed(() => theme.value === "dark");

  return {
    theme: readonly(theme),
    isDark,
    hasUserPreference: readonly(hasUserPreference),
    setTheme,
    toggleTheme: () => setTheme(isDark.value ? "light" : "dark"),
    clearThemePreference,
  };
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  initializeTheme();
}
