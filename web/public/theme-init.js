// Apply before the stylesheet paints. Only this appearance preference is persisted.
(() => {
  let theme = "system";
  try {
    const saved = localStorage.getItem("practice-room-theme");
    if (["light", "dark", "system"].includes(saved)) theme = saved;
  } catch {
    /* Storage can be unavailable in private browser contexts. */
  }
  const dark =
    theme === "dark" ||
    (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.dataset.theme = theme;
})();
