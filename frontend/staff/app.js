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
    not_needed: "No account needed for this request"
  };

  var state = {
    cases: [],
    known: null, // case IDs seen so far; null until the first successful load
    arrived: {},
    signature: null,
    selectedId: null,
    openToken: 0
  };

  var listEl = document.getElementById("case-list");
  var queueStatusEl = document.getElementById("queue-status");
  var caseEl = document.getElementById("case");
  var statusFilter = document.getElementById("filter-status");
  var categoryFilter = document.getElementById("filter-category");
  var flaggedFilter = document.getElementById("filter-flagged");

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

  function humanize(value) {
    var text = String(value || "").replace(/_/g, " ");
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function label(map, value) {
    return map[value] || humanize(value);
  }

  function formatTime(iso) {
    var date = new Date(iso);
    if (isNaN(date)) return iso || "";
    return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
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
    return id ? el("span", { class: "source", text: id }) : null;
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
          if (!state.known[item.case_id]) state.arrived[item.case_id] = true;
        });
      }
      state.known = {};
      cases.forEach(function (item) { state.known[item.case_id] = true; });
      // Skip the redraw when nothing changed so polling never steals keyboard focus.
      var signature = JSON.stringify(cases);
      var wasError = queueStatusEl.className !== "queue-status";
      if (signature === state.signature && !wasError) return;
      state.signature = signature;
      state.cases = cases;
      queueStatusEl.className = "queue-status";
      syncFilterOptions();
      renderQueue();
    }).catch(function (error) {
      queueStatusEl.className = "queue-status error";
      queueStatusEl.textContent = error.message;
    });
  }

  function syncFilterOptions() {
    fillSelect(statusFilter, unique(state.cases.map(function (c) { return c.status; })), STATUS_LABELS);
    fillSelect(categoryFilter, unique([].concat.apply([], state.cases.map(function (c) { return c.categories || []; }))), {});
  }

  function unique(values) {
    return values.filter(function (value, index) { return value && values.indexOf(value) === index; }).sort();
  }

  function fillSelect(select, values, labels) {
    var current = select.value;
    var wanted = [""].concat(values);
    var existing = Array.prototype.map.call(select.options, function (o) { return o.value; });
    if (wanted.join("|") === existing.join("|")) return;
    select.textContent = "";
    wanted.forEach(function (value) {
      select.appendChild(el("option", { value: value, text: value ? label(labels, value) : "All" }));
    });
    select.value = wanted.indexOf(current) !== -1 ? current : "";
  }

  function visibleCases() {
    return state.cases.filter(function (item) {
      if (statusFilter.value && item.status !== statusFilter.value) return false;
      if (categoryFilter.value && (item.categories || []).indexOf(categoryFilter.value) === -1) return false;
      if (flaggedFilter.checked && !(item.flags || []).length) return false;
      return true;
    });
  }

  function renderQueue() {
    var rows = visibleCases();
    listEl.textContent = "";

    if (!state.cases.length) {
      queueStatusEl.textContent = "No requests are waiting. A request appears here as soon as a client confirms it.";
      return;
    }
    if (!rows.length) {
      queueStatusEl.textContent = "";
      queueStatusEl.appendChild(document.createTextNode("No requests match these filters. "));
      queueStatusEl.appendChild(el("button", { type: "button", class: "quiet", text: "Clear filters", onclick: clearFilters }));
      return;
    }
    queueStatusEl.textContent = rows.length === state.cases.length
      ? rows.length + (rows.length === 1 ? " request" : " requests")
      : "Showing " + rows.length + " of " + state.cases.length + " requests";

    rows.forEach(function (item) {
      var security = isSecurity(item);
      var flagged = (item.flags || []).length > 0;
      var tags = el("div", { class: "row-tags" },
        el("span", { class: "tag status " + item.status, text: label(STATUS_LABELS, item.status) }));
      (item.categories || []).forEach(function (category) {
        tags.appendChild(el("span", {
          class: "tag" + (category === "fraud_or_security" ? " security" : ""), text: humanize(category)
        }));
      });
      (item.flags || []).forEach(function (flag) {
        tags.appendChild(el("span", { class: "tag flag", text: label(FLAG_LABELS, flag) }));
      });

      var button = el("button", {
        type: "button",
        class: "case-row" + (security ? " security" : flagged ? " flagged" : "") + (state.arrived[item.case_id] ? " arrived" : ""),
        "aria-current": item.case_id === state.selectedId ? "true" : null,
        onclick: function () { openCase(item.case_id, true); }
      },
        el("div", { class: "row-top" },
          el("strong", { text: item.case_id }),
          el("span", { text: formatTime(item.created_at) })),
        el("div", { class: "row-client", text: item.client_display_name }),
        el("p", { class: "row-request", text: item.confirmed_plain_language_request }),
        tags);
      listEl.appendChild(el("li", {}, button));
    });
    state.arrived = {};
  }

  function clearFilters() {
    statusFilter.value = "";
    categoryFilter.value = "";
    flaggedFilter.checked = false;
    renderQueue();
  }

  // ---------- case document ----------

  function openCase(caseId, moveFocus) {
    state.selectedId = caseId;
    if (location.hash.slice(1) !== caseId) history.replaceState(null, "", "#" + caseId);
    renderQueue();
    var token = ++state.openToken;
    caseEl.textContent = "";
    caseEl.appendChild(el("div", { class: "placeholder" }, el("p", { text: "Opening " + caseId + "…" })));

    var id = encodeURIComponent(caseId);
    var candidates = api("/staff/cases/" + id + "/candidates").then(
      function (data) { return { list: data.candidates || [] }; },
      function (error) { return { error: error.message, list: [] }; });

    Promise.all([api("/staff/cases/" + id), candidates]).then(function (results) {
      if (token !== state.openToken) return;
      renderCase(results[0], results[1]);
      if (moveFocus) caseEl.focus();
    }).catch(function (error) {
      if (token !== state.openToken) return;
      caseEl.textContent = "";
      caseEl.appendChild(el("div", { class: "sheet" },
        el("div", { class: "notice error", role: "alert" },
          el("strong", { text: "Couldn't open " + caseId }),
          error.message),
        el("button", { type: "button", class: "primary", text: "Try again", onclick: function () { openCase(caseId, true); } })));
    });
  }

  function block(title, body, origin) {
    return el("div", { class: "block" },
      el("h3", { text: title }), body, origin ? el("p", { class: "origin", text: origin }) : null);
  }

  function renderCase(record, candidates, notice) {
    var security = isSecurity(record);
    var routing = record.routing || {};
    var context = record.account_context;
    caseEl.textContent = "";

    if (security) {
      caseEl.appendChild(el("div", { class: "security-banner", role: "alert" },
        el("h2", { text: "Send to " + humanize(routing.destination || "security_specialist_review").toLowerCase() }),
        el("p", { text: "This request reports possible unauthorized access. It goes to the specialist queue for review, not to a planning advisor." })));
    }

    // Page 1: request and routing
    var page1 = el("article", { class: "sheet" },
      el("div", { class: "sheet-head" },
        el("h2", { text: "Request and routing" }),
        el("p", { text: "Page 1 of 2" })),
      el("div", { class: "case-meta" },
        el("strong", { text: record.case_id }),
        el("span", { text: record.client_display_name }),
        el("span", { text: "Received " + formatTime(record.created_at) }),
        el("span", { class: "tag status " + record.status, text: label(STATUS_LABELS, record.status) })),
      block("What the client said",
        el("blockquote", { class: "client-words", text: "“" + record.original_words + "”" }),
        record.input_mode === "voice" ? "Spoken by the client and transcribed. Unedited." : "Typed by the client. Unedited."));

    if ((record.flags || []).indexOf("client_term_did_not_match_account_type") !== -1) {
      page1.appendChild(el("div", { class: "mismatch" },
        el("strong", { text: "The client's wording did not match their records" }),
        context
          ? "The account the client confirmed is recorded as a " + label(ACCOUNT_TYPE_LABELS, context.account_type) +
            ". The client corrected this before sending; the request below is the confirmed version. "
          : "The client corrected this before sending; the request below is the confirmed version. ",
        context ? source(context.account_source_id) : null));
    }

    page1.appendChild(block("What the client confirmed",
      el("p", { class: "confirmed", text: record.confirmed_plain_language_request }),
      "Reviewed and confirmed by the client before sending."));
    page1.appendChild(block("Staff summary",
      el("p", { text: record.staff_summary }),
      "Drafted by the triage agent. It describes the question; it is not advice to take any action."));

    var facts = el("dl", { class: "facts" });
    function fact(name) {
      var dd = el("dd", {});
      for (var i = 1; i < arguments.length; i++) {
        var part = arguments[i];
        if (part) dd.appendChild(typeof part === "string" ? document.createTextNode(part) : part);
      }
      facts.appendChild(el("dt", { text: name }));
      facts.appendChild(dd);
    }
    fact("Intent", humanize(record.intent));
    fact("Amount", record.amount_requested != null
      ? formatMoney(record.amount_requested, record.currency) + ", stated and confirmed by the client"
      : "None stated");
    fact("Account", label(MATCH_LABELS, record.account_match_status),
      record.selected_account_id ? el("span", { class: "muted", text: record.selected_account_id }) : null);
    var categoryTags = el("span", { class: "row-tags" });
    (record.categories || []).forEach(function (category) {
      categoryTags.appendChild(el("span", {
        class: "tag" + (category === "fraud_or_security" ? " security" : ""), text: humanize(category)
      }));
    });
    fact("Categories", categoryTags);
    if ((record.flags || []).length) {
      var flagTags = el("span", { class: "row-tags" });
      record.flags.forEach(function (flag) {
        flagTags.appendChild(el("span", { class: "tag flag", text: label(FLAG_LABELS, flag) }));
      });
      fact("Flags", flagTags);
    }
    fact("Suggested destination", humanize(routing.destination || "staff_review"));
    page1.appendChild(el("div", { class: "block" }, facts));

    var questions = record.unresolved_questions || [];
    var questionList = el("ul", { class: "plain-list" });
    questions.forEach(function (question) { questionList.appendChild(el("li", { text: question })); });
    page1.appendChild(block("Still open",
      questions.length ? questionList : el("p", { class: "muted", text: "Nothing was left open at intake." })));
    caseEl.appendChild(page1);

    // Page 2: relevant account context
    var page2 = el("article", { class: "sheet" },
      el("div", { class: "sheet-head" },
        el("h2", { text: "Relevant account context" }),
        el("p", { text: "Page 2 of 2" })));
    if (!context) {
      page2.appendChild(el("p", { class: "muted", text: security
        ? "No account details are attached. The specialist queue reviews account access directly."
        : "No account is attached to this request." }));
    } else {
      var accountFacts = el("dl", { class: "facts" });
      [
        ["Account type", label(ACCOUNT_TYPE_LABELS, context.account_type)],
        ["Account number", context.masked_identifier],
        ["Balance snapshot", formatMoney(context.balance, record.currency) + " as of " + formatDate(context.balance_as_of)]
      ].forEach(function (row) {
        accountFacts.appendChild(el("dt", { text: row[0] }));
        accountFacts.appendChild(el("dd", {}, row[1], source(context.account_source_id)));
      });
      page2.appendChild(el("div", { class: "block" }, accountFacts));

      var events = context.relevant_events || [];
      var eventList = el("dl", { class: "facts" });
      events.forEach(function (event) {
        eventList.appendChild(el("dt", { text: formatDate(event.date) }));
        eventList.appendChild(el("dd", {}, humanize(event.type), source(event.source_id)));
      });
      page2.appendChild(block("Earlier activity that explains this request",
        events.length ? eventList : el("p", { class: "muted", text: "No earlier activity is relevant to this request." })));

      page2.appendChild(block("Cautions",
        el("ul", { class: "plain-list" },
          el("li", { text: "The balance is a snapshot. It is not the amount available to withdraw." }),
          el("li", { text: "Tax effects and eligibility have not been assessed." }))));
    }
    caseEl.appendChild(page2);

    caseEl.appendChild(renderAssignment(record, candidates, security, notice));
  }

  // ---------- assignment ----------

  function renderAssignment(record, candidates, security, notice) {
    var routing = record.routing || {};
    var sheet = el("article", { class: "sheet" },
      el("div", { class: "sheet-head" },
        el("h2", { text: security ? "Specialist review" : "Assign an advisor" }),
        el("p", { text: "A staff member decides. Nothing is sent to an advisor from this prototype." })));

    if (notice) sheet.appendChild(notice);

    if (security) {
      sheet.appendChild(el("p", { text: "Destination: " + humanize(routing.destination || "security_specialist_review") +
        ". Advisor matching is turned off for this request." }));
      return sheet;
    }

    if (record.status === "assigned" && routing.assigned_advisor_id) {
      var match = candidates.list.filter(function (c) { return c.advisor_id === routing.assigned_advisor_id; })[0];
      if (!notice) {
        sheet.appendChild(el("div", { class: "notice ok" },
          el("strong", { text: "Assigned to " + (match ? match.display_name + " (" + match.advisor_id + ")" : routing.assigned_advisor_id) })));
      }
      if (routing.staff_decision) {
        sheet.appendChild(block("Staff reason", el("p", { text: routing.staff_decision })));
      }
      return sheet;
    }

    var shown = candidates.list.slice(0, MAX_CANDIDATES);
    var recommended = routing.recommended_advisor_ids || [];
    var form = el("form", { novalidate: true });
    var group = el("fieldset", { class: "candidates" }, el("legend", { text: "Suggested advisors" }));

    if (candidates.error) {
      group.appendChild(el("div", { class: "notice error" },
        el("strong", { text: "Couldn't load advisor suggestions" }), candidates.error));
    } else if (!shown.length) {
      group.appendChild(el("p", { class: "muted", text: "No advisors were suggested for this request. Enter an advisor ID below to assign it yourself." }));
    }

    shown.forEach(function (candidate) {
      var details = el("dl", {});
      function row(name, value) {
        details.appendChild(el("dt", { text: name }));
        details.appendChild(typeof value === "string" ? el("dd", { text: value }) : el("dd", {}, value));
      }
      row("Specialty", (candidate.specialties || []).map(humanize).join(", ") || "None listed");
      row("Availability", el("span", {
        class: candidate.available ? "avail-yes" : "avail-no",
        text: candidate.available ? "Available for a new case" : "Not available"
      }));
      // existing_client_relationship is an optional version-two field; version one does not send it.
      row("Existing client", candidate.existing_client_relationship === true ? "Yes, this is the client's current advisor"
        : candidate.existing_client_relationship === false ? "No existing relationship"
        : "Not reported");
      row("Why suggested", candidate.reason || "No reason given");

      group.appendChild(el("label", { class: "candidate" },
        el("input", { type: "radio", name: "advisor", value: candidate.advisor_id }),
        el("span", { class: "name" },
          candidate.display_name,
          el("small", { text: candidate.advisor_id }),
          recommended.indexOf(candidate.advisor_id) !== -1 ? el("span", { class: "tag", text: "Recommended at triage" }) : null),
        el("div", { class: "detail" }, details)));
    });

    var otherInput = el("input", { type: "text", id: "other-advisor", placeholder: "ADV-00", autocomplete: "off", "aria-label": "Advisor ID" });
    var otherRadio = el("input", { type: "radio", name: "advisor", value: "__other__" });
    group.appendChild(el("label", { class: "candidate" },
      otherRadio,
      el("span", { class: "name", text: "Choose a different advisor" }),
      el("div", { class: "detail" }, otherInput)));
    form.appendChild(group);

    var reason = el("textarea", { id: "staff-reason", required: true, "aria-describedby": "reason-hint" });
    form.appendChild(el("div", { class: "field" },
      el("label", { for: "staff-reason", text: "Reason for this assignment" }),
      el("span", { class: "hint", id: "reason-hint", text: "Required. Saved with the case so the decision can be reviewed." }),
      reason));

    var errorSlot = el("div", {});
    var submit = el("button", { type: "submit", class: "primary", text: "Assign case", disabled: true });
    form.appendChild(errorSlot);
    form.appendChild(submit);

    function chosenAdvisor() {
      var checked = form.querySelector('input[name="advisor"]:checked');
      if (!checked) return "";
      return checked.value === "__other__" ? otherInput.value.trim() : checked.value;
    }
    function update() {
      submit.disabled = !(chosenAdvisor() && reason.value.trim());
    }
    otherInput.addEventListener("focus", function () { otherRadio.checked = true; update(); });
    form.addEventListener("input", update);
    form.addEventListener("change", update);

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var advisorId = chosenAdvisor();
      if (!advisorId || !reason.value.trim()) return;
      submit.disabled = true;
      submit.textContent = "Assigning…";
      errorSlot.textContent = "";
      api("/staff/cases/" + encodeURIComponent(record.case_id) + "/assign", {
        method: "POST",
        body: { advisor_id: advisorId, staff_reason: reason.value.trim() }
      }).then(function (result) {
        // Only a successful response changes what the page shows.
        var updated = Object.assign({}, record, {
          status: result.status,
          routing: Object.assign({}, routing, {
            assigned_advisor_id: result.assigned_advisor_id,
            staff_decision: reason.value.trim()
          })
        });
        var name = candidates.list.filter(function (c) { return c.advisor_id === result.assigned_advisor_id; })[0];
        renderCase(updated, candidates, el("div", { class: "notice ok", role: "status" },
          el("strong", { text: "Assigned to " + (name ? name.display_name + " (" + name.advisor_id + ")" : result.assigned_advisor_id) }),
          "The case status is now " + label(STATUS_LABELS, result.status).toLowerCase() + "."));
        loadQueue();
      }).catch(function (error) {
        submit.textContent = "Assign case";
        update();
        errorSlot.textContent = "";
        errorSlot.appendChild(el("div", { class: "notice error", role: "alert" },
          el("strong", { text: "The case was not assigned" }), error.message));
      });
    });

    return sheet.appendChild(form), sheet;
  }

  // ---------- start ----------

  [statusFilter, categoryFilter, flaggedFilter].forEach(function (control) {
    control.addEventListener("change", renderQueue);
  });
  document.getElementById("filters").addEventListener("submit", function (event) { event.preventDefault(); });
  document.getElementById("refresh").addEventListener("click", loadQueue);
  window.addEventListener("hashchange", function () {
    var id = decodeURIComponent(location.hash.slice(1));
    if (id && id !== state.selectedId) openCase(id, true);
  });

  queueStatusEl.textContent = "Loading requests…";
  loadQueue().then(function () {
    var id = decodeURIComponent(location.hash.slice(1));
    if (id) openCase(id, false);
  });
  setInterval(function () {
    if (!document.hidden) loadQueue();
  }, POLL_MS);
})();
