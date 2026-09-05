# Synthetic fixture pack v1

V2-002. Dataset ID: `candidate-practice-v1`.

All text is fictional and was authored for this repository. Audio was synthesized offline from
that text using the standard macOS Samantha voice at 165 words per minute. No microphone,
candidate data, existing interview artifacts, or paid provider was used. These files are test
inputs, not evidence that an interview succeeded or that consent handling passed.

- `resume.txt` and `role.txt` are supported V1 document inputs for a backend engineering sample.
- `transcript.json` contains independent reference utterances: consent, a substantive answer,
  repetition, withdrawal, and graceful ending. It is not a session transcript or the M1 replay scenario schema.
- Each speech WAV has a corresponding reference utterance. Timestamps are local to its clip,
  measured from file start, and include any synthesized leading or trailing silence. They are
  clip boundaries, not word alignments or measured VAD boundaries.
- `audio/silence.wav` is exactly one second of zero-valued PCM. Repeat it to exercise a configured
  timeout; a one-second file alone does not prove silence handling.
- `manifest.json` pins every input's SHA-256, length, provenance, and audio format: mono 24 kHz
  signed 16-bit little-endian PCM WAV. Strip the WAV header before streaming raw PCM to STT.

Validate the pinned assets without audio devices, credentials, or provider calls:

```sh
uv run pytest tests/test_benchmark_fixtures.py --no-cov
```

Use the committed bytes for comparisons. Speech regeneration is not bit-reproducible across macOS
voice updates. If an input changes, create a new dataset version and compare both pipelines on
that version; do not silently refresh these hashes. The manifest excludes this explanatory README.

To recreate a speech clip for a new version, save its reference text to a temporary UTF-8 file:

```sh
say -v Samantha -r 165 -f /tmp/synthetic-utterance.txt -o /tmp/synthetic-utterance.aiff
ffmpeg -i /tmp/synthetic-utterance.aiff -ar 24000 -ac 1 -c:a pcm_s16le \
  -map_metadata -1 -fflags +bitexact -flags:a +bitexact /tmp/synthetic-utterance.wav
```

Verify the WAV has nonzero frames and signal before using it. Some restricted environments can
produce an empty speech file even when synthesis exits successfully.

The offline control check records a V1 gap: "Could you repeat the question, please?" is not
recognized by the deterministic repeat guard. Keep this wording to expose the gap in baseline
results; do not interpret a passing fixture test as successful repetition behavior.

Limitations: one fictional role, one synthetic US English voice, clean audio, and five utterances.
This pack supports an initial baseline, not accent/noise robustness, broad conversation quality,
or the required V2 safety suite. M1 adds versioned scenarios, adversarial inputs, and graders.
