/**
 * Login form — client validation and submit loading state (no Alpine).
 */
(function () {
  const form = document.getElementById("login-form");
  if (!form) return;

  const submitBtn = document.getElementById("login-submit");
  const labelEl = document.getElementById("login-btn-label");
  const loadingEl = document.getElementById("login-btn-loading");
  const statusEl = document.getElementById("login-status");

  const fields = [
    {
      input: document.getElementById("id_username"),
      clientError: document.getElementById("username-error-client"),
      requiredMessage: "Email is required.",
      invalidMessage: "Enter a valid email address.",
    },
    {
      input: document.getElementById("id_password"),
      clientError: document.getElementById("password-error-client"),
      requiredMessage: "Password is required.",
      invalidMessage: "Password is required.",
    },
  ];

  function setLoading(on) {
    if (!submitBtn || !labelEl || !loadingEl) return;
    submitBtn.disabled = on;
    labelEl.hidden = on;
    loadingEl.hidden = !on;
    if (statusEl) statusEl.hidden = !on;
  }

  function clearClientError(field) {
    field.input?.classList.remove("form-input-error");
    if (field.clientError) {
      field.clientError.textContent = "";
      field.clientError.hidden = true;
    }
  }

  function showClientError(field, message) {
    field.input?.classList.add("form-input-error");
    if (field.clientError) {
      field.clientError.textContent = message;
      field.clientError.hidden = false;
    }
  }

  function validateClient() {
    let valid = true;
    fields.forEach((field) => {
      clearClientError(field);
      const input = field.input;
      if (!input) return;
      const value = input.value.trim();
      if (!value) {
        showClientError(field, field.requiredMessage);
        valid = false;
        return;
      }
      if (input.type === "email" && !input.checkValidity()) {
        showClientError(field, field.invalidMessage);
        valid = false;
      }
    });
    return valid;
  }

  fields.forEach((field) => {
    field.input?.addEventListener("input", () => clearClientError(field));
  });

  form.addEventListener("submit", (event) => {
    if (!validateClient()) {
      event.preventDefault();
      setLoading(false);
      return;
    }
    setLoading(true);
  });

  setLoading(false);
})();
