import { useEffect, useReducer } from "react";
import { sampleScenario, sampleRoles, type RoleId } from "./scenarios";

export type Screen =
  | "start"
  | "configure"
  | "ready"
  | "live"
  | "preparing"
  | "review"
  | "compare"
  | "recovery"
  | "deleted";
export type Voice =
  | "speaking"
  | "listening"
  | "thinking"
  | "paused"
  | "reconnecting"
  | "finishing";
export type Fault =
  | "permission"
  | "device"
  | "silence"
  | "network"
  | "provider"
  | "report";
export type Confirmation = "end" | "withdraw" | "delete" | "help" | null;
export interface PracticeState {
  screen: Screen;
  role: RoleId;
  goal: string;
  mode: "focused" | "mock";
  duration: string;
  source: string;
  resume: boolean;
  mic: boolean;
  consent: boolean;
  retain: boolean;
  muted: boolean;
  voice: Voice;
  caption: string;
  activeQuestion: string;
  answered: boolean;
  originalAnswered: boolean;
  isRetry: boolean;
  retried: boolean;
  fault: Fault | null;
  evidence: "gap" | "strength" | null;
  saved: boolean;
  recoveryFrom: Screen;
  confirmation: Confirmation;
  repeat: number;
}
export const defaults = (): PracticeState => ({
  screen: "start",
  role: "backend",
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
  caption: "",
  activeQuestion: "",
  answered: false,
  originalAnswered: false,
  isRetry: false,
  retried: false,
  fault: null,
  evidence: null,
  saved: false,
  recoveryFrom: "ready",
  confirmation: null,
  repeat: 0,
});
type StateUpdate =
  | { type: "patch"; patch: Partial<PracticeState> }
  | { type: "reset"; patch?: Partial<PracticeState> };
const reducer = (state: PracticeState, event: StateUpdate): PracticeState =>
  event.type === "reset"
    ? { ...defaults(), ...event.patch }
    : { ...state, ...event.patch };

export const failures: Record<Fault, [string, string, string]> = {
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

export function usePractice() {
  const [state, dispatch] = useReducer(reducer, undefined, defaults);
  const patch = (value: Partial<PracticeState>) =>
    dispatch({ type: "patch", patch: value });
  const sample = sampleScenario(state.role, state.goal, state.resume);
  const canStart = state.mic && state.consent && !state.fault;
  const modeName =
    state.mode === "focused" ? "Focused practice" : "Mock interview";

  useEffect(() => {
    if (state.screen !== "live" || state.confirmation) return;
    let next: Partial<PracticeState>;
    if (state.voice === "speaking") next = { voice: "listening" };
    else if (state.voice === "thinking") {
      const caption =
        state.mode === "mock" ? sample.mockFollowup : sample.followup;
      next = { voice: "speaking", caption, activeQuestion: caption };
    } else if (state.voice === "finishing") {
      next = {
        saved: true,
        screen: state.isRetry
          ? state.answered
            ? "compare"
            : "review"
          : "preparing",
        retried: state.retried || (state.isRetry && state.answered),
      };
    } else return;
    const timer = window.setTimeout(
      () => dispatch({ type: "patch", patch: next }),
      state.voice === "finishing" ? 600 : 1200,
    );
    return () => window.clearTimeout(timer);
  }, [
    state.screen,
    state.voice,
    state.repeat,
    state.confirmation,
    state.mode,
    state.isRetry,
    state.answered,
    state.retried,
    sample.mockFollowup,
    sample.followup,
  ]);

  function start(isRetry = false) {
    if (!canStart) return;
    patch({
      screen: "live",
      voice: "speaking",
      caption: sample.question,
      activeQuestion: sample.question,
      muted: false,
      isRetry,
      answered: false,
      saved: false,
    });
  }
  function confirm(kind: Confirmation) {
    patch({
      confirmation: kind,
      ...(state.screen === "live" ? { voice: "paused" } : {}),
    });
  }
  function act(action: string) {
    switch (action) {
      case "home":
        dispatch({ type: "reset" });
        break;
      case "configure":
        patch({ screen: "configure" });
        break;
      case "ready":
        patch({ screen: "ready", fault: null });
        break;
      case "mic":
        patch({ mic: true });
        break;
      case "begin":
        start();
        break;
      case "retry":
        start(true);
        break;
      case "mute":
        patch({ muted: !state.muted });
        break;
      case "pause":
        patch({ voice: state.voice === "paused" ? "listening" : "paused" });
        break;
      case "repeat":
        patch({
          caption: state.activeQuestion,
          voice: "speaking",
          repeat: state.repeat + 1,
        });
        break;
      case "sample-answer":
        if (state.voice !== "listening" || state.muted || state.answered)
          return;
        patch({
          answered: true,
          originalAnswered: state.originalAnswered || !state.isRetry,
          voice: "thinking",
          caption: state.isRetry ? sample.retry : sample.original,
        });
        break;
      case "finish":
        patch({ voice: "finishing" });
        break;
      case "end":
      case "withdraw":
      case "delete":
      case "help":
        confirm(action);
        break;
      case "cancel":
        patch({ confirmation: null });
        break;
      case "confirm-end":
        patch({ confirmation: null, voice: "finishing" });
        break;
      case "confirm-delete":
        dispatch({ type: "reset", patch: { screen: "deleted" } });
        break;
      case "review":
        patch({ screen: "review", isRetry: false });
        break;
      case "compare":
        patch({ screen: "compare" });
        break;
      case "next":
        dispatch({
          type: "reset",
          patch: { screen: "configure", role: state.role, goal: "Clarity" },
        });
        break;
      case "evidence-gap":
        patch({ evidence: "gap" });
        break;
      case "evidence-strength":
        patch({ evidence: "strength" });
        break;
      case "recover":
        if (state.fault === "report") patch({ fault: null, screen: "review" });
        else if (state.recoveryFrom === "ready" || state.fault === "device")
          patch({
            fault: null,
            screen: "ready",
            mic: false,
            consent: state.recoveryFrom === "live" ? false : state.consent,
          });
        else patch({ fault: null, voice: "listening", screen: "live" });
        break;
      case "exit-recovery":
        patch({
          fault: null,
          screen: state.recoveryFrom === "ready" ? "configure" : "live",
          voice: "paused",
          confirmation: state.recoveryFrom === "ready" ? null : "end",
        });
        break;
      case "export":
        downloadReview();
        break;
    }
  }
  function selectRole(role: RoleId) {
    patch({
      role,
      goal: state.goal === "Clarity" ? "Clarity" : sampleRoles[role].focus,
      retain: false,
      mic: false,
      consent: false,
    });
  }
  function fault(kind: Fault) {
    patch({
      fault: kind,
      recoveryFrom: state.screen,
      screen: "recovery",
      voice: "reconnecting",
    });
  }
  function downloadReview() {
    const report = [
      "Practice review",
      "Sample session using example answers.",
      "",
      `Role: ${sample.name}`,
      `Focus: ${state.goal}`,
      `Format: ${modeName}`,
      `Question: ${sample.question}`,
      "",
      "Original answer",
      sample.original,
      "",
      "What to improve",
      sample.observation,
      `Opening: "${sample.opening}"`,
      `Suggestion: ${sample.suggestion}`,
      "",
      "What worked well",
      sample.strength,
      `Evidence: "${sample.result}"`,
      ...(state.retried ? ["", "Revised answer", sample.retry] : []),
      "",
      "Next practice",
      sample.next,
    ].join("\n");
    const url = URL.createObjectURL(
      new Blob([report], { type: "text/plain;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "practice-review.txt";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return { state, sample, canStart, modeName, patch, act, selectRole, fault };
}
export type Practice = ReturnType<typeof usePractice>;
