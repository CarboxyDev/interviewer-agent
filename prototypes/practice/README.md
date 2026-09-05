# Practice flow study

V2-008. A low-fidelity, interactive implementation of the V2 candidate journey. This is an isolated
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

- Visual thesis: warm neutral surfaces, clear typography, one green accent, and quiet voice activity.
- Content plan: orient, configure, check readiness, practice, reflect, and retry; one main job per view.
- Interaction thesis: brief screen transitions, restrained voice activity, and direct evidence
  navigation. Reduced-motion preferences disable animation. Keyboard focus follows transitions,
  evidence, controls, and confirmation dialogs.

## What to try

1. Start sample practice without an account or upload. Change the goal, mode, or duration and inspect
   the focus preview. Personal context paths use fixed fictional content, never real uploads.
2. At the ready check, try starting with only consent or only a microphone check. Both are required.
   Audio retention is separately optional. The policy describes the planned 24-hour retention and
   deletion behavior, while clearly stating that this prototype saves nothing beyond the tab.
3. Start practice, open optional captions, mute, repeat, and pause. Use the sample answer to advance
   through listening, thinking, and speaking. Mock mode shows no coaching during the interview.
4. Finish the segment or end early. With an answer, continue to evidence-linked sample feedback;
   without one, there is no invented coaching. Inspect both observations and optional audio.
5. Retry one answer and inspect the original and retry text plus the evidence of the changed
   opening. Export the authored sample report or start the recommended focused practice.
6. Withdraw consent during practice or delete from review. Cancel to keep the session, or confirm
   to clear all demo choices and answers. Starting again requires fresh checks and consent.
7. Expand **Prototype scenarios** below the workspace to simulate permission denial, device loss,
   silence, network interruption, provider delay, and report failure at the applicable step.

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
- Consent, recording, device readiness, recovery, timers, and finalization are simulations.
- Audio playback uses the public fictional V2-002 answer, not a captured interview. Evidence timing
  is approximate. The voice preview is this same clip, not the final interviewer voice.
- Original feedback and retry text are authored examples, not model evaluations. The retry has no
  recorded audio. Goals share one fictional scenario, not an adaptive question generator.
- Reloading clears all work. Starting the next practice also resets the demo; export first if needed.
- Production durable save, resumable reports, real deletion acknowledgement, browser navigation
  recovery, Safari/Firefox microphone behavior, and accessibility assistive-technology testing
  remain later milestones. No hosting resources were created.
