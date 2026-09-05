# Repository Instructions

## Version 2 source of truth

- Read `docs/v2-plan.md` before starting Version 2 work.
- Treat its milestone order, scope, acceptance criteria, and non-goals as the current product contract.
- Use the `V2-###` task ID in implementation notes, commits, and pull requests.
- Work on the current milestone unless the user explicitly changes the priority.

## Checklist tracking

- At the start of a work session, inspect the working tree and the plan's Current status section.
- When beginning a task, set it as the current task in the plan. Do not check it off yet.
- Check a task only after its acceptance criteria pass.
- Record completion evidence in the plan's Evidence log. Include the task ID, commit when available,
  tests or measurements, and any remaining limitation.
- Do not mark a milestone complete until every required task and milestone exit criterion is complete.
- Leave blocked tasks unchecked and record the blocker in Current status.
- Update the plan in the same change as the work it records when practical.
- Do not use estimated completion percentages. Report concrete completed and remaining items.
- Do not add delivery or calendar estimates unless the user explicitly asks for them.
- Add material scope or architecture changes to the Decision log before implementing them.

## Candidate practice UX

- Treat the Practice experience and UX contract in `docs/v2-plan.md` as acceptance criteria.
- Optimize the default path for a first-time candidate, not an administrator or recruiter.
- Keep the live interview calm and distraction-free. Show conversation state and essential controls;
  keep transcripts optional and technical metrics out of the primary live view.
- Make the feedback loop actionable: evidence, playback, retry, comparison, and the next practice step.
- Do not turn the product into a generic dashboard or a collection of decorative cards.

## Public repository safety

- The repository and V2 plan are public.
- Never commit resumes, job descriptions containing private information, transcripts, recordings,
  meeting links, browser profiles, credentials, API keys, cookies, or provider tokens.
- Use synthetic fixtures and clearly labelled sample artifacts for tests, demos, and documentation.
- Keep candidate data deletion and recording consent behavior fail-closed.
- Do not add candidate ranking, employability scores, emotion inference, identity inference, or hiring
  recommendations.

## Implementation discipline

- Preserve the existing transport and provider boundaries unless an approved decision changes them.
- Add or update focused tests with behavior changes, then run the relevant focused checks.
- Run `make check` before declaring a milestone or release complete.
- Treat unit tests separately from live browser, audio, provider, and deployment verification.
- Preserve unrelated working-tree changes.
- Do not push or publish without an explicit user request.
