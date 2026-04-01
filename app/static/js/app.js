document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("input:not([type='password']), textarea").forEach(el => {
    el.addEventListener("input", function() {
      this.value = this.value.toUpperCase();
    });
  });
  document.querySelectorAll(".party-select").forEach(select => {
    const toggle = () => {
      const target = document.getElementById(select.dataset.target);
      if (!target) return;
      if (select.value === "NO") target.classList.remove("hidden");
      else target.classList.add("hidden");
    };
    select.addEventListener("change", toggle);
    toggle();
  });
  const jobInput = document.getElementById("replacementJobId");
  if (jobInput) {
    const syncContext = async () => {
      const v = jobInput.value.trim().toUpperCase();
      if (!v) return;
      try {
        const res = await fetch(`/api/plate-context?job_id=${encodeURIComponent(v)}`);
        const data = await res.json();
        document.getElementById("plateSetPreview").textContent = data.found ? data.plate_set_id : "NOT FOUND";
        document.getElementById("locationPreview").textContent = data.found ? data.location_id : "NOT FOUND";
      } catch (e) {}
    };
    jobInput.addEventListener("blur", syncContext);
    jobInput.addEventListener("change", syncContext);
  }
});
function filterMasterTable() {
  const input = document.getElementById("masterSearch");
  const table = document.getElementById("masterTable");
  if (!input || !table) return;
  const q = input.value.toUpperCase();
  table.querySelectorAll("tbody tr").forEach(row => {
    row.style.display = row.innerText.toUpperCase().includes(q) ? "" : "none";
  });
}
