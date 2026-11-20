# First run

## Open the desktop

After [starting Devbox](README.md#quick-start), open `https://localhost:4200/`.
Use the desktop username and password from your local `.env`. Those credentials
are separate from all GitHub, Google, and VPN logins. Do not share `.env` or paste
it into issue reports.

The first launch uses a self-signed TLS certificate. The browser does not trust
it automatically. Confirm the certificate shown by the browser matches the one
generated for your deployment before accepting it:

```bash
openssl x509 -in data/home/ssl/cert.pem -noout -fingerprint -sha256
```

If you set a different `DEVBOX_DATA_DIR`, use that path instead of `data`.
Do not disable certificate validation globally. Use a trusted certificate
and the [reverse-proxy setup](README.md#optional-vpn-or-remote-https) for a shared
deployment.

## Sign in to GitHub and configure Git

Run these in **GNOME Terminal inside Devbox**, as the normal `abc` user and
without `sudo`:

```bash
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git --hostname github.com
gh api --hostname github.com user --jq .login
```

Follow the browser/device-code prompts. `setup-git` lets Git use the GitHub CLI
login when pushing to HTTPS remotes. The last command prints the signed-in login
without showing a token. Set the author name and email for your commits:

```bash
git config --global user.name "Your Name"
git config --global user.email "YOUR_VERIFIED_OR_NOREPLY_EMAIL"
```

Use a verified email or the no-reply address in **GitHub > Settings > Emails**.
The Git author name is not your GitHub login. These settings and saved sign-ins
live in the mounted home and survive container recreation.

## Start developing

- **Chrome:** Open **Google Chrome** in the menu. Sign in to Google only if you
  want account features. Your profile lives under `~/.config/google-chrome`.
  The Docker-compatible `--no-sandbox` launcher shows a real security warning;
  don't use it for untrusted browsing.
- **Copilot CLI:** Run `copilot login --device-code`. In Copilot desktop, use
  **Sign in to GitHub**; in VS Code, use the app's account menu. These apps may
  ask for separate authorization. Copilot needs the applicable entitlement.
- **Desktop apps:** Use **VS Code (Development Desktop)** and **GitHub Copilot
  (Development Desktop)** from the menu. These launchers configure the
  container flags and use the encrypted GNOME Login keyring. The keyring
  unlocks with the desktop password on startup; don't reset it if changing
  passwords. Logins can still expire or be revoked by their providers.
- **REA:** Startup registers the MCP server and skill for Copilot CLI and VS
  Code. Check Copilot CLI with `copilot mcp get rea`; use `rea mcp doctor --json`
  for a standalone adapter check. Restart an already-open client after changing
  MCP setup. Native decompilers and external providers are not bundled.
- **Tools and projects:** Keep projects under `~/projects` or a persistent
  bind mount. `npm install -g` without `sudo` installs under `~/.local` and
  survives rebuilds. Project-local npm installs stay with the project. See the
  [app inventory](README.md#whats-installed) and
  [Ollama setup](README.md#optional-ollama-and-nvidia).

Prefer interactive account logins. `.env.example` also documents optional
CLI token settings for users who need them. Tokens passed through Compose are
visible to Docker administrators; do not commit them, include them in logs,
or copy them into the image.
