#!/usr/bin/env bash
set -euo pipefail

if (($# == 1)) && [[ "$1" == --help || "$1" == -h ]]; then
    printf 'Usage: %s\nCreates .env with your Linux UID/GID and a random desktop password. Does not overwrite an existing .env.\n' "$0"
    exit 0
fi
if (($#)); then
    printf 'Usage: %s\n' "$0" >&2
    exit 2
fi

directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
config="$directory/.env"
if [[ -e "$config" || -L "$config" ]]; then
    printf '%s already exists; left unchanged.\n' "$config"
    exit 0
fi

uid="$(id -u)"
gid="$(id -g)"
if [[ "$uid" == 0 ]]; then
    printf 'Run setup.sh as the non-root user who will own the desktop files.\n' >&2
    exit 1
fi
if ! command -v openssl >/dev/null; then
    printf 'OpenSSL is required to generate a desktop password. Install openssl or configure .env manually.\n' >&2
    exit 1
fi

umask 077
password="$(openssl rand -hex 24)"
temporary="$(mktemp "$directory/.env.tmp.XXXXXXXX")"
trap 'rm -f -- "$temporary"' EXIT
while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
        PUID=*) printf 'PUID=%s\n' "$uid" ;;
        PGID=*) printf 'PGID=%s\n' "$gid" ;;
        DESKTOP_PASSWORD=*) printf 'DESKTOP_PASSWORD=%s\n' "$password" ;;
        *) printf '%s\n' "$line" ;;
    esac
done < "$directory/.env.example" > "$temporary"
ln -T -- "$temporary" "$config"

printf 'Created %s. Open it locally for the desktop login; do not share it.\n' "$config"
