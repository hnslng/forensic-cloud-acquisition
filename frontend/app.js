"use strict";
const $ = (id) => document.getElementById(id);
const providers = { apple: "iCloud", google: "Google", microsoft: "OneDrive" };
const statuses = {
  active: "Aktiv",
  completed: "Abgeschlossen",
  archived: "Archiviert",
};
const eventNames = {
  case_created: "Fall angelegt",
  case_updated: "Fall aktualisiert",
  case_member_granted: "Fallzugriff erteilt",
  case_member_revoked: "Fallzugriff entzogen",
  cloud_account_added: "Cloud-Konto hinzugefügt",
  cloud_account_renamed: "Cloud-Bezeichnung geändert",
};
let currentUser = null,
  activeCase = null,
  caseList = [],
  cloudList = [],
  authGeneration = 0,
  caseGeneration = 0,
  caseSubmitting = false;
let connectionContext = null;
let dialogStack = [],
  loginContinuation = null,
  cloudContext = null;
function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
const formData = (form) => Object.fromEntries(new FormData(form));
function clearMessages() {
  $("message").hidden = true;
  document.querySelectorAll(".dialog-message").forEach((el) => {
    el.hidden = true;
    el.textContent = "";
  });
}
function message(text) {
  const dialog = [...dialogStack]
    .reverse()
    .map($)
    .find((el) => el.open);
  const target = dialog?.querySelector(".dialog-message") || $("message");
  target.textContent = text;
  target.hidden = false;
}
function syncBackdrops() {
  dialogStack = dialogStack.filter((id) => $(id).open);
  for (const id of dialogStack)
    $(id).classList.toggle("nested-open", id !== dialogStack.at(-1));
}
function openDialog(id) {
  clearMessages();
  const dialog = $(id);
  if (!dialog.open) {
    dialog.showModal();
    dialogStack.push(id);
  }
  syncBackdrops();
}
function closeDialog(id) {
  if ($(id).open) $(id).close();
  syncBackdrops();
}
function closeDialogs() {
  [...dialogStack].reverse().forEach(closeDialog);
}
async function api(path, options = {}) {
  const csrf = decodeURIComponent(
    document.cookie
      .split("; ")
      .find((c) => c.startsWith("__Host-fca_csrf="))
      ?.split("=")[1] || "",
  );
  const response = await fetch("/api" + path, {
    credentials: "same-origin",
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf,
      ...options.headers,
    },
  });
  if (!response.headers.get("content-type")?.includes("application/json"))
    throw new Error("Server derzeit nicht verfügbar. Bitte erneut versuchen.");
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401 && currentUser) lockApplication();
    throw new Error(result.detail || "Anfrage fehlgeschlagen.");
  }
  return result;
}
function renderWorkspace() {
  const ready = Boolean(activeCase && currentUser);
  $("start-overlay").hidden = ready;
  $("workspace-frame").inert = !ready;
  $("active-case-display").classList.toggle("locked", !ready);
  $("active-case-number").textContent = ready
    ? activeCase.business_number
    : "KEIN FALL";
  $("active-operator").textContent = ready
    ? "Bearbeiter " + activeCase.operator_initials
    : "";
  $("system-state").textContent = ready ? "FALL AKTIV" : "KEIN FALL AKTIV";
  $("dock-case-name").textContent = ready
    ? activeCase.name || "OHNE FALLBEZEICHNUNG"
    : "KEIN FALL GESTARTET";
  $("dock-case-note").textContent = ready
    ? "Fallstatus: " + statuses[activeCase.status]
    : "Fallnummer und Bearbeiter eingeben, dann „Fall starten“.";
  $("open-case-button").textContent = ready
    ? "Fall wechseln / öffnen"
    : "+ Fall anlegen / öffnen";
  $("case-status").textContent = ready
    ? statuses[activeCase.status]
    : "Kein Fall aktiv";
  $("case-status").classList.toggle(
    "status-success",
    ready && activeCase.status === "active",
  );
  $("leave-case-button").hidden = !ready;
  $("add-cloud-button").disabled = !ready || !activeCase.can_edit;
  $("audit-panel").hidden = !ready;
  renderClouds();
}
function clearCase() {
  caseGeneration++;
  activeCase = null;
  cloudList = [];
  cloudContext = null;
  connectionContext = null;
  $("cloud-list").replaceChildren();
  $("audit-list").replaceChildren();
  $("acquisition-history-list").replaceChildren();
  $("member-list").replaceChildren();
  $("member-user").replaceChildren();
  $("audit-panel").open = false;
  $("edit-case-form").reset();
  ["edit-case-context", "rights-context", "cloud-case-context"].forEach(
    (id) => ($(id).textContent = ""),
  );
  renderWorkspace();
  updateSettingsIdentity();
}
function lockApplication() {
  authGeneration++;
  currentUser = null;
  caseList = [];
  closeDialogs();
  clearMessages();
  clearCase();
  sessionStorage.removeItem("fca-return-case");
  sessionStorage.removeItem("fca-oauth");
  $("case-list").replaceChildren();
  $("case-search").value = "";
  $("login-form").reset();
  $("user-rows").replaceChildren();
  $("case-form").reset();
  $("cloud-form").reset();
  $("user-form").reset();
  $("password-form").reset();
  $("icloud-login-form").reset();
  $("icloud-confirm-form").reset();
  $("icloud-entries").replaceChildren();
  $("icloud-context").textContent = "";
  $("icloud-path").textContent = "";
  $("technical-status").textContent = "Zur Statusanzeige anmelden.";
  document
    .querySelectorAll("input[type=password]")
    .forEach((input) => (input.value = ""));
  updateCaseReadiness();
}
function updateSettingsIdentity() {
  const logged = Boolean(currentUser),
    admin = currentUser?.role === "admin";
  $("settings-identity").textContent = logged
    ? currentUser.username +
      " / " +
      currentUser.initials +
      " · " +
      (admin ? "Administrator" : "Bearbeiter")
    : "NICHT ANGEMELDET";
  $("settings-login").hidden = logged;
  $("logout-button").hidden = !logged;
  $("password-button").hidden = !logged;
  $("users-tab").hidden = !admin;
  $("rights-tab").hidden = !admin;
  $("case-edit-section").hidden = !activeCase;
  $("case-session-info").textContent = logged
    ? "Angemeldet als " + currentUser.username
    : "Geschützte Arbeitssitzung erforderlich.";
  $("case-login-button").hidden = logged;
  $("archive-count").textContent = logged
    ? caseList.length + " FALLAKTEN"
    : "ANMELDUNG ERFORDERLICH";
  if (activeCase) {
    const form = $("edit-case-form");
    form.elements.version.value = activeCase.version;
    form.elements.name.value = activeCase.name;
    form.elements.status.value = activeCase.status;
    form.elements.operator_initials.value = currentUser?.initials || "";
    for (const el of form.elements) el.disabled = !activeCase.can_edit;
    $("edit-case-context").textContent = activeCase.business_number;
  }
}
function updateCaseReadiness() {
  const ready = Boolean(currentUser && $("case-form").checkValidity());
  $("case-start").disabled = !ready || caseSubmitting;
  $("case-start-message").textContent = caseSubmitting
    ? "FALL WIRD GESTARTET …"
    : !currentUser
      ? "BITTE ARBEITSSITZUNG ANMELDEN"
      : ready
        ? "BEREIT — FALL AUSDRÜCKLICH STARTEN"
        : "GESCHÄFTSZAHL UND BEARBEITERKÜRZEL EINGEBEN";
  $("case-start-message").classList.toggle("ready", ready && !caseSubmitting);
}
async function refreshIndex() {
  const generation = authGeneration;
  const rows = await api("/cases");
  if (generation !== authGeneration || !currentUser) return;
  caseList = rows;
  updateSettingsIdentity();
  renderArchive();
}
async function refreshTechnical() {
  const generation = authGeneration;
  const status = await api("/status");
  if (generation !== authGeneration || !currentUser) return;
  $("technical-status").textContent =
    (status.evidence_mounted
      ? "Sicherungsdatenträger verfügbar"
      : "Sicherungsdatenträger nicht verfügbar") +
    (status.free_bytes === null
      ? ""
      : " · " + (status.free_bytes / 1024 ** 3).toFixed(1) + " GiB frei");
}
async function signedIn(user) {
  currentUser = user;
  if (!$("case-form").elements.operator_initials.value)
    $("case-form").elements.operator_initials.value = user.initials;
  updateSettingsIdentity();
  updateCaseReadiness();
  await refreshIndex();
  const returnCase=sessionStorage.getItem("fca-return-case");
  sessionStorage.removeItem("fca-return-case");
  if(returnCase && /^[a-f0-9-]{36}$/i.test(returnCase)) await activateCase(returnCase);
}
function openCaseForm() {
  $("case-form").reset();
  if (currentUser)
    $("case-form").elements.operator_initials.value = currentUser.initials;
  updateSettingsIdentity();
  updateCaseReadiness();
  openDialog("case-dialog");
}
function openLogin(continuation = null) {
  loginContinuation = continuation;
  openDialog("login-dialog");
}
async function openArchive() {
  if (!currentUser) {
    openLogin(openArchive);
    return;
  }
  await refreshIndex();
  if (!currentUser) return;
  openDialog("archive-dialog");
}
function renderArchive() {
  const query = $("case-search").value.toLocaleLowerCase();
  $("case-list").replaceChildren();
  const rows = caseList.filter((c) =>
    (c.business_number + " " + c.name).toLocaleLowerCase().includes(query),
  );
  if (!rows.length)
    $("case-list").append(
      node(
        "p",
        query ? "KEINE PASSENDEN FÄLLE" : "NOCH KEINE FÄLLE VORHANDEN",
        "case-profile-hint",
      ),
    );
  for (const c of rows) {
    const row = node("div", undefined, "case-list-row"),
      copy = node("div", undefined, "case-list-copy"),
      button = node("button", "Fall öffnen →");
    copy.append(
      node("strong", c.business_number),
      node(
        "span",
        (c.name || "Ohne Fallbezeichnung") + " · " + statuses[c.status],
      ),
    );
    button.type = "button";
    button.addEventListener("click", () =>
      activateCase(c.id).catch((e) => message(e.message)),
    );
    row.append(copy, button);
    $("case-list").append(row);
  }
}
async function activateCase(id) {
  const generation = ++caseGeneration,
    auth = authGeneration;
  const [c, accounts, audit] = await Promise.all([
    api("/cases/" + id),
    api("/cases/" + id + "/cloud-accounts"),
    api("/cases/" + id + "/audit"),
  ]);
  if (generation !== caseGeneration || auth !== authGeneration || !currentUser)
    return;
  activeCase = c;
  cloudList = accounts;
  closeDialogs();
  clearMessages();
  renderWorkspace();
  renderAudit(audit);
  updateSettingsIdentity();
  $("add-cloud-button").focus();
}
function renderAudit(rows) {
  $("audit-list").replaceChildren();
  for (const a of rows) {
    const row = node("div", undefined, "audit-row");
    row.append(
      node("time", new Date(a.occurred_at).toLocaleString("de-AT")),
      node(
        "b",
        (eventNames[a.event_type] || a.event_type) +
          " / " +
          (a.actor || "System"),
      ),
      node("span", a.operator_initials || "–"),
    );
    $("audit-list").append(row);
  }
}
async function refreshActive(id) {
  if (activeCase?.id !== id) return;
  const generation = ++caseGeneration,
    auth = authGeneration;
  const [c, accounts, audit] = await Promise.all([
    api("/cases/" + id),
    api("/cases/" + id + "/cloud-accounts"),
    api("/cases/" + id + "/audit"),
  ]);
  if (
    generation !== caseGeneration ||
    auth !== authGeneration ||
    !currentUser ||
    activeCase?.id !== id
  )
    return;
  activeCase = c;
  cloudList = accounts;
  renderWorkspace();
  renderAudit(audit);
  updateSettingsIdentity();
}
function renderClouds() {
  $("cloud-list").replaceChildren();
  $("cloud-count").textContent = cloudList.length + " KONTEN";
  $("cloud-empty").hidden = cloudList.length > 0;
  $("cloud-empty-title").textContent = activeCase
    ? "NOCH KEINE CLOUD-KONTEN"
    : "KEIN FALL AKTIV";
  $("cloud-empty-copy").textContent = activeCase
    ? "Über „+ Cloud hinzufügen“ ein Konto diesem Fall zuordnen."
    : "Zuerst einen Fall starten. Cloud-Konten werden ausschließlich diesem Fall zugeordnet.";
  for (const account of cloudList) {
    const card = node("article", undefined, "cloud-card");
    card.dataset.accountId = account.id;
    card.dataset.provider = account.provider;
    card.setAttribute("aria-label", account.label);
    const top = node("div", undefined, "cloud-card-top");
    const identity = node("div", undefined, "cloud-identity");
    const mark = node("span", undefined, "provider-mark");
    // Fixed local assets: no requests to providers and no account-supplied URLs.
    const logo = document.createElement("img");
    logo.src = "/icons/" + ({apple:"apple",google:"google",microsoft:"microsoft"}[account.provider]) + ".svg";
    logo.alt = {apple:"Apple iCloud",google:"Google",microsoft:"Microsoft"}[account.provider];
    logo.width = 36; logo.height = 36;
    mark.append(logo);
    const copy = node("div", undefined, "cloud-identity-copy");
    copy.append(
      node("h3", account.label, "cloud-name"),
      node(
        "p",
        {
          apple: "Apple iCloud · Drive und Fotos",
          google: "Google · Drive und Kalender",
          microsoft: "Microsoft · OneDrive und Outlook-Kalender",
        }[account.provider],
        "provider-description",
      ),
    );
    identity.append(mark, copy);
    const connectionStatus = account.connection_status;
    const job = account.acquisition;
    const busy = job && ["queued","running","pausing"].includes(job.status);
    const activeFiles = busy ? Number(job.files_active ?? 0) : 0;
    const downloading = activeFiles > 0;
    const discovering = job?.status === "running" && !job.inventory_complete;
    const jobLabels = {queued:"Wartet", running:discovering ? (downloading || job.bytes_done > 0 || job.files_done > 0 ? "Erfassen und herunterladen" : "Dateien werden erfasst") : "Dateien werden heruntergeladen", pausing:"Wird pausiert", paused:"Pausiert", failed:"Fehlgeschlagen", incomplete:"Unvollständig", completed:"Abgeschlossen"};
    const connectionLabel =
      {
        connected: "Verbunden",
        challenge: "2FA ausstehend",
        expired: "Erneut anmelden",
        error: "Anmeldung fehlgeschlagen",
      }[connectionStatus] || "Nicht verbunden";
    top.append(
      identity,
      node(
        "span",
        job ? jobLabels[job.status] : connectionLabel,
        "status-badge " +
          ((job ? job.status === "completed" : connectionStatus === "connected")
            ? "status-success"
            : "status-disconnected"),
      ),
    );
    const information = node("div", undefined, "acquisition-info");
    information.append(
      node("strong", job ? ({drive:"Dateien",photos:"Fotos",both:"iCloud Drive und Fotos",calendar:"Kalender"}[job.category]) : "Noch keine Sicherung gestartet"),
      node(
        "p",
        job?.reason || (job?.status === "pausing" ? "Laufende Übertragungen werden angehalten. Danach erscheint Fortsetzen." : discovering ? "Dateierfassung läuft noch. Bereits erfasste Dateien werden parallel heruntergeladen." : busy ? "Die Sicherung läuft im Hintergrund weiter." : (account.can_authenticate
          ? connectionStatus === "connected"
            ? "Bereit zur Sicherung. Datenbereich auswählen und starten."
            : "Nächster Schritt: Cloud-Konto anmelden."
          : "Anmeldung muss in den Einstellungen eingerichtet werden.")),
      ),
    );
    const progress = node("div", undefined, "acquisition-progress");
    const summary = node("div", undefined, "progress-summary");
    summary.append(
      node("span", job ? formatBytes(job.bytes_done) + " übertragen" : "Noch keine Daten übertragen"),
      node("span", job ? Number(job.files_discovered ?? 0).toLocaleString("de-DE") + (job.inventory_complete ? " Dateien insgesamt · Erfassung abgeschlossen" : " Dateien erfasst · Dateierfassung noch offen") : ""),
    );
    const track = node("div", undefined, "progress-track unavailable");
    track.setAttribute("role", "img");
    track.setAttribute("aria-label", "Kein Sicherungsfortschritt verfügbar");
    if (job) {
      track.classList.remove("unavailable");
      const fill = node("div", undefined, "progress-fill");
      const percent = job.status === "completed" ? 100 : (job.inventory_complete && job.total_known && job.bytes_total > 0 ? Math.min(99, 100 * job.bytes_done / job.bytes_total) : 0);
      fill.style.width = percent + "%";
      if (job.status === "completed") fill.style.background = "#47B881";
      track.replaceChildren(fill);
      track.setAttribute("aria-label", jobLabels[job.status]);
    }
    const metrics = node("div", undefined, "transfer-metrics");
    metrics.append(
      node("span", job?.status === "running" ? activeFiles + " von " + job.configured_limit + " Downloads aktiv" + (job.transfer_limit < job.configured_limit ? " · vorübergehend gedrosselt" : "") : "Downloads: —"),
      node("span", job?.status === "running" ? "Gesamtgeschwindigkeit: " + formatBytes(job.speed || 0) + "/s" : "Geschwindigkeit: —"),
      node("span", !discovering && job?.speed && job.total_known && job.bytes_total > job.bytes_done ? "Restzeit: ca. " + Math.ceil((job.bytes_total-job.bytes_done)/job.speed/60) + " Min." : "Restzeit: —"),
      node("span", job ? "MD5: " + (job.md5_done ?? 0) + ((job.md5_done ?? 0) < job.files_done ? " von " + job.files_done : "") + " Dateien geprüft" : "MD5: noch nicht verfügbar"),
    );
    progress.append(summary, track, metrics);
    const actions = node("div", undefined, "cloud-actions");
    const authenticate = node(
      "button",
      connectionStatus === "connected"
        ? "Erneut anmelden"
        : "Anmelden",
    );
    authenticate.type = "button";
    authenticate.disabled = !activeCase.can_edit || !account.can_authenticate || busy;
    authenticate.title = account.can_authenticate
      ? "Mit deinem vorbereiteten iCloud-Konto anmelden"
      : "Noch nicht verfügbar";
    authenticate.addEventListener("click", () => account.provider === "apple" ? openICloud(account) : beginOAuth(account));
    const browse = node("button", "Bereiche ansehen");
    browse.type = "button";
    browse.disabled = !activeCase.can_edit || !account.can_browse || busy;
    browse.addEventListener("click", () => openICloud(account, true));
    const acquire = node("button", "Sicherung starten");
    acquire.type = "button";
    acquire.disabled = !activeCase.can_edit || !account.can_acquire || busy || job?.status === "paused";
    acquire.title = "Datenbereich auswählen und sichern";
    acquire.addEventListener("click", () => openAcquisition(account));
    if (!busy) {
      actions.append(authenticate);
      if(account.provider === "apple") actions.append(browse);
      if(job?.status !== "paused") actions.append(acquire);
    }
    if (job) {
      const history=node("button","Sicherungsläufe");
      history.addEventListener("click",()=>showAcquisitionHistory(account).catch(error=>message(error.message)));
      actions.append(history);
    }
    if (job && activeCase.can_edit && ["queued","running","pausing","paused","failed"].includes(job.status)) {
      const action = ["queued","running"].includes(job.status) ? "pause" : "resume";
      const control = node("button", job.status === "pausing" ? "Wird angehalten …" : action === "pause" ? "Pausieren" : "Fortsetzen");
      control.disabled = job.status === "pausing";
      control.addEventListener("click", async () => {
        control.disabled = true;
        try { await api("/cases/"+activeCase.id+"/acquisitions/"+job.id+"/"+action,{method:"POST",body:"{}"}); await refreshActive(activeCase.id); }
        catch(error) { message(error.message); control.disabled=false; }
      });
      actions.append(control);
    }
    const rename = node("button", "Bezeichnung bearbeiten", "cloud-rename");
    rename.type = "button";
    rename.disabled = !activeCase?.can_edit;
    rename.addEventListener("click", () => openCloud(account));
    const footer = node("div", undefined, "cloud-card-footer");
    footer.append(actions, rename);
    card.append(top, information, progress, footer);
    $("cloud-list").append(card);
  }
}
function openICloud(account, browse = false) {
  if (!activeCase?.can_edit) return;
  connectionContext = {
    caseId: activeCase.id,
    accountId: account.id,
    challengeId: null,
    service: null,
    path: "",
  };
  $("icloud-context").textContent =
    activeCase.business_number + " / " + account.label;
  $("icloud-login-form").reset();
  $("icloud-confirm-form").reset();
  $("icloud-login-form").hidden = browse;
  $("icloud-confirm-form").hidden = true;
  $("icloud-browser").hidden = !browse;
  $("icloud-entries").replaceChildren();
  $("icloud-path").textContent = "Noch kein Bereich geöffnet.";
  $("icloud-up").hidden = true;
  $("icloud-forget").hidden = !account.can_browse;
  openDialog("icloud-dialog");
}
async function icloudRequest(context, action, body) {
  return api(
    "/cases/" +
      context.caseId +
      "/cloud-accounts/" +
      context.accountId +
      "/icloud/" +
      action,
    { method: "POST", body: JSON.stringify(body) },
  );
}
function showICloudStep(context, result) {
  if (connectionContext !== context || activeCase?.id !== context.caseId)
    return;
  $("icloud-login-form").hidden = true;
  $("icloud-confirm-form").hidden = result.status !== "challenge";
  $("icloud-browser").hidden = result.status !== "connected";
  $("icloud-forget").hidden = result.status !== "connected";
  if (result.status === "challenge") {
    context.challengeId = result.challenge_id;
    const form = $("icloud-confirm-form");
    form.reset();
    const choices = $("icloud-choices");
    choices.replaceChildren();
    for (const value of result.choices || []) {
      const option = node("option", value);
      option.value = value;
      choices.append(option);
    }
    choices.hidden = !(result.choices || []).length;
    form.elements.answer.hidden = !choices.hidden;
    form.elements.answer.required = choices.hidden;
    $("icloud-challenge-hint").textContent =
      result.field === "config_2fa_phone"
        ? "Apple bietet mehrere Zustellwege. Bitte einen Auswahlwert wählen."
        : "Bestätigungscode vom vertrauenswürdigen Apple-Gerät eingeben. Falls benötigt, „sms“ eingeben, um einen SMS-Code anzufordern.";
    if (choices.hidden) form.elements.answer.focus();
  } else
    message(
      "iCloud-Anmeldung abgeschlossen. Wähle jetzt Drive oder Fotos, um die zugänglichen Bereiche anzusehen. Es wird nichts heruntergeladen.",
    );
}
async function browseICloud(service, path = "") {
  const context = connectionContext;
  if (!context || activeCase?.id !== context.caseId) return;
  const auth = authGeneration;
  $("icloud-entries").replaceChildren(node("p", "Bereich wird abgefragt …"));
  $("icloud-browser").setAttribute("aria-busy", "true");
  try {
    const result = await icloudRequest(context, "browse", { service, path });
    if (
      connectionContext !== context ||
      auth !== authGeneration ||
      activeCase?.id !== context.caseId
    )
      return;
    context.service = service;
    context.path = path;
    $("icloud-path").textContent =
      (service === "drive" ? "iCloud Drive" : "iCloud Fotos") +
      (path ? " / " + path : "");
    $("icloud-up").hidden = !path;
    $("icloud-entries").replaceChildren();
    if (!result.entries.length)
      $("icloud-entries").append(
        node(
          "p",
          "Dieser Bereich ist leer oder enthält keine zugänglichen Einträge.",
        ),
      );
    for (const entry of result.entries) {
      const row = node("div", undefined, "icloud-entry");
      row.append(
        node("span", entry.is_dir ? "Ordner / Album" : "Datei", "entry-type"),
        node("strong", entry.name),
      );
      if (entry.is_dir) {
        const button = node("button", "Öffnen");
        button.type = "button";
        button.addEventListener("click", () =>
          browseICloud(service, entry.path).catch((e) => message(e.message)),
        );
        row.append(button);
      } else
        row.append(
          node(
            "span",
            entry.size >= 0
              ? (entry.size / 1024 ** 2).toFixed(2) + " MiB"
              : "Größe unbekannt",
          ),
        );
      $("icloud-entries").append(row);
    }
  } catch (error) {
    if (connectionContext === context)
      $("icloud-entries").replaceChildren(
        node(
          "p",
          "Bereich konnte nicht geöffnet werden. Erneute Anmeldung oder Freigabe auf dem Apple-Gerät kann erforderlich sein.",
        ),
      );
    throw error;
  } finally {
    $("icloud-browser").removeAttribute("aria-busy");
  }
}
function openCloud(account = null) {
  if (!activeCase?.can_edit) return;
  cloudContext = {
    caseId: activeCase.id,
    businessNumber: activeCase.business_number,
    account,
  };
  const form = $("cloud-form");
  form.reset();
  $("provider-choices").disabled = Boolean(account);
  if (account) {
    form.elements.provider.value = account.provider;
    form.elements.label.value = account.label;
  }
  $("cloud-title").textContent = account
    ? "CLOUD-BEZEICHNUNG BEARBEITEN"
    : "CLOUD HINZUFÜGEN";
  $("cloud-submit").textContent = account
    ? "Bezeichnung speichern"
    : "Cloud hinzufügen";
  $("cloud-case-context").textContent = "FALL / " + activeCase.business_number;
  openDialog("cloud-dialog");
  if (account) form.elements.label.focus();
}
async function selectPane(pane) {
  if (["users", "rights"].includes(pane) && currentUser?.role !== "admin")
    return;
  document
    .querySelectorAll("[data-pane]")
    .forEach((button) =>
      button.setAttribute("aria-pressed", String(button.dataset.pane === pane)),
    );
  document
    .querySelectorAll("[data-settings-pane]")
    .forEach(
      (section) => (section.hidden = section.dataset.settingsPane !== pane),
    );
  if (pane === "users") await loadUsers();
  if (pane === "rights") await loadRights();
  if (pane === "technical" && currentUser) { await refreshTechnical(); await loadDownloadSettings(); }
}
function openSettings() {
  updateSettingsIdentity();
  openDialog("settings-dialog");
  selectPane("session").catch((e) => message(e.message));
}
async function loadUsers() {
  const auth = authGeneration;
  const users = await api("/admin/users");
  if (auth !== authGeneration || currentUser?.role !== "admin") return;
  $("user-rows").replaceChildren();
  for (const u of users) {
    const row = node("tr"),
      action = node("td");
    if (u.id !== currentUser.id) {
      const button = node("button", u.active ? "Deaktivieren" : "Aktivieren");
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await api("/admin/users/" + u.id, {
            method: "PATCH",
            body: JSON.stringify({ active: !u.active }),
          });
          await loadUsers();
        } catch (e) {
          message(e.message);
          button.disabled = false;
        }
      });
      action.append(button);
    }
    row.append(
      node("td", u.username),
      node("td", u.initials),
      node("td", u.role === "admin" ? "Administrator" : "Bearbeiter"),
      node("td", u.active ? "Aktiv" : "Deaktiviert"),
      action,
    );
    $("user-rows").append(row);
  }
}
async function loadRights() {
  const c = activeCase,
    auth = authGeneration;
  $("membership-panel").hidden = !c;
  $("rights-context").textContent = c
    ? "FALL / " + c.business_number
    : "Zuerst einen Fall öffnen.";
  $("member-list").replaceChildren();
  $("member-user").replaceChildren();
  if (!c) return;
  const [users, members] = await Promise.all([
    api("/admin/users"),
    api("/cases/" + c.id + "/members"),
  ]);
  if (
    auth !== authGeneration ||
    activeCase?.id !== c.id ||
    currentUser?.role !== "admin"
  )
    return;
  for (const u of users.filter((u) => u.active)) {
    const opt = node("option", u.username + " / " + u.initials);
    opt.value = u.id;
    $("member-user").append(opt);
  }
  for (const m of members) {
    const row = node(
        "p",
        m.username +
          " / " +
          (m.access === "editor" ? "Bearbeiten" : "Lesen") +
          " ",
      ),
      button = node("button", "Zugriff entziehen");
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await api("/cases/" + c.id + "/members/" + m.id, { method: "DELETE" });
        if (activeCase?.id === c.id) {
          await loadRights();
          await refreshActive(c.id);
        }
      } catch (e) {
        message(e.message);
        button.disabled = false;
      }
    });
    row.append(button);
    $("member-list").append(row);
  }
}
function formAction(id, action) {
  $(id).addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget,
      button = form.querySelector('button[type="submit"]');
    if (button?.disabled) return;
    if (button) button.disabled = true;
    clearMessages();
    try {
      await action(form);
    } catch (e) {
      message(e.message);
    } finally {
      if (button) button.disabled = false;
      if (id === "case-form") updateCaseReadiness();
    }
  });
}
formAction("icloud-login-form", async (form) => {
  const context = connectionContext,
    auth = authGeneration;
  if (!context) return;
  try {
    const result = await icloudRequest(context, "login", formData(form));
    if (auth !== authGeneration || context !== connectionContext) return;
    showICloudStep(context, result);
    await refreshActive(context.caseId);
  } finally {
    form.elements.password.value = "";
  }
});
formAction("icloud-confirm-form", async (form) => {
  const context = connectionContext,
    auth = authGeneration;
  if (!context) return;
  const answer = $("icloud-choices").hidden
    ? form.elements.answer.value
    : $("icloud-choices").value;
  try {
    const result = await icloudRequest(context, "confirm", {
      challenge_id: context.challengeId,
      answer,
    });
    if (auth !== authGeneration || context !== connectionContext) return;
    showICloudStep(context, result);
    await refreshActive(context.caseId);
  } finally {
    form.elements.answer.value = "";
  }
});
$("icloud-drive").addEventListener("click", () =>
  browseICloud("drive").catch((e) => message(e.message)),
);
$("icloud-photos").addEventListener("click", () =>
  browseICloud("photos").catch((e) => message(e.message)),
);
$("icloud-up").addEventListener("click", () => {
  const c = connectionContext;
  if (c)
    browseICloud(c.service, c.path.split("/").slice(0, -1).join("/")).catch(
      (e) => message(e.message),
    );
});
$("icloud-forget").addEventListener("click", async () => {
  const context = connectionContext;
  if (!context) return;
  $("icloud-forget").disabled = true;
  try {
    await icloudRequest(context, "forget", {});
    if (connectionContext !== context) return;
    closeDialog("icloud-dialog");
    await refreshActive(context.caseId);
  } catch (e) {
    message(e.message);
  } finally {
    $("icloud-forget").disabled = false;
  }
});
formAction("login-form", async (form) => {
  const generation = ++authGeneration;
  try {
    const user = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify(formData(form)),
    });
    if (generation !== authGeneration) return;
    const continuation = loginContinuation;
    await signedIn(user);
    closeDialog("login-dialog");
    if (continuation) await continuation();
  } finally {
    form.elements.password.value = "";
  }
});
formAction("case-form", async (form) => {
  caseSubmitting = true;
  updateCaseReadiness();
  const auth = authGeneration;
  try {
    const c = await api("/cases", {
      method: "POST",
      body: JSON.stringify(formData(form)),
    });
    if (auth !== authGeneration || !currentUser) return;
    closeDialog("case-dialog");
    await refreshIndex();
    await activateCase(c.id);
  } finally {
    caseSubmitting = false;
    updateCaseReadiness();
  }
});
formAction("cloud-form", async (form) => {
  const context = cloudContext,
    auth = authGeneration;
  if (!context || !currentUser) return;
  const label = form.elements.label.value;
  const path =
    "/cases/" +
    context.caseId +
    "/cloud-accounts" +
    (context.account ? "/" + context.account.id : "");
  const body = context.account
    ? { label, version: context.account.version }
    : { label, provider: form.elements.provider.value };
  await api(path, {
    method: context.account ? "PATCH" : "POST",
    body: JSON.stringify(body),
  });
  if (auth !== authGeneration) return;
  closeDialog("cloud-dialog");
  await refreshActive(context.caseId);
});
formAction("edit-case-form", async (form) => {
  const id = activeCase?.id;
  if (!id) return;
  await api("/cases/" + id, {
    method: "PATCH",
    body: JSON.stringify({
      ...formData(form),
      version: Number(form.elements.version.value),
    }),
  });
  await refreshIndex();
  await refreshActive(id);
});
formAction("member-form", async (form) => {
  const id = activeCase?.id;
  if (!id) return;
  await api("/cases/" + id + "/members", {
    method: "PUT",
    body: JSON.stringify(formData(form)),
  });
  if (activeCase?.id === id) {
    await loadRights();
    await refreshActive(id);
  }
});
formAction("user-form", async (form) => {
  try {
    await api("/admin/users", {
      method: "POST",
      body: JSON.stringify(formData(form)),
    });
    closeDialog("user-dialog");
    form.reset();
    await loadUsers();
  } finally {
    form.elements.password.value = "";
  }
});
formAction("password-form", async (form) => {
  try {
    await api("/auth/password", {
      method: "POST",
      body: JSON.stringify(formData(form)),
    });
    lockApplication();
    message("Passwort geändert. Bitte erneut anmelden.");
  } finally {
    form.reset();
  }
});
$("start-open-case").addEventListener("click", openCaseForm);
$("open-case-button").addEventListener("click", openCaseForm);
$("open-archive").addEventListener("click", () =>
  openArchive().catch((e) => message(e.message)),
);
$("case-login-button").addEventListener("click", () => openLogin());
$("settings-login").addEventListener("click", () => openLogin());
$("start-settings").addEventListener("click", openSettings);
$("open-settings").addEventListener("click", openSettings);
$("leave-case-button").addEventListener("click", clearCase);
$("home-button").addEventListener("click", () =>
  window.scrollTo({ top: 0, behavior: "smooth" }),
);
$("add-cloud-button").addEventListener("click", () => openCloud());
$("add-user-button").addEventListener("click", () => openDialog("user-dialog"));
$("password-button").addEventListener("click", () =>
  openDialog("password-dialog"),
);
$("logout-button").addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST", body: "{}" });
    lockApplication();
  } catch (e) {
    message(e.message);
  }
});
$("case-form").addEventListener("input", updateCaseReadiness);
$("case-search").addEventListener("input", renderArchive);
document
  .querySelectorAll("[data-close]")
  .forEach((button) =>
    button.addEventListener("click", () => closeDialog(button.dataset.close)),
  );
document
  .querySelectorAll("[data-pane]")
  .forEach((button) =>
    button.addEventListener("click", () =>
      selectPane(button.dataset.pane).catch((e) => message(e.message)),
    ),
  );
document.querySelectorAll("dialog").forEach((dialog) =>
  dialog.addEventListener("close", () => {
    dialog
      .querySelectorAll('input[type="password"]')
      .forEach((input) => (input.value = ""));
    if (dialog.id === "login-dialog") loginContinuation = null;
    if (dialog.id === "icloud-dialog") {
      connectionContext = null;
      $("icloud-login-form").reset();
      $("icloud-confirm-form").reset();
      $("icloud-entries").replaceChildren();
      $("icloud-context").textContent = "";
      $("icloud-path").textContent = "";
    }
    syncBackdrops();
  }),
);
function clock() {
  $("clock").textContent = "LOKAL " + new Date().toLocaleTimeString("de-AT");
}
clock();
setInterval(clock, 1000);
renderWorkspace();
updateCaseReadiness();
const initialAuth = authGeneration;
api("/auth/me")
  .then((user) => {
    if (initialAuth === authGeneration) return signedIn(user);
  })
  .catch(() => {});


function formatBytes(value) {
  if (value < 1024) return value + " B";
  const units=["KiB","MiB","GiB","TiB"]; let amount=value/1024, index=0;
  while(amount>=1024 && index<units.length-1){amount/=1024;index++;}
  return amount.toLocaleString("de-AT",{maximumFractionDigits:1})+" "+units[index];
}
async function beginOAuth(account){
  try {
    const context={case_id:activeCase.id,account_id:account.id};
    const result=await api("/cases/"+context.case_id+"/cloud-accounts/"+account.id+"/oauth/begin",{method:"POST",body:"{}"});
    sessionStorage.setItem("fca-oauth",JSON.stringify(context));
    location.assign(result.url);
  } catch(error){message(error.message);}
}
let acquisitionContext=null;
function openAcquisition(account){
  acquisitionContext={caseId:activeCase.id,accountId:account.id,provider:account.provider,auth:authGeneration};
  const form=$("acquisition-form");form.reset();
  $("acquisition-context").textContent=account.label;
  form.elements.service.replaceChildren();
  for(const [value,label] of (account.provider === "apple" ? [["both","iCloud Drive und Fotos"],["drive","Nur iCloud Drive"],["photos","Nur iCloud Fotos"]] : [["drive",account.provider === "google"?"Google Drive":"OneDrive"],["calendar",account.provider === "google"?"Google Kalender":"Outlook-Kalender"]])){
    const option=node("option",label);option.value=value;form.elements.service.append(option);
  }
  $("scope-field").hidden=account.provider!=="apple";
  updateCalendarPeriod();
  openDialog("acquisition-dialog");
}
formAction("acquisition-form",async(form)=>{
  const context=acquisitionContext;if(!context || context.auth!==authGeneration || activeCase?.id!==context.caseId)return;
  await api("/cases/"+context.caseId+"/cloud-accounts/"+context.accountId+"/acquisitions",{method:"POST",body:JSON.stringify(formData(form))});
  closeDialog("acquisition-dialog");await refreshActive(context.caseId);
});
async function loadDownloadSettings(){
  $("download-settings").hidden=currentUser?.role!=="admin";
  $("oauth-settings").hidden=currentUser?.role!=="admin";
  if(currentUser?.role!=="admin")return;
  const result=await api("/admin/acquisition-settings");
  const form=$("download-settings");form.elements.file_parallelism.value=result.file_parallelism;form.elements.account_parallelism.value=result.account_parallelism;
  if(result.resources?.available_memory_bytes) $("technical-status").textContent += " · " + formatBytes(result.resources.available_memory_bytes) + " RAM verfügbar";
  $("oauth-configured").textContent="Anmeldung eingerichtet: Google "+(result.providers.google?"ja":"nein")+" · Microsoft "+(result.providers.microsoft?"ja":"nein");
  $("oauth-settings").hidden=false;$("oauth-settings").elements.redirect_uri.value=location.origin+"/api/oauth/callback";
}
formAction("download-settings",async(form)=>{
  await api("/admin/acquisition-settings",{method:"PUT",body:JSON.stringify({file_parallelism:Number(form.elements.file_parallelism.value),account_parallelism:Number(form.elements.account_parallelism.value),reserve_bytes:2147483648})});
  message("Sicherungseinstellungen gespeichert.");
});
formAction("oauth-settings",async(form)=>{
  try {await api("/admin/oauth-settings",{method:"PUT",body:JSON.stringify(formData(form))});await loadDownloadSettings();if(activeCase)await refreshActive(activeCase.id);message("Anbieteranwendung gespeichert.");}
  finally {form.elements.client_secret.value="";}
});
setInterval(async()=>{
  if(!currentUser || !activeCase || document.hidden || document.querySelector("dialog[open]"))return;
  if(!cloudList.some(a=>a.acquisition && ["queued","running","pausing"].includes(a.acquisition.status)))return;
  try {await refreshActive(activeCase.id);} catch { /* existing session handling applies */ }
},2000);

function updateCalendarPeriod(){
  const form=$("acquisition-form");
  const enabled=acquisitionContext?.provider === "microsoft" && form.elements.service.value === "calendar";
  $("calendar-period").hidden=!enabled;
  const service=form.elements.service.value,provider=acquisitionContext?.provider;
  const combined=provider === "apple" && service === "both";
  $("scope-field").hidden=provider!=="apple" || combined;
  form.elements.path.disabled=combined;
  if(combined)form.elements.path.value="";
  $("acquisition-scope-note").textContent=combined ? "iCloud Drive und die zugängliche Fotoansicht werden gemeinsam gesichert, in getrennten Unterordnern. Weitere Bildvarianten und Gerätebackups sind nicht zugesichert." : service === "calendar"
    ? (provider === "microsoft" ? "Kalenderexport für den gewählten Zeitraum. Anlagen werden nicht heruntergeladen." : "Kalender und zugängliche Termine als Datenexport. Anhänge werden nicht heruntergeladen.")
    : provider === "google" ? "Gesichert wird „Meine Ablage“ mit Unterordnern. Geteilte Ablagen außerhalb dieses Bereichs sind nicht enthalten."
    : provider === "microsoft" ? "Dateien und Ordner des Standard-OneDrive. Externe Verknüpfungen und weitere SharePoint-Sammlungen sind nicht enthalten."
    : service === "photos" ? "Gesichert wird die zugängliche Fotoansicht. Weitere Bildvarianten und Gerätebackups sind nicht zugesichert."
    : "Gesichert wird der gewählte Ordner mit Unterordnern. Ohne Ordnerangabe: der sichtbare iCloud-Drive-Bereich.";
  for(const name of ["calendar_start","calendar_end"]){form.elements[name].disabled=!enabled;form.elements[name].required=enabled;}
  const year=new Date().getUTCFullYear();
  if(enabled && !form.elements.calendar_start.value){form.elements.calendar_start.value=(year-5)+"-01-01";form.elements.calendar_end.value=(year+1)+"-12-31";}
}
$("acquisition-form").elements.service.addEventListener("change",updateCalendarPeriod);

async function showAcquisitionHistory(account){
  const caseId=activeCase.id,auth=authGeneration;
  const jobs=await api("/cases/"+caseId+"/acquisitions");
  if(auth!==authGeneration || activeCase?.id!==caseId)return;
  $("acquisition-history-list").replaceChildren();
  const labels={queued:"Wartet",running:"Läuft",pausing:"Wird pausiert",paused:"Pausiert",failed:"Fehlgeschlagen",incomplete:"Unvollständig",completed:"Abgeschlossen"};
  for(const job of jobs.filter(job=>job.account_id===account.id)){
    const row=node("article",undefined,"history-entry");
    row.append(node("h3",({drive:"Dateien",photos:"Fotos",both:"Drive und Fotos",calendar:"Kalender"}[job.category])+" · "+labels[job.status]),node("p",new Date(job.created_at).toLocaleString("de-AT")+" · "+formatBytes(job.bytes_done)),node("code",job.id));
    if(job.reason)row.append(node("p",job.reason));
    if(!["queued","running","pausing"].includes(job.status)){
      for(const [kind,label] of [["bericht","Sicherungsbericht"],["dateien","Dateien und Prüfsummen"]]){
        const link=node("a",label);link.href="/api/cases/"+caseId+"/acquisitions/"+job.id+"/report/"+kind;link.download="";row.append(link);
      }
    }
    $("acquisition-history-list").append(row);
  }
  openDialog("acquisition-history-dialog");
}
