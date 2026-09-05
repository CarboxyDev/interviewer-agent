import { useLayoutEffect, useRef } from "react";
import { ThemePicker } from "@/components/theme-picker";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Action } from "@/components/practice-controls";
import { PracticeContext } from "@/lib/practice-context";
import {
  Welcome,
  Configure,
  Ready,
  Live,
  Review,
  Comparison,
  Recovery,
  Preparing,
  Deleted,
} from "@/components/practice-screens";
import { usePractice, type Fault } from "@/lib/practice";

export default function App() {
  const room = usePractice();
  const { state, patch, act, fault } = room;
  const main = useRef<HTMLElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const qa = new URLSearchParams(location.search).get("qa") === "1";
  useLayoutEffect(() => {
    if (state.screen !== "start") main.current?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [state.screen]);
  const phase = ["start", "configure", "ready"].includes(state.screen)
    ? 0
    : ["live", "recovery"].includes(state.screen) && !state.saved
      ? 1
      : 2;
  const screens = {
    start: <Welcome />,
    configure: <Configure qa={qa} />,
    ready: <Ready />,
    live: <Live />,
    review: <Review />,
    compare: <Comparison />,
    recovery: <Recovery />,
    preparing: <Preparing />,
    deleted: <Deleted />,
  };
  const allowed: Fault[] =
    state.screen === "ready"
      ? ["permission", "device"]
      : state.screen === "live"
        ? ["device", "silence", "network", "provider"]
        : state.screen === "preparing" && state.answered
          ? ["report"]
          : [];
  const deleting =
    state.confirmation !== "end" && state.confirmation !== "help";
  const help = state.confirmation === "help";
  return (
    <PracticeContext.Provider value={room}>
      <a className="skip" href="#workspace">
        Skip to practice
      </a>
      <header className="app-header">
        <a href="./" aria-label="Practice room home">
          Practice Room
        </a>
        <div className="header-controls">
          <span className="session-label">Sample session</span>
          <ThemePicker />
        </div>
      </header>
      <nav id="steps" aria-label="Practice steps">
        {!["start", "deleted"].includes(state.screen) && (
          <ol>
            {["Set up", "Practice", "Review"].map((label, i) => (
              <li key={label} aria-current={phase === i ? "step" : undefined}>
                {label}
              </li>
            ))}
          </ol>
        )}
      </nav>
      <main
        key={state.screen}
        id="workspace"
        ref={main}
        tabIndex={-1}
        className="screen-enter"
        onClickCapture={(event) => {
          const target = (event.target as HTMLElement).closest<HTMLElement>(
            "button[data-action]",
          );
          if (
            target &&
            ["end", "delete", "withdraw", "help"].includes(
              target.dataset.action || "",
            )
          )
            returnFocus.current = target;
        }}
      >
        {screens[state.screen]}
      </main>
      <footer>
        <span>Example answers · Microphone off</span>
        <span>Your session clears when you close or refresh this page.</span>
        {qa && (
          <details id="lab">
            <summary>Recovery checks</summary>
            <div id="scenarios">
              {allowed.length ? (
                allowed.map((kind) => (
                  <Button
                    key={kind}
                    variant="outline"
                    onClick={() => fault(kind)}
                  >
                    {kind[0].toUpperCase() + kind.slice(1)} failure
                  </Button>
                ))
              ) : (
                <p>
                  No failure scenarios at this step. Continue to a ready check,
                  interview, or feedback preparation.
                </p>
              )}
            </div>
          </details>
        )}
      </footer>
      <Dialog
        open={state.confirmation !== null}
        onOpenChange={(open) => {
          if (!open) patch({ confirmation: null });
        }}
      >
        <DialogContent
          showCloseButton={false}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (returnFocus.current?.isConnected) returnFocus.current.focus();
            else main.current?.focus();
          }}
          onPointerDownOutside={(event) => event.preventDefault()}
        >
          <DialogTitle>
            {help
              ? "Take a moment"
              : state.confirmation === "withdraw"
                ? "Withdraw consent and delete?"
                : deleting
                  ? "Delete this session?"
                  : "End this interview?"}
          </DialogTitle>
          <DialogDescription>
            {help
              ? "Practice is paused. Use Repeat question to hear the prompt again, or Resume when ready. End interview keeps your work for review. Withdraw consent stops and deletes it."
              : deleting
                ? "This stops the session and clears its answers, review, and session choices. This cannot be undone."
                : "End the conversation and keep your answers for review. To erase the session instead, choose withdraw consent and delete."}
          </DialogDescription>
          <div className="flex flex-wrap gap-3">
            {help ? (
              <Button onClick={() => act("cancel")}>Back to practice</Button>
            ) : (
              <>
                <Action action={deleting ? "confirm-delete" : "confirm-end"}>
                  {deleting ? "Delete session now" : "End and review"}
                </Action>
                <Action action="cancel" variant="outline">
                  Keep session
                </Action>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </PracticeContext.Provider>
  );
}
