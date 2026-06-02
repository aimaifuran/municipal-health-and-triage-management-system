/**
 * Mobile sidebar open/close — works with Alpine on <body> and falls back if needed.
 */
(function () {
  function setSidebarOpen(open) {
    const body = document.body;
    if (window.Alpine && typeof Alpine.$data === "function") {
      const data = Alpine.$data(body);
      if (data && Object.prototype.hasOwnProperty.call(data, "sidebarOpen")) {
        data.sidebarOpen = open;
        return;
      }
    }
    const overlay = document.querySelector("[data-mobile-sidebar-overlay]");
    if (!overlay) return;
    overlay.hidden = !open;
  }

  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-sidebar-close]")) {
      event.preventDefault();
      event.stopPropagation();
      setSidebarOpen(false);
      return;
    }
    if (event.target.closest("[data-sidebar-open]")) {
      setSidebarOpen(true);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setSidebarOpen(false);
  });
})();
