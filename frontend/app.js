"use strict";
let currentUser = null,
  caseList = [],
  selectedCase = null,
  currentView = "overview",
  caseGeneration = 0;
const $ = (id) => document.getElementById(id);
const labels = {
  active: "Aktiv",
  completed: "Abgeschlossen",
  archived: "Archiviert",
};
const events = {
  case_created: "Fall angelegt",
  case_updated: "Fall aktualisiert",
  case_member_granted: "Fallzugriff erteilt",
  case_member_revoked: "Fallzugriff entzogen",
};
const csrf = () =>
  decodeURIComponent(
    document.cookie
      .split("; ")
      .find((x) => x.startsWith("__Host-fca_csrf="))
      ?.split("=")[1] || "",
  );
function message(text) {
  $("message").textContent = text;
  $("message").hidden = false;
}
async function api(path, options = {}) {
  const response = await fetch("/api" + path, {
    credentials: "same-origin",
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf(),
      ...options.headers,
    },
  });
  if (!response.headers.get("content-type")?.includes("application/json"))
    throw new Error("Server derzeit nicht verfügbar. Bitte erneut versuchen.");
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401 && currentUser) signedOut();
    throw new Error(result.detail || "Anfrage fehlgeschlagen.");
  }
  return result;
}
const data = (form) => Object.fromEntries(new FormData(form));
function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function signedOut() {
  caseGeneration++;
  document
    .querySelectorAll("input[type=password]")
    .forEach((i) => (i.value = ""));
  currentUser = null;
  caseList = [];
  selectedCase = null;
  $("case-rows").replaceChildren();
  $("audit-list").replaceChildren();
  $("user-rows").replaceChildren();
  $("case-detail").hidden = true;
  $("workspace").hidden = true;
  $("login-panel").hidden = false;
  $("identity-label").textContent = "";
  document.querySelectorAll("dialog[open]").forEach((d) => d.close());
}
async function signedIn(user) {
  currentUser = user;
  $("login-panel").hidden = true;
  $("workspace").hidden = false;
  $("identity-label").textContent = user.username + " / " + user.initials;
  $("users-nav").hidden = user.role !== "admin";
  $("case-form").elements.operator_initials.value = user.initials;
  await refresh();
  showView("overview");
}
function showView(view) {
  caseGeneration++;
  currentView = view;
  document
    .querySelectorAll("[data-view]")
    .forEach((b) => b.classList.toggle("selected", b.dataset.view === view));
  $("page-title").textContent = {
    overview: "Übersicht",
    cases: "Fälle",
    users: "Benutzer",
  }[view];
  $("overview").hidden = view !== "overview";
  $("cases-panel").hidden = view === "users";
  $("users-panel").hidden = view !== "users";
  $("case-detail").hidden = true;
  selectedCase = null;
  $("new-case-button").hidden = view === "users";
  if (view === "users") loadUsers().catch((e) => message(e.message));
}
async function refresh() {
  caseList = await api("/cases");
  renderCases();
  const status = await api("/status");
  $("disk-free").textContent =
    status.free_bytes === null
      ? "–"
      : (status.free_bytes / 1024 ** 3).toFixed(1) + " GiB";
  $("disk-state").textContent = status.evidence_mounted
    ? "Separate Testdatendisk"
    : "DATENDISK NICHT VERFÜGBAR";
  $("stage-note").textContent = status.note;
  $("connection").textContent = "ANGEMELDET / HTTPS";
}
function renderCases() {
  const query = $("case-search").value.toLocaleLowerCase();
  $("case-count").textContent = String(caseList.length);
  $("active-count").textContent = String(
    caseList.filter((c) => c.status === "active").length,
  );
  $("case-rows").replaceChildren();
  const shown = caseList.filter((c) =>
    (c.business_number + " " + c.name).toLocaleLowerCase().includes(query),
  );
  $("case-empty").hidden = shown.length > 0;
  $("case-empty").firstElementChild.textContent = query
    ? "Keine passenden Fälle"
    : "Noch keine Fälle";
  for (const c of shown) {
    const tr = node("tr"),
      title = node("td");
    title.append(
      node("strong", c.business_number),
      node("small", c.name || "Ohne Fallnamen"),
    );
    const status = node("td");
    status.append(node("span", labels[c.status], "tag " + c.status));
    const action = node("td"),
      button = node("button", "Fall öffnen →");
    button.addEventListener("click", () =>
      openCase(c.id).catch((e) => message(e.message)),
    );
    action.append(button);
    tr.append(
      title,
      status,
      node("td", c.operator_initials),
      node("td", new Date(c.created_at).toLocaleDateString("de-AT")),
      action,
    );
    $("case-rows").append(tr);
  }
}
async function openCase(id) {
  const generation = ++caseGeneration;
  $("case-detail").hidden = true;
  selectedCase = null;
  const [c, audit, users, members] = await Promise.all([
    api("/cases/" + encodeURIComponent(id)),
    api("/cases/" + encodeURIComponent(id) + "/audit"),
    currentUser.role === "admin" ? api("/admin/users") : Promise.resolve([]),
    currentUser.role === "admin"
      ? api("/cases/" + encodeURIComponent(id) + "/members")
      : Promise.resolve([]),
  ]);
  if (generation !== caseGeneration || !currentUser) return;
  selectedCase = c.id;
  $("case-detail").hidden = false;
  $("detail-title").textContent = "FALL / " + c.business_number;
  $("detail-id").textContent = "Interne ID: " + c.id;
  const form = $("edit-case-form");
  form.elements.version.value = c.version;
  for (const el of form.elements) el.disabled = !c.can_edit;
  form.elements.name.value = c.name;
  form.elements.status.value = c.status;
  form.elements.operator_initials.value = currentUser.initials;
  $("audit-list").replaceChildren();
  for (const a of audit) {
    const row = node("div", undefined, "audit");
    row.append(
      node("time", new Date(a.occurred_at).toLocaleString("de-AT")),
      node(
        "b",
        (events[a.event_type] || a.event_type) + " / " + (a.actor || "System"),
      ),
      node("span", a.operator_initials || "–"),
    );
    $("audit-list").append(row);
  }
  $("membership-panel").hidden = currentUser.role !== "admin";
  $("member-user").replaceChildren();
  for (const u of users.filter((u) => u.active)) {
    const opt = node("option", u.username + " / " + u.initials);
    opt.value = u.id;
    $("member-user").append(opt);
  }
  $("member-list").replaceChildren();
  for (const member of members) {
    const row = node(
      "p",
      member.username +
        " / " +
        (member.access === "editor" ? "Bearbeiten" : "Lesen") +
        " ",
    );
    const button = node("button", "Zugriff entziehen");
    button.addEventListener("click", async () => {
      try {
        await api("/cases/" + c.id + "/members/" + member.id, {
          method: "DELETE",
        });
        if (selectedCase === c.id) await openCase(c.id);
        message("Fallzugriff entzogen: " + c.business_number);
      } catch (e) {
        message(e.message);
      }
    });
    row.append(button);
    $("member-list").append(row);
  }
  $("case-detail").scrollIntoView({ behavior: "smooth", block: "nearest" });
}
async function loadUsers() {
  const users = await api("/admin/users");
  $("user-rows").replaceChildren();
  for (const u of users) {
    const tr = node("tr"),
      action = node("td");
    if (u.id !== currentUser.id) {
      const button = node("button", u.active ? "Deaktivieren" : "Aktivieren");
      button.addEventListener("click", async () => {
        try {
          await api("/admin/users/" + u.id, {
            method: "PATCH",
            body: JSON.stringify({ active: !u.active }),
          });
          await loadUsers();
          message("Benutzerstatus aktualisiert.");
        } catch (e) {
          message(e.message);
        }
      });
      action.append(button);
    }
    tr.append(
      node("td", u.username),
      node("td", u.initials),
      node("td", u.role === "admin" ? "Administrator" : "Bearbeiter"),
      node("td", u.active ? "Aktiv" : "Deaktiviert"),
      action,
    );
    $("user-rows").append(tr);
  }
}
function formAction(id, action) {
  $(id).addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget,
      button =
        form.querySelector('button[type="submit"],button.primary') ||
        form.querySelector(":scope > button");
    if (button) button.disabled = true;
    $("message").hidden = true;
    try {
      await action(form);
    } catch (error) {
      message(error.message);
    } finally {
      if (button) button.disabled = false;
    }
  });
}
formAction("login-form", async (f) => {
  const body = data(f);
  try {
    await signedIn(
      await api("/auth/login", { method: "POST", body: JSON.stringify(body) }),
    );
  } finally {
    f.elements.password.value = "";
  }
});
formAction("case-form", async (f) => {
  const c = await api("/cases", {
    method: "POST",
    body: JSON.stringify(data(f)),
  });
  $("case-dialog").close();
  f.reset();
  f.elements.operator_initials.value = currentUser.initials;
  await refresh();
  showView("cases");
  await openCase(c.id);
  message("Fall angelegt.");
});
formAction("edit-case-form", async (f) => {
  await api("/cases/" + selectedCase, {
    method: "PATCH",
    body: JSON.stringify({
      ...data(f),
      version: Number(f.elements.version.value),
    }),
  });
  await refresh();
  await openCase(selectedCase);
  message("Fall aktualisiert.");
});
formAction("member-form", async (f) => {
  await api("/cases/" + selectedCase + "/members", {
    method: "PUT",
    body: JSON.stringify(data(f)),
  });
  await openCase(selectedCase);
  message("Fallzugriff gespeichert.");
});
formAction("user-form", async (f) => {
  try {
    await api("/admin/users", {
      method: "POST",
      body: JSON.stringify(data(f)),
    });
    $("user-dialog").close();
    f.reset();
    await loadUsers();
    message("Benutzer angelegt.");
  } finally {
    f.elements.password.value = "";
  }
});
formAction("password-form", async (f) => {
  try {
    await api("/auth/password", {
      method: "POST",
      body: JSON.stringify(data(f)),
    });
    signedOut();
    message("Passwort geändert. Bitte erneut anmelden.");
  } finally {
    f.reset();
  }
});
$("logout-button").addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST", body: "{}" });
    signedOut();
  } catch (e) {
    message(e.message);
  }
});
$("new-case-button").addEventListener("click", () =>
  $("case-dialog").showModal(),
);
$("add-user-button").addEventListener("click", () =>
  $("user-dialog").showModal(),
);
$("password-button").addEventListener("click", () =>
  $("password-dialog").showModal(),
);
$("close-case").addEventListener("click", () => {
  caseGeneration++;
  $("case-detail").hidden = true;
  selectedCase = null;
});
$("case-search").addEventListener("input", renderCases);
document
  .querySelectorAll("[data-view]")
  .forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));
document
  .querySelectorAll("[data-close]")
  .forEach((b) =>
    b.addEventListener("click", () => $(b.dataset.close).close()),
  );
api("/auth/me")
  .then(signedIn)
  .catch(() => signedOut());

document
  .querySelectorAll("dialog")
  .forEach((d) =>
    d.addEventListener("close", () =>
      d.querySelectorAll("input[type=password]").forEach((i) => (i.value = "")),
    ),
  );
