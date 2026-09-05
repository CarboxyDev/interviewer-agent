/* V2-008: synthetic flow study. No capture, network calls, uploads, or persistence. */
const main = document.querySelector("main");
const dialog = document.querySelector("dialog");
const question = "How did you make the inventory update safe to retry?";
const original =
  "I built the inventory update endpoint. I used a client supplied idempotency key and a unique database constraint. I stored the result in the same transaction as the update, so a retry returned the saved result. In a sample test with one hundred requests, including twenty duplicates, each unique update applied once. The tradeoff was storing request results and deciding when to expire them.";
const retry =
  "My goal was to prevent duplicate inventory updates when clients retried. I owned the endpoint and stored the idempotency key, update, and result in one transaction. In a sample test of 100 requests with 20 duplicates, each unique update applied once. The storage cost meant we also needed an expiry policy.";
const defaults = () => ({
  screen: "start",
  goal: "Technical depth",
  mode: "focused",
  duration: "5",
  source: "sample",
  resume: false,
  mic: false,
  consent: false,
  retain: false,
  muted: false,
  voice: "speaking",
  caption: question,
  answered: false,
  originalAnswered: false,
  isRetry: false,
  retried: false,
  fault: null,
  evidence: null,
  saved: false,
});
let state = defaults();
let pending;
let returnFocus;
const button = (action, text, kind = "", disabled = false) =>
  `<button type="button" data-action="${action}" class="${kind}" ${disabled ? "disabled" : ""}>${text}</button>`;
const canStart = () => state.mic && state.consent && !state.fault;
const modeName = () =>
  state.mode === "focused" ? "Focused practice" : "Mock interview";
const audio = "/sample-answer.wav";
function later(action, delay = 1200) {
  clearTimeout(pending);
  pending = setTimeout(action, delay);
}
function go(screen) {
  clearTimeout(pending);
  state.screen = screen;
  render();
  main.focus();
}
function preview() {
  return `<aside class="preview" aria-label="Focus preview"><span class="eyebrow">Your focus</span><h2>${state.goal}</h2><dl><dt>Format</dt><dd>${modeName()} · ${state.duration} minutes</dd><dt>Role</dt><dd>Backend engineer · fictional inventory service</dd><dt>Likely topics</dt><dd>Ownership, reliable updates, and explaining a technical tradeoff.</dd><dt>Feedback timing</dt><dd>${state.mode === "focused" ? "Reflect after the practice segment, then retry one answer." : "Complete the interview first. No coaching between questions."}</dd></dl></aside>`;
}
function configure() {
  const goals = [
    "Technical depth",
    "Behavioral stories",
    "System design explanation",
    "Clarity",
    "Concise answers",
  ];
  return `<span class="eyebrow">01 / Set your intention</span><h1>What would you like to practice?</h1><div class="split"><div>
    <div class="field"><label for="goal">Practice goal</label><select id="goal">${goals.map((x) => `<option ${state.goal === x ? "selected" : ""}>${x}</option>`).join("")}</select></div>
    <fieldset><legend>Practice mode</legend>${[
      ["focused", "Focused practice", "Work on one skill and retry an answer."],
      [
        "mock",
        "Mock interview",
        "Rehearse across role topics. Feedback comes at the end.",
      ],
    ]
      .map(
        ([v, title, sub]) =>
          `<label class="choice"><input type="radio" name="mode" value="${v}" ${state.mode === v ? "checked" : ""}><span>${title}<small>${sub}</small></span></label>`,
      )
      .join("")}</fieldset>
    <div class="field"><label for="duration">Duration</label><select id="duration">${["5", "10", "15"].map((x) => `<option value="${x}" ${state.duration === x ? "selected" : ""}>${x} minutes</option>`).join("")}</select></div>
    <div class="field"><label for="source">Role context</label><select id="source"><option value="sample" ${state.source === "sample" ? "selected" : ""}>Use a sample role</option><option value="paste" ${state.source === "paste" ? "selected" : ""}>Pasted role description (sample)</option><option value="document" ${state.source === "document" ? "selected" : ""}>Role document (sample)</option></select></div>
    ${state.source !== "sample" ? `<div class="feedback"><p>${state.source === "paste" ? "Preview of pasted role text" : "Sample role document selected: fictional-backend-role.txt"}</p><p class="subtle">Backend engineer working on inventory APIs, database transactions, and reliable retries.</p><p class="subtle">This prototype uses fixed fictional text. Personal input and file selection arrive in M2.</p></div>` : ""}
    <label class="choice"><input id="resume" type="checkbox" ${state.resume ? "checked" : ""}><span>Include a sample resume <small>Optional fictional background in APIs and database projects.</small></span></label>
    <div class="actions">${button("ready", "Continue to ready check")}${button("home", "Back", "quiet")}</div></div>${preview()}</div>`;
}
function ready() {
  return `<span class="eyebrow">02 / Before you begin</span><h1>Make room for a good answer.</h1><div class="split"><div>
    <div class="check"><h2>How your practice will be handled</h2><p>In the planned product, audio is transcribed to guide the conversation and support feedback. Keeping an audio recording for playback is optional.</p><p>Session content, including supplied documents, expires within 24 hours. You can delete it from review at any time. Withdrawing consent during practice stops capture and deletes the session.</p><p class="subtle">Here, everything is simulated in this tab. No personal content is collected or retained, and reloading clears the demo.</p></div>
    <div class="check"><h2>Microphone check</h2><p id="mic-status" aria-live="polite">${state.mic ? "Simulated input detected. Your real microphone was not opened." : "Check the input before starting. This demo simulates permission and a healthy microphone."}</p>${button("mic", state.mic ? "Check again" : "Simulate microphone check", "secondary")}</div>
    <div class="check"><h2>Hear the sample voice</h2><p class="subtle">Fictional candidate recording to preview the playback interaction. This is not the final interviewer voice.</p><audio controls preload="none" aria-label="Synthetic voice sample" src="${audio}"></audio></div>
    <label class="choice"><input id="consent" type="checkbox" ${state.consent ? "checked" : ""}><span>I agree to transcription for this practice session.<small>Required for adaptive questions and evidence-linked feedback. Separate from microphone permission.</small></span></label>
    <label class="choice"><input id="retain" type="checkbox" ${state.retain ? "checked" : ""}><span>Also keep audio for answer playback.<small>Optional. Without it, review includes transcript evidence only.</small></span></label>
    <p id="start-help" class="subtle">${canStart() ? "Ready. The next action begins the simulated interview." : "To begin, complete the microphone check and agree to transcription."}</p>
    <div class="actions">${button("begin", "Start practice", "", !canStart())}${button("configure", "Back to setup", "quiet")}</div></div>${preview()}</div>`;
}
function live() {
  const labels = {
    speaking: "Interviewer speaking",
    listening: "Your turn",
    thinking: "Thinking",
    paused: "Take your time",
    reconnecting: "Reconnecting",
    finishing: "Finishing your practice",
  };
  const descriptions = {
    speaking: "Listen to the question. You can ask to hear it again.",
    listening: "There is room to pause before you answer.",
    thinking: "The interviewer is considering your answer.",
    paused: "The interview is paused. Input is paused too.",
    reconnecting: "Input is paused while the connection recovers.",
    finishing: "Input has stopped. Your practice segment is complete.",
  };
  return `<section class="live"><div class="meta"><span>${modeName()}${state.isRetry ? " · Answer retry" : ""} · ${state.goal}</span><span>${state.duration}:00 remaining · demo timer</span></div>
    <div class="voice ${["listening", "speaking"].includes(state.voice) && !state.muted ? "active" : ""}" aria-hidden="true">${"<i></i>".repeat(9)}</div>
    <h1 aria-live="polite">${labels[state.voice]}</h1><p class="lede">${descriptions[state.voice]}</p>
    <p class="subtle">Transcription ${state.voice === "paused" || state.muted ? "paused" : "on"} · Audio ${state.retain ? "retained for playback" : "not retained"} · Simulated</p>
    <div class="actions">${button("mute", state.muted ? "Unmute" : "Mute", "secondary", state.voice === "finishing")}${button("repeat", "Repeat question", "secondary", ["paused", "finishing", "thinking"].includes(state.voice))}${button("pause", state.voice === "paused" ? "Resume" : "Pause for a moment", "secondary", state.voice === "finishing")}${button("end", "End interview", "secondary", state.voice === "finishing")}</div>
    <details id="captions"><summary>Optional captions</summary><p>${state.caption}</p></details>
    <div class="actions">${button("sample-answer", state.isRetry ? "Use sample retry answer" : "Use sample answer", "", state.voice !== "listening" || state.muted)}${state.answered ? button("finish", state.isRetry ? "Finish retry" : "Finish sample segment", "secondary", state.voice === "finishing") : ""}</div>
    <p class="subtle">Sample controls advance this flow without recording your voice.</p>
    <div class="actions">${button("help", "Help", "quiet")}${button("withdraw", "Withdraw consent and delete", "quiet")}</div></section>`;
}
function review() {
  if (!state.originalAnswered)
    return `<span class="eyebrow">Practice ended</span><h1>No answer to review yet.</h1><p>You ended before the sample answer. There is no evidence for coaching.</p><div class="actions">${button("next", "Try focused practice")}${button("delete", "Delete session", "quiet")}</div>`;
  return `<span class="eyebrow">04 / Reflect and retry · Sample feedback</span><h1>Lead with the problem you solved.</h1><p class="lede">Your implementation is concrete. Give the listener the goal before the mechanism.</p>
    <div class="split"><div><article class="observation"><h2>Improve first: make the goal explicit</h2><p><strong>Observed:</strong> The answer opens with the endpoint you built, then names the implementation.</p><p><strong>Suggestion:</strong> Start by explaining that retries could apply the same update twice.</p>${button("evidence-gap", "Open improvement evidence", "secondary")}</article>
    <article class="observation"><h2>Strength: a specific test result</h2><p><strong>Observed:</strong> You cite 100 requests, 20 duplicates, and one update per unique request.</p>${button("evidence-strength", "Open strength evidence", "secondary")}</article>
    ${state.evidence ? evidence() : ""}
    <details><summary>Suggested answer structure</summary><p>Goal → your responsibility → decision → evidence → tradeoff.</p><p><strong>Authored example, not something you said:</strong> “I needed retries to be safe, so a duplicated request could not change inventory twice.”</p></details>
    </div><aside class="preview"><h2>Your next step</h2><p>Retry this answer with the goal in the first sentence.</p>${button("retry", "Retry this answer")}<p class="subtle">One answer only. Then compare both attempts.</p><h3>Coverage and confidence</h3><p class="subtle">Reliable updates: supported by one sample answer. Broader backend depth: not observed. These examples are authored, not AI assessment.</p></aside></div>
    <div class="actions">${state.retried ? button("compare", "Compare attempts", "secondary") : ""}${button("export", "Export sample report", "quiet")}${button("delete", "Delete session", "quiet")}</div>`;
}
function evidence() {
  const strength = state.evidence === "strength";
  return `<section id="evidence" class="feedback" tabindex="-1"><h2>${strength ? "Strength evidence" : "Improvement evidence"}</h2><p class="subtle">Original answer · fictional transcript · ${strength ? "00:12 to 00:19" : "00:00 to 00:03"}</p><blockquote>${strength ? "In a sample test with one hundred requests, including twenty duplicates, each unique update applied once." : "I built the inventory update endpoint."}</blockquote>${state.retain ? `<audio id="evidence-audio" controls preload="metadata" aria-label="Original answer evidence audio" src="${audio}#t=${strength ? "12,19" : "0,3"}"></audio><p class="subtle">Timing is approximate in this authored sample. Play to hear the matching passage.</p>` : '<p class="subtle">Audio was not retained. Transcript evidence is still available.</p>'}</section>`;
}
function comparison() {
  return `<span class="eyebrow">05 / Compare · Authored sample</span><h1>A clearer opening. The same evidence.</h1><p class="lede">The retry names the goal before explaining how the endpoint works.</p><div class="compare"><div><h2>Original answer</h2><blockquote>${original}</blockquote>${state.retain ? `<audio controls preload="none" aria-label="Original answer audio" src="${audio}"></audio>` : '<p class="subtle">Audio not retained.</p>'}</div><div><h2>Retry answer</h2><blockquote>${retry}</blockquote><p class="subtle">Authored text sample. No retry recording exists in this prototype.</p></div></div><div class="feedback"><h2>What changed</h2><p><strong>Evidence:</strong> The original opens “I built the inventory update endpoint.” The retry opens “My goal was to prevent duplicate inventory updates when clients retried.”</p><p><strong>Suggestion:</strong> Keep that goal-first opening, then practice explaining the expiry tradeoff. A single retry does not establish broader improvement.</p></div><div class="actions">${button("next", "Practice explaining tradeoffs")}${button("review", "Back to review", "secondary")}${button("export", "Export sample report", "quiet")}${button("delete", "Delete session", "quiet")}</div>`;
}
const failures = {
  permission: [
    "Microphone permission was denied",
    "Allow microphone access in your browser settings, then run the check again. You can also return to setup.",
    "Try microphone again",
  ],
  device: [
    "Microphone disconnected",
    "Reconnect or select a working microphone. Input is paused until you check it again.",
    "Check microphone again",
  ],
  silence: [
    "We did not hear an answer",
    "Take a moment, check your microphone, or ask to hear the question again.",
    "Continue when ready",
  ],
  network: [
    "Connection interrupted",
    "Input is paused. Once your connection returns, resume from the last question. If it stays offline, you can end here.",
    "Try reconnecting",
  ],
  provider: [
    "The interviewer is taking longer",
    "Input is paused. Try again or end the interview with the work already available.",
    "Try interviewer again",
  ],
  report: [
    "Feedback is not ready yet",
    "Your sample answer remains available in this tab. Retry feedback or inspect the available transcript. Reloading this prototype clears it; safe background processing is a later capability.",
    "Retry feedback",
  ],
};
function recovery() {
  const [title, description, label] = failures[state.fault];
  return `<span class="eyebrow">${state.fault === "network" ? "Reconnecting · " : ""}Practice recovery · Simulated</span><h1 aria-live="assertive">${title}</h1><p class="lede">${description}</p>${state.fault === "report" ? `<details><summary>Available transcript</summary><blockquote>${state.isRetry ? retry : original}</blockquote></details>` : ""}<div class="actions">${button("recover", label)}${button(state.saved ? "delete" : "exit-recovery", state.saved ? "Delete session" : state.recoveryFrom === "ready" ? "Back to setup" : "End interview", "secondary")}${!state.saved && state.recoveryFrom === "live" ? button("withdraw", "Withdraw consent and delete", "quiet") : ""}</div>`;
}
function render() {
  const active = document.activeElement;
  const focusSelector = active?.dataset?.action
    ? `button[data-action="${active.dataset.action}"]`
    : active?.tagName === "SUMMARY" && active.parentElement.id
      ? `#${active.parentElement.id} > summary`
      : null;
  const screens = {
    start: () =>
      `<section><span class="eyebrow">Interview practice / For you</span><h1>Find the words.<br>Then try them out.</h1><p class="lede">Practice a role-focused interview and leave with one clear way to improve your next answer.</p><div class="actions">${button("configure", "Start a practice session")}</div><p class="subtle">Start with a fictional backend role. No account or documents needed.</p><div class="support"><h2>Speak. Reflect. Try again.</h2><p>A focused segment or a realistic mock, followed by feedback tied to your words.</p></div></section>`,
    configure,
    ready,
    live,
    review,
    compare: comparison,
    recovery,
    preparing: () =>
      `<span class="eyebrow">03 / Practice ended</span><h1 aria-live="polite">Preparing your feedback</h1><p>The simulated session has stopped. Your sample answer is available in this tab.</p><p class="subtle">Preparing observations and transcript links. This prototype cannot save work after you close or reload the page.</p><div class="actions">${button("review", "View sample feedback")}${button("delete", "Delete session", "quiet")}</div>`,
    deleted: () =>
      `<span class="eyebrow">You are in control</span><h1 aria-live="polite">Session cleared.</h1><p>The demo consent choices, answers, and comparison have been cleared. No personal content was collected.</p><div class="actions">${button("configure", "Start a new practice")}</div>`,
  };
  const captionsOpen = document.querySelector("#captions")?.open;
  main.innerHTML = screens[state.screen]();
  if (captionsOpen && document.querySelector("#captions"))
    document.querySelector("#captions").open = true;
  const allowed =
    state.screen === "ready"
      ? ["permission", "device"]
      : state.screen === "live"
        ? ["device", "silence", "network", "provider"]
        : state.screen === "preparing" && state.answered
          ? ["report"]
          : [];
  document.querySelector("#scenarios").innerHTML = allowed.length
    ? allowed
        .map((x) =>
          button(
            `fault-${x}`,
            `${x[0].toUpperCase()}${x.slice(1)} failure`,
            "secondary",
          ),
        )
        .join("")
    : "<p>No failure scenarios at this step. Continue to a ready check, interview, or feedback preparation.</p>";
  if (focusSelector) document.querySelector(focusSelector)?.focus();
}
function start() {
  if (!canStart()) return;
  state.voice = "speaking";
  state.caption = question;
  state.muted = false;
  go("live");
  later(() => {
    state.voice = "listening";
    render();
  });
}
function finish() {
  clearTimeout(pending);
  state.voice = "finishing";
  render();
  later(() => {
    state.saved = true;
    if (state.isRetry && state.answered) {
      state.retried = true;
      go("compare");
    } else if (state.isRetry) go("review");
    else go("preparing");
  }, 600);
}
function confirm(kind) {
  clearTimeout(pending);
  returnFocus = document.activeElement?.dataset?.action;
  const deleting = kind !== "end";
  if (state.screen === "live") {
    state.voice = "paused";
    render();
  }
  dialog.innerHTML = `<h2 id="dialog-title">${kind === "withdraw" ? "Withdraw consent and delete?" : deleting ? "Delete this session?" : "End this interview?"}</h2><p>${deleting ? "This stops the session and clears its sample answers, consent, and comparison. This cannot be undone." : "End the conversation and keep consented work for review. To erase the session instead, choose withdraw consent and delete."}</p><div class="actions">${button(deleting ? "confirm-delete" : "confirm-end", deleting ? "Delete session now" : "End and review")}${button("cancel", "Keep session", "secondary")}</div>`;
  dialog.showModal();
}
function closeDialog() {
  dialog.close();
  const target = document.querySelector(`button[data-action="${returnFocus}"]`);
  if (target) target.focus();
  else main.focus();
}
const actions = {
  home: () => {
    state = defaults();
    go("start");
  },
  configure: () => go("configure"),
  ready: () => {
    state.fault = null;
    go("ready");
  },
  mic: () => {
    state.mic = true;
    render();
  },
  begin: start,
  mute: () => {
    state.muted = !state.muted;
    render();
  },
  pause: () => {
    clearTimeout(pending);
    state.voice = state.voice === "paused" ? "listening" : "paused";
    render();
  },
  repeat: () => {
    clearTimeout(pending);
    state.caption = question;
    state.voice = "speaking";
    render();
    later(() => {
      state.voice = "listening";
      render();
    });
  },
  "sample-answer": () => {
    if (state.voice !== "listening" || state.muted) return;
    state.answered = true;
    if (!state.isRetry) state.originalAnswered = true;
    state.voice = "thinking";
    state.caption = state.isRetry ? retry : original;
    render();
    later(() => {
      state.voice = "speaking";
      state.caption =
        state.mode === "mock"
          ? "What tradeoff would you explain to the team before shipping this?"
          : "How would you decide when to expire the saved results?";
      render();
      later(() => {
        state.voice = "listening";
        render();
      });
    });
  },
  finish,
  end: () => confirm("end"),
  withdraw: () => confirm("withdraw"),
  delete: () => confirm("delete"),
  "confirm-end": () => {
    closeDialog();
    finish();
  },
  "confirm-delete": () => {
    closeDialog();
    state = defaults();
    go("deleted");
  },
  cancel: closeDialog,
  help: () => {
    clearTimeout(pending);
    state.voice = "paused";
    render();
    returnFocus = "help";
    dialog.innerHTML = `<h2 id="dialog-title">Take a moment</h2><p>Practice is paused. Use Repeat question to hear the prompt again, or Resume when ready. End interview keeps your work for review. Withdraw consent stops and deletes it.</p><div class="actions">${button("cancel", "Back to practice")}</div>`;
    dialog.showModal();
  },
  review: () => {
    state.isRetry = false;
    go("review");
  },
  compare: () => go("compare"),
  retry: () => {
    state.isRetry = true;
    state.answered = false;
    state.saved = false;
    start();
  },
  next: () => {
    state = { ...defaults(), goal: "Clarity", mode: "focused" };
    go("configure");
  },
  "evidence-gap": () => {
    state.evidence = "gap";
    render();
    document.querySelector("#evidence").focus();
  },
  "evidence-strength": () => {
    state.evidence = "strength";
    render();
    document.querySelector("#evidence").focus();
  },
  recover: () => {
    const fault = state.fault;
    state.fault = null;
    if (fault === "report") {
      go("review");
    } else if (state.recoveryFrom === "ready" || fault === "device") {
      state.mic = false;
      if (state.recoveryFrom === "live") state.consent = false;
      go("ready");
    } else {
      state.voice = "listening";
      go("live");
    }
  },
  "exit-recovery": () => {
    state.fault = null;
    if (state.recoveryFrom === "ready") go("configure");
    else { state.voice = "paused"; go("live"); confirm("end"); }
  },
  export: () => {
    const report = {
      synthetic: true,
      notice:
        "Authored V2-008 flow study, not a real interview or AI assessment.",
      goal: state.goal,
      mode: state.mode,
      original,
      observations: [
        {
          observed: "Opens with the implementation before explaining the goal.",
          evidence: "I built the inventory update endpoint.",
          suggestion: "Name the duplicate-update problem first.",
        },
        {
          observed: "Includes a concrete test result.",
          evidence:
            "In a sample test with one hundred requests, including twenty duplicates, each unique update applied once.",
        },
      ],
      retry: state.retried ? retry : null,
      next_practice: "Practice explaining the expiry tradeoff.",
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "synthetic-practice-report.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
document.addEventListener("click", (event) => {
  const target = event.target.closest("button[data-action]");
  if (!target || target.disabled) return;
  const action = target.dataset.action;
  if (action.startsWith("fault-")) {
    clearTimeout(pending);
    state.fault = action.slice(6);
    state.recoveryFrom = state.screen;
    state.voice = "reconnecting";
    go("recovery");
  } else actions[action]?.();
});
document.addEventListener("change", (event) => {
  const el = event.target;
  if (el.name === "mode") state.mode = el.value;
  else if (["goal", "duration", "source"].includes(el.id))
    state[el.id] = el.value;
  else if (["resume", "consent", "retain"].includes(el.id))
    state[el.id] = el.checked;
  else return;
  const selector = el.id
    ? `#${el.id}`
    : `input[name="mode"][value="${el.value}"]`;
  render();
  document.querySelector(selector)?.focus();
});
dialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  closeDialog();
});
render();
