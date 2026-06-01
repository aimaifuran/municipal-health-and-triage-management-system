/**
 * Discharged patient detail modal — shared by doctor and nurse dashboards (HTMX-loaded).
 */
(function () {
  "use strict";

  function closeDischargedDetailModal() {
    document.getElementById("discharged-patient-detail-modal")?.replaceChildren();
    document.body.classList.remove("overflow-hidden");
  }

  function initDischargedDetailModal(backdrop) {
    if (!backdrop || backdrop.dataset.doctorBound === "1") return;
    backdrop.dataset.doctorBound = "1";
    document.body.classList.add("overflow-hidden");

    backdrop.querySelectorAll('[data-action="close-discharged-detail"]').forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.preventDefault();
        closeDischargedDetailModal();
      });
    });

    backdrop.addEventListener("click", (event) => {
      if (event.target === backdrop) closeDischargedDetailModal();
    });
  }

  function initFromRoot(root) {
    if (!root) return;
    if (root.id === "discharged-patient-detail-modal") {
      const backdrop = root.querySelector("[data-discharged-detail-modal]");
      if (backdrop) initDischargedDetailModal(backdrop);
      return;
    }
    root.querySelectorAll("[data-discharged-detail-modal]").forEach(initDischargedDetailModal);
    root
      .querySelector?.("#discharged-patient-detail-modal")
      ?.querySelectorAll("[data-discharged-detail-modal]")
      .forEach(initDischargedDetailModal);
  }

  function onKeydown(event) {
    if (event.key === "Escape" && document.querySelector("[data-discharged-detail-modal]")) {
      closeDischargedDetailModal();
    }
  }

  function boot() {
    initFromRoot(document);
    document.addEventListener("keydown", onKeydown);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  document.body.addEventListener("htmx:afterSwap", (event) => {
    initFromRoot(event.detail.target);
  });

  document.body.addEventListener("htmx:afterSettle", (event) => {
    initFromRoot(event.detail.target);
  });
})();
