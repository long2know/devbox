"""Verify the publication target offline; optionally test vendor install/recreate."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import uuid

from runtime_smoke import (
    check_cinnamon_appearance, check_desktop_https, check_keyring, docker, healthy,
)


BASE_PATH = "/devbox/"


ABSENT_VENDOR_APPS = r"""
set -euo pipefail
for package in code google-chrome-stable; do
    status="$(dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null || :)"
    if [[ "$status" == installed ]]; then
        echo "$package is installed in the public target" >&2
        exit 1
    fi
done
for path in /opt/google/chrome /usr/share/code /usr/bin/github \
    /usr/local/share/dev-desktop/copilot-app-package \
    /usr/local/share/dev-desktop/copilot-app-command.json \
    /usr/local/share/applications/{dev-chrome,dev-code,dev-copilot}.desktop; do
    if [[ -e "$path" || -L "$path" ]]; then
        echo "Unexpected vendor application file: $path" >&2
        exit 1
    fi
done
"""

INSTALLED_VENDOR_APPS = r"""
set -euo pipefail
read -r copilot_package < /usr/local/share/dev-desktop/copilot-app-package
for package in code google-chrome-stable "$copilot_package"; do
    [[ "$(dpkg-query -W -f='${db:Status-Status}' "$package")" == installed ]]
done
for app in dev-chrome dev-code dev-copilot; do
    desktop-file-validate "/usr/local/share/applications/$app.desktop"
done
test -s /usr/local/share/dev-desktop/copilot-app-command.json
test -x /usr/bin/code
test -x /usr/bin/google-chrome-stable
"""


def verify_image(image):
    variant = docker("image", "inspect", "--format", '{{index .Config.Labels "io.devbox.variant"}}', image)
    if variant.strip() != "public":
        raise RuntimeError(f"Refusing to release a non-public-target image: {image}")

    # Fail the release if the distributed Copilot CLI license changes.
    script = ABSENT_VENDOR_APPS + r"""
cli=/usr/local/lib/node_modules/@github/copilot
platform="$cli/node_modules/@github/copilot-linux-x64"
if [[ ! -d "$platform" ]]; then
    platform=/usr/local/lib/node_modules/@github/copilot-linux-x64
fi
reviewed=b9680937e10425bf19862908856c16ed274e6b81a1368bd62be7a757eab21628
printf '%s  %s\n' "$reviewed" "$cli/LICENSE.md" "$reviewed" "$platform/LICENSE.md" | sha256sum -c -
"""
    docker("run", "--rm", "--pull", "never", "--network", "none", "--tmpfs", "/config",
           "--entrypoint", "/bin/bash", image, "-c", script)


def boot(name, image, home, *, vendor=False):
    docker(
        "run", "--detach", "--pull", "never", "--name", name,
        "--network", "bridge" if vendor else "none", "--shm-size", "512m",
        "--tmpfs", "/run:exec,mode=0755", "--tmpfs", "/tmp:exec,mode=1777",
        "--mount", f"type=bind,src={home},dst=/config",
        "--env", f"PUID={os.getuid()}", "--env", f"PGID={os.getgid()}",
        "--env", "CUSTOM_USER=smoke", "--env", "PASSWORD=devbox-public-fixture1!",
        "--env", f"SUBFOLDER={BASE_PATH}",
        "--env", f"DEVBOX_INSTALL_VENDOR_APPS={int(vendor)}",
        image,
    )


def remove(name):
    inspected = subprocess.run(
        ["docker", "container", "inspect", "--format", "{{.Id}}", name], capture_output=True
    )
    if inspected.returncode == 0:
        docker("rm", "--force", name)


def check_vendor_recreation(name, image, home):
    boot(name, image, home, vendor=True)
    healthy(name, timeout=600)
    check_desktop_https(name, BASE_PATH)
    docker("exec", name, "bash", "-c", INSTALLED_VENDOR_APPS)
    check_keyring(name, create=True)
    docker("exec", "--user", "abc", name, "sh", "-ec",
           "mkdir -p \"$HOME/.config/google-chrome/Default\"; "
           "printf '%s\\n' keep-me > \"$HOME/.config/google-chrome/Default/devbox-fixture\"")
    docker("restart", name)
    healthy(name)
    assert "vendor apps are already installed" in docker("logs", name)

    remove(name)
    boot(name, image, home, vendor=True)
    healthy(name, timeout=600)
    check_desktop_https(name, BASE_PATH)
    docker("exec", name, "bash", "-c", INSTALLED_VENDOR_APPS)
    check_keyring(name)
    profile_fixture = home / ".config/google-chrome/Default/devbox-fixture"
    assert profile_fixture.read_text() == "keep-me\n"
    print("Vendor apps remain installed on restart, reinstall on recreation, and preserve the encrypted keyring and profile files.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--vendor-apps", action="store_true")
    args = parser.parse_args()

    verify_image(args.image)
    name = f"devbox-public-smoke-{uuid.uuid4().hex[:8]}"
    with tempfile.TemporaryDirectory(prefix="devbox-public-smoke-") as directory:
        home = Path(directory)
        try:
            boot(name, args.image, home)
            healthy(name)
            docker("exec", name, "bash", "-c", ABSENT_VENDOR_APPS)
            check_desktop_https(name, BASE_PATH)
            check_cinnamon_appearance(name)
            assert not (home / ".local/state/devbox/google-browser-default-cinnamon-v1").exists()
            print("Public base boots offline without vendor apps and serves authenticated TLS.", flush=True)
            if args.vendor_apps:
                remove(name)
                check_vendor_recreation(name, args.image, home)
        finally:
            remove(name)


if __name__ == "__main__":
    main()
