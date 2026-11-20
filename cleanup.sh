#!/usr/bin/env bash
set -euo pipefail

if (($# == 1)) && [[ "$1" == --help || "$1" == -h ]]; then
    printf 'Usage: %s\nPrunes unused, untagged Debox images.\nSet DEVBOX_PRUNE_BUILD_CACHE=1 to also trim unused shared build cache toward 8GB.\n' "$0"
    exit 0
fi
if (($#)); then
    printf 'Usage: %s\n' "$0" >&2
    exit 2
fi

prune_cache="${DEVBOX_PRUNE_BUILD_CACHE:-0}"
case "$prune_cache" in
    0|1) ;;
    *) printf 'DEVBOX_PRUNE_BUILD_CACHE must be 0 or 1.\n' >&2; exit 2 ;;
esac

docker image prune --force --filter label=io.debox.managed=true
if [[ "$prune_cache" == 1 ]]; then
    builder="$(docker context show)"
    docker buildx prune --builder "$builder" --all --force --max-used-space 8GB
fi
