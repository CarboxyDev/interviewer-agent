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
pactl load-module \
    module-remap-source \
    master=bot_microphone.monitor \
    source_name=bot_microphone_source \
    source_properties=device.description=Bot_Microphone >/dev/null
pactl set-default-sink meet_output
pactl set-default-source bot_microphone_source

Xvfb "$DISPLAY" -screen 0 1280x800x24 -nolisten tcp &

if [ "${INTERVIEWER_BROWSER_DESKTOP:-false}" = "true" ]; then
    x11vnc \
        -display "$DISPLAY" \
        -forever \
        -shared \
        -nopw \
        -localhost \
        -rfbport 5900 \
        -o /tmp/interviewer-x11vnc.log \
        -bg
    websockify --web=/usr/share/novnc 6080 localhost:5900 >/tmp/interviewer-novnc.log 2>&1 &
fi

if [ "${1:-}" = "voice-interviewer" ] && [ "${2:-}" = "serve" ]; then
    alembic upgrade head
fi

exec "$@"
