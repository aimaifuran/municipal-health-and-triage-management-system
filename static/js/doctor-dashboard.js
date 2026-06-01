/**
 * Doctor dashboard — vanilla JS for discharge panel and consultation modal (HTMX-safe).
 */
(function () {
  "use strict";

  function htmxAjaxPost(form) {
    if (!form || typeof htmx === "undefined") return;
    htmx.ajax("POST", form.getAttribute("hx-post"), {
      source: form,
      target: form.getAttribute("hx-target"),
      swap: form.getAttribute("hx-swap") || "outerHTML",
      indicator: form.getAttribute("hx-indicator"),
    });
  }

  function labelsFromChecked(checked) {
    return Array.from(checked).map((checkbox) => {
      const label = checkbox.closest("label");
      return label?.textContent?.replace(/\s+/g, " ").trim() || "Selected patient";
    });
  }

  function populatePatientList(listEl, names) {
    if (!listEl) return;
    listEl.replaceChildren();
    names.forEach((name) => {
      const li = document.createElement("li");
      li.className = "px-3 py-2 text-slate-700";
      li.textContent = name;
      listEl.appendChild(li);
    });
  }

  function setModalOpen(modal, open) {
    if (!modal) return;
    modal.classList.toggle("is-open", open);
  }

  function initBulkDischargePanel(panel) {
    if (!panel || panel.dataset.doctorBound === "1") return;
    panel.dataset.doctorBound = "1";

    const readmitForm = panel.querySelector('[data-ref="readmitForm"]');
    const dischargeForm = panel.querySelector('[data-ref="dischargeForm"]');
    const noReadmitAlert = panel.querySelector('[data-alert="no-readmit"]');
    const noSelectionAlert = panel.querySelector('[data-alert="no-selection"]');
    const readmitModal = panel.querySelector('[data-modal="readmit-confirm"]');
    const dischargeModal = panel.querySelector('[data-modal="discharge-confirm"]');

    panel.querySelector('[data-action="readmit-open"]')?.addEventListener("click", () => {
      const checked =
        readmitForm?.querySelectorAll('input[name="readmit_consultation_ids"]:checked') || [];
      if (!checked.length) {
        noReadmitAlert?.classList.remove("hidden");
        return;
      }
      noReadmitAlert?.classList.add("hidden");
      const names = labelsFromChecked(checked);
      const count = String(names.length);
      readmitModal?.querySelectorAll("[data-readmit-count]").forEach((el) => {
        el.textContent = count;
      });
      populatePatientList(readmitModal?.querySelector("[data-patient-list]"), names);
      setModalOpen(dischargeModal, false);
      setModalOpen(readmitModal, true);
    });

    panel.querySelector('[data-action="discharge-open"]')?.addEventListener("click", () => {
      const checked = dischargeForm?.querySelectorAll('input[name="consultation_ids"]:checked') || [];
      if (!checked.length) {
        noSelectionAlert?.classList.remove("hidden");
        return;
      }
      noSelectionAlert?.classList.add("hidden");
      const names = labelsFromChecked(checked);
      const count = String(names.length);
      dischargeModal?.querySelectorAll("[data-discharge-count]").forEach((el) => {
        el.textContent = count;
      });
      populatePatientList(dischargeModal?.querySelector("[data-patient-list]"), names);
      setModalOpen(readmitModal, false);
      setModalOpen(dischargeModal, true);
    });

    readmitModal?.querySelector('[data-action="readmit-cancel"]')?.addEventListener("click", () => {
      setModalOpen(readmitModal, false);
    });
    readmitModal?.querySelector('[data-action="readmit-confirm"]')?.addEventListener("click", () => {
      setModalOpen(readmitModal, false);
      htmxAjaxPost(readmitForm);
    });
    readmitModal?.addEventListener("click", (event) => {
      if (event.target === readmitModal) setModalOpen(readmitModal, false);
    });

    dischargeModal?.querySelector('[data-action="discharge-cancel"]')?.addEventListener("click", () => {
      setModalOpen(dischargeModal, false);
    });
    dischargeModal?.querySelector('[data-action="discharge-confirm"]')?.addEventListener("click", () => {
      setModalOpen(dischargeModal, false);
      htmxAjaxPost(dischargeForm);
    });
    dischargeModal?.addEventListener("click", (event) => {
      if (event.target === dischargeModal) setModalOpen(dischargeModal, false);
    });
  }

  function closeConsultationModal() {
    document.getElementById("doctor-consultation-modal")?.replaceChildren();
  }

  function setConsultAiLoading(backdrop, loading) {
    const btn = backdrop.querySelector('[data-action="consult-ai"]');
    if (!btn) return;
    btn.disabled = loading;
    backdrop.querySelector("[data-consult-ai-idle]")?.classList.toggle("hidden", loading);
    const busyEl = backdrop.querySelector("[data-consult-ai-busy]");
    if (busyEl) {
      busyEl.classList.toggle("hidden", !loading);
      busyEl.classList.toggle("inline-flex", loading);
    }
  }

  function showConsultMessage(backdrop, type, message) {
    const errorEl = backdrop.querySelector('[data-consult-ai-error]');
    const disclaimerEl = backdrop.querySelector('[data-consult-ai-disclaimer]');
    if (type === "error") {
      if (errorEl) {
        errorEl.textContent = message;
        errorEl.classList.toggle("hidden", !message);
      }
      disclaimerEl?.classList.add("hidden");
      return;
    }
    errorEl?.classList.add("hidden");
    if (disclaimerEl) {
      const note = disclaimerEl.querySelector("[data-disclaimer-text]");
      if (note) note.textContent = message;
      disclaimerEl.classList.toggle("hidden", !message);
    }
  }

  async function runConsultAI(backdrop) {
    const patientId = backdrop.dataset.patientId;
    const aiUrl = backdrop.dataset.aiUrl;
    const form = backdrop.querySelector('[data-ref="consultForm"]');
    if (!patientId || !aiUrl || !form) return;

    const csrf = form.querySelector('[name="csrfmiddlewaretoken"]')?.value;
    if (!csrf) {
      showConsultMessage(backdrop, "error", "Security token missing. Refresh the page and try again.");
      return;
    }

    setConsultAiLoading(backdrop, true);
    showConsultMessage(backdrop, "error", "");
    showConsultMessage(backdrop, "disclaimer", "");

    try {
      const body = new URLSearchParams();
      body.set("patient_id", patientId);
      body.set("csrfmiddlewaretoken", csrf);
      const response = await fetch(aiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "X-CSRFToken": csrf,
          "HX-Request": "true",
        },
        body: body.toString(),
        credentials: "same-origin",
      });
      const data = await response.json();
      if (!response.ok) {
        showConsultMessage(backdrop, "error", data.error || "Could not generate AI consultation draft.");
        return;
      }
      ["diagnosis", "treatment", "prescription", "consultation_notes"].forEach((name) => {
        const field = form.querySelector(`[name="${name}"]`);
        if (field) field.value = data[name] || "";
      });
      showConsultMessage(
        backdrop,
        "disclaimer",
        data.disclaimer ||
          "Review and edit all fields before saving. You remain responsible for the medical record."
      );
    } catch (err) {
      showConsultMessage(backdrop, "error", "Network error. Check your connection and try again.");
    } finally {
      setConsultAiLoading(backdrop, false);
    }
  }

  function submitConsultForm(backdrop, action) {
    const form = backdrop.querySelector('[data-ref="consultForm"]');
    if (!form) return;
    const actionInput = form.querySelector('[name="action"]');
    if (actionInput) actionInput.value = action;
    if (action !== "admit" && !form.reportValidity()) return;
    htmx.ajax("POST", form.getAttribute("hx-post"), {
      source: form,
      target: form.getAttribute("hx-target") || "#doctor-consult-feedback",
      swap: form.getAttribute("hx-swap") || "none",
      indicator: form.getAttribute("hx-indicator"),
    });
  }

  function initConsultationModal(backdrop) {
    if (!backdrop || backdrop.dataset.doctorBound === "1") return;
    backdrop.dataset.doctorBound = "1";

    const admitModal = backdrop.querySelector('[data-modal="admit-confirm"]');

    backdrop.querySelectorAll('[data-action="close-consultation"]').forEach((btn) => {
      btn.addEventListener("click", closeConsultationModal);
    });

    backdrop.addEventListener("click", (event) => {
      if (event.target !== backdrop) return;
      if (!admitModal?.classList.contains("is-open")) closeConsultationModal();
    });

    backdrop.querySelector('[data-action="consult-ai"]')?.addEventListener("click", () => {
      runConsultAI(backdrop);
    });

    backdrop.querySelector('[data-action="consult-save"]')?.addEventListener("click", () => {
      submitConsultForm(backdrop, "save");
    });

    backdrop.querySelector('[data-action="consult-admit-open"]')?.addEventListener("click", () => {
      const form = backdrop.querySelector('[data-ref="consultForm"]');
      if (form && !form.reportValidity()) return;
      setModalOpen(admitModal, true);
    });

    admitModal?.querySelector('[data-action="admit-cancel"]')?.addEventListener("click", () => {
      setModalOpen(admitModal, false);
    });

    admitModal?.querySelector('[data-action="admit-confirm"]')?.addEventListener("click", () => {
      setModalOpen(admitModal, false);
      submitConsultForm(backdrop, "admit");
    });

    admitModal?.addEventListener("click", (event) => {
      if (event.target === admitModal) setModalOpen(admitModal, false);
    });

    document.addEventListener("keydown", function onEscape(event) {
      if (event.key !== "Escape" || !document.body.contains(backdrop)) {
        document.removeEventListener("keydown", onEscape);
        return;
      }
      if (admitModal?.classList.contains("is-open")) {
        setModalOpen(admitModal, false);
        return;
      }
      closeConsultationModal();
      document.removeEventListener("keydown", onEscape);
    });
  }

  function initDoctorDashboard(root) {
    if (!root) return;

    if (root.id === "bulk-discharge-panel") {
      initBulkDischargePanel(root);
    } else {
      root.querySelectorAll("#bulk-discharge-panel").forEach(initBulkDischargePanel);
    }

    if (root.id === "doctor-consultation-modal") {
      const backdrop = root.querySelector("[data-consultation-modal]");
      if (backdrop) initConsultationModal(backdrop);
    } else {
      root.querySelectorAll("[data-consultation-modal]").forEach(initConsultationModal);
      const host = root.querySelector?.("#doctor-consultation-modal");
      host?.querySelectorAll("[data-consultation-modal]").forEach(initConsultationModal);
    }
  }

  document.addEventListener("DOMContentLoaded", () => initDoctorDashboard(document));
  document.body.addEventListener("htmx:afterSwap", (event) => {
    initDoctorDashboard(event.detail.target);
  });
})();
