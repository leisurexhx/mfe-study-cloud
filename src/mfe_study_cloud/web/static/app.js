function cookieValue(name) {
  const prefix = `${name}=`;
  const item = document.cookie.split("; ").find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

async function pollJob(element) {
  const url = element.dataset.jobUrl;
  if (!url) return;
  const statusTarget = element.querySelector("[data-job-status]");
  const progressTarget = element.querySelector("[data-job-progress]");
  try {
    const response = await fetch(url, { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) return;
    const job = await response.json();
    statusTarget.textContent = job.status;
    progressTarget.textContent = `${job.completed_pages} / ${job.total_pages} 页`;
    if (["queued", "running"].includes(job.status)) {
      window.setTimeout(() => pollJob(element), 2500);
    } else {
      window.setTimeout(() => window.location.reload(), 600);
    }
  } catch (_) {
    window.setTimeout(() => pollJob(element), 5000);
  }
}

async function recordProgress(element) {
  const url = element.dataset.progressUrl;
  const page = Number(element.dataset.page);
  if (!url || !page) return;
  try {
    await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": cookieValue("mfe_csrf") },
      body: JSON.stringify({ page_number: page, seconds_delta: 0 }),
    });
  } catch (_) {
    // Progress is best-effort; the reader remains fully usable when offline.
  }
}

window.addEventListener("DOMContentLoaded", () => {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/service-worker.js");
  const job = document.querySelector("[data-job-url]");
  if (job) pollJob(job);
  const reader = document.querySelector("[data-progress-url]");
  if (reader) recordProgress(reader);
});
