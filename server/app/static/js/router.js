let current = null;

export function startRouter(routes, mount) {
  async function handle() {
    const hash = location.hash.replace(/^#/, "") || "/overview";
    if (current && current.stop) { try { current.stop(); } catch (_) {} }
    mount.innerHTML = "";
    for (const route of routes) {
      const m = hash.match(route.match);
      if (m) {
        current = route.module;
        document.querySelectorAll("[data-nav]").forEach((a) =>
          a.classList.toggle("active", a.dataset.nav === route.nav));
        await route.module.render(mount, m.slice(1));
        return;
      }
    }
    mount.textContent = "Not found";
  }
  window.addEventListener("hashchange", handle);
  handle();
}
