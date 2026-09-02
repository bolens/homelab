(() => {
  const root = document.documentElement;
  const storageKey = root.dataset.colorModeStorage;
  const mediaQuery = query => typeof matchMedia === "function" ? matchMedia(query) : { matches: false };
  const darkQuery = mediaQuery("(prefers-color-scheme: dark)");
  const lightQuery = mediaQuery("(prefers-color-scheme: light)");
  const modes = new Set(["system", "time", "light", "dark"]);
  let timer;

  let requested;
  let saved;
  try { requested = new URLSearchParams(location.search).get("theme"); } catch {}
  try { saved = storageKey ? localStorage.getItem(storageKey) : null; } catch {}
  let preference = modes.has(requested) ? requested : modes.has(saved) ? saved : "system";

  const resolve = mode => {
    if (mode === "light" || mode === "dark") return mode;
    if (mode === "time") {
      const hour = new Date().getHours();
      return hour >= 7 && hour < 19 ? "light" : "dark";
    }
    if (lightQuery.matches) return "light";
    if (darkQuery.matches) return "dark";
    return "dark";
  };
  const syncColor = () => {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) return;
    const styles = getComputedStyle(root);
    for (const name of ["--page"]) {
      const value = styles.getPropertyValue(name).trim();
      if (value) { meta.content = value; break; }
    }
  };
  const apply = mode => {
    preference = mode;
    root.dataset.colorMode = mode;
    const scheme = resolve(mode);
    root.dataset.colorScheme = scheme;
    const select = document.querySelector("select[data-color-mode]");
    if (select) select.value = mode;
    clearInterval(timer);
    if (mode === "time") timer = setInterval(() => apply("time"), 60_000);
    if (document.body) {
      syncColor();
      const topology = document.querySelector(".topology-frame iframe");
      if (topology) {
        const source = new URL(topology.getAttribute("src"), location.href);
        if (source.searchParams.get("theme") !== scheme) {
          source.searchParams.set("theme", scheme);
          topology.src = source.href;
        }
      }
    }
  };
  const mount = () => {
    const host = document.querySelector("header nav, .docs-header, .site-header");
    let select = document.querySelector("select[data-color-mode]");
    if (!select) {
      if (!host) { syncColor(); return; }
      const label = document.createElement("label");
      label.className = "color-mode-picker";
      label.innerHTML = '<span>Theme</span><select data-color-mode aria-label="Color theme"><option value="system">System</option><option value="time">Day cycle</option><option value="light">Light</option><option value="dark">Dark</option></select>';
      host.append(label);
      select = label.querySelector("select");
    }
    select.addEventListener("change", event => {
      try { if (storageKey) localStorage.setItem(storageKey, event.target.value); } catch {}
      apply(event.target.value);
    });
    apply(preference);
  };

  apply(preference);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount, { once: true });
  else mount();
  darkQuery.addEventListener?.("change", () => { if (preference === "system") apply("system"); });
  lightQuery.addEventListener?.("change", () => { if (preference === "system") apply("system"); });
})();
