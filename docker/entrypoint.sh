#!/bin/sh
set -eu

mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

INTERVIEWER_PULSE_SERVER="$PULSE_SERVER"
unset PULSE_SERVER
pulseaudio --start --exit-idle-time=-1 --log-target=stderr
export PULSE_SERVER="$INTERVIEWER_PULSE_SERVER"
pactl load-module module-null-sink sink_name=meet_output sink_properties=device.description=Meet_Output >/dev/null
pactl load-module module-null-sink sink_name=bot_microphone sink_properties=device.description=Bot_Microphone >/dev/null
pactl set-default-sink meet_output
pactl set-default-source bot_microphone.monitor

Xvfb "$DISPLAY" -screen 0 1280x800x24 -nolisten tcp &

if [ "${1:-}" = "voice-interviewer" ] && [ "${2:-}" = "serve" ]; then
    alembic upgrade head
fi

exec "$@"
