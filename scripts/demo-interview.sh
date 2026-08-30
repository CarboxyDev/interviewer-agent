#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(dirname -- "$script_dir")"
meeting_url="${1:-}"
duration_minutes="${2:-}"
job_description_file="$project_dir/input/backend-job-description.txt"

if [[ -z "$meeting_url" ]]; then
    read -r -p "Google Meet URL: " meeting_url
fi

if [[ -z "$duration_minutes" ]]; then
    read -r -p "Duration in minutes [15]: " duration_minutes
    duration_minutes="${duration_minutes:-15}"
fi

if [[ "$meeting_url" != https://meet.google.com/* ]]; then
    echo "Enter a Google Meet URL beginning with https://meet.google.com/" >&2
    exit 2
fi

if [[ ! "$duration_minutes" =~ ^[0-9]+$ ]] || (( duration_minutes < 5 || duration_minutes > 45 )); then
    echo "Duration must be a whole number from 5 to 45 minutes." >&2
    exit 2
fi

shopt -s nullglob
resume_files=("$project_dir"/input/*.pdf)
if (( ${#resume_files[@]} != 1 )); then
    echo "Place exactly one PDF resume in $project_dir/input." >&2
    exit 2
fi

if [[ ! -f "$job_description_file" ]]; then
    echo "Missing job description: $job_description_file" >&2
    exit 2
fi

resume_container_path="/input/$(basename -- "${resume_files[0]}")"

cd "$project_dir"

start_response="$(docker compose exec -T interviewer voice-interviewer interview start \
    --meeting-url "$meeting_url" \
    --resume "$resume_container_path" \
    --job-description "/input/backend-job-description.txt" \
    --duration-minutes "$duration_minutes" \
    --authorized)"

printf '%s\n' "$start_response"

session_id="$(printf '%s\n' "$start_response" | sed -n 's/^[[:space:]]*"id": "\([^"]*\)",*$/\1/p')"
if [[ -z "$session_id" ]]; then
    echo "Interview started, but the launcher could not read its session ID." >&2
    exit 1
fi

echo
echo "Following interview $session_id. Listen and respond in Google Meet."
echo "Press Ctrl+C to stop following. The interview will continue in the service."

last_state=""
trap 'echo; echo "Stopped following. The interview is still running."; exit 130' INT

while true; do
    status_response="$(docker compose exec -T interviewer voice-interviewer interview status "$session_id")"
    state="$(printf '%s\n' "$status_response" | sed -n 's/^[[:space:]]*"state": "\([^"]*\)",*$/\1/p')"

    if [[ -z "$state" ]]; then
        echo "Could not read the interview state." >&2
        exit 1
    fi

    if [[ "$state" != "$last_state" ]]; then
        echo "State: $state"
        last_state="$state"
    fi

    case "$state" in
        COMPLETED|STOPPED)
            echo "Artifacts: $project_dir/data/sessions/$session_id"
            break
            ;;
        FAILED)
            printf '%s\n' "$status_response" >&2
            exit 1
            ;;
    esac

    sleep 2
done
