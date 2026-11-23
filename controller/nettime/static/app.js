"use strict";
(function () {
  var DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
  var LABEL = {mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun"};
  var KEY = "nettime.key";
  var MAX_IMPORT = 64 * 1024;
  var state = null, lost = false, lastDevices = null, awayDraft = [];
  var $ = function (id) { return document.getElementById(id); };

  // Optional one-time link: #key=... is read, stored in this tab only, and removed from the address bar.
  if (location.hash.indexOf("#key=") === 0) {
    try {
      var linkKey = decodeURIComponent(location.hash.slice(5));
      if (/^[A-Za-z0-9_-]{1,200}$/.test(linkKey)) sessionStorage.setItem(KEY, linkKey);
    } catch (e) { /* Ignore malformed fragments. */ }
    history.replaceState(null, "", location.pathname);
  }

  function el(tag, text, cls) { var e = document.createElement(tag); if (text != null) e.textContent = text; if (cls) e.className = cls; return e; }
  function api(method, path, body) {
    return fetch(path, {method: method, headers: Object.assign({"Authorization": "Bearer " + sessionStorage.getItem(KEY)},
      body ? {"Content-Type": "application/json"} : {}), body: body ? JSON.stringify(body) : undefined})
      .then(function (r) { return r.json().catch(function () { var e = new Error("Controller not reachable"); e.lost = true; throw e; }).then(function (j) {
        if (r.status === 401) { sessionStorage.removeItem(KEY); showLogin("Access key not accepted."); }
        if (!r.ok) { var e = new Error(j.error || "Request failed"); e.auth = r.status === 401; throw e; } return j; }); },
        function () { var e = new Error("Controller not reachable"); e.lost = true; throw e; });
  }
  function say(t, bad) { var m = $("msg"); m.hidden = false; m.textContent = t; m.className = "notice" + (bad ? " warn" : ""); }
  function fmt(sec) { var m = Math.floor(sec / 60); return (m >= 60 ? Math.floor(m / 60) + "h " : "") + (m % 60) + "m"; }
  function ago(ts) { return ts ? new Date(ts * 1000).toLocaleTimeString("en-GB", {timeZone: "Europe/London"}) + " (London)" : "never"; }
  var MUTATORS = ["enf-btn", "resume-btn", "release-btn", "save", "bonus-btn", "bonus-clear", "discover", "export", "import-file", "bulk-wd-btn", "bulk-we-btn", "unselect-btn", "away-add"];
  function setLost(on) {
    lost = on; $("lost").hidden = !on;
    if (on) {
      MUTATORS.forEach(function (id) { $(id).disabled = true; });
      Array.prototype.forEach.call(document.querySelectorAll("#devices button, #away-windows button"), function (b) { b.disabled = true; });
      $("mode-pill").textContent = "Controller connection unknown"; $("mode-pill").className = "pill bad";
    } else {
      MUTATORS.forEach(function (id) { $(id).disabled = false; });
      if (state) renderSelection(state);
      Array.prototype.forEach.call(document.querySelectorAll("#devices button, #away-windows button"), function (b) { b.disabled = false; });
    }
  }

  function showLogin(err) { $("login").hidden = false; $("app").hidden = true; $("login-err").textContent = err || ""; $("mode-pill").textContent = "Not signed in"; }

  var STATUS_TEXT = {
    router: {ok: "Connected", error: "Error", "tls-pin": "Certificate changed — re-run setup", unknown: "Checking…", "not-configured": "Not set up"},
    connection: {connected: "Router reports this address connected", "not-connected": "This address not connected (or the selected device's Wi-Fi address changed)", "not-listed": "Not in router's list", unknown: "Unknown"},
    metering: {off: "Not counting (observation only)", counting: "Counting", exception: "Exception — time not counted", away: "Away — allowance counting paused", blocked: "Not counting (blocked)", "not-connected": "Not counting (not connected)", unknown: "Unknown — router not answering"}
  };

  function render(s) {
    state = s;
    var st = s.status, t = s.today;
    var pill = $("mode-pill");
    pill.textContent = s.paused ? "Automation paused" : s.enforcement ? "Blocking on" : "Observation only";
    pill.className = "pill " + (s.paused ? "bad" : s.enforcement ? "ok" : "warn");
    var rows = [
      ["Router", STATUS_TEXT.router[st.router] || st.router],
      ["Last successful read", ago(st.lastSuccess)],
      ["Last error", st.lastError ? st.lastError.message : "None"],
      ["Filter mode", st.mode || "Unknown"],
      ["Device", s.target ? (s.targetName || "Selected") + " · " + s.target : "Not selected"],
      ["In router deny list", st.targetInList == null ? "Unknown" : st.targetInList ? "Yes" : "No"],
      ["Wi-Fi connection", (STATUS_TEXT.connection[st.connection] || st.connection) + (st.connectionStale ? " (last known: " + (STATUS_TEXT.connection[st.connectionStale] || st.connectionStale) + ", stale)" : "")],
      ["Time counting", st.metering === "exception" ? (st.exceptionLabel || "Exception") + " exception — time not counted" : (STATUS_TEXT.metering[st.metering] || st.metering)],
      ["Away period", st.awayLabel || "None"],
      ["Used today (" + t.date + ")", fmt(t.usedSeconds) + (t.bonusMinutes ? " · +" + t.bonusMinutes + "m extra" : "")],
      ["Rule now", t.decision.label],
      ["Last router change", st.ruleMessage || "None"]
    ];
    var dl = $("status"); dl.textContent = "";
    rows.forEach(function (r) { var d = el("div"); d.appendChild(el("dt", r[0])); d.appendChild(el("dd", r[1])); dl.appendChild(d); });
    $("paused").hidden = !s.paused; $("paused").textContent = s.paused ? "Automation paused: " + s.paused + ". No automatic router changes until you check the router." : "";
    var rb = $("release-btn"); rb.hidden = !s.releaseAttention;
    rb.dataset.confirm = (!s.ownedBlock && s.pending && s.pending.status === "present-unverified") ? "1" : "";
    rb.textContent = s.ownedBlock ? "Retry removing block" : rb.dataset.confirm ? "Remove uncertain block" : "Check uncertain block";
    $("resume-btn").hidden = !s.paused;
    $("enf-text").textContent = s.enforcement
      ? "Blocking is on. NetTime adds/removes only the selected device in the router's deny list."
      : "Observation only. NetTime reads the router and changes nothing until you switch blocking on.";
    var ul = $("problems"); ul.textContent = "";
    (s.activationProblems || []).forEach(function (p) { ul.appendChild(el("li", p)); });
    $("enf-btn").textContent = s.enforcement ? "Switch blocking off" : "Switch blocking on";
    $("enf-btn").disabled = !s.enforcement && s.activationProblems.length > 0;
    renderSelection(s);
    renderDevices();
  }

  function renderSelection(s) {
    $("sel-summary").textContent = s.target ? "Selected: " + (s.targetName || "Device") + " · " + s.target : "No device selected";
    var ub = $("unselect-btn"), why = $("unselect-why");
    ub.hidden = !s.target;
    var reason = !s.target ? "" : s.enforcement ? "Switch blocking off before unselecting the device."
      : (s.ownedBlock || s.pending) ? "A router change for this device is unresolved. Use the removal button under Blocking first." : "";
    ub.disabled = lost || !!reason;
    why.hidden = !reason; why.textContent = reason;
  }

  function renderDevices() {
    var box = $("devices"); if (!lastDevices) return; box.textContent = "";
    lastDevices.forEach(function (d) {
      d.addresses.forEach(function (a) {
        var m = a.mac, row = el("div", null, "dev");
        row.appendChild(el("span", d.name + " · " + m + " · " + (a.connected ? "connected" : "not connected")));
        if (!a.reason) { var b = el("button", state && m === state.target ? "Selected" : "Select", "outline"); b.disabled = lost;
          b.addEventListener("click", function () { act(api("POST", "/api/target", {mac: m, name: d.name})); }); row.appendChild(b); }
        else row.appendChild(el("span", a.reason, "muted"));
        box.appendChild(row);
      });
    });
    if (!lastDevices.length) box.appendChild(el("p", "Router returned no devices.", "muted"));
  }

  function renderSettings(set) {
    var days = $("days"); days.textContent = "";
    DAYS.forEach(function (d) {
      var l = el("label", LABEL[d] + " (min)"); var i = el("input"); i.type = "number"; i.min = 0; i.max = 1440; i.id = "day-" + d;
      i.value = set.weekly[d] == null ? "" : set.weekly[d]; i.placeholder = "unset"; l.appendChild(i); days.appendChild(l);
    });
    var ex = $("exceptions"); ex.textContent = "";
    set.exceptions.forEach(function (e, n) {
      var row = el("div", null, "row"); row.appendChild(el("span", e.label + " (" + e.days.map(function (d) { return LABEL[d]; }).join(", ") + ")"));
      ["start", "end"].forEach(function (k) { var i = el("input"); i.type = "time"; i.value = e[k]; i.id = "ex-" + n + "-" + k; row.appendChild(i); });
      ex.appendChild(row);
    });
    var school = set.schoolHours || {enabled: false, start: "09:00", end: "15:00"};
    $("school-enabled").checked = school.enabled;
    $("school-start").value = school.start;
    $("school-end").value = school.end;
    awayDraft = JSON.parse(JSON.stringify(set.awayWindows || []));
    renderAway();
    $("paused-box").checked = set.leisurePaused;
  }

  function collectAway() {
    return awayDraft.map(function (w, n) {
      return {id: w.id, label: $("away-" + n + "-label").value.trim(),
        enabled: $("away-" + n + "-enabled").checked,
        days: DAYS.filter(function (d) { return $("away-" + n + "-" + d).checked; }),
        start: $("away-" + n + "-start").value, end: $("away-" + n + "-end").value};
    });
  }
  function renderAway() {
    var box = $("away-windows"); box.textContent = "";
    awayDraft.forEach(function (w, n) {
      var group = el("fieldset", null, "away-period"); group.appendChild(el("legend", "Away period " + (n + 1)));
      var row = el("div", null, "row");
      var name = el("label", "Name "), text = el("input"); text.id = "away-" + n + "-label"; text.value = w.label; text.maxLength = 40; name.appendChild(text); row.appendChild(name);
      var toggle = el("label", "Enabled "), check = el("input"); check.type = "checkbox"; check.id = "away-" + n + "-enabled"; check.checked = w.enabled; toggle.appendChild(check); row.appendChild(toggle);
      ["start", "end"].forEach(function (k) { var label = el("label", k === "start" ? "Leave " : "Return "), input = el("input"); input.type = "time"; input.id = "away-" + n + "-" + k; input.value = w[k]; label.appendChild(input); row.appendChild(label); });
      group.appendChild(row);
      var days = el("div", null, "row");
      DAYS.forEach(function (d) { var label = el("label", LABEL[d] + " "), input = el("input"); input.type = "checkbox"; input.id = "away-" + n + "-" + d; input.checked = w.days.indexOf(d) >= 0; label.appendChild(input); days.appendChild(label); });
      group.appendChild(days);
      var remove = el("button", "Remove away period", "ghost"); remove.type = "button"; remove.disabled = lost;
      remove.addEventListener("click", function () { awayDraft = collectAway(); awayDraft.splice(n, 1); renderAway(); }); group.appendChild(remove); box.appendChild(group);
    });
    $("away-add").disabled = lost || awayDraft.length >= 10;
  }

  function collect() {
    var s = JSON.parse(JSON.stringify(state.settings));
    DAYS.forEach(function (d) { var v = $("day-" + d).value.trim(); s.weekly[d] = v === "" ? null : Number(v); });
    s.exceptions.forEach(function (e, n) { e.start = $("ex-" + n + "-start").value; e.end = $("ex-" + n + "-end").value; });
    s.schoolHours = {enabled: $("school-enabled").checked, start: $("school-start").value, end: $("school-end").value};
    s.awayWindows = collectAway();
    s.leisurePaused = $("paused-box").checked;
    return s;
  }

  function refresh(first) {
    return api("GET", "/api/status").then(function (s) {
      $("login").hidden = true; $("app").hidden = false; if (lost) setLost(false); render(s); if (first || !$("day-mon")) renderSettings(s.settings);
    }).catch(function (e) {
      if (e.auth) return;
      if (!$("app").hidden && state) setLost(true); else if (first) $("login-err").textContent = e.message;
    });
  }
  function act(p) { return p.then(function (r) { say(r.message || "Done"); return refresh(); }).catch(function (e) { if (e.lost) setLost(true); else say(e.message, true); }); }

  $("away-add").addEventListener("click", function () {
    awayDraft = collectAway();
    if (awayDraft.length >= 10) return;
    awayDraft.push({id: "away-" + Date.now() + "-" + Math.random().toString(36).slice(2, 9), label: "Away from home", enabled: true,
      days: ["mon", "tue", "wed", "thu", "fri"], start: "08:00", end: "16:00"});
    renderAway();
  });
  $("login-form").addEventListener("submit", function (ev) { ev.preventDefault(); sessionStorage.setItem(KEY, $("key").value.trim()); $("key").value = ""; refresh(true); });
  $("save").addEventListener("click", function () { act(api("POST", "/api/settings", {settings: collect()})); });
  $("bulk-wd-btn").addEventListener("click", function () { ["mon", "tue", "wed", "thu", "fri"].forEach(function (d) { $("day-" + d).value = $("bulk-wd").value; }); });
  $("bulk-we-btn").addEventListener("click", function () { ["sat", "sun"].forEach(function (d) { $("day-" + d).value = $("bulk-we").value; }); });
  $("bonus-btn").addEventListener("click", function () { act(api("POST", "/api/bonus", {minutes: Number($("bonus").value)})); });
  $("bonus-clear").addEventListener("click", function () { act(api("POST", "/api/bonus/clear", {})); });
  $("unselect-btn").addEventListener("click", function () {
    if (!confirm("Unselect this device? Blocking stays off and the router is not changed.")) return;
    act(api("POST", "/api/target/clear", {}));
  });
  $("resume-btn").addEventListener("click", function () { act(api("POST", "/api/resume", {})); });
  $("release-btn").addEventListener("click", function () {
    var c = $("release-btn").dataset.confirm === "1";
    if (c && !confirm("Remove the device from the router's deny list? NetTime could not confirm whether it added this entry; only continue if no one blocked it manually.")) return;
    act(api("POST", "/api/release", c ? {confirmUncertain: true} : {}));
  });
  $("enf-btn").addEventListener("click", function () {
    var on = !state.enforcement;
    if (on && !confirm("Switch blocking on? NetTime will add/remove the selected device in the router's deny list on schedule.")) return;
    act(api("POST", "/api/enforcement", {enabled: on}));
  });
  $("discover").addEventListener("click", function () {
    api("POST", "/api/discover", {}).then(function (r) { lastDevices = r.devices; renderDevices(); })
      .catch(function (e) { if (e.lost) setLost(true); else say(e.message, true); });
  });
  $("export").addEventListener("click", function () {
    api("GET", "/api/export").then(function (s) {
      var a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(s, null, 2)], {type: "application/json"}));
      a.download = "nettime-settings.json"; a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 30000);
    }).catch(function (e) { say(e.message, true); });
  });
  $("import-file").addEventListener("change", function (ev) {
    var f = ev.target.files[0]; if (!f) return;
    ev.target.value = "";
    if (f.size > MAX_IMPORT) { say("Settings file exceeds 64 KiB.", true); return; }
    f.text().then(function (txt) {
      var parsed; try { parsed = JSON.parse(txt); } catch (e) { say("File is not valid JSON.", true); return; }
      return api("POST", "/api/import", {settings: parsed}).then(function (r) { say(r.message); return refresh(true); });
    }).catch(function (e) { say(e.message, true); });
  });

  if (sessionStorage.getItem(KEY)) refresh(true); else showLogin();
  setInterval(function () { if (!$("app").hidden) refresh(false); }, 10000);
})();
