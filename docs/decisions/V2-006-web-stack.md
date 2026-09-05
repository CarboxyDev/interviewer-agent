# V2-006: Typed browser application on the existing Python service

Status: Accepted for M2 implementation. Date: 2026-09-05.

## Decision

Use React, TypeScript, and Vite in a `web/` workspace. Keep FastAPI as the only application server
and the authoritative owner of session lifecycle, consent, persistence, and provider calls. Build
the web bundle into the browser-service image and serve it with the API from one HTTPS origin.
Node is a build/test dependency; it is not a second production application server.

Vite supports producing static build assets; its preview server is for local inspection rather than
production serving. This fits the existing Python application. [Vite deployment guide](https://vite.dev/guide/static-deploy)

React's documentation describes Vite as an option for a client application and calls out the need
to choose routing and data-fetching patterns. We accept those explicit choices for this focused
practice flow. [React build-from-scratch guide](https://react.dev/learn/build-a-react-app-from-scratch)

| Concern | Choice | Reason |
| --- | --- | --- |
| UI | React + strict TypeScript | Explicit session state, accessible reusable controls, mature component testing |
| Build | Vite; npm with a committed lockfile | Small client build and reproducible CI; pin supported versions when V2-201 starts |
| Navigation | React Router, client-side routes | Setup, ready, live, review and retry have distinct navigation/recovery needs |
| State | Typed reducer for practice flow; local state for forms and disclosure | Makes consent and connection transitions explicit without a global state framework |
| HTTP | Generated OpenAPI types plus a small native-fetch client | Keeps FastAPI contracts authoritative and error handling visible |
| Realtime | Versioned JSON control/events and binary PCM over a same-origin WebSocket | Fits bidirectional audio and the existing async service; no second message broker |
| Audio | Web Audio API with AudioWorklet capture/playback and explicit format conversion | Browser samples may differ from the pipeline's 24 kHz PCM format |
| Styling | Tailwind CSS v4, semantic theme tokens, shadcn/ui and Lucide icons | User-approved V2-010 amendment; accessible reusable controls, light/dark/system themes and restrained motion |
| Verification | Vitest + Testing Library; Playwright browser tests; existing Python checks | Separate state/component coverage, contract drift, browser behavior and live provider evidence |

`openapi-typescript` generates TypeScript types from OpenAPI but does not provide runtime validation.
Validate external data at the server and explicitly validate incoming realtime events in the client;
TypeScript types alone cannot establish protocol safety. [Tool documentation](https://openapi-ts.dev/introduction)

## Contract and runtime boundaries

- V2-201 exports OpenAPI from an isolated application composition with no production credentials,
  database initialization, browser launch, or provider calls. CI regenerates types and fails on drift.
- HTTP contracts and realtime event envelopes are versioned separately. M1 defines the event
  semantics; M2 adds browser connection/session identity, sequence handling and reconnect behavior.
  The browser never decides authoritative consent or saved-session status from optimistic UI alone.
- Use a single origin for HTTP, WebSocket and static assets in production. Vite's development proxy
  forwards API/realtime paths locally. SPA fallback must not swallow API errors or artifact routes.
- Keep capture local during microphone checks. Send audio only after required consent and start
  acknowledgement. Retaining a recording remains an independent server-side choice.
- Browser audio and WebSocket buffers must be bounded. Pause capture on backpressure/disconnect;
  do not silently accumulate and replay a private answer after reconnection. Define resumable
  control events and utterance identity before reconnect is implemented.
- An explicit browser audio transport is selected initially. WebRTC and direct browser-to-provider
  sessions remain alternatives for M3 only if the measured pipeline comparison warrants them.

Microphone access and AudioWorklet use secure-context browser APIs, so production uses HTTPS.
Microphone permission is separate from recording/transcription consent. Browser support and device
behavior still need the Chrome/Safari checks in M2. [getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia),
[AudioWorklet](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet)

## Alternatives and consequences

- Next.js would add a second server and another lifecycle/auth boundary without a current SSR need.
  Revisit if public content or server rendering becomes a product requirement.
- Server-rendered templates would be adequate for setup but do not simplify the live voice state,
  transcript evidence navigation, playback, and retry comparison enough for this product.
- A large component kit, global store, and query framework can be added for an observed need; they
  are not initial dependencies. Accessibility still requires keyboard/focus and assistive-tech QA.

V2-010 brings the typed UI scaffold forward at explicit user priority. The sample moves into `web/`,
with API contract generation and live browser transport still pending V2-201 onward.

M0's original prototype is a disposable flow experiment with synthetic state. It must not be treated as a
working interview or bypass M1. No package installation, application scaffold, contract generation,
or browser transport is implemented by this decision. V2-201 through V2-210 deliver and verify it.
