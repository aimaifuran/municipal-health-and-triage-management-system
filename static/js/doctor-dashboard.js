/**
 * Doctor dashboard Alpine components — load with defer before Alpine (see base.html).
 */
document.addEventListener("alpine:init", () => {
  Alpine.data("doctorConsultationModal", () => ({
    showAdmitConfirm: false,
    patientName: "",
    patientNumber: "",
    patientId: "",
    aiUrl: "",
    alreadyAdmitted: false,
    consultAiLoading: false,
    consultAiError: "",
    consultAiDisclaimer: "",

    init() {
      this.showAdmitConfirm = false;
      this.consultAiLoading = false;
      this.consultAiError = "";
      this.consultAiDisclaimer = "";
      this.initFromDataset();
    },

    initFromDataset() {
      this.patientName = this.$el.dataset.patientName || "";
      this.patientNumber = this.$el.dataset.patientNumber || "";
      this.patientId = this.$el.dataset.patientId || "";
      this.aiUrl = this.$el.dataset.aiUrl || "";
      this.alreadyAdmitted = this.$el.dataset.alreadyAdmitted === "true";
    },

    _setFieldValue(name, value) {
      const form = this.$refs.consultForm;
      if (!form) return;
      const field = form.querySelector(`[name="${name}"]`);
      if (field) field.value = value || "";
    },

    async requestConsultAI() {
      if (this.consultAiLoading || !this.patientId || !this.aiUrl) return;
      const form = this.$refs.consultForm;
      const csrf = form?.querySelector('[name="csrfmiddlewaretoken"]')?.value;
      if (!csrf) {
        this.consultAiError = "Security token missing. Refresh the page and try again.";
        return;
      }
      this.consultAiLoading = true;
      this.consultAiError = "";
      try {
        const body = new URLSearchParams();
        body.set("patient_id", this.patientId);
        body.set("csrfmiddlewaretoken", csrf);
        const response = await fetch(this.aiUrl, {
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
          this.consultAiError = data.error || "Could not generate AI consultation draft.";
          return;
        }
        this._setFieldValue("diagnosis", data.diagnosis);
        this._setFieldValue("treatment", data.treatment);
        this._setFieldValue("prescription", data.prescription);
        this._setFieldValue("consultation_notes", data.consultation_notes);
        this.consultAiDisclaimer =
          data.disclaimer ||
          "Review and edit all fields before saving. You remain responsible for the medical record.";
      } catch (err) {
        this.consultAiError = "Network error. Check your connection and try again.";
      } finally {
        this.consultAiLoading = false;
      }
    },

    _submitConsultForm(action) {
      const form = this.$refs.consultForm;
      if (!form || typeof htmx === "undefined") return;
      const actionInput = form.querySelector('[name="action"]');
      if (actionInput) actionInput.value = action;
      htmx.ajax("POST", form.getAttribute("hx-post"), {
        source: form,
        target: form.getAttribute("hx-target") || "#doctor-consult-feedback",
        swap: form.getAttribute("hx-swap") || "none",
        indicator: form.getAttribute("hx-indicator"),
      });
    },

    submitSave() {
      const form = this.$refs.consultForm;
      if (form && !form.reportValidity()) return;
      this._submitConsultForm("save");
    },

    openAdmitConfirm() {
      const form = this.$refs.consultForm;
      if (form && !form.reportValidity()) return;
      this.showAdmitConfirm = true;
    },

    cancelAdmit() {
      this.showAdmitConfirm = false;
    },

    confirmAdmit() {
      this.showAdmitConfirm = false;
      this._submitConsultForm("admit");
    },
  }));

  Alpine.data("bulkDischargePanel", () => ({
    showConfirm: false,
    noSelection: false,
    selectedPatients: [],
    showReadmitConfirm: false,
    noReadmitSelection: false,
    selectedReadmitPatients: [],

    init() {
      this.showConfirm = false;
      this.noSelection = false;
      this.showReadmitConfirm = false;
      this.noReadmitSelection = false;
    },

    _labelsFromChecked(checked, fallback) {
      return Array.from(checked).map((checkbox) => {
        const label = checkbox.closest("label");
        const text = label?.textContent?.replace(/\s+/g, " ").trim();
        return text || fallback;
      });
    },

    _submitForm(form) {
      if (!form || typeof htmx === "undefined") return;
      htmx.ajax("POST", form.getAttribute("hx-post"), {
        source: form,
        target: form.getAttribute("hx-target"),
        swap: form.getAttribute("hx-swap") || "outerHTML",
        indicator: form.getAttribute("hx-indicator"),
      });
    },

    openDischargeConfirm() {
      this.showReadmitConfirm = false;
      this.noSelection = false;
      const form = this.$refs.dischargeForm;
      if (!form) return;
      const checked = form.querySelectorAll('input[name="consultation_ids"]:checked');
      if (!checked.length) {
        this.noSelection = true;
        return;
      }
      this.selectedPatients = this._labelsFromChecked(checked, "Selected patient");
      this.showConfirm = true;
    },

    openReadmitConfirm() {
      this.showConfirm = false;
      this.noReadmitSelection = false;
      const form = this.$refs.readmitForm;
      if (!form) return;
      const checked = form.querySelectorAll('input[name="readmit_consultation_ids"]:checked');
      if (!checked.length) {
        this.noReadmitSelection = true;
        return;
      }
      this.selectedReadmitPatients = this._labelsFromChecked(checked, "Selected patient");
      this.showReadmitConfirm = true;
    },

    cancel() {
      this.showConfirm = false;
    },

    cancelReadmit() {
      this.showReadmitConfirm = false;
    },

    confirmDischarge() {
      this.showConfirm = false;
      this._submitForm(this.$refs.dischargeForm);
    },

    confirmReadmit() {
      this.showReadmitConfirm = false;
      this._submitForm(this.$refs.readmitForm);
    },
  }));
});

document.body.addEventListener("htmx:afterSwap", (event) => {
  const target = event.detail.target;
  if (!target) return;
  if (
    (target.id === "discharged-patient-detail-modal" || target.id === "doctor-consultation-modal") &&
    typeof Alpine !== "undefined"
  ) {
    Alpine.initTree(target);
    return;
  }
  const panel =
    target.id === "bulk-discharge-panel" ? target : target.querySelector?.("#bulk-discharge-panel");
  if (panel && typeof Alpine !== "undefined") {
    Alpine.initTree(panel);
  }
});
