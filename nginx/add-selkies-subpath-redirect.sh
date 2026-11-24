#!/bin/sh
set -eu

template="$1"

# Selkies expands SUBFOLDER with a trailing slash. Match only the slashless
# form, so an already canonical URL (including a root mount) cannot loop.
sed -E -i '/^[[:blank:]]*location[[:blank:]]+SUBFOLDER[[:blank:]]*\{/i\
  location ~ "^SUBFOLDER?(?<!/)$" {\
    absolute_redirect off;\
    return 308 SUBFOLDER$is_args$args;\
  }' "$template"

if [ "$(grep -Fc 'return 308 SUBFOLDER$is_args$args;' "$template")" -ne 2 ]; then
    echo "Expected slash redirects on both Selkies nginx listeners in $template." >&2
    exit 1
fi
