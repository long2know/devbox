# Gamebox

Gamebox is a separate **Ubuntu Cinnamon gaming desktop** streamed to your
browser by Selkies. It uses the same desktop and `/config` layout as Devbox,
but does not bundle the Devbox toolchain, Copilot, REA, or Ollama.

| Image | Steam | Google Chrome |
| --- | --- | --- |
| `gamebox-cinnamon:latest` (local build) | Launcher and 32-bit dependencies included | Installed at build time |
| `ghcr.io/long2know/gamebox:latest` (public target) | Same launcher and dependencies | Not included; set `GAMEBOX_INSTALL_VENDOR_APPS=1` to install on first startup of each new container |

Both use Ubuntu's `steam-installer`. Open **Steam** in Cinnamon and approve
the first-launch download from Valve, then sign in. The Steam client and any
downloaded games or runtimes aren't baked into either image. See
[third-party notices](THIRD_PARTY.md) and vendor terms before opting in.

## Run Gamebox

On an x86-64 Linux host with Docker Buildx and Compose 2.30+, work from
`gaming/`. Copy `.env.example` to `.env` for a new deployment, make it private
with `chmod 600 .env`, and set `GAMEBOX_PASSWORD` to a strong unique password
(for example, generate one with `openssl rand -hex 24`). Set `GAMEBOX_PUID`
and `GAMEBOX_PGID` to the host UID and GID that own the files. If moving a
home from Devbox, see [Copy an existing home](#copy-an-existing-home) first.

Steam's client and default library live in its persistent home, `/config`.
The separate `/games` bind is for extra libraries. It defaults to `games/`
under `GAMEBOX_DATA_DIR` (normally `data/games`). To use existing game
libraries, change the bind as shown below.

```bash
docker compose build
docker compose up -d --wait --wait-timeout 600
```

By default, open **`https://localhost:4201/gamebox/`** and sign in with
`GAMEBOX_USER` and `GAMEBOX_PASSWORD`. Opening `/gamebox` redirects to
`/gamebox/`. The first boot generates a self-signed certificate as
[Devbox does](../FIRST_RUN.md#open-the-desktop).
To build locally without Chrome, set `GAMEBOX_BUILD_TARGET=public`.

To use the published image instead, set
`GAMEBOX_IMAGE=ghcr.io/long2know/gamebox:latest` in `.env`, then run:

```bash
docker pull ghcr.io/long2know/gamebox:latest
docker compose up -d --no-build --wait --wait-timeout 600
```

Enable the optional Chrome install **before** creating the public container
and allow it outbound internet. Recreating downloads Chrome again; normal
restarts preserve the installed package. The Chrome profile and encrypted
keyring persist under `/config`. Chrome uses the same launcher as Devbox;
its browser sandbox is off by default for container compatibility. Do not
use it for untrusted browsing. Set `GAMEBOX_APP_SANDBOX=1` only on a host
where Chrome's sandbox can run in a container.

### NVIDIA and existing game libraries

Use the NVIDIA Container Toolkit on the host. Include the same overlay on
every Compose command that manages this instance:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d --no-build --wait --wait-timeout 600
docker compose -f compose.yaml -f compose.gpu.yaml exec --user abc gamebox glxinfo -B
```

Build or pull the image first. For NVIDIA's 32-bit graphics libraries, the
toolkit needs matching 32-bit driver userspace libraries on the host.
Check Selkies **Stats** for hardware video encoding separately from game
rendering. Selkies Gaming Mode captures the pointer for games. Steam prefers
native bubblewrap and uses Selkies' PRoot fallback if the host disallows
user namespaces. Game, Proton, and controller compatibility varies.

To expose an existing games folder, replace only the `/games` line under
`volumes:`:

```yaml
      - /data/Games:/games
```

In **Steam → Settings → Storage**, add the directory containing `steamapps`
(for example, `/games/Steam`). If you install Heroic separately, you can import
games from `/games/Epic Games`. Steam may still fetch updates or different
platform builds. Verify that your host folder exists and any network share is
mounted before starting; Compose's short bind syntax can create an empty
directory at a missing source path.

If you share a library between operating systems, don't let two clients update
it at once. Keep Proton's `steamapps/compatdata` on a local Linux filesystem;
back up existing prefixes before switching.

### Copy an existing home

Use separate host directories for Devbox and Gamebox. Quit Chrome and
Steam, then stop both desktops before copying. Back up the destination
first. Copy the contents, including hidden files, preserving ownership,
modes, and symlinks. Use the same UID/GID and desktop password on the
destination if you want its existing encrypted Login keyring to unlock.
Exclude `ssl/` to generate a separate TLS identity and omit the transient
`.XDG/` directory.

Cinnamon settings and compatible application profiles carry across. Config
for an application absent from the destination image is just dormant;
copying a home doesn't install packages. Keep both homes private, since a
copy can contain saved logins and credentials. Do not mount the same live
home into both containers.

### Use `/gaming/` behind nginx

Set `GAMEBOX_BASE_PATH=/gaming` (a trailing slash is also accepted). In your
existing HTTPS vhost, send `/gaming/` to Gamebox's private backend port and
leave `/develop/` pointing to Devbox. Redirect `/gaming` to `/gaming/`. Use
`proxy_pass` **without a URI or trailing slash** so `/gaming/` and its API
and WebSocket routes reach the backend unchanged. Apply the same Authentik
forward-auth check to the entire gaming location, including WebSocket
upgrades, and preserve the original path on sign-in.

For nginx on a second machine, set `GAMEBOX_BIND_ADDRESS` to the gaming
host's LAN IP and restrict port `4201` to nginx with Docker-aware firewall
rules. Use verified HTTPS between the two machines. Do not forward the
backend port from the internet or mount the Docker socket. Treat Gamebox
as a single-user desktop.

## Publish the public image

On `main`, run **Actions → Publish Gamebox image → Run workflow**. It builds
and smoke-tests the `public` target, then pushes the commit SHA tag and
`latest` to `ghcr.io/long2know/gamebox`. On the first publish, set the
Gamebox package visibility to **Public** in its GHCR package settings if
necessary for anonymous pulls. The Devbox package and workflow are unchanged.

Run the config tests from the repository root with
`python3 -m unittest discover -s gaming/tests -v`. For a built image,
`python3 gaming/tests/image_smoke.py IMAGE` checks the public startup
offline. Add `--install-chrome` to test the opt-in download or
`--variant full` to test a local full build.
