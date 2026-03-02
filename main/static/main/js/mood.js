document.addEventListener("DOMContentLoaded", () => {
  const chips = document.querySelectorAll(".chip");
  const continueBtn = document.getElementById("continueBtn");

  const selected = new Set();

  function syncContinue() {
    if (!continueBtn) return;
    continueBtn.disabled = selected.size === 0;
  }

  chips.forEach((chip) => {
    chip.addEventListener("click", (e) => {
      e.preventDefault();

      const label = chip.textContent.trim();

      // toggle
      if (selected.has(label)) {
        selected.delete(label);
        chip.classList.remove("chip--selected");
      } else {
        selected.add(label);
        chip.classList.add("chip--selected");
      }

      syncContinue();
      console.log("Selected moods:", Array.from(selected));
    });
  });

  if (continueBtn) {
    continueBtn.addEventListener("click", () => {
      const baseUrl = continueBtn.dataset.resultsUrl || "/results/";
      const moods = Array.from(selected).join(",");
      window.location.href = `${baseUrl}?moods=${encodeURIComponent(moods)}`;
    });
  }

  // initial state
  syncContinue();
});
