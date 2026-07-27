(function () {
  const timerEl = document.getElementById("quiz-timer");
  if (!timerEl) return;

  const deadlineAt = new Date(timerEl.dataset.deadlineAt).getTime();
  const serverTime = new Date(timerEl.dataset.serverTime).getTime();

  // Client display only -- the server independently enforces the real
  // deadline on every autosave/submit/page-load, so a wrong client clock
  // (or disabled JS) can't let a student overrun their time.
  window.MCQ_CLOCK_OFFSET = serverTime - Date.now();

  const remainingEl = document.getElementById("time-remaining");
  let intervalId = null;

  function tick() {
    const now = Date.now() + window.MCQ_CLOCK_OFFSET;
    const remainingMs = deadlineAt - now;

    if (remainingMs <= 0) {
      remainingEl.textContent = "0:00";
      clearInterval(intervalId);
      const form = document.getElementById("quiz-form");
      if (form) form.submit();
      return;
    }

    const totalSeconds = Math.floor(remainingMs / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    remainingEl.textContent = minutes + ":" + String(seconds).padStart(2, "0");

    if (remainingMs < 60000) {
      timerEl.classList.add("low-time");
    }
  }

  intervalId = setInterval(tick, 1000);
  tick();
})();
