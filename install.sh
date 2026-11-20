#!/usr/bin/env bash
set -euo pipefail

if [[ "$TARGETARCH" != amd64 ]]; then
    echo "Devbox targets linux/amd64." >&2
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
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    -o /etc/apt/keyrings/githubcli.gpg
chmod 0644 /etc/apt/keyrings/githubcli.gpg
. /etc/os-release
curl -fsSL "https://packages.microsoft.com/config/ubuntu/${VERSION_ID}/packages-microsoft-prod.deb" \
    -o /tmp/packages-microsoft-prod.deb
dpkg -i /tmp/packages-microsoft-prod.deb
rm -f /tmp/packages-microsoft-prod.deb
printf '%s\n' \
    'deb [arch=amd64 signed-by=/etc/apt/keyrings/githubcli.gpg] https://cli.github.com/packages stable main' \
    > /etc/apt/sources.list.d/github-cli.list
apt-get update
apt-get install -y --no-install-recommends gh powershell

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
