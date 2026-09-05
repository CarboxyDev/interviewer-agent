# Practice flow study

V2-008 and V2-009. An interactive candidate-facing study of the V2 practice journey. This is an isolated
M0 artifact, not the M2 React application or a working interview service.

## Run

```sh
uv sync --frozen --all-groups
make prototype
```

Open `http://127.0.0.1:8765`. The loopback server serves only the prototype and the pinned synthetic
answer clip. It does not expose the repository, `.env`, browser profiles, or session storage.
Use `uv run python prototypes/practice/server.py --port 8766` if the default port is occupied.

## Design intent

- Visual thesis: a restrained application layout, compact sans-serif typography, and one green accent.
- Content plan: orient, configure, check readiness, practice, reflect, and retry; one main job per view.
- Interaction thesis: clear setup/practice/review navigation, restrained voice activity, and direct
  evidence navigation. Reduced-motion preferences disable animation. Keyboard focus follows transitions,
  evidence, controls, and confirmation dialogs.

## What to try

1. Start sample practice without an account or upload. Change the goal, mode, or duration and inspect
   the focus preview. Choose backend engineering, product management, customer success, or finance.
   Each role has a professional focus and a Clarity goal; questions, follow-ups, coaching and
   exports follow those choices.
2. At the ready check, play the audio and confirm sound. Sound confirmation and permission to
   include a written transcript are separate gates; review audio is optional. The privacy text
   describes actual tab-only behavior. Real microphone permission remains M2 work.
3. Start practice, open optional captions, mute, repeat, and pause. Use the sample answer to advance
   through listening, thinking, and speaking. Mock mode shows no coaching during the interview.
4. Finish the segment or end early. With an answer, continue to evidence-linked sample feedback;
   without one, there is no invented coaching. Inspect both observations and optional audio.
5. Retry one answer and inspect the original and retry text plus the evidence of the changed
   opening. Download the readable plain-text review or start the recommended focused practice.
6. Withdraw consent during practice or delete from review. Cancel to keep the session, or confirm
   to clear all demo choices and answers. Starting again requires fresh checks and consent.
7. For engineering validation only, open `http://127.0.0.1:8765/?qa=1` and expand **Recovery checks**
   below the workspace. It exposes permission, device, silence, network, provider, and report
   scenarios, plus the synthetic personal-context paths. These controls are absent from the normal
   page, not merely collapsed. QA mode enables no additional device or backend access.

## Validation

```sh
uv run playwright install chromium
make prototype-test
make check
```

The browser suite uses ephemeral Chromium profiles and the restricted loopback server, with no
provider calls or real microphone permission. It runs separately from the existing Python tests.
For an unwritable browser cache, set `PLAYWRIGHT_BROWSERS_PATH=/tmp/interviewer-playwright` for both
installation and testing. For an unwritable uv cache, set `UV_CACHE_DIR=/tmp/interviewer-voice-agent-uv-cache`.

See [V2-008 validation](../../docs/validation/V2-008-practice-prototype.md) for findings and remaining
product work. These checks validate the simulated interaction contract, not live integration or
candidate usability research.

## Deliberate limits

- No microphone API, uploads, storage, backend integration, credentials, or provider requests.
- Consent, recording, recovery, and finalization are simulations. The sample uses a sound
  confirmation instead of claiming to detect a microphone. Duration is a session setting, not a
  fake running countdown.
- Audio playback uses the public fictional V2-002 answer, not a captured interview. Evidence timing
  is approximate. Only the engineering example has matching audio; other roles disable review
  audio and show transcript evidence without invented timestamps. The sound check uses this same clip, not the final interviewer voice.
- Original feedback and retry text are authored examples, not model evaluations. The retry has no
  recorded audio. Each role has one fictional answer and retry, with two goal-specific question and coaching
  variants. These are authored scenarios, not an adaptive question generator. The UI does not
  send these choices to the interview service.
- Reloading clears all work. Starting the next practice clears answers and consent while preserving the selected role;
  export first if needed.
- Production durable save, resumable reports, real deletion acknowledgement, browser navigation
  recovery, Safari/Firefox microphone behavior, and accessibility assistive-technology testing
  remain later milestones. No hosting resources were created.
