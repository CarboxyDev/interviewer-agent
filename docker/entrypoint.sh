#!/bin/sh
set -eu

mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
rm -f "$XDG_RUNTIME_DIR/pulse/pid" "$XDG_RUNTIME_DIR/pulse/native"

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

display_number=${DISPLAY#:}
display_number=${display_number%%.*}
display_socket="/tmp/.X11-unix/X${display_number}"
display_lock="/tmp/.X${display_number}-lock"
rm -f "$display_socket" "$display_lock"

Xvfb "$DISPLAY" -screen 0 1280x800x24 -nolisten tcp &
xvfb_pid=$!
display_wait_attempt=0
while [ ! -S "$display_socket" ]; do
    if ! kill -0 "$xvfb_pid" 2>/dev/null; then
        wait "$xvfb_pid"
        exit 1
    fi
    display_wait_attempt=$((display_wait_attempt + 1))
    if [ "$display_wait_attempt" -ge 100 ]; then
        echo "Xvfb did not become ready within 5 seconds" >&2
        exit 1
    fi
    sleep 0.05
done

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
