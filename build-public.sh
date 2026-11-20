#!/usr/bin/env bash
set -euo pipefail

directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec docker build --pull --platform linux/amd64 \
    --tag "${DEVBOX_PUBLIC_IMAGE:-devbox-public:local}" "$@" --target public "$directory"
