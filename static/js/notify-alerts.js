/**
 * Auto-dismiss inline notification alerts after 5 seconds.
 */
(function () {
  const DISMISS_MS = 5000;
  const FADE_MS = 300;

  function dismissAlert(el) {
    if (!el || el.dataset.dismissed === "true") return;
    el.dataset.dismissed = "true";
    el.classList.add("notify-alert--hiding");
    window.setTimeout(() => {
      const parent = el.parentElement;
      el.remove();
      if (parent?.classList.contains("notify-alert-group") && !parent.children.length) {
        parent.remove();
      }
      if (parent?.id === "doctor-consult-feedback" && !parent.textContent.trim()) {
        parent.innerHTML = "";
      }
    }, FADE_MS);
  }

  function scheduleDismiss(el) {
    if (!el || el.dataset.dismissScheduled === "true") return;
    el.dataset.dismissScheduled = "true";
    window.setTimeout(() => dismissAlert(el), DISMISS_MS);
  }

  function setupAutoDismissAlerts(root) {
    if (!root) return;
    if (root.nodeType === 1) {
      if (root.classList?.contains("notify-alert")) scheduleDismiss(root);
      root.querySelectorAll?.(".notify-alert").forEach(scheduleDismiss);
      return;
    }
    document.querySelectorAll(".notify-alert").forEach(scheduleDismiss);
  }

  document.addEventListener("DOMContentLoaded", () => setupAutoDismissAlerts(document));
  document.body.addEventListener("htmx:afterSwap", (event) => {
    setupAutoDismissAlerts(event.detail?.target);
  });
  document.body.addEventListener("htmx:oobAfterSwap", (event) => {
    setupAutoDismissAlerts(event.detail?.target);
  });
})();
