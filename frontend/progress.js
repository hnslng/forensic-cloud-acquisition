"use strict";

// A byte percentage is valid only after inventory and all source sizes are known.
// Google document exports can have unknown sizes even after inventory finishes.
function acquisitionProgress(job) {
  if (!job) return { mode: "unavailable", percent: null, label: "Kein Sicherungsfortschritt verfügbar" };
  if (job.status === "completed") return { mode: "completed", percent: 100, label: "Abgeschlossen · 100 %" };
  const count = Math.max(0, Number(job.files_discovered) || 0);
  const done = Math.max(0, Number(job.files_done) || 0);
  if (!job.inventory_complete) return { mode: "inventory", percent: null, label: "Dateierfassung noch offen · Gesamtfortschritt noch nicht bestimmbar" };
  if (job.total_known && Number(job.bytes_total) > 0) {
    const percent = Math.max(0, Math.min(99, 100 * (Number(job.bytes_done) || 0) / Number(job.bytes_total)));
    return { mode: "bytes", percent, label: percent.toLocaleString("de-DE", { maximumFractionDigits: 1 }) + " % nach Datenmenge" };
  }
  if (count > 0) return {
    mode: "files", percent: Math.min(99, 100 * done / count),
    label: Math.min(done, count).toLocaleString("de-DE") + " von " + count.toLocaleString("de-DE") + " Dateien gesichert · Fortschritt nach Dateien, Gesamtgröße unbekannt",
  };
  return { mode: "inventory", percent: null, label: "Noch kein Gesamtfortschritt bestimmbar" };
}
if (typeof module !== "undefined" && module.exports) module.exports = { acquisitionProgress };
