import { useLayoutEffect, useRef } from "react";
import { Action, Choice } from "./practice-controls";
import { useRoom } from "@/lib/practice-context";
import { NativeSelect, NativeSelectOption } from "./ui/native-select";
import { Label } from "./ui/label";
import { sampleRoles, type RoleId } from "@/lib/scenarios";
import { failures } from "@/lib/practice";

export function Preview() {
  const { state, sample, modeName } = useRoom();
  return (
    <aside className="preview" aria-label="Focus preview">
      <span className="eyebrow">Session details</span>
      <h2>{sample.name}</h2>
      <p className="subtle">{sample.summary}</p>
      <dl>
        <dt>Focus</dt>
        <dd>{state.goal}</dd>
        <dt>Format</dt>
        <dd>
          {modeName} · {state.duration} minutes
        </dd>
        <dt>Topics</dt>
        <dd>{sample.topics}</dd>
        <dt>Feedback</dt>
        <dd>
          {state.mode === "focused"
            ? "After your practice segment, with a chance to retry."
            : "At the end of the interview. No coaching between questions."}
        </dd>
      </dl>
    </aside>
  );
}
export function Welcome() {
  return (
    <section className="welcome">
      <div>
        <h1>Interview practice</h1>
        <p className="lede">
          Work through an interview question and get specific feedback on your
          answer.
        </p>
        <div className="actions">
          <Action action="configure">Set up practice</Action>
        </div>
        <p className="subtle">No account or documents needed.</p>
      </div>
      <aside className="welcome-details">
        <span className="eyebrow">Your first session</span>
        <h2>Practice for your role</h2>
        <p>
          Choose from product, customer success, finance, or engineering. Review
          an example and practice a clearer answer.
        </p>
        <ol className="journey">
          <li>
            <strong>Choose your focus</strong>
            <span>One skill or a full mock interview.</span>
          </li>
          <li>
            <strong>Work through a question</strong>
            <span>Follow a prepared example answer.</span>
          </li>
          <li>
            <strong>Review and retry</strong>
            <span>See what worked and what to change.</span>
          </li>
        </ol>
      </aside>
    </section>
  );
}
export function Configure({ qa }: { qa: boolean }) {
  const { state, sample, patch, selectRole } = useRoom();
  return (
    <>
      <h1>Set up your practice</h1>
      <p className="lede">
        Choose what you want to work on and how you would like to practice.
      </p>
      <div className="split">
        <div>
          <div className="field">
            <Label htmlFor="role">Practice role</Label>
            <NativeSelect
              id="role"
              value={state.role}
              onChange={(e) => selectRole(e.target.value as RoleId)}
            >
              {Object.entries(sampleRoles).map(([id, role]) => (
                <NativeSelectOption key={id} value={id}>
                  {role.name}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          <div className="field">
            <Label htmlFor="goal">Practice goal</Label>
            <NativeSelect
              id="goal"
              value={state.goal}
              onChange={(e) => patch({ goal: e.target.value })}
            >
              {[sampleRoles[state.role].focus, "Clarity"].map((goal) => (
                <NativeSelectOption key={goal}>{goal}</NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          <fieldset>
            <legend>Practice mode</legend>
            <div className="mode-options">
              {(
                [
                  [
                    "focused",
                    "Focused practice",
                    "Work on one skill, then retry your answer.",
                  ],
                  [
                    "mock",
                    "Mock interview",
                    "Cover several topics. Review at the end.",
                  ],
                ] as const
              ).map(([mode, title, description]) => (
                <label key={mode} className="choice mode-choice">
                  <input
                    type="radio"
                    name="mode"
                    value={mode}
                    checked={state.mode === mode}
                    onChange={() => patch({ mode })}
                  />
                  <span>
                    {title}
                    <small>{description}</small>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="field">
            <Label htmlFor="duration">Duration</Label>
            <NativeSelect
              id="duration"
              value={state.duration}
              onChange={(e) => patch({ duration: e.target.value })}
            >
              {["5", "10", "15"].map((value) => (
                <NativeSelectOption key={value} value={value}>
                  {value} minutes
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          {qa && (
            <div className="field">
              <Label htmlFor="source">Role context</Label>
              <NativeSelect
                id="source"
                value={state.source}
                onChange={(e) => patch({ source: e.target.value })}
              >
                <NativeSelectOption value="sample">
                  Sample role
                </NativeSelectOption>
                <NativeSelectOption value="paste">
                  Role description
                </NativeSelectOption>
                <NativeSelectOption value="document">
                  Role document
                </NativeSelectOption>
              </NativeSelect>
            </div>
          )}
          {qa && state.source !== "sample" && (
            <div className="feedback">
              <h2>{sample.name}</h2>
              <p>{sample.summary}</p>
              <p className="subtle">
                Example role description. No document upload needed.
              </p>
            </div>
          )}
          {qa && (
            <Choice
              id="resume"
              label="Include a sample resume"
              description={`Add background in ${sample.background.toLowerCase()}.`}
              checked={state.resume}
              onChange={(resume) => patch({ resume })}
            />
          )}
          <div className="actions">
            <Action action="ready">Continue</Action>
            <Action action="home" variant="ghost">
              Back
            </Action>
          </div>
        </div>
        <Preview />
      </div>
    </>
  );
}
export function Ready() {
  const { state, sample, patch, canStart } = useRoom();
  return (
    <>
      <h1>Before you start</h1>
      <p className="lede">
        Check your sound and choose what to include in your review.
      </p>
      <div className="split">
        <div>
          <section className="check">
            <h2>Check your sound</h2>
            <p className="subtle">
              Play this voice sample to check that you can hear it clearly.
            </p>
            <audio
              controls
              preload="none"
              aria-label="Sound check"
              src="/sample-answer.wav"
            />
            <div className="sound-confirm">
              <Action action="mic" variant="outline">
                {state.mic ? "Check again" : "Sound is working"}
              </Action>
              <span id="mic-status" aria-live="polite" className="subtle">
                {state.mic ? "Sound confirmed" : "Confirm when you are ready."}
              </span>
            </div>
          </section>
          <section className="check">
            <h2>Your transcript and audio</h2>
            <p className="subtle">
              This sample uses a prepared answer. Your microphone stays off.
            </p>
            <Choice
              id="consent"
              label="Allow a transcript for this session"
              description="Use the written answer to support your feedback."
              checked={state.consent}
              onChange={(consent) => patch({ consent })}
            />
            <Choice
              id="retain"
              label="Include audio in my review"
              description={
                sample.audio
                  ? "Replay the answer alongside the transcript."
                  : "This role has a written example only. Review audio is unavailable."
              }
              checked={state.retain}
              disabled={!sample.audio}
              onChange={(retain) => patch({ retain })}
            />
          </section>
          <details className="privacy">
            <summary>Privacy and deleting your session</summary>
            <p>
              Your choices and review stay on this page. Closing or refreshing
              this page clears them. You can also delete the session at any
              time.
            </p>
            <p>
              Ending keeps the review available here. Withdrawing consent clears
              the session. Only your appearance preference is remembered for
              future visits.
            </p>
          </details>
          <p id="start-help" className="subtle">
            {canStart
              ? "You are ready to start."
              : "Confirm your sound and allow a transcript to continue."}
          </p>
          <div className="actions">
            <Action action="begin" disabled={!canStart}>
              Start practice
            </Action>
            <Action action="configure" variant="ghost">
              Back to setup
            </Action>
          </div>
        </div>
        <Preview />
      </div>
    </>
  );
}
export function Live() {
  const { state, modeName } = useRoom();
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
    listening: state.answered
      ? "Your example answer is complete. Continue to review."
      : "Continue with the example answer when you are ready.",
    thinking: "The interviewer is considering your answer.",
    paused: "Resume whenever you are ready.",
    reconnecting: "Input is paused while the connection recovers.",
    finishing: "Your answer is ready to review.",
  };
  return (
    <section className="live">
      <div className="meta">
        <span>
          {modeName}
          {state.isRetry ? " · Answer retry" : ""} · {state.goal}
        </span>
        <span>{state.duration}-minute session</span>
      </div>
      <div
        className={`voice ${["listening", "speaking"].includes(state.voice) && !state.muted ? "active" : ""}`}
        aria-hidden="true"
      >
        {Array.from({ length: 9 }, (_, i) => (
          <i key={i} />
        ))}
      </div>
      <h1 aria-live="polite">{labels[state.voice]}</h1>
      <p className="question">{state.activeQuestion}</p>
      <p className="lede">{descriptions[state.voice]}</p>
      <p className="subtle">
        Transcript{" "}
        {state.voice === "paused" || state.muted ? "paused" : "included"} ·
        Review audio {state.retain ? "included" : "off"} · Microphone off
      </p>
      <div className="actions">
        <Action
          action="mute"
          variant="outline"
          disabled={state.voice === "finishing"}
        >
          {state.muted ? "Unmute" : "Mute"}
        </Action>
        <Action
          action="repeat"
          variant="outline"
          disabled={["paused", "finishing", "thinking"].includes(state.voice)}
        >
          Repeat question
        </Action>
        <Action
          action="pause"
          variant="outline"
          disabled={state.voice === "finishing"}
        >
          {state.voice === "paused" ? "Resume" : "Pause for a moment"}
        </Action>
        <Action
          action="end"
          variant="outline"
          disabled={state.voice === "finishing"}
        >
          End interview
        </Action>
      </div>
      <details id="captions">
        <summary>Optional captions</summary>
        <p>{state.caption}</p>
      </details>
      <div className="actions">
        {state.answered ? (
          <Action action="finish" disabled={state.voice !== "listening"}>
            {state.isRetry ? "Finish retry" : "Review answer"}
          </Action>
        ) : (
          <Action
            action="sample-answer"
            disabled={state.voice !== "listening" || state.muted}
          >
            {state.isRetry
              ? "Continue with revised answer"
              : "Continue with example answer"}
          </Action>
        )}
      </div>
      <div className="actions">
        <Action action="help" variant="ghost">
          Help
        </Action>
        <Action action="withdraw" variant="ghost">
          Withdraw consent and delete
        </Action>
      </div>
    </section>
  );
}
export function Evidence() {
  const { state, sample } = useRoom();
  const ref = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    ref.current?.focus();
  }, [state.evidence]);
  const strength = state.evidence === "strength";
  const times = state.evidence ? sample.times?.[state.evidence] : undefined;
  const stamp = (seconds: number) => `00:${String(seconds).padStart(2, "0")}`;
  return (
    <section ref={ref} id="evidence" className="feedback" tabIndex={-1}>
      <h2>{strength ? "Strength evidence" : "Improvement evidence"}</h2>
      <p className="subtle">
        Original answer
        {times
          ? ` · ${stamp(times[0])} to ${stamp(times[1])}`
          : " · Written example"}
      </p>
      <blockquote>{strength ? sample.result : sample.opening}</blockquote>
      {state.retain && sample.audio && times ? (
        <>
          <audio
            key={state.evidence}
            id="evidence-audio"
            controls
            preload="metadata"
            aria-label="Original answer evidence audio"
            src={`${sample.audio}#t=${times.join(",")}`}
          />
          <p className="subtle">Play to hear this part of the answer.</p>
        </>
      ) : (
        <p className="subtle">
          Audio is not included. You can still read the transcript.
        </p>
      )}
    </section>
  );
}
export function Review() {
  const { state, sample } = useRoom();
  if (!state.originalAnswered)
    return (
      <>
        <span className="eyebrow">Practice ended</span>
        <h1>No answer to review yet.</h1>
        <p>The session ended before an answer was completed.</p>
        <div className="actions">
          <Action action="next">Try focused practice</Action>
          <Action action="delete" variant="ghost">
            Delete session
          </Action>
        </div>
      </>
    );
  return (
    <>
      <span className="eyebrow">
        Practice review · {sample.name} · {state.goal}
      </span>
      <h1>{sample.title}</h1>
      <p className="lede">{sample.lede}</p>
      <div className="split">
        <div>
          <article className="observation">
            <h2>What to improve</h2>
            <p>
              <strong>Observed:</strong> {sample.observation}
            </p>
            <p>
              <strong>Suggestion:</strong> {sample.suggestion}
            </p>
            <Action action="evidence-gap" variant="outline">
              See opening in transcript
            </Action>
          </article>
          <article className="observation">
            <h2>What worked well</h2>
            <p>
              <strong>Observed:</strong> {sample.strength}
            </p>
            <Action action="evidence-strength" variant="outline">
              See result in transcript
            </Action>
          </article>
          {state.evidence && <Evidence />}
          <details>
            <summary>Suggested answer structure</summary>
            <p>Goal → your responsibility → decision → evidence → tradeoff.</p>
            <p>
              <strong>Suggested opening:</strong> “{sample.suggestedOpening}”
            </p>
          </details>
        </div>
        <aside className="preview">
          <h2>Your next step</h2>
          <p>Retry this answer with the goal in the first sentence.</p>
          <Action action="retry">Retry this answer</Action>
          <p className="subtle mt-3">
            One answer only. Then compare both attempts.
          </p>
          <h3>What this answer covers</h3>
          <p className="subtle">{sample.coverage}</p>
        </aside>
      </div>
      <div className="actions">
        {state.retried && (
          <Action action="compare" variant="outline">
            Compare attempts
          </Action>
        )}
        <Action action="export" variant="ghost">
          Download review
        </Action>
        <Action action="delete" variant="ghost">
          Delete session
        </Action>
      </div>
    </>
  );
}
export function Comparison() {
  const { state, sample } = useRoom();
  return (
    <>
      <span className="eyebrow">
        Answer comparison · {sample.name} · {state.goal}
      </span>
      <h1>Compare your answers</h1>
      <p className="lede">
        The retry explains the purpose before describing the work.
      </p>
      <div className="compare">
        <div>
          <h2>Original answer</h2>
          <blockquote>{sample.original}</blockquote>
          {state.retain && sample.audio ? (
            <audio
              controls
              preload="none"
              aria-label="Original answer audio"
              src={sample.audio}
            />
          ) : (
            <p className="subtle">Audio is not included.</p>
          )}
        </div>
        <div>
          <h2>Retry answer</h2>
          <blockquote>{sample.retry}</blockquote>
          <p className="subtle">
            Text example. Audio is not available for this answer.
          </p>
        </div>
      </div>
      <div className="feedback">
        <h2>What changed</h2>
        <p>
          <strong>Evidence:</strong> The original opens “{sample.opening}” The
          retry opens “{sample.revisedOpening}”
        </p>
        <p>
          <strong>Suggestion:</strong> {sample.next} A single retry does not
          establish broader improvement.
        </p>
      </div>
      <div className="actions">
        <Action action="next">Continue focused practice</Action>
        <Action action="review" variant="outline">
          Back to review
        </Action>
        <Action action="export" variant="ghost">
          Download review
        </Action>
        <Action action="delete" variant="ghost">
          Delete session
        </Action>
      </div>
    </>
  );
}
export function Recovery() {
  const { state, sample } = useRoom();
  if (!state.fault) return null;
  const [title, description, label] = failures[state.fault];
  return (
    <>
      <span className="eyebrow">
        {state.fault === "network" ? "Reconnecting · " : ""}Connection and sound
      </span>
      <h1 aria-live="assertive">{title}</h1>
      <p className="lede">{description}</p>
      {state.fault === "report" && (
        <details>
          <summary>Available transcript</summary>
          <blockquote>
            {state.isRetry ? sample.retry : sample.original}
          </blockquote>
        </details>
      )}
      <div className="actions">
        <Action action="recover">{label}</Action>
        <Action
          action={state.saved ? "delete" : "exit-recovery"}
          variant="outline"
        >
          {state.saved
            ? "Delete session"
            : state.recoveryFrom === "ready"
              ? "Back to setup"
              : "End interview"}
        </Action>
        {!state.saved && state.recoveryFrom === "live" && (
          <Action action="withdraw" variant="ghost">
            Withdraw consent and delete
          </Action>
        )}
      </div>
    </>
  );
}
export function Preparing() {
  return (
    <>
      <span className="eyebrow">Practice complete</span>
      <h1 aria-live="polite">Preparing your feedback</h1>
      <p>The interview has ended. Your answer is ready.</p>
      <p className="subtle">
        Keep this page open while you review. Closing or refreshing this page
        clears the session.
      </p>
      <div className="actions">
        <Action action="review">View feedback</Action>
        <Action action="delete" variant="ghost">
          Delete session
        </Action>
      </div>
    </>
  );
}
export function Deleted() {
  return (
    <>
      <span className="eyebrow">You are in control</span>
      <h1 aria-live="polite">Session cleared.</h1>
      <p>Your answers, review, and session choices have been cleared.</p>
      <div className="actions">
        <Action action="configure">Start a new practice</Action>
      </div>
    </>
  );
}
