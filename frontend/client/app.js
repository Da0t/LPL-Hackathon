(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  // Minimal presentation-only projection of the frozen synthetic fixture.
  // API v1 has no client/profile GET endpoint. Never use this as authorization.
  const profiles = {
    "CLIENT-017": {
      name: "Mara Ellis",
      accounts: [
        {
          id: "ACCT-201",
          label: "Retirement account from former employer",
          mask: "•••• 4821",
        },
        { id: "ACCT-202", label: "Everyday investments", mask: "•••• 7314" },
      ],
    },
    "CLIENT-022": {
      name: "Evan Brooks",
      accounts: [
        { id: "ACCT-301", label: "Roth retirement account", mask: "•••• 6205" },
      ],
    },
  };
  const base = String(window.SAMEPAGE_API_BASE || "").replace(/\/$/, "");
  const draftKey = "samepage.client.draft.v1";
  let clientId = "CLIENT-017",
    session = null,
    screen = "start",
    revision = 0;
  let timer,
    inFlight = null,
    lastStarted = 0,
    syncedRevision = -1;
  let selectedOption = null,
    selectedAccount = null,
    options = [],
    result = null;
  let paused = false,
    humanHelp = false,
    noneSelected = false,
    enteringReview = false;
  let inputMode = "text",
    recognition = null,
    listening = false,
    speechPrefix = "";
  let confirmBusy = false,
    confirmationUncertain = false;
  let reviewRevision = -1;

  function message(text = "") {
    $("error").textContent = text;
    $("error").hidden = !text;
  }
  function status(text) {
    $("turn-status").textContent = text;
  }
  function saveDraft() {
    try {
      localStorage.setItem(
        draftKey,
        JSON.stringify({ clientId, words: $("words").value }),
      );
    } catch {
      /* Storage is optional. */
    }
  }
  function setScreen(next) {
    screen = next;
    for (const name of ["start", "intake", "review", "success"])
      $(name + "-screen").hidden = name !== next;
    const step =
      next === "review" ? "review" : next === "success" ? "sent" : "describe";
    for (const name of ["describe", "review", "sent"]) {
      if (name === step) $("step-" + name).setAttribute("aria-current", "step");
      else $("step-" + name).removeAttribute("aria-current");
    }
    if (next !== "intake") {
      clearTimeout(timer);
      stopSpeech();
    }
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  async function api(path, body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 45000);
    try {
      const response = await fetch(base + path, {
        method: "POST",
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          "X-Demo-Role": "client",
          "X-Demo-Client-Id": clientId,
        },
        body: JSON.stringify(body),
      });
      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error("The service returned an unreadable response.");
      }
      if (!response.ok) {
        const error = new Error(
          data.message || "The service could not process this request.",
        );
        // A 5xx may occur after a write; only definite validation/role failures are retryable.
        error.definiteRejection =
          response.status >= 400 && response.status < 500;
        throw error;
      }
      return data;
    } catch (error) {
      if (error.name === "AbortError")
        throw new Error("The service took too long to respond.");
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }
  function accountFor(id) {
    return profiles[clientId].accounts.find((a) => a.id === id);
  }
  function invalidate() {
    revision++;
    selectedOption = null;
    selectedAccount = null;
    result = null;
    options = [];
    noneSelected = false;
    humanHelp = false;
    $("suggestion-section").hidden = true;
    document.querySelector(".guidance").hidden = false;
    $("review").disabled = true;
    saveDraft();
  }
  function schedule() {
    clearTimeout(timer);
    if (
      paused ||
      screen !== "intake" ||
      enteringReview ||
      !$("words").value.trim()
    )
      return;
    status("Waiting for a pause in your words…");
    timer = setTimeout(() => sendTurn().catch(() => {}), 1250);
  }
  function changed(mode = "text") {
    inputMode = mode;
    invalidate();
    message();
    schedule();
    if (paused)
      status(
        "Suggestions paused. You can keep editing, or update when you’re ready.",
      );
  }
  function renderTurn(data) {
    options =
      !noneSelected && !humanHelp && Array.isArray(data.suggestions)
        ? data.suggestions.slice(0, 3)
        : [];
    // A stale server-side selection must never re-select an account after a client edit/rejection.
    if (
      selectedOption &&
      data.selected_account_id &&
      data.selected_account_id === selectedAccount
    ) {
      $("question").textContent =
        "Thank you. You can review the details when you’re ready.";
    } else {
      $("question").textContent =
        data.question || "Do any of these sound like what you mean?";
    }
    $("uncertainty").textContent = data.uncertainty || "";
    $("why").hidden = !data.uncertainty;
    $("definitions").replaceChildren();
    for (const definition of (Array.isArray(data.definitions)
      ? data.definitions
      : []
    ).slice(0, 3)) {
      const details = document.createElement("details");
      const title = document.createElement("summary");
      title.textContent = "What is a " + definition.term + "?";
      const explanation = document.createElement("p");
      explanation.textContent = definition.plain;
      details.append(title, explanation);
      $("definitions").append(details);
    }
    $("suggestions").replaceChildren();
    for (const option of options) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "suggestion-card";
      button.setAttribute("aria-pressed", String(selectedOption === option.id));
      const text = document.createElement("span");
      text.textContent = option.label;
      const account = accountFor(option.account_id);
      if (account) {
        const mask = document.createElement("small");
        mask.textContent = account.mask;
        text.append(mask);
      }
      const arrow = document.createElement("span");
      arrow.className = "arrow";
      arrow.textContent = "↗";
      arrow.setAttribute("aria-hidden", "true");
      button.append(text, arrow);
      button.addEventListener("click", () => {
        stopSpeech();
        clearTimeout(timer);
        selectedOption = option.id;
        selectedAccount = option.account_id || null;
        humanHelp = false;
        noneSelected = false;
        revision++;
        $("review").disabled = true;
        $("suggestions")
          .querySelectorAll("button")
          .forEach((b) => {
            b.disabled = true;
          });
        sendTurn().catch(() => {});
      });
      $("suggestions").append(button);
    }
    $("suggestion-section").hidden = false;
    document.querySelector(".guidance").hidden = true;
    $("review").disabled = !(
      selectedOption ||
      data.status === "ready_for_client_review" ||
      noneSelected ||
      humanHelp
    );
    status(
      selectedAccount
        ? "Account selected. Review and confirm your request next."
        : "Check the suggestions, or keep editing your words.",
    );
    if (selectedOption && !enteringReview && !$("review").disabled)
      $("review").focus();
  }
  async function sendTurn() {
    clearTimeout(timer);
    if (!session || !$("words").value.trim()) return;
    if (inFlight) {
      await inFlight;
      if (syncedRevision !== revision) return sendTurn();
      return;
    }
    if (syncedRevision === revision) return;
    const job = (async () => {
      // Serialize turns and enforce at least 1.2s between calls, including card clicks.
      const wait = Math.max(0, 1200 - (Date.now() - lastStarted));
      if (wait) await new Promise((resolve) => setTimeout(resolve, wait));
      const version = revision;
      const payload = {
        text: $("words").value.trim(),
        input_mode: inputMode,
        selected_option_id: selectedOption,
      };
      lastStarted = Date.now();
      status("Finding a clearer next step…");
      $("update").disabled = true;
      try {
        const data = await api(
          "/intake/" + encodeURIComponent(session) + "/turn",
          payload,
        );
        if (version !== revision || screen !== "intake") return;
        result = data;
        syncedRevision = version;
        message();
        renderTurn(data);
      } catch (error) {
        if (version === revision) {
          message(
            error.message +
              " Your words are still here. Select “Find the right next step” to try again.",
          );
          status("Your draft is saved. The service hasn’t updated it yet.");
          $("suggestions")
            .querySelectorAll("button")
            .forEach((b) => {
              b.disabled = false;
            });
        }
        throw error;
      } finally {
        $("update").disabled = false;
      }
    })();
    inFlight = job;
    try {
      await job;
    } finally {
      if (inFlight === job) inFlight = null;
    }
  }
  async function begin(event) {
    event.preventDefault();
    message();
    $("start").disabled = true;
    $("start").textContent = "Starting…";
    clientId = $("client").value;
    try {
      const data = await api("/intake/start", { client_id: clientId });
      if (!data.session_id)
        throw new Error("The service did not return a session.");
      session = data.session_id;
      $("greeting").textContent =
        "A little clarity for " +
        (data.client_display_name || profiles[clientId].name).split(" ")[0];
      setScreen("intake");
      $("words").focus();
      saveDraft();
      // Restored drafts stay local until a deliberate edit or update action.
      if ($("words").value.trim())
        status(
          "Your words were restored. Select “Find the right next step” when ready.",
        );
    } catch (error) {
      message(error.message + " Please try starting again.");
    } finally {
      $("start").disabled = false;
      $("start").textContent = "Start a request →";
    }
  }
  function populateAccounts() {
    $("account").replaceChildren(
      new Option("I’m not sure / no account needed", ""),
    );
    for (const account of profiles[clientId].accounts)
      $("account").add(
        new Option(account.label + " · " + account.mask, account.id),
      );
    // Unknown future accounts are not invented from incomplete v1 data.
    if (selectedAccount && !accountFor(selectedAccount)) selectedAccount = null;
    $("account").value = selectedAccount || "";
    $("unresolved").hidden = Boolean(selectedAccount);
  }
  async function review() {
    if (enteringReview) return;
    enteringReview = true;
    stopSpeech();
    clearTimeout(timer);
    $("review").disabled = true;
    message();
    try {
      await sendTurn();
      if (syncedRevision !== revision)
        throw new Error("Update your words before reviewing.");
      if (reviewRevision !== revision) {
        $("original").textContent = $("words").value.trim();
        const account = accountFor(selectedAccount);
        $("summary").value = humanHelp
          ? "I would like to speak with a person. " + $("words").value.trim()
          : account &&
              result?.candidate_intent === "discuss_possible_withdrawal"
            ? "I want to speak with an advisor about a possible withdrawal from my " +
              account.label.toLowerCase() +
              "."
            : $("words").value.trim();
        $("amount").value = "";
        populateAccounts();
        reviewRevision = revision;
      }
      setScreen("review");
      $("summary").focus();
    } catch (error) {
      message(error.message + " Your draft has not been sent.");
    } finally {
      enteringReview = false;
      $("review").disabled = false;
    }
  }
  async function confirm(event) {
    event.preventDefault();
    if (confirmBusy || confirmationUncertain) return;
    message();
    const summary = $("summary").value.trim();
    const amountText = $("amount").value.trim();
    const amount = amountText ? Number(amountText.replace(/,/g, "")) : null;
    if (!summary) {
      message("Please add a short description of the request.");
      $("summary").focus();
      return;
    }
    if (
      amountText &&
      (!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$/.test(amountText) ||
        !Number.isFinite(amount) ||
        amount <= 0)
    ) {
      message(
        "Enter a positive dollar amount, such as 6,000 or 6000.00, or leave it blank.",
      );
      $("amount").focus();
      return;
    }
    confirmBusy = true;
    $("confirm").disabled = true;
    $("confirm").textContent = "Sending your request…";
    for (const id of ["summary", "account", "amount", "back", "edit-words"])
      $(id).disabled = true;
    try {
      const wait = Math.max(0, 1200 - (Date.now() - lastStarted));
      if (wait) await new Promise((resolve) => setTimeout(resolve, wait));
      lastStarted = Date.now();
      const data = await api(
        "/intake/" + encodeURIComponent(session) + "/confirm",
        {
          confirmed_plain_language_request: summary,
          selected_account_id: $("account").value || null,
          amount_requested: amount,
        },
      );
      if (!data.case_id || data.status !== "submitted")
        throw new Error("A case number could not be verified.");
      $("case-id").textContent = data.case_id;
      $("client-summary").textContent =
        data.client_summary || "Your request has been sent for staff review.";
      try {
        localStorage.removeItem(draftKey);
      } catch {
        /* Optional storage. */
      }
      setScreen("success");
      $("success-screen").focus();
    } catch (error) {
      confirmationUncertain = !error.definiteRejection;
      message(
        confirmationUncertain
          ? "We couldn’t verify whether your request was received. Please ask the demo staff to check their case queue before sending another request. Your details are still visible here."
          : error.message +
              " Your request was not accepted. Check the details and try again.",
      );
    } finally {
      confirmBusy = false;
      $("confirm").disabled = confirmationUncertain;
      $("confirm").textContent = confirmationUncertain
        ? "Receipt needs to be checked"
        : "Confirm and send request →";
      for (const id of ["summary", "account", "amount", "back", "edit-words"])
        $(id).disabled = confirmationUncertain;
    }
  }
  function stopSpeech() {
    if (!recognition) return;
    if (recognition && listening) {
      listening = false;
      recognition.stop();
    }
    $("mic").setAttribute("aria-pressed", "false");
    $("mic").textContent = "◉ Speak instead";
  }
  function setupSpeech() {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      $("mic").disabled = true;
      $("mic").textContent = "Microphone unavailable";
      $("speech-status").textContent =
        "This browser doesn’t support speech input. Typing has all the same features.";
      return;
    }
    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;
    $("speech-status").textContent =
      "Optional voice input uses your browser’s speech service.";
    $("mic").addEventListener("click", () => {
      if (listening) {
        stopSpeech();
        $("speech-status").textContent =
          "Microphone stopped. You can edit your words below.";
        return;
      }
      speechPrefix = $("words").value.trim();
      try {
        recognition.start();
        listening = true;
        $("mic").setAttribute("aria-pressed", "true");
        $("mic").textContent = "■ Stop microphone";
        $("speech-status").textContent =
          "Listening with browser speech recognition. Speak only fictional demo content.";
      } catch {
        $("speech-status").textContent =
          "Microphone could not start. You can type your request below.";
        $("words").focus();
      }
    });
    recognition.onresult = (event) => {
      if (!listening || screen !== "intake") return;
      let transcript = "",
        stable = true;
      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript + " ";
        stable = stable && event.results[i].isFinal;
      }
      $("words").value = [speechPrefix, transcript.trim()]
        .filter(Boolean)
        .join(" ")
        .slice(0, 4000);
      inputMode = "voice";
      invalidate();
      clearTimeout(timer);
      if (stable) schedule();
      else status("Listening… suggestions update after a complete phrase.");
    };
    recognition.onerror = (event) => {
      stopSpeech();
      $("speech-status").textContent =
        event.error === "not-allowed" || event.error === "service-not-allowed"
          ? "Microphone permission was denied. Type below to continue with all the same features."
          : "Speech input is unavailable. Your words are preserved; you can continue by typing.";
      $("words").focus();
    };
    recognition.onend = () => {
      stopSpeech();
      if (screen === "intake") schedule();
    };
  }
  $("start-form").addEventListener("submit", begin);
  $("client").addEventListener("change", () => {
    clientId = $("client").value;
    $("words").value = "";
    $("restored").hidden = true;
    saveDraft();
  });
  $("words").addEventListener("input", () => {
    stopSpeech();
    changed();
  });
  $("update").addEventListener("click", () => {
    stopSpeech();
    if (!$("words").value.trim()) {
      message("Tell us a little about what you need first.");
      $("words").focus();
      return;
    }
    sendTurn().catch(() => {});
  });
  $("pause").addEventListener("click", () => {
    paused = !paused;
    clearTimeout(timer);
    stopSpeech();
    $("pause").setAttribute("aria-pressed", String(paused));
    $("pause").textContent = paused
      ? "Resume suggestions"
      : "Pause suggestions";
    status(
      paused
        ? "Suggestions paused. You can keep editing, or update when you’re ready."
        : "Suggestions resumed.",
    );
    if (!paused) schedule();
  });
  $("none").addEventListener("click", () => {
    stopSpeech();
    clearTimeout(timer);
    selectedAccount = null;
    selectedOption = null;
    noneSelected = true;
    revision++;
    $("suggestion-section").hidden = true;
    $("review").disabled = !$("words").value.trim();
    status(
      "No account selected. Add a little more detail, or review with the account left for staff to clarify.",
    );
    $("words").focus();
  });
  $("person").addEventListener("click", () => {
    stopSpeech();
    clearTimeout(timer);
    humanHelp = true;
    selectedOption = null;
    selectedAccount = null;
    revision++;
    if (!$("words").value.trim()) {
      $("words").value = "I would like help describing my request.";
      revision++;
      saveDraft();
    }
    review();
  });
  $("review").addEventListener("click", review);
  for (const id of ["back", "edit-words"])
    $(id).addEventListener("click", () => {
      setScreen("intake");
      message();
      $("words").focus();
    });
  $("account").addEventListener("change", () => {
    $("unresolved").hidden = Boolean($("account").value);
  });
  $("confirm-form").addEventListener("submit", confirm);
  $("new-request").addEventListener("click", () => location.reload());
  $("environment-note").hidden = !window.SAMEPAGE_MOCK_MODE;
  try {
    const draft = JSON.parse(localStorage.getItem(draftKey));
    if (draft && profiles[draft.clientId] && typeof draft.words === "string") {
      clientId = draft.clientId;
      $("client").value = clientId;
      $("words").value = draft.words.slice(0, 4000);
      $("restored").hidden = !draft.words;
    }
  } catch {
    /* A malformed or unavailable local draft must not block intake. */
  }
  setupSpeech();
})();
