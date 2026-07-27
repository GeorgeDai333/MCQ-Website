(function () {
  const form = document.getElementById("quiz-form");
  if (!form) return;

  const autosaveUrl = form.dataset.autosaveUrl;
  const saveBtn = document.getElementById("save-btn");
  const saveIndicator = document.getElementById("save-indicator");

  function doAutosave(useBeacon) {
    const formData = new FormData(form);

    if (useBeacon && navigator.sendBeacon) {
      navigator.sendBeacon(autosaveUrl, formData);
      return;
    }

    fetch(autosaveUrl, {
      method: "POST",
      body: formData,
      headers: { "X-CSRFToken": formData.get("csrfmiddlewaretoken") },
      credentials: "same-origin",
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "submitted") {
          window.location.href = data.redirect_url;
          return;
        }
        if (data.server_time) {
          window.MCQ_CLOCK_OFFSET = new Date(data.server_time).getTime() - Date.now();
        }
        if (saveIndicator) {
          saveIndicator.textContent = "Saved at " + new Date().toLocaleTimeString();
        }
      })
      .catch(() => {
        if (saveIndicator) saveIndicator.textContent = "Save failed -- will retry.";
      });
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", () => doAutosave(false));
  }

  // Periodic background autosave so progress survives a crash/power loss.
  setInterval(() => doAutosave(false), 25000);

  // Best-effort save on tab close/hide (won't survive true power loss, but
  // catches the far more common "closed the tab" case).
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") doAutosave(true);
  });
  window.addEventListener("beforeunload", () => doAutosave(true));
})();
