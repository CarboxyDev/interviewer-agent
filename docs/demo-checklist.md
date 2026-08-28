# Demo checklist

## One-time setup

- [ ] Install and start Docker Desktop.
- [ ] Create an OpenAI API key with sufficient project quota.
- [ ] Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
- [ ] Run `docker compose build`.
- [ ] Run `docker compose up -d`.
- [ ] Run `docker compose exec interviewer voice-interviewer doctor --live`.
- [ ] Complete one private rehearsal using two devices and no real candidate data.

## Before each demo

- [ ] Use a fresh Google Meet owned by you.
- [ ] Set meeting access to `Open`.
- [ ] Join the meeting as host before starting the bot.
- [ ] Use synthetic or authorized resume and job description files.
- [ ] Confirm the meeting owner authorized an automated guest participant.
- [ ] Keep a manual stop command ready.
- [ ] Close unrelated tabs and silence local notifications.

## Start and observe

```bash
docker compose exec interviewer voice-interviewer interview start \
  --meeting-url 'https://meet.google.com/abc-defg-hij' \
  --resume /input/resume.pdf \
  --job-description /input/job-description.txt \
  --authorized
```

- [ ] Confirm the guest appears as `AI Interviewer` without an admission request.
- [ ] Confirm it starts with disclosure and a consent question.
- [ ] Confirm no audio file exists before the candidate says yes.
- [ ] Interrupt one bot question and confirm playback stops promptly.
- [ ] Confirm questions refer naturally to the resume and role.
- [ ] Stop immediately if Google presents account or security friction.

## After the demo

- [ ] Confirm status is `COMPLETED` or intentionally `STOPPED`.
- [ ] Download and inspect all five output files.
- [ ] Confirm transcript speaker labels and timestamps are sensible.
- [ ] Confirm notes contain evidence but no score or hiring decision.
- [ ] End the Meet and discard the meeting link.
- [ ] Delete artifacts that are no longer needed.
