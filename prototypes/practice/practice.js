/* V2-008: synthetic flow study. No capture, network calls, uploads, or persistence. */
const main = document.querySelector("main");
const dialog = document.querySelector("dialog");
const qaMode = new URLSearchParams(location.search).get("qa") === "1";
if (qaMode) {
  document
    .querySelector("footer")
    .insertAdjacentHTML(
      "beforeend",
      `<details id="lab"><summary>Recovery checks</summary><div id="scenarios"></div></details>`,
    );
}
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
  main.focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: "instant" });
}
function preview() {
  return `<aside class="preview" aria-label="Focus preview"><span class="eyebrow">Session details</span><h2>Backend engineer</h2><p class="subtle">A sample role focused on reliable systems and technical decisions.</p><dl><dt>Focus</dt><dd>${state.goal}</dd><dt>Format</dt><dd>${modeName()} · ${state.duration} minutes</dd><dt>Topics</dt><dd>Ownership, reliable updates, and technical tradeoffs.</dd><dt>Feedback</dt><dd>${state.mode === "focused" ? "After your practice segment, with a chance to retry." : "At the end of the interview. No coaching between questions."}</dd></dl></aside>`;
}
function configure() {
  const goals = [
    "Technical depth",
    "Behavioral stories",
    "System design explanation",
    "Clarity",
    "Concise answers",
  ];
  return `<h1>Set up your practice</h1><p class="lede">Choose what you want to work on and how you would like to practice.</p><div class="split"><div>
    <div class="field"><label for="goal">Practice goal</label><select id="goal">${goals.map((x) => `<option ${state.goal === x ? "selected" : ""}>${x}</option>`).join("")}</select></div>
    <fieldset><legend>Practice mode</legend><div class="mode-options">${[
      [
        "focused",
        "Focused practice",
        "Work on one skill, then retry your answer.",
      ],
      ["mock", "Mock interview", "Cover several topics. Review at the end."],
    ]
      .map(
        ([v, title, sub]) =>
          `<label class="choice mode-choice"><input type="radio" name="mode" value="${v}" ${state.mode === v ? "checked" : ""}><span>${title}<small>${sub}</small></span></label>`,
      )
      .join("")}</div></fieldset>
    <div class="field"><label for="duration">Duration</label><select id="duration">${["5", "10", "15"].map((x) => `<option value="${x}" ${state.duration === x ? "selected" : ""}>${x} minutes</option>`).join("")}</select></div>
    ${qaMode ? `<div class="field"><label for="source">Role context</label><select id="source"><option value="sample" ${state.source === "sample" ? "selected" : ""}>Sample role</option><option value="paste" ${state.source === "paste" ? "selected" : ""}>Role description</option><option value="document" ${state.source === "document" ? "selected" : ""}>Role document</option></select></div>` : ""}
    ${state.source !== "sample" ? `<div class="feedback"><h2>Backend engineer</h2><p>Build reliable inventory services and explain the decisions behind them.</p><p class="subtle">Example role description. No document upload needed.</p></div>` : ""}
    <label class="choice"><input id="resume" type="checkbox" ${state.resume ? "checked" : ""}><span>Include a sample resume<small>Add background in API and database projects.</small></span></label>
    <div class="actions">${button("ready", "Continue")}${button("home", "Back", "quiet")}</div></div>${preview()}</div>`;
}
function ready() {
  return `<h1>Before you start</h1><p class="lede">Check your sound and choose what to include in your review.</p><div class="split"><div>
    <section class="check"><h2>Check your sound</h2><p class="subtle">Play this short answer to check that you can hear it clearly.</p><audio controls preload="none" aria-label="Sound check" src="${audio}"></audio><div class="sound-confirm">${button("mic", state.mic ? "Check again" : "Sound is working", "secondary")}<span id="mic-status" aria-live="polite" class="subtle">${state.mic ? "Sound confirmed" : "Confirm when you are ready."}</span></div></section>
    <section class="check"><h2>Your transcript and audio</h2><p class="subtle">This sample uses a prepared answer. Your microphone stays off.</p>
    <label class="choice"><input id="consent" type="checkbox" ${state.consent ? "checked" : ""}><span>Allow a transcript for this session<small>Use the written answer to support your feedback.</small></span></label>
    <label class="choice"><input id="retain" type="checkbox" ${state.retain ? "checked" : ""}><span>Include audio in my review<small>Replay the answer alongside the transcript.</small></span></label></section>
    <details class="privacy"><summary>Privacy and deleting your session</summary><p>Your choices and review stay on this page. Closing or refreshing this page clears them. You can also delete the session at any time.</p><p>Ending keeps the review available here. Withdrawing consent clears the session.</p></details>
    <p id="start-help" class="subtle">${canStart() ? "You are ready to start." : "Confirm your sound and allow a transcript to continue."}</p>
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
    listening: "Continue with the example answer when you are ready.",
    thinking: "The interviewer is considering your answer.",
    paused: "Resume whenever you are ready.",
    reconnecting: "Input is paused while the connection recovers.",
    finishing: "Your answer is ready to review.",
  };
  return `<section class="live"><div class="meta"><span>${modeName()}${state.isRetry ? " · Answer retry" : ""} · ${state.goal}</span><span>${state.duration}-minute session</span></div>
    <div class="voice ${["listening", "speaking"].includes(state.voice) && !state.muted ? "active" : ""}" aria-hidden="true">${"<i></i>".repeat(9)}</div>
    <h1 aria-live="polite">${labels[state.voice]}</h1><p class="question">${question}</p><p class="lede">${descriptions[state.voice]}</p>
    <p class="subtle">Transcript ${state.voice === "paused" || state.muted ? "paused" : "included"} · Review audio ${state.retain ? "included" : "off"} · Microphone off</p>
    <div class="actions">${button("mute", state.muted ? "Unmute" : "Mute", "secondary", state.voice === "finishing")}${button("repeat", "Repeat question", "secondary", ["paused", "finishing", "thinking"].includes(state.voice))}${button("pause", state.voice === "paused" ? "Resume" : "Pause for a moment", "secondary", state.voice === "finishing")}${button("end", "End interview", "secondary", state.voice === "finishing")}</div>
    <details id="captions"><summary>Optional captions</summary><p>${state.caption}</p></details>
    <div class="actions">${button("sample-answer", state.isRetry ? "Continue with revised answer" : "Continue with example answer", "", state.voice !== "listening" || state.muted)}${state.answered ? button("finish", state.isRetry ? "Finish retry" : "Review answer", "secondary", state.voice === "finishing") : ""}</div>

    <div class="actions">${button("help", "Help", "quiet")}${button("withdraw", "Withdraw consent and delete", "quiet")}</div></section>`;
}
function review() {
  if (!state.originalAnswered)
    return `<span class="eyebrow">Practice ended</span><h1>No answer to review yet.</h1><p>The session ended before an answer was completed.</p><div class="actions">${button("next", "Try focused practice")}${button("delete", "Delete session", "quiet")}</div>`;
  return `<span class="eyebrow">Practice review</span><h1>Start with the problem you solved.</h1><p class="lede">Explain the goal first, then describe your approach.</p>
    <div class="split"><div><article class="observation"><h2>What to improve</h2><p><strong>Observed:</strong> The answer opens with the endpoint you built, then names the implementation.</p><p><strong>Suggestion:</strong> Start by explaining that retries could apply the same update twice.</p>${button("evidence-gap", "See opening in transcript", "secondary")}</article>
    <article class="observation"><h2>What worked well</h2><p><strong>Observed:</strong> You cite 100 requests, 20 duplicates, and one update per unique request.</p>${button("evidence-strength", "See result in transcript", "secondary")}</article>
    ${state.evidence ? evidence() : ""}
    <details><summary>Suggested answer structure</summary><p>Goal → your responsibility → decision → evidence → tradeoff.</p><p><strong>Suggested opening:</strong> “I needed retries to be safe, so a duplicated request could not change inventory twice.”</p></details>
    </div><aside class="preview"><h2>Your next step</h2><p>Retry this answer with the goal in the first sentence.</p>${button("retry", "Retry this answer")}<p class="subtle">One answer only. Then compare both attempts.</p><h3>What this answer covers</h3><p class="subtle">This answer explains reliable updates. It does not yet show how you would handle other backend challenges.</p></aside></div>
    <div class="actions">${state.retried ? button("compare", "Compare attempts", "secondary") : ""}${button("export", "Download review", "quiet")}${button("delete", "Delete session", "quiet")}</div>`;
}
function evidence() {
  const strength = state.evidence === "strength";
  return `<section id="evidence" class="feedback" tabindex="-1"><h2>${strength ? "Strength evidence" : "Improvement evidence"}</h2><p class="subtle">Original answer · ${strength ? "00:12 to 00:19" : "00:00 to 00:03"}</p><blockquote>${strength ? "In a sample test with one hundred requests, including twenty duplicates, each unique update applied once." : "I built the inventory update endpoint."}</blockquote>${state.retain ? `<audio id="evidence-audio" controls preload="metadata" aria-label="Original answer evidence audio" src="${audio}#t=${strength ? "12,19" : "0,3"}"></audio><p class="subtle">Play to hear this part of the answer.</p>` : '<p class="subtle">Audio is not included. You can still read the transcript.</p>'}</section>`;
}
function comparison() {
  return `<span class="eyebrow">Answer comparison</span><h1>Compare your answers</h1><p class="lede">The retry names the goal before explaining how the endpoint works.</p><div class="compare"><div><h2>Original answer</h2><blockquote>${original}</blockquote>${state.retain ? `<audio controls preload="none" aria-label="Original answer audio" src="${audio}"></audio>` : '<p class="subtle">Audio is not included.</p>'}</div><div><h2>Retry answer</h2><blockquote>${retry}</blockquote><p class="subtle">Text example. Audio is not available for this answer.</p></div></div><div class="feedback"><h2>What changed</h2><p><strong>Evidence:</strong> The original opens “I built the inventory update endpoint.” The retry opens “My goal was to prevent duplicate inventory updates when clients retried.”</p><p><strong>Suggestion:</strong> Keep that goal-first opening, then practice explaining the expiry tradeoff. A single retry does not establish broader improvement.</p></div><div class="actions">${button("next", "Practice explaining tradeoffs")}${button("review", "Back to review", "secondary")}${button("export", "Download review", "quiet")}${button("delete", "Delete session", "quiet")}</div>`;
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
    "Your answer is still available here. Try again or read the transcript. Keep this page open to keep your session.",
    "Retry feedback",
  ],
};
function recovery() {
  const [title, description, label] = failures[state.fault];
  return `<span class="eyebrow">${state.fault === "network" ? "Reconnecting · " : ""}Connection and sound</span><h1 aria-live="assertive">${title}</h1><p class="lede">${description}</p>${state.fault === "report" ? `<details><summary>Available transcript</summary><blockquote>${state.isRetry ? retry : original}</blockquote></details>` : ""}<div class="actions">${button("recover", label)}${button(state.saved ? "delete" : "exit-recovery", state.saved ? "Delete session" : state.recoveryFrom === "ready" ? "Back to setup" : "End interview", "secondary")}${!state.saved && state.recoveryFrom === "live" ? button("withdraw", "Withdraw consent and delete", "quiet") : ""}</div>`;
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
      `<section class="welcome"><div class="welcome-intro"><h1>Interview practice</h1><p class="lede">Work through an interview question and get specific feedback on your answer.</p><div class="actions">${button("configure", "Set up practice")}</div><p class="subtle">No account or documents needed.</p></div><aside class="welcome-details"><span class="eyebrow">Your first session</span><h2>Backend engineer</h2><p>Explain a technical decision, support it with evidence, and practice a clearer answer.</p><ol class="journey"><li><strong>Choose your focus</strong><span>One skill or a full mock interview.</span></li><li><strong>Work through a question</strong><span>Follow a prepared example answer.</span></li><li><strong>Review and retry</strong><span>See what worked and what to change.</span></li></ol></aside></section>`,
    configure,
    ready,
    live,
    review,
    compare: comparison,
    recovery,
    preparing: () =>
      `<span class="eyebrow">Practice complete</span><h1 aria-live="polite">Preparing your feedback</h1><p>The interview has ended. Your answer is ready.</p><p class="subtle">Keep this page open while you review. Closing or refreshing this page clears the session.</p><div class="actions">${button("review", "View feedback")}${button("delete", "Delete session", "quiet")}</div>`,
    deleted: () =>
      `<span class="eyebrow">You are in control</span><h1 aria-live="polite">Session cleared.</h1><p>Your answers, review, and session choices have been cleared.</p><div class="actions">${button("configure", "Start a new practice")}</div>`,
  };
  const phase = ["start", "configure", "ready"].includes(state.screen)
    ? 0
    : ["live", "recovery"].includes(state.screen) && !state.saved
      ? 1
      : 2;
  document.querySelector("#steps").innerHTML =
    state.screen === "start" || state.screen === "deleted"
      ? ""
      : `<ol>${["Set up", "Practice", "Review"].map((label, index) => `<li ${phase === index ? 'aria-current="step"' : ""}>${label}</li>`).join("")}</ol>`;
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
  if (qaMode)
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
  dialog.innerHTML = `<h2 id="dialog-title">${kind === "withdraw" ? "Withdraw consent and delete?" : deleting ? "Delete this session?" : "End this interview?"}</h2><p>${deleting ? "This stops the session and clears its answers, review, and session choices. This cannot be undone." : "End the conversation and keep your answers for review. To erase the session instead, choose withdraw consent and delete."}</p><div class="actions">${button(deleting ? "confirm-delete" : "confirm-end", deleting ? "Delete session now" : "End and review")}${button("cancel", "Keep session", "secondary")}</div>`;
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
    else {
      state.voice = "paused";
      go("live");
      confirm("end");
    }
  },
  export: () => {
    const report = [
      "Practice review",
      "Sample session using example answers.",
      "",
      "Role: Backend engineer",
      `Focus: ${state.goal}`,
      `Format: ${modeName()}`,
      "",
      "Original answer",
      original,
      "",
      "What to improve",
      "Start with the problem you solved, then describe your approach.",
      'Opening: "I built the inventory update endpoint."',
      "Suggestion: Explain that retries could apply the same update twice.",
      "",
      "What worked well",
      "You supported your answer with a specific test result.",
      'Evidence: "In a sample test with one hundred requests, including twenty duplicates, each unique update applied once."',
      ...(state.retried ? ["", "Revised answer", retry] : []),
      "",
      "Next practice",
      "Practice explaining the expiry tradeoff.",
    ].join("\n");
    const url = URL.createObjectURL(
      new Blob([report], { type: "text/plain;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "practice-review.txt";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
document.addEventListener("click", (event) => {
  const target = event.target.closest("button[data-action]");
  if (!target || target.disabled) return;
  const action = target.dataset.action;
  if (action.startsWith("fault-") && qaMode) {
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
