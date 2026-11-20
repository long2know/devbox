#!/usr/bin/env bash
set -euo pipefail

if [[ "$TARGETARCH" != amd64 ]]; then
    echo "This image requires amd64: Google Chrome's Linux package is amd64-only." >&2
    exit 1
fi

# Keep runtime package installation working on this host too; signatures stay on.
printf 'APT::Sandbox::User "root";\n' > /etc/apt/apt.conf.d/99-devbox-sandbox-user

printf '\nInstalling development and desktop packages\n'
apt-get update
apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl dbus-x11 file gdb git gnome-keyring \
    gnupg jq libicu-dev libkrb5-3 libsecret-tools libssl-dev mesa-utils \
    nano openssh-client pkg-config procps python3 python3-venv ripgrep \
    socat sudo unzip x11-utils xdg-utils zlib1g
install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --batch --yes --dearmor -o /etc/apt/keyrings/google.gpg
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --batch --yes --dearmor -o /etc/apt/keyrings/microsoft.gpg
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    -o /etc/apt/keyrings/githubcli.gpg
chmod 0644 /etc/apt/keyrings/*.gpg
printf '%s\n' \
    'deb [arch=amd64 signed-by=/etc/apt/keyrings/google.gpg] https://dl.google.com/linux/chrome/deb/ stable main' \
    > /etc/apt/sources.list.d/google-chrome.list
printf '%s\n' \
    'deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/code stable main' \
    > /etc/apt/sources.list.d/vscode.list
. /etc/os-release
curl -fsSL "https://packages.microsoft.com/config/ubuntu/${VERSION_ID}/packages-microsoft-prod.deb" \
    -o /tmp/packages-microsoft-prod.deb
dpkg -i /tmp/packages-microsoft-prod.deb
rm -f /tmp/packages-microsoft-prod.deb
printf '%s\n' \
    'deb [arch=amd64 signed-by=/etc/apt/keyrings/githubcli.gpg] https://cli.github.com/packages stable main' \
    > /etc/apt/sources.list.d/github-cli.list
printf 'code code/add-microsoft-repo boolean false\n' | debconf-set-selections
apt-get update
apt-get install -y --no-install-recommends code gh google-chrome-stable powershell
if [[ "$(dpkg-query -W -f='${db:Status-Status}' chromium 2>/dev/null)" == installed ]]; then
    apt-get remove -y --no-auto-remove chromium
fi

printf '\nInstalling Node.js, .NET SDKs, Ollama CLI, Copilot CLI, and REA\n'
cp -a /build-node/bin/node /usr/local/bin/node
cp -a /build-node/lib/node_modules/. /usr/local/lib/node_modules/
install -d /usr/share/dotnet
cp -a /build-dotnet-lts/. /usr/share/dotnet/
cp -a /build-dotnet-current/. /usr/share/dotnet/
cp /build-ollama /usr/local/bin/ollama
chmod 0755 /usr/local/bin/ollama
ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
ln -s /usr/share/dotnet/dotnet /usr/local/bin/dotnet
npm install --global --prefix /usr/local --engine-strict --allow-scripts=frida \
    "@github/copilot@${COPILOT_CLI_VERSION}" "rea-agents@${REA_VERSION}"
npm cache clean --force

printf '\nInstalling verified GitHub Copilot desktop release\n'
python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path
import urllib.request

version = os.environ["COPILOT_APP_VERSION"]
release = "latest" if version == "latest" else f"tags/v{version.removeprefix('v')}"
request = urllib.request.Request(
    f"https://api.github.com/repos/github/app/releases/{release}",
    headers={"User-Agent": "dev-desktop-image-build"},
)
with urllib.request.urlopen(request, timeout=60) as response:
    metadata = json.load(response)
asset = next(a for a in metadata["assets"] if a["name"] == "GitHub-Copilot-linux-x64.deb")
digest = asset.get("digest", "")
if not digest.startswith("sha256:"):
    raise SystemExit("Copilot app release has no SHA-256 digest; refusing an unverified download.")
target = Path("/tmp/copilot-desktop.deb")
with urllib.request.urlopen(asset["browser_download_url"], timeout=120) as response:
    with target.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
with target.open("rb") as package:
    actual = hashlib.file_digest(package, "sha256").hexdigest()
if actual != digest.removeprefix("sha256:"):
    raise SystemExit("Copilot app package checksum mismatch.")
print(f"Verified GitHub Copilot desktop {metadata['tag_name']}")
PY
apt-get update
apt-get install -y --no-install-recommends /tmp/copilot-desktop.deb
COPILOT_PACKAGE="$(dpkg-deb -f /tmp/copilot-desktop.deb Package)" python3 - <<'PY'
import configparser
import json
import os
from pathlib import Path
import shlex
import subprocess

files = subprocess.check_output(["dpkg", "-L", os.environ["COPILOT_PACKAGE"]], text=True)
launchers = [Path(p) for p in files.splitlines() if "/applications/" in p and p.endswith(".desktop")]
if len(launchers) != 1:
    raise SystemExit(f"Expected one Copilot desktop launcher; found {len(launchers)}.")
desktop = configparser.ConfigParser(interpolation=None)
desktop.read(launchers[0])
command = [arg for arg in shlex.split(desktop["Desktop Entry"]["Exec"]) if not arg.startswith("%")]
if not command:
    raise SystemExit("Copilot desktop launcher has no command.")
directory = Path("/usr/local/share/dev-desktop")
directory.mkdir(parents=True, exist_ok=True)
(directory / "copilot-app-command.json").write_text(json.dumps(command) + "\n")
PY

ln -s /usr/local/bin/chrome /usr/local/bin/x-www-browser
ln -s /usr/local/bin/chrome /usr/local/bin/google-chrome
ln -s /usr/local/bin/code-desktop /usr/local/bin/code
# The base image moves Chromium's launcher; keep old shortcuts on real Chrome.
ln -sfn /usr/local/bin/chrome /usr/bin/chromium-browser
for launcher in \
    /usr/share/applications/google-chrome.desktop \
    /usr/share/applications/com.google.Chrome.desktop; do
    if [[ -f "$launcher" ]]; then
        sed -i \
            -e 's|^Exec=/usr/bin/google-chrome-stable|Exec=/usr/local/bin/chrome|' \
            -e 's|^Exec=/usr/bin/google-chrome|Exec=/usr/local/bin/chrome|' \
            "$launcher"
    fi
done
rm -f /tmp/copilot-desktop.deb
rm -rf /var/lib/apt/lists/*

printf '\nInstalled tool versions\n'
node --version
npm --version
dotnet --list-sdks
dotnet --list-runtimes
pwsh -NoLogo -NoProfile -Command '$PSVersionTable.PSVersion.ToString()'
gh --version
env -u COPILOT_CLI_VERSION copilot --version
rea --version
google-chrome-stable --version
