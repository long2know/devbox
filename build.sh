#!/usr/bin/env bash
set -euo pipefail

directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cleanup=1
for argument in "$@"; do
    case "$argument" in
        --help|-h|--check|--call|--call=*|--target|--target=*) cleanup=0 ;;
    esac
done

docker build --pull \
    --tag "${DEVBOX_IMAGE:-devbox-cinnamon:latest}" "$@" "$directory"

if ((cleanup)); then
    "$directory/cleanup.sh"
fi
