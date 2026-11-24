"""Verify a Gamebox image using an isolated desktop home and synthetic credentials."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))
from runtime_smoke import (
    check_cinnamon_appearance, check_keyring, docker, healthy, launch_desktop,
)


def check_packages(image, variant):
    label = docker("image", "inspect", "--format", '{{index .Config.Labels "io.gamebox.variant"}}', image)
    if label.strip() != variant:
        raise RuntimeError(f"Expected a {variant} Gamebox image, got {label.strip()!r}.")

    docker(
        "run", "--rm", "--pull", "never", "--network", "none",
        "--entrypoint", "/bin/bash", image, "-c", r"""
set -euo pipefail
for package in steam-installer steam-libs-i386:i386 mesa-vulkan-drivers:i386; do
    [[ "$(dpkg-query -W -f='${db:Status-Status}' "$package")" == installed ]]
done
test -x /usr/games/steam.distrib
test -x /usr/local/bin/steam
for tool in dotnet copilot rea ollama node cmake docker dockerd gcc g++ git make; do
    if command -v "$tool"; then
        echo "Gamebox contains unexpected tool: $tool" >&2
        exit 1
    fi
done
test "$START_DOCKER" = false
test ! -e /config/.steam
test ! -e /config/.local/share/Steam
if [[ "$1" == public ]]; then
    test ! -e /opt/google/chrome
    test ! -e /usr/local/share/applications/dev-chrome.desktop
else
    test -x /usr/bin/google-chrome-stable
    test -r /usr/local/share/applications/dev-chrome.desktop
fi
""", "check-packages", variant,
    )


def check_https(name):
    docker("exec", "--interactive", name, "python3", "-", input_text="""
import base64
from contextlib import closing
import http.client
import os
import ssl

ssl_context = ssl.create_default_context(cafile="/config/ssl/cert.pem")
ssl_context.check_hostname = False
with closing(http.client.HTTPSConnection("127.0.0.1", 3001, context=ssl_context, timeout=10)) as conn:
    conn.request("GET", "/gaming/")
    response = conn.getresponse()
    assert response.status == 401 and "Basic" in response.getheader("WWW-Authenticate", "")
    response.read()
    credential = f"{os.environ['CUSTOM_USER']}:{os.environ['PASSWORD']}"
    headers = {"Authorization": "Basic " + base64.b64encode(credential.encode()).decode()}
    conn.request("GET", "/gaming/manifest.json", headers=headers)
    response = conn.getresponse()
    assert response.status == 200 and b'/gaming/' in response.read()
""")


def check_steam_launcher(name):
    log = "/tmp/gamebox-steam-smoke.log"
    script = """
import os
import subprocess
import time

with subprocess.Popen(["steam"], env={**os.environ, "LC_ALL": "C"}) as launcher:
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and launcher.poll() is None:
            windows = subprocess.check_output(["xwininfo", "-root", "-tree"], text=True, timeout=3)
            if '"Steam installer"' in windows:
                print("Steam opens its first-run installer without a bundled client.")
                break
            time.sleep(0.25)
        else:
            raise RuntimeError(f"Steam did not show the installer; exit status: {launcher.poll()}")
    finally:
        if launcher.poll() is None:
            launcher.terminate()
"""
    try:
        launch_desktop(name, log, "python3", "-c", script, wait=True)
    finally:
        print(docker("exec", name, "cat", log).strip(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--variant", choices=("public", "full"), default="public")
    parser.add_argument("--install-chrome", action="store_true")
    args = parser.parse_args()
    check_packages(args.image, args.variant)

    name = f"gamebox-smoke-{uuid.uuid4().hex[:8]}"
    with tempfile.TemporaryDirectory(prefix="gamebox-smoke-") as directory:
        home, games = Path(directory) / "home", Path(directory) / "games"
        home.mkdir()
        (games / "steamapps").mkdir(parents=True)
        (games / "steamapps/library-fixture").write_text("shared library")
        docker(
            "run", "--detach", "--pull", "never", "--name", name,
            "--network", "bridge" if args.install_chrome else "none",
            "--shm-size", "512m", "--tmpfs", "/run:exec,mode=0755",
            "--tmpfs", "/tmp:exec,mode=1777",
            "--mount", f"type=bind,src={home},dst=/config",
            "--mount", f"type=bind,src={games},dst=/games",
            "--env", f"PUID={os.getuid()}", "--env", f"PGID={os.getgid()}",
            "--env", "CUSTOM_USER=smoke", "--env", "PASSWORD=gamebox-test-only!",
            "--env", "SUBFOLDER=/gaming",
            "--env", f"GAMEBOX_INSTALL_VENDOR_APPS={int(args.install_chrome)}",
            args.image,
        )
        try:
            healthy(name, timeout=600)
            check_https(name)
            if not args.install_chrome:
                check_cinnamon_appearance(name)
            check_keyring(name, create=True)
            check_steam_launcher(name)
            assert docker(
                "exec", "--user", "abc", name, "cat", "/games/steamapps/library-fixture"
            ) == "shared library"
            if args.install_chrome or args.variant == "full":
                docker("exec", "--user", "abc", name, "chrome", "--version")
                docker(
                    "exec", name, "grep", "-q", "^Exec=/usr/local/bin/chrome ",
                    "/usr/share/applications/google-chrome.desktop",
                )
                marker = home / ".local/state/devbox/google-browser-default-cinnamon-v1"
                if not marker.is_file():
                    raise RuntimeError("The desktop did not initialize the Chrome default.")
            print("Gamebox booted with Cinnamon, an encrypted keyring, and authenticated /gaming/.")
        finally:
            subprocess.run(["docker", "rm", "--force", name], check=True)


if __name__ == "__main__":
    main()
