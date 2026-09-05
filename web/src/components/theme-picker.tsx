import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";

export type Theme = "light" | "dark" | "system";
const isTheme = (value: string | null | undefined): value is Theme =>
  value === "light" || value === "dark" || value === "system";

export function ThemePicker() {
  const [theme, setTheme] = useState<Theme>(() => {
    const initial = document.documentElement.dataset.theme;
    return isTheme(initial) ? initial : "system";
  });
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      document.documentElement.classList.toggle(
        "dark",
        theme === "dark" || (theme === "system" && media.matches),
      );
      document.documentElement.dataset.theme = theme;
    };
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key === "practice-room-theme" || event.key === null)
        setTheme(isTheme(event.newValue) ? event.newValue : "system");
    };
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);
  const Icon = theme === "dark" ? Moon : theme === "light" ? Sun : Monitor;
  return (
    <div className="flex items-center gap-2 text-muted-foreground">
      <Icon size={16} aria-hidden="true" />
      <NativeSelect
        aria-label="Appearance"
        value={theme}
        className="h-9 w-25 text-xs"
        onChange={(event) => {
          const next = event.target.value;
          if (!isTheme(next)) return;
          setTheme(next);
          try {
            localStorage.setItem("practice-room-theme", next);
          } catch {
            /* The current tab still works. */
          }
        }}
      >
        <NativeSelectOption value="system">System</NativeSelectOption>
        <NativeSelectOption value="light">Light</NativeSelectOption>
        <NativeSelectOption value="dark">Dark</NativeSelectOption>
      </NativeSelect>
    </div>
  );
}
