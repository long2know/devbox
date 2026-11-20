#!/usr/bin/env bash
set -euo pipefail

directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
options=(--project-directory "$directory" -f "$directory/compose.yaml")

while (($#)); do
    case "$1" in
        --gpu) options+=(-f "$directory/compose.gpu.yaml"); shift ;;
        --vpn) options+=(-f "$directory/compose.vpn.yaml"); shift ;;
        --ollama) options+=(--profile ollama); shift ;;
        --help)
            printf 'Usage: %s [--gpu] [--vpn] [--ollama] COMPOSE_COMMAND [ARGS...]\n' "$0"
            printf 'Example: %s --gpu --ollama up -d\n' "$0"
            exit 0
            ;;
        *) break ;;
    esac
done

if (($# == 0)); then
    printf 'A Compose command is required. Use --help for examples.\n' >&2
    exit 2
fi

exec docker compose "${options[@]}" "$@"
