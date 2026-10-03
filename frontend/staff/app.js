// SamePage staff review page. Talks only to the version-one staff endpoints in contracts/API_V1.md.
(function () {
  "use strict";

  var API_BASE = (window.SAMEPAGE_API_BASE || "").replace(/\/$/, "");
  var POLL_MS = 5000;
  var MAX_CANDIDATES = 3;

  var STATUS_LABELS = {
    submitted: "Submitted",
    staff_review: "In staff review",
    needs_client_followup: "Needs client follow-up",
    assigned: "Assigned"
  };
  var FLAG_LABELS = {
    client_term_did_not_match_account_type: "Client's term did not match the account type",
    possible_unauthorized_access: "Possible unauthorized access"
  };
  var ACCOUNT_TYPE_LABELS = {
    rollover_ira: "Rollover IRA",
    roth_ira: "Roth IRA",
    traditional_ira: "Traditional IRA",
    brokerage: "Brokerage account",
    joint_brokerage: "Joint brokerage account",
    cash_management: "Cash account"
  };
  var MATCH_LABELS = {
    client_confirmed: "Confirmed by the client",
    unresolved: "Not resolved",
    not_needed: "No account needed"
  };
  var VIEWS = [
    { id: "all", label: "All requests", test: function () { return true; } },
    { id: "open", label: "To assign", test: function (c) { return c.status !== "assigned" && !isSecurity(c); } },
    { id: "flagged", label: "Flagged", test: function (c) { return (c.flags || []).length > 0; } },
    { id: "assigned", label: "Assigned", test: function (c) { return c.status === "assigned"; } }
  ];
  // Static icon markup only; never built from API data.
  var ICONS = {
    refresh: '<path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9M13.5 2.5v3h-3"/>',
    flag: '<path d="M3.5 14V2.5M3.5 3h8l-1.8 2.75L11.5 8.5h-8"/>',
    shield: '<path d="M8 1.8 2.8 3.6v4c0 3 2 5.3 5.2 6.6 3.2-1.3 5.2-3.600 5.2-6.600v-4z"/><path d="M8 5.500v3M8 10.600v.1"/>',
    mic: '<rect x="5.75" y="1.75" width="4.5" height="7.5" rx="2.25"/><path d="M3.5 7.500a4.500 4.500 0 0 0 9 0M8 12v2.250"/>',
    keyboard: '<rect x="1.75" y="4" width="12.5" height="8" rx="1.500"/><path d="M4.500 6.750h.1M7 6.750h.1M9.500 6.750h.1M11.500 6.750h.1M5 9.500h6"/>',
    check: '<path d="m3 8.500 3.200 3.200L13 4.800"/>',
    doc: '<path d="M4 1.750h5l3 3v9.500H4z"/><path d="M9 1.750v3h3"/>',
    info: '<circle cx="8" cy="8" r="6.250"/><path d="M8 7.250v4M8 4.900v.1"/>',
    alert: '<path d="M8 2 1.750 13.250h12.500z"/><path d="M8 6.500v3.250M8 11.500v.1"/>'
  };

  var state = {
    cases: [],
    known: null, // case IDs seen so far; null until the first successful load
    arrived: {},
    unread: {},
    signature: null,
    openStatus: null,
    selectedId: null,
    openToken: 0,
    view: "all"
  };

  var listEl = document.getElementById("case-list");
  var queueStatusEl = document.getElementById("queue-status");
  var caseEl = document.getElementById("case");
  var viewsEl = document.getElementById("views");
  var searchEl = document.getElementById("search");
  var categoryFilter = document.getElementById("filter-category");
  var refreshEl = document.getElementById("refresh");
  var toastEl = document.getElementById("toast");
  var toastTimer = null;

  // ---------- helpers ----------

  function el(tag, attrs) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      var value = attrs[key];
      if (value == null || value === false) return;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.indexOf("on") === 0) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? "" : value);
    });
    for (var i = 2; i < arguments.length; i++) {
      var child = arguments[i];
      if (child == null || child === false) continue;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  }

  function icon(name) {
    var holder = document.createElement("span");
    holder.innerHTML = '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" ' +
      'stroke-width="1.500" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS[name] + "</svg>";
    return holder.firstChild;
  }

  function humanize(value) {
    var text = String(value || "").replace(/_/g, " ");
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function label(map, value) {
    return map[value] || humanize(value);
  }

  function avatar(name, size) {
    var words = String(name || "?").trim().split(/\s+/);
    var initials = (words[0].charAt(0) + (words.length > 1 ? words[words.length - 1].charAt(0) : "")).toUpperCase();
    var sum = 0;
    for (var i = 0; i < String(name).length; i++) sum += String(name).charCodeAt(i);
    return el("span", { class: "avatar hue-" + (sum % 5) + (size ? " " + size : ""), "aria-hidden": "true", text: initials });
  }

  function formatTime(iso) {
    var date = new Date(iso);
    if (isNaN(date)) return iso || "";
    return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  }

  function formatAgo(iso) {
    var date = new Date(iso);
    if (isNaN(date)) return iso || "";
    var minutes = Math.round((Date.now() - date.getTime()) / 60000);
    if (minutes < 0 || minutes >= 24 * 60) return formatTime(iso);
    if (minutes < 1) return "Just now";
    if (minutes < 60) return minutes + " min ago";
    return Math.floor(minutes / 60) + " hr ago";
  }

  function formatDate(day) {
    var date = new Date(day + "T00:00:00");
    if (isNaN(date)) return day || "";
    return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function formatMoney(amount, currency) {
    try {
      return new Intl.NumberFormat(undefined, {
        style: "currency", currency: currency || "USD", maximumFractionDigits: 0
      }).format(amount);
    } catch (e) {
      return String(amount);
    }
  }

  function isSecurity(item) {
    var destination = (item.routing && item.routing.destination) || "";
    return (item.categories || []).indexOf("fraud_or_security") !== -1 ||
      (item.flags || []).indexOf("possible_unauthorized_access") !== -1 ||
      destination.indexOf("security") !== -1;
  }

  function source(id) {
    return id ? el("span", { class: "source", title: "Source record " + id }, icon("doc"), id) : null;
  }

  function categoryTag(category, matched) {
    return el("span", {
      class: "tag" + (category === "fraud_or_security" ? " security" : matched ? " match" : ""),
      text: humanize(category)
    });
  }

  function notice(kind, title, body) {
    return el("div", { class: "notice " + kind, role: kind === "error" ? "alert" : "status" },
      icon(kind === "error" ? "alert" : "check"),
      el("div", {}, el("strong", { text: title }), body || null));
  }

  function toast(message) {
    toastEl.textContent = "";
    toastEl.appendChild(icon("check"));
    toastEl.appendChild(document.createTextNode(message));
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 3200);
  }

  function api(path, options) {
    options = options || {};
    var headers = { "X-Demo-Role": "staff" };
    if (options.body) headers["Content-Type"] = "application/json";
    return fetch(API_BASE + path, {
      method: options.method || "GET",
      headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) {
          var error = new Error(data.message || "The case service returned an error (" + response.status + ").");
          error.code = data.error_code;
          throw error;
        }
        return data;
      });
    }, function () {
      throw new Error("Can't reach the case service" + (API_BASE ? " at " + API_BASE : "") + ". Check that it is running, then try again.");
    });
  }

  // ---------- queue ----------

  function loadQueue() {
    return api("/staff/cases").then(function (data) {
      var cases = (data.cases || []).slice().sort(function (a, b) {
        return String(b.created_at).localeCompare(String(a.created_at));
      });
      if (state.known) {
        cases.forEach(function (item) {
          if (!state.known[item.case_id]) {
            state.arrived[item.case_id] = true;
            state.unread[item.case_id] = true;
          }
        });
      }
      state.known = {};
      cases.forEach(function (item) { state.known[item.case_id] = true; });
      // Skip the redraw when nothing changed so polling never steals keyboard focus.
      var signature = JSON.stringify(cases);
      var wasError = queueStatusEl.classList.contains("error");
      if (signature === state.signature && !wasError) return;
      state.signature = signature;
      state.cases = cases;
      syncCategories();
      renderQueue();
      // If the open case changed elsewhere (for example, a colleague assigned it), reload it.
      var open = cases.filter(function (item) { return item.case_id === state.selectedId; })[0];
      if (open && state.openStatus && open.status !== state.openStatus) openCase(state.selectedId, false);
    }).catch(function (error) {
      queueStatusEl.className = "queue-status error";
      queueStatusEl.textContent = error.message;
    });
  }

  function syncCategories() {
    var all = [].concat.apply([], state.cases.map(function (c) { return c.categories || []; }));
    var values = all.filter(function (value, index) { return value && all.indexOf(value) === index; }).sort();
    var wanted = [""].concat(values);
    var existing = Array.prototype.map.call(categoryFilter.options, function (o) { return o.value; });
    if (wanted.join("|") === existing.join("|")) return;
    var current = categoryFilter.value;
    categoryFilter.textContent = "";
    wanted.forEach(function (value) {
      categoryFilter.appendChild(el("option", { value: value, text: value ? humanize(value) : "All categories" }));
    });
    categoryFilter.value = wanted.indexOf(current) !== -1 ? current : "";
  }

  function visibleCases() {
    var view = VIEWS.filter(function (v) { return v.id === state.view; })[0];
    var query = searchEl.value.trim().toLowerCase();
    return state.cases.filter(function (item) {
      if (!view.test(item)) return false;
      if (categoryFilter.value && (item.categories || []).indexOf(categoryFilter.value) === -1) return false;
      if (query) {
        var haystack = [item.case_id, item.client_display_name, item.confirmed_plain_language_request].join(" ").toLowerCase();
        if (haystack.indexOf(query) === -1) return false;
      }
      return true;
    });
  }

  function renderViews() {
    var current = VIEWS.filter(function (v) { return v.id === state.view; })[0];
    document.getElementById("queue-title").textContent = current.id === "all" ? "Requests" : current.label;
    viewsEl.textContent = "";
    VIEWS.forEach(function (view) {
      viewsEl.appendChild(el("button", {
        type: "button", class: "view", "aria-pressed": String(view.id === state.view),
        onclick: function () { state.view = view.id; renderQueue(); }
      }, view.label, el("span", { class: "count", text: String(state.cases.filter(view.test).length) })));
    });
  }

  function renderQueue() {
    var rows = visibleCases();
    renderViews();
    listEl.textContent = "";
    queueStatusEl.className = "queue-status";
    queueStatusEl.textContent = "";

    if (!state.cases.length) {
      queueStatusEl.className = "queue-status empty";
      queueStatusEl.textContent = "No requests are waiting. A request appears here as soon as a client confirms it.";
      return;
    }
    if (!rows.length) {
      queueStatusEl.className = "queue-status empty";
      queueStatusEl.appendChild(document.createTextNode("No requests match. "));
      queueStatusEl.appendChild(el("button", { type: "button", class: "quiet", text: "Clear filters", onclick: clearFilters }));
      return;
    }

    rows.forEach(function (item) {
      var security = isSecurity(item);
      var categories = item.categories || [];
      var tags = el("div", { class: "row-tags" },
        el("span", { class: "tag status " + item.status, text: label(STATUS_LABELS, item.status) }));
      if (categories.length) tags.appendChild(categoryTag(categories[0]));
      if (categories.length > 1) tags.appendChild(el("span", { class: "tag", text: "+" + (categories.length - 1), title: categories.slice(1).map(humanize).join(", ") }));
      if ((item.flags || []).length && !security) {
        tags.appendChild(el("span", { class: "tag flag", title: item.flags.map(function (f) { return label(FLAG_LABELS, f); }).join(", ") },
          icon("flag"), "Flagged"));
      }

      var button = el("button", {
        type: "button",
        class: "case-row" + (security ? " security" : "") + (state.arrived[item.case_id] ? " arrived" : ""),
        "data-case": item.case_id,
        "aria-current": item.case_id === state.selectedId ? "true" : null,
        onclick: function () { openCase(item.case_id, true); }
      },
        state.unread[item.case_id] ? el("span", { class: "unread", title: "New" }) : null,
        avatar(item.client_display_name),
        el("div", { class: "row-body" },
          el("div", { class: "row-top" },
            el("span", { class: "row-client" }, item.client_display_name, el("small", { text: item.case_id })),
            el("span", { class: "row-time", text: formatAgo(item.created_at) })),
          el("p", { class: "row-request", text: item.confirmed_plain_language_request }),
          tags));
      listEl.appendChild(el("li", {}, button));
    });
    state.arrived = {};
  }

  function clearFilters() {
    state.view = "all";
    searchEl.value = "";
    categoryFilter.value = "";
    renderQueue();
  }

  function moveSelection(step) {
    var rows = visibleCases();
    if (!rows.length) return;
    var index = rows.map(function (c) { return c.case_id; }).indexOf(state.selectedId);
    var next = rows[Math.max(0, Math.min(rows.length - 1, index === -1 ? 0 : index + step))];
    openCase(next.case_id, false);
    var row = listEl.querySelector('[data-case="' + next.case_id + '"]');
    if (row) row.scrollIntoView({ block: "nearest" });
  }

  // ---------- case detail ----------

  function openCase(caseId, moveFocus) {
    state.selectedId = caseId;
    state.openStatus = null;
    toastEl.classList.remove("show");
    delete state.unread[caseId];
    if (location.hash.slice(1) !== caseId) history.replaceState(null, "", "#" + caseId);
    renderQueue();
    var token = ++state.openToken;
    caseEl.textContent = "";
    caseEl.appendChild(el("div", { class: "sheet skeleton", "aria-label": "Opening " + caseId },
      el("i", { style: "width:35%" }), el("i", { style: "width:80%" }), el("i", { style: "width:65%" }), el("i", { style: "width:72%" })));

    var id = encodeURIComponent(caseId);
    var candidates = api("/staff/cases/" + id + "/candidates").then(
      function (data) { return { list: data.candidates || [] }; },
      function (error) { return { error: error.message, list: [] }; });

    Promise.all([api("/staff/cases/" + id), candidates]).then(function (results) {
      if (token !== state.openToken) return;
      renderCase(results[0], results[1]);
      caseEl.scrollTop = 0;
      if (moveFocus) {
        caseEl.focus({ preventScroll: true });
        // On a narrow screen the case sits below the queue, so bring it into view.
        if (window.matchMedia("(max-width: 54rem)").matches) caseEl.scrollIntoView({ block: "start" });
      }
    }).catch(function (error) {
      if (token !== state.openToken) return;
      caseEl.textContent = "";
      caseEl.appendChild(el("div", { class: "sheet" },
        notice("error", "Couldn't open " + caseId, error.message),
        el("button", { type: "button", class: "primary", text: "Try again", onclick: function () { openCase(caseId, true); } })));
    });
  }

  function step(kind, title, body, origin) {
    return el("li", { class: "step " + kind },
      el("h3", { text: title }), body, origin ? el("p", { class: "origin", text: origin }) : null);
  }

  // Says only what the case record supports: the recorded account type, any sourced
  // conflict statements (optional version-two field), and whether the client confirmed.
  function mismatchNotice(record, context) {
    var box = el("div", { class: "mismatch" },
      el("strong", { text: "The client's wording did not match their records" }));
    var conflicts = record.conflicts || [];
    conflicts.forEach(function (conflict) {
      box.appendChild(el("p", {}, conflict.statement + " ", source(conflict.source_id)));
    });
    if (!conflicts.length && context) {
      box.appendChild(el("p", {},
        "The account on this request is recorded as a " + label(ACCOUNT_TYPE_LABELS, context.account_type) + ". ",
        source(context.account_source_id)));
    }
    box.appendChild(el("p", { text: record.account_match_status === "client_confirmed"
      ? "The client confirmed this account before sending, so the request below is the corrected version."
      : "The client has not confirmed which account they mean. Check with the client before assigning." }));
    return box;
  }

  function tile(name, value, detail) {
    return el("div", { class: "tile" },
      el("dt", { text: name }),
      el("dd", {}, value, detail ? el("small", { text: detail }) : null));
  }

  function renderCase(record, candidates, banner) {
    var security = isSecurity(record);
    var routing = record.routing || {};
    var context = record.account_context;
    var flags = record.flags || [];
    state.openStatus = record.status;
    caseEl.textContent = "";

    var voice = record.input_mode === "voice";
    caseEl.appendChild(el("header", { class: "case-head" },
      avatar(record.client_display_name, "large"),
      el("div", {},
        el("h2", { text: record.client_display_name }),
        el("div", { class: "case-meta" },
          el("strong", { text: record.case_id }),
          el("span", { text: "Received " + formatTime(record.created_at) }),
          el("span", { class: "with-icon" }, icon(voice ? "mic" : "keyboard"), voice ? "Spoken" : "Typed"),
          record.preferred_contact_channel
            ? el("span", { text: "Prefers contact by " + humanize(record.preferred_contact_channel).toLowerCase() }) : null,
          el("span", { class: "tag status " + record.status, text: label(STATUS_LABELS, record.status) })))));

    if (security) {
      caseEl.appendChild(el("div", { class: "security-banner", role: "alert" },
        icon("shield"),
        el("div", {},
          el("h2", { text: "Send to " + humanize(routing.destination || "security_specialist_review").toLowerCase() }),
          el("p", { text: "This request reports possible unauthorized access. It goes to the specialist queue for review, not to a planning advisor." }))));
    }

    // Page 1: request and routing
    var steps = el("ol", { class: "steps" },
      step("said", "Client said",
        el("blockquote", { class: "client-words", text: "“" + record.original_words + "”" }),
        voice ? "Spoken by the client and transcribed. Unedited." : "Typed by the client. Unedited."));
    if (flags.indexOf("client_term_did_not_match_account_type") !== -1) {
      steps.appendChild(step("caught", "Checked against the client's records", mismatchNotice(record, context)));
    }
    steps.appendChild(step("done", "Client confirmed",
      el("p", { class: "confirmed", text: record.confirmed_plain_language_request }),
      record.client_confirmed_at
        ? "Reviewed and confirmed by the client, " + formatTime(record.client_confirmed_at) + "."
        : "Reviewed and confirmed by the client before sending."));
    steps.appendChild(step("done", "Staff summary",
      el("p", { text: record.staff_summary }),
      "Drafted by the triage agent. It describes the question; it is not advice to take any action."));

    var tiles = el("dl", { class: "tiles" },
      tile("Intent", humanize(record.intent)),
      tile("Amount", record.amount_requested != null ? formatMoney(record.amount_requested, record.currency) : "None stated",
        record.amount_requested != null ? "Stated and confirmed by the client" : null),
      tile("Account", label(MATCH_LABELS, record.account_match_status), record.selected_account_id),
      tile("Suggested destination", humanize(routing.destination || "staff_review"), routing.reason));

    var labels = el("div", { class: "row-tags" });
    (record.categories || []).forEach(function (category) { labels.appendChild(categoryTag(category)); });
    flags.forEach(function (flag) {
      labels.appendChild(el("span", { class: "tag flag" }, icon("flag"), label(FLAG_LABELS, flag)));
    });

    var questions = record.unresolved_questions || [];
    var questionList = el("ul", { class: "open-list" });
    questions.forEach(function (question) { questionList.appendChild(el("li", { text: question })); });

    var page1 = el("article", { class: "sheet" },
      el("div", { class: "sheet-head" }, el("h2", { text: "Request and routing" }), el("p", { text: "Page 1 of 2" })),
      steps, tiles,
      el("div", { class: "block" }, el("h3", { text: "Categories and flags" }), labels),
      el("div", { class: "block" }, el("h3", { text: "Still open" }),
        questions.length ? questionList : el("p", { class: "muted", text: "Nothing was left open at intake." })));

    // Page 2: relevant account context
    var page2 = el("article", { class: "sheet" },
      el("div", { class: "sheet-head" }, el("h2", { text: "Relevant account context" }), el("p", { text: "Page 2 of 2" })));
    if (!context) {
      page2.appendChild(el("p", { class: "muted", text: security
        ? "No account details are attached. The specialist queue reviews account access directly."
        : "No account is attached to this request." }));
    } else {
      var facts = el("dl", { class: "kv" });
      var row = function (name, value, detail, sourceId, extra) {
        facts.appendChild(el("div", { class: extra || null },
          el("dt", { text: name }),
          el("dd", {}, value, detail ? el("small", { text: " " + detail }) : null),
          el("span", { class: "src" }, source(sourceId))));
      };
      if (context.familiar_label) row("Client knows it as", context.familiar_label, null, context.account_source_id);
      row("Account type", label(ACCOUNT_TYPE_LABELS, context.account_type), null, context.account_source_id);
      row("Account number", context.masked_identifier, null, context.account_source_id);
      row("Balance snapshot", formatMoney(context.balance, context.currency),
        "as of " + formatDate(context.balance_as_of), context.account_source_id, "balance");
      page2.appendChild(facts);

      var events = context.relevant_events || [];
      var eventList = el("dl", { class: "kv" });
      events.forEach(function (event) {
        eventList.appendChild(el("div", {},
          el("dt", { text: formatDate(event.date) }),
          el("dd", {}, humanize(event.type), event.summary ? el("small", { text: " " + event.summary }) : null),
          el("span", { class: "src" }, source(event.source_id))));
      });
      page2.appendChild(el("div", { class: "block" },
        el("h3", { text: "Earlier activity that explains this request" }),
        events.length ? eventList : el("p", { class: "muted", text: "No earlier activity is relevant to this request." })));

      page2.appendChild(el("div", { class: "note" }, icon("info"),
        el("p", { text: "The balance is a snapshot, not the amount available to withdraw. Tax effects and eligibility have not been assessed." })));
    }

    caseEl.appendChild(el("div", { class: "detail-grid" },
      el("div", { class: "detail-main" }, page1, page2),
      el("aside", { class: "detail-rail" }, renderAssignment(record, candidates, security, banner))));
  }

  // ---------- assignment ----------

  function advisorName(candidates, advisorId) {
    var match = candidates.list.filter(function (c) { return c.advisor_id === advisorId; })[0];
    return match ? match.display_name + " (" + match.advisor_id + ")" : advisorId;
  }

  function renderAssignment(record, candidates, security, banner) {
    var routing = record.routing || {};
    var sheet = el("article", { class: "sheet" },
      el("div", { class: "sheet-head" }, el("h2", { text: security ? "Specialist review" : "Assign an advisor" })));

    if (security) {
      sheet.appendChild(el("div", { class: "specialist" },
        el("span", { class: "badge" }, icon("shield")),
        el("strong", { text: humanize(routing.destination || "security_specialist_review") }),
        el("p", { class: "muted", text: "Advisor matching is turned off for this request. A staff member decides the next step; nothing is sent from this prototype." })));
      return sheet;
    }

    sheet.appendChild(el("p", { class: "assign-sub", text: "You decide. Nothing is sent to an advisor from this prototype." }));
    if (banner) sheet.appendChild(banner);

    if (record.status === "assigned" && routing.assigned_advisor_id) {
      if (!banner) sheet.appendChild(notice("ok", "Assigned to " + advisorName(candidates, routing.assigned_advisor_id)));
      if (routing.staff_decision) {
        sheet.appendChild(el("div", { class: "block" }, el("h3", { text: "Staff reason" }), el("p", { text: routing.staff_decision })));
      }
      return sheet;
    }

    var shown = candidates.list.slice(0, MAX_CANDIDATES);
    var recommended = routing.recommended_advisor_ids || [];
    var wanted = record.categories || [];
    var reasons = {};
    var form = el("form", { novalidate: true });
    var group = el("fieldset", { class: "candidates" }, el("legend", { text: "Suggested advisors" }));

    if (candidates.error) {
      group.appendChild(notice("error", "Couldn't load advisor suggestions", candidates.error));
    } else if (!shown.length) {
      group.appendChild(el("p", { class: "muted", text: "No advisors were suggested for this request. Enter an advisor ID below to assign it yourself." }));
    }

    shown.forEach(function (candidate) {
      reasons[candidate.advisor_id] = candidate.reason;
      var tags = el("div", { class: "cand-tags" });
      if (recommended.indexOf(candidate.advisor_id) !== -1) tags.appendChild(el("span", { class: "tag recommended", text: "Recommended", title: "Recommended when the request was triaged" }));
      if (candidate.existing_client_relationship === true) tags.appendChild(el("span", { class: "tag match", text: "Current advisor" }));
      (candidate.specialties || []).forEach(function (specialty) {
        tags.appendChild(el("span", {
          class: "tag" + (wanted.indexOf(specialty) !== -1 ? " match" : ""),
          title: wanted.indexOf(specialty) !== -1 ? "Matches this request" : null, text: humanize(specialty)
        }));
      });

      var facts = el("div", { class: "cand-facts" },
        el("span", {}, el("i", { class: "dot" + (candidate.available ? "" : " no") }),
          candidate.available ? "Available for a new case" : "Not available"));
      // existing_client_relationship, meeting_mode, and capacity are optional version-two fields.
      facts.appendChild(el("span", { text: candidate.existing_client_relationship === true ? "Already works with this client"
        : candidate.existing_client_relationship === false ? "No existing relationship with this client"
        : "Existing relationship: not reported" }));
      if (candidate.meeting_mode) facts.appendChild(el("span", { text: "Meets by " + candidate.meeting_mode.map(humanize).join(", ").toLowerCase() }));
      if (candidate.capacity != null) facts.appendChild(el("span", { text: "Room for " + candidate.capacity + (candidate.capacity === 1 ? " more case" : " more cases") }));

      group.appendChild(el("label", { class: "candidate" },
        el("input", { type: "radio", name: "advisor", value: candidate.advisor_id }),
        el("div", { class: "cand-head" },
          avatar(candidate.display_name, "small"),
          el("div", { class: "cand-name" }, candidate.display_name, el("small", { text: candidate.advisor_id }))),
        tags, facts,
        el("p", { class: "cand-why" }, el("b", { text: "Why suggested: " }), candidate.reason || "No reason given")));
    });

    var otherInput = el("input", { type: "text", id: "other-advisor", placeholder: "ADV-00", autocomplete: "off", "aria-label": "Advisor ID" });
    var otherRadio = el("input", { type: "radio", name: "advisor", value: "__other__" });
    group.appendChild(el("label", { class: "candidate other" },
      otherRadio,
      el("div", { class: "cand-name", text: "Choose a different advisor" }),
      otherInput,
      el("p", { class: "muted", text: "Enter the advisor's ID. The case service rejects IDs it does not know." })));
    form.appendChild(group);

    var reason = el("textarea", { id: "staff-reason", required: true, "aria-describedby": "reason-hint" });
    var useSuggested = el("button", { type: "button", class: "quiet", text: "Use suggested reason", disabled: true });
    form.appendChild(el("div", { class: "field" },
      el("div", { class: "field-top" },
        el("label", { for: "staff-reason", text: "Reason" }), useSuggested),
      reason,
      el("span", { class: "hint", id: "reason-hint", text: "Required. Saved with the case so the decision can be reviewed." })));

    var errorSlot = el("div", {});
    var submit = el("button", { type: "submit", class: "primary", text: "Assign case", disabled: true });
    form.appendChild(errorSlot);
    form.appendChild(submit);

    function checkedValue() {
      var checked = form.querySelector('input[name="advisor"]:checked');
      return checked ? checked.value : "";
    }
    function chosenAdvisor() {
      var value = checkedValue();
      return value === "__other__" ? otherInput.value.trim() : value;
    }
    function update() {
      submit.disabled = !(chosenAdvisor() && reason.value.trim());
      useSuggested.disabled = !reasons[checkedValue()];
    }
    otherInput.addEventListener("focus", function () { otherRadio.checked = true; update(); });
    useSuggested.addEventListener("click", function () {
      reason.value = reasons[checkedValue()] || "";
      reason.focus();
      update();
    });
    form.addEventListener("input", update);
    form.addEventListener("change", update);

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var advisorId = chosenAdvisor();
      var staffReason = reason.value.trim();
      if (!advisorId || !staffReason) return;
      submit.disabled = true;
      submit.textContent = "Assigning…";
      errorSlot.textContent = "";
      api("/staff/cases/" + encodeURIComponent(record.case_id) + "/assign", {
        method: "POST",
        body: { advisor_id: advisorId, staff_reason: staffReason }
      }).then(function (result) {
        // Only a successful response changes what the page shows.
        var updated = Object.assign({}, record, {
          status: result.status,
          routing: Object.assign({}, routing, { assigned_advisor_id: result.assigned_advisor_id, staff_decision: staffReason })
        });
        var name = advisorName(candidates, result.assigned_advisor_id);
        renderCase(updated, candidates, notice("ok", "Assigned to " + name,
          el("span", { text: "The case status is now " + label(STATUS_LABELS, result.status).toLowerCase() + "." })));
        var confirmation = caseEl.querySelector(".notice.ok");
        if (confirmation) {
          confirmation.setAttribute("tabindex", "-1");
          confirmation.focus();
        }
        toast("Assigned to " + name);
        loadQueue();
      }).catch(function (error) {
        submit.textContent = "Assign case";
        update();
        errorSlot.textContent = "";
        errorSlot.appendChild(notice("error", "The case was not assigned", error.message));
      });
    });

    sheet.appendChild(form);
    return sheet;
  }

  // ---------- start ----------

  refreshEl.appendChild(icon("refresh"));
  refreshEl.addEventListener("click", function () {
    refreshEl.classList.remove("spinning");
    void refreshEl.offsetWidth;
    refreshEl.classList.add("spinning");
    loadQueue();
  });
  searchEl.addEventListener("input", renderQueue);
  categoryFilter.addEventListener("change", renderQueue);
  document.getElementById("filters").addEventListener("submit", function (event) { event.preventDefault(); });

  document.addEventListener("keydown", function (event) {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName);
    if (event.key === "Escape" && event.target === searchEl) { searchEl.value = ""; renderQueue(); searchEl.blur(); return; }
    if (typing) return;
    if (event.key === "/") { event.preventDefault(); searchEl.focus(); }
    else if (event.key === "j") moveSelection(1);
    else if (event.key === "k") moveSelection(-1);
  });

  window.addEventListener("hashchange", function () {
    var id = decodeURIComponent(location.hash.slice(1));
    if (id && id !== state.selectedId) openCase(id, true);
  });

  renderViews();
  loadQueue().then(function () {
    var id = decodeURIComponent(location.hash.slice(1));
    if (id) openCase(id, false);
  });
  setInterval(function () {
    if (!document.hidden) loadQueue();
  }, POLL_MS);
})();
