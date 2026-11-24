# Devbox

Devbox is an **Ubuntu Cinnamon development desktop in Docker**, accessible in a
browser over HTTPS. It includes a persistent home, a full development toolchain,
and optional Ollama inference, NVIDIA acceleration, and VPN routing. The desktop
starts with the Lines wallpaper, dark mode, and a folder icon for Nemo. You can
change those defaults in Cinnamon and keep your choices across rebuilds.

For a separate gaming desktop with Steam and no Devbox toolchain, see
[Gamebox](gaming/README.md).

Both variants use LinuxServer's Ubuntu/Selkies base and the same Compose ports,
home mount, and keyring integration. Images don't contain models, credentials,
or personal deployment data.

| Variant | How to get it | Vendor desktop apps |
| --- | --- | --- |
| **Full local build** | `./build.sh` → `devbox-cinnamon:latest` | Chrome, Microsoft VS Code, and Copilot desktop are installed during the build. |
| **Public target** | `./build-public.sh` or the [GHCR package](#use-the-ghcr-image) | Those three apps aren't shipped. Set `DEVBOX_INSTALL_VENDOR_APPS=1` to install them from their vendors on the first startup of each new container. |

## Quick start

You need an **x86-64 Linux host**, Docker with Buildx and **Compose 2.30+**,
and OpenSSL for the setup script. Run the commands as a non-root user with Docker
access. Allow at least 20 GB of available Docker storage for the build and
additional space for models. Internet access is needed to fetch upstream images
and packages. No accounts or GPU are required to start the desktop.

```bash
git clone https://github.com/long2know/devbox.git
cd devbox
./setup.sh
./build.sh
./compose.sh up -d --wait --wait-timeout 300
```

1. `setup.sh` creates a private `.env` from `.env.example`, sets your Linux
   UID/GID, and generates a random desktop password. It leaves an existing
   `.env` alone.
2. After building and starting, open **`https://localhost:4200/`** on the
   Docker host. Use `DESKTOP_USER`
   (default `developer`) and `DESKTOP_PASSWORD` from your local `.env`.
3. Expect a self-signed certificate on first use: see
   [First run](FIRST_RUN.md#open-the-desktop) for how to verify it. Use a
   trusted HTTPS reverse proxy for shared access.

The default image is `devbox-cinnamon:latest`, the container is `devbox`, and
the Compose service is `devbox`. First builds download several gigabytes and
can take a few minutes. Follow [First run](FIRST_RUN.md) to sign in to GitHub,
configure Git and Copilot, and check REA.

## Use the GHCR image

Pull the public Linux amd64 image from `ghcr.io/long2know/devbox:latest`.
No GitHub login is needed. The **Publish public image** workflow publishes
both `latest` and a tag for the source commit.

Run `./setup.sh` from the checkout if you don't already have a `.env`. Set the
image reference in `.env`, then pull and start without building:

```dotenv
DEVBOX_IMAGE=ghcr.io/long2know/devbox:latest
```

```bash
docker pull ghcr.io/long2know/devbox:latest
./compose.sh up -d --no-build --wait --wait-timeout 600
```

To opt into **Chrome, VS Code, and Copilot desktop**, read the
[Chrome terms](https://www.google.com/chrome/terms/),
[VS Code license](https://code.visualstudio.com/license), and
[Copilot desktop terms and releases](https://github.com/github/app). Set
`DEVBOX_INSTALL_VENDOR_APPS=1` in `.env` before starting. The container uses
signed APT repositories and checks the Copilot desktop release digest. Allow
outbound internet and extra time and disk space on first startup. A normal
restart does not reinstall the apps; deleting/recreating the container does.
Profiles, projects, and the encrypted keyring live on the home mount, not in
the container. An image is not a backup of that home.

For an existing deployment, **keep the same home mount, UID/GID, and password**.
Change `DEVBOX_IMAGE` to the pulled tag. If you use your own Compose file rather
than this repo's, also pass `DEVBOX_INSTALL_VENDOR_APPS` into the `devbox`
service's `environment` (an `.env` entry by itself isn't passed into a
container):

```yaml
services:
  devbox:
    environment:
      DEVBOX_INSTALL_VENDOR_APPS: ${DEVBOX_INSTALL_VENDOR_APPS:-0}
```

Recreate only the Devbox service, with `up -d --no-deps --no-build --wait
--wait-timeout 600 devbox`, from the directory of your existing Compose project.
Stop any other container using that same home before starting this one. Use the
same desktop password so the existing keyring can unlock. To revert, use the
previous image reference and recreate the service again.

If GHCR is unavailable, you can build the same public target with
`./build-public.sh` and use `DEVBOX_IMAGE=devbox-public:local`.

## What's installed

| Area | Applications and tools |
| --- | --- |
| Desktop | Cinnamon, Muffin, Cinnamon Settings and screen locker, Nemo file manager, GNOME Terminal, Selkies browser streaming, GNOME Keyring |
| Browser | Official Google Chrome in the full or opted-in image; no browser is bundled in the public target |
| Editors and agents | GitHub Copilot CLI, REA (`rea-agents`) MCP server and workflow skill; Visual Studio Code and GitHub Copilot desktop in the full or opted-in image |
| Runtimes and SDKs | Node.js 26 and npm; .NET 10 and 11 SDKs, .NET and ASP.NET Core runtimes; PowerShell; Python 3 and `venv` |
| Version control and build tools | Git, GitHub CLI (`gh`), GCC/C++, Make, GDB, `pkg-config`, OpenSSH client |
| Media and diagnostics | FFmpeg/ffprobe, MKVToolNix CLI and GUI, OpenGL utilities (`glxinfo`) |
| Shell utilities | curl, jq, ripgrep, nano, file, GnuPG, socat, sudo, unzip, X11/XDG utilities |
| Local-model client | Ollama CLI and a loopback-only relay. The **server** is an optional Compose service. |

Ollama models, the NVIDIA driver/toolkit, NordVPN's native client, Squad CLI,
and third-party REA providers are not installed in the desktop image. Start
the Ollama or Gluetun sidecars only if you want them. Account access for Chrome,
GitHub, Copilot, or VPN is separate from the desktop password.

## Configuration and persistence

`./setup.sh` is optional: you can copy `.env.example` to `.env` if it does not
exist, set permissions with `chmod 600 .env`, and edit the variables below.
Use a long, unique `DESKTOP_PASSWORD`. If your password includes `$`, use a
single-quoted value so Compose won't interpolate it. Do not source `.env`
as a shell script. Run `./compose.sh config --quiet` to check the configuration
without printing credentials.

| `.env` variable | Default | What it controls |
| --- | --- | --- |
| `DESKTOP_USER`, `DESKTOP_PASSWORD` | `developer`, generated by setup | Web login. The password also unlocks the encrypted Login keyring and is used by `sudo` inside the container. |
| `PUID`, `PGID` | Your `id -u` / `id -g` with setup; otherwise `1000` | Ownership of persisted files. The Linux user inside is `abc`, regardless of the web username. |
| `DEVBOX_DATA_DIR` | `./data` | Path on the Docker host; relative paths resolve from this checkout. For data outside the checkout, use an absolute path. |
| `DESKTOP_BIND_ADDRESS`, `DESKTOP_PORT` | `127.0.0.1`, `4200` | The single published port. Keep loopback unless you intend to expose it. |
| `DESKTOP_BACKEND_PORT` | `3001` | Direct HTTPS. Use `3000` only behind an HTTPS-terminating reverse proxy or for localhost HTTP access. |
| `BASE_PATH`, `DESKTOP_TITLE`, `TZ` | `/`, `devbox`, `America/Los_Angeles` | URL prefix, browser tab title, and timezone. Prefixes must begin and end with `/`. |
| `OLLAMA_SERVER_HOST`, `OLLAMA_SERVER_PORT` | `desktop-ollama`, `11434` | Model API reachable from Devbox. |
| `DEVBOX_INSTALL_VENDOR_APPS` | `0` | Set to `1` to install the vendor desktop apps in a pulled/public container. The full local build already includes them. |
| `DEVBOX_IMAGE` | `devbox-cinnamon:latest` | Local image tag or an explicitly pulled compatible image. Other build arguments and version pins are shown in `.env.example`. |

| Host directory | Persists |
| --- | --- |
| `data/home/` | Entire desktop `~` (`/config`): projects, downloads, Chrome and VS Code profiles, login keyring, Git/Copilot settings, user npm tools, HTTPS certificate and key |
| `data/ollama/` | Optional Ollama server's models and settings |
| `data/gluetun/` | Optional VPN server metadata |

Back up **both `.env` and the data directory**. Keep the same UID/GID and
password when restoring them; changing the password does not re-encrypt an
existing keyring. Use a filesystem that supports Unix ownership and
permissions, or protect the directory with host ACLs if it does not.
`.env` and `data/` are excluded from Git and the build context.

Use the mounted home or another persistent bind mount for work you want to keep.
Install extra system packages in the Dockerfile; changes elsewhere in a running
container are lost when that container is replaced. For network shares, mount
the share on the host first, then add a Compose bind mount. Avoid giving the
desktop privileges to mount filesystems or access the Docker socket.

## Optional: Ollama and NVIDIA

Start a CPU-only model server alongside the desktop:

```bash
./compose.sh --ollama up -d --wait --wait-timeout 300
./compose.sh --ollama exec desktop-ollama ollama pull qwen3:4b
./compose.sh --ollama exec desktop-ollama ollama list
```

The model is an example, not a prerequisite. Choose a size that fits your
memory and review its license before using it. Models are not fetched at build or
startup. The server stays on the private Compose network with **no host API
port published**. The Ollama CLI inside Devbox is configured to talk to it.
Copilot CLI can discover models through the loopback relay; open `/model`
and look under **Local and self-hosted**. Model availability there is separate
from GitHub-hosted Copilot access.

For GPU acceleration, install compatible NVIDIA drivers and the [NVIDIA
Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
on the host. The desktop overlay expects `/dev/dri` and `/dev/nvidia-modeset`;
set `GPU_RENDER_NODE` if the intended render node is not `/dev/dri/renderD128`.
Add `--gpu` for accelerated desktop rendering and, with `--ollama`, inference:

```bash
./compose.sh --gpu --ollama up -d --wait --wait-timeout 300
./compose.sh --gpu --ollama exec --user abc devbox glxinfo -B
./compose.sh --gpu --ollama exec desktop-ollama ollama ps
```

For an **existing Ollama server**, omit `--ollama` and set
`OLLAMA_SERVER_HOST` / `OLLAMA_SERVER_PORT` to an address the desktop can reach.
The host's `127.0.0.1` is not reachable as localhost from the container. Use a
reachable private address or a shared Docker network. Do not share the same
model directory between two running Ollama servers. See [Ollama's Docker
guide](https://docs.ollama.com/docker) for server-specific options.

## Optional: VPN or remote HTTPS

- **VPN:** Set `NORDVPN_USERNAME` and `NORDVPN_PASSWORD` to NordVPN's manual
  setup **service credentials** and set `NORDVPN_COUNTRIES`. A working
  `/dev/net/tun` is required. Run `./compose.sh --vpn up -d --wait`, adding
  `--gpu` or `--ollama` as needed. Gluetun provides the network namespace and
  kill switch for the whole desktop; it does not route the separate Ollama
  server through the VPN. Keep `VPN_ALLOWED_SUBNETS` limited to the required
  private destinations. Use the same flags on `up`, `stop`, and `down`;
  use `down` in the old mode before changing between VPN and non-VPN modes.
  Verify outbound IP and DNS with your own VPN configuration before relying on it.
- **LAN or VPN clients:** Bind `DESKTOP_BIND_ADDRESS` to a reachable, trusted
  host interface and use `https://<host>:4200/`. Plain HTTP to a LAN IP is not
  a secure browser context for desktop streaming. For private access with
  the loopback binding, an SSH tunnel is an alternative.
- **nginx:** For a proxy on the same host, set `DESKTOP_BACKEND_PORT=3000` and
  `BASE_PATH=/devbox/`, keep the loopback binding, and include
  [`nginx/location.conf`](nginx/location.conf) inside an HTTPS server block.
  Preserve the prefix and WebSocket upgrade. Containerized nginx on the
  Compose network can use `devbox:3000` (`vpn:3000` in VPN mode).
  An nginx server on a different machine cannot use the Docker host's loopback;
  use a restricted, reachable backend and validate TLS if proxying to
  the HTTPS listener. The web client always uses the proxy's HTTPS URL.
  Keep the trailing slash in `BASE_PATH`; the embedded nginx redirects
  requests for the prefix without it.

This is a **single-user development desktop**, not a sandbox for hostile sites
or untrusted code. Chrome and Electron launchers default to `--no-sandbox`
for compatibility. Do not expose the desktop directly to the internet; use a
private network or an HTTPS proxy with access controls and MFA. Do not publish
the unauthenticated Ollama API. Do not mount the Docker socket.

## Stop, update, and troubleshoot

```bash
./compose.sh ps
./compose.sh logs --tail=100 devbox
./compose.sh stop
./compose.sh up -d --wait --wait-timeout 300
```

Pass the same `--gpu`, `--ollama`, and `--vpn` flags you use at startup.
`stop` preserves containers; `down` removes only this project's containers
and network and leaves bind-mounted files alone. Each project is one shared
desktop session. For an independent second instance, use distinct project and
container names, data directory, port, subnet, and credentials.

To rebuild and apply updates using versions from `.env`:

```bash
./compose.sh build --pull
./compose.sh up -d --wait --wait-timeout 300
```

Save work before applying an image/Compose change: Compose may recreate the
desktop. `./build.sh` is also available for building without `.env`; it accepts
Docker build flags and uses `DEVBOX_IMAGE` from the shell environment. Upstream
packages and images can change; optional build args can pin versions. There is
no requirement to install proprietary packages directly on your host.
To update the GHCR variant, pull again and recreate with `--no-build`.
If opted-in setup fails, `./compose.sh logs devbox` shows the error; fix it and
restart, or change the flag to `0` and recreate to use only the public base.

`./cleanup.sh` prunes only unused, untagged images labeled
`io.devbox.standalone.managed=true`.
`./build.sh` runs it after a successful final-image build. Shared BuildKit
cache pruning is **off by default**. Set `DEVBOX_PRUNE_BUILD_CACHE=1` when
invoking `./cleanup.sh` or `./build.sh` to trim unused cache toward 8 GB. That
can evict cached layers for other projects on the current Docker context.
Neither script prunes containers or volumes.

### Checks

```bash
python3 -m unittest discover -s tests -v
python3 tests/mkvtoolnix_runtime.py
# After starting the Ollama profile, with the default Compose project name:
python3 tests/runtime_smoke.py
# For a locally built public target (add --vendor-apps to test real installs and recreation):
python3 tests/public_image_smoke.py devbox-public:local
```

The runtime checks use disposable desktop state and synthetic credentials. Use
`--gpu` on `runtime_smoke.py` to also test NVIDIA rendering, Chrome WebGL, and
NVENC encoding. The media smoke test encodes 10-bit HEVC and checks a real
Matroska mux, metadata edit, and extraction.

## License

The Devbox build recipe, scripts, and documentation are [MIT licensed](LICENSE).
See [third-party notices and source locations](THIRD_PARTY.md) for software in
the image. Installed applications and any downloaded models keep their own
licenses or terms.
