/**
 * Doctor dashboard — vanilla JS (event delegation + HTMX-safe).
 */
(function () {
  "use strict";

  const READMIT_MODAL = () => document.querySelector('[data-modal="readmit-confirm"]');
  const DISCHARGE_MODAL = () => document.querySelector('[data-modal="discharge-confirm"]');

  function getDischargePanel() {
    return document.getElementById("bulk-discharge-panel");
  }

  function htmxSubmitForm(form) {
    if (!form) return false;
    if (typeof htmx !== "undefined") {
      htmx.ajax("POST", form.getAttribute("hx-post"), {
        source: form,
        target: form.getAttribute("hx-target"),
        swap: form.getAttribute("hx-swap") || "outerHTML",
        indicator: form.getAttribute("hx-indicator"),
      });
      return true;
    }
    form.requestSubmit();
    return true;
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
    if (open) {
      document.body.classList.add("overflow-hidden");
    } else if (!READMIT_MODAL()?.classList.contains("is-open") && !DISCHARGE_MODAL()?.classList.contains("is-open")) {
      document.body.classList.remove("overflow-hidden");
    }
  }

  function openDischargeConfirm() {
    const panel = getDischargePanel();
    const form = panel?.querySelector('[data-ref="dischargeForm"]');
    const alert = panel?.querySelector('[data-alert="no-selection"]');
    const modal = DISCHARGE_MODAL();
    if (!form || !modal) return;

    const checked = form.querySelectorAll('input[name="consultation_ids"]:checked');
    if (!checked.length) {
      alert?.classList.remove("hidden");
      return;
    }
    alert?.classList.add("hidden");

    const names = labelsFromChecked(checked);
    const count = String(names.length);
    modal.querySelectorAll("[data-discharge-count]").forEach((el) => {
      el.textContent = count;
    });
    populatePatientList(modal.querySelector("[data-patient-list]"), names);
    setModalOpen(READMIT_MODAL(), false);
    setModalOpen(modal, true);
  }

  function openReadmitConfirm() {
    const panel = getDischargePanel();
    const form = panel?.querySelector('[data-ref="readmitForm"]');
    const alert = panel?.querySelector('[data-alert="no-readmit"]');
    const modal = READMIT_MODAL();
    if (!form || !modal) return;

    const checked = form.querySelectorAll('input[name="readmit_consultation_ids"]:checked');
    if (!checked.length) {
      alert?.classList.remove("hidden");
      return;
    }
    alert?.classList.add("hidden");

    const names = labelsFromChecked(checked);
    const count = String(names.length);
    modal.querySelectorAll("[data-readmit-count]").forEach((el) => {
      el.textContent = count;
    });
    populatePatientList(modal.querySelector("[data-patient-list]"), names);
    setModalOpen(DISCHARGE_MODAL(), false);
    setModalOpen(modal, true);
  }

  function handleBulkDischargeClick(event) {
    const target = event.target.closest("[data-action]");
    if (!target) return;

    const action = target.getAttribute("data-action");

    if (action === "discharge-open") {
      event.preventDefault();
      openDischargeConfirm();
      return;
    }

    if (action === "readmit-open") {
      event.preventDefault();
      openReadmitConfirm();
      return;
    }

    if (action === "discharge-cancel") {
      event.preventDefault();
      setModalOpen(DISCHARGE_MODAL(), false);
      return;
    }

    if (action === "readmit-cancel") {
      event.preventDefault();
      setModalOpen(READMIT_MODAL(), false);
      return;
    }

    if (action === "discharge-confirm") {
      event.preventDefault();
      const form = getDischargePanel()?.querySelector('[data-ref="dischargeForm"]');
      setModalOpen(DISCHARGE_MODAL(), false);
      htmxSubmitForm(form);
      return;
    }

    if (action === "readmit-confirm") {
      event.preventDefault();
      const form = getDischargePanel()?.querySelector('[data-ref="readmitForm"]');
      setModalOpen(READMIT_MODAL(), false);
      htmxSubmitForm(form);
    }
  }

  function handleBulkDischargeBackdropClick(event) {
    const modal = event.target.closest("[data-modal]");
    if (!modal || event.target !== modal) return;
    if (modal.dataset.modal === "discharge-confirm" || modal.dataset.modal === "readmit-confirm") {
      setModalOpen(modal, false);
    }
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
    const errorEl = backdrop.querySelector("[data-consult-ai-error]");
    const disclaimerEl = backdrop.querySelector("[data-consult-ai-disclaimer]");
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
  }

  function initDoctorDashboard(root) {
    if (!root) return;

    if (root.id === "doctor-consultation-modal") {
      const backdrop = root.querySelector("[data-consultation-modal]");
      if (backdrop) initConsultationModal(backdrop);
    } else {
      root.querySelectorAll("[data-consultation-modal]").forEach(initConsultationModal);
      const host = root.querySelector?.("#doctor-consultation-modal");
      host?.querySelectorAll("[data-consultation-modal]").forEach(initConsultationModal);
    }

    const panel = root.id === "bulk-discharge-panel" ? root : root.querySelector?.("#bulk-discharge-panel");
    if (panel && typeof htmx !== "undefined") {
      htmx.process(panel);
    }
  }

  function onKeydown(event) {
    if (event.key !== "Escape") return;
    if (DISCHARGE_MODAL()?.classList.contains("is-open")) {
      setModalOpen(DISCHARGE_MODAL(), false);
      return;
    }
    if (READMIT_MODAL()?.classList.contains("is-open")) {
      setModalOpen(READMIT_MODAL(), false);
    }
  }

  function boot() {
    document.addEventListener("click", handleBulkDischargeClick);
    document.addEventListener("click", handleBulkDischargeBackdropClick);
    document.addEventListener("keydown", onKeydown);
    initDoctorDashboard(document);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  document.body.addEventListener("htmx:afterSwap", (event) => {
    initDoctorDashboard(event.detail.target);
  });

  document.body.addEventListener("htmx:afterSettle", (event) => {
    initDoctorDashboard(event.detail.target);
  });
})();
