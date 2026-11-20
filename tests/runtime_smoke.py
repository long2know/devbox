"""Boot-test a built devbox without using or modifying real account credentials."""

import argparse
import base64
import configparser
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid


def docker(*arguments, timeout=600, input_text=None):
    result = subprocess.run(
        ["docker", *arguments],
        capture_output=True,
        text=True,
        input=input_text,
        timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(
            f"Docker {arguments[0]} failed:\n"
            f"{result.stdout[-8000:]}\n{result.stderr[-8000:]}"
        )
    return result.stdout + result.stderr if arguments[0] == "logs" else result.stdout


def healthy(name):
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        state = json.loads(docker("inspect", name))[0]["State"]
        if state.get("Health", {}).get("Status") == "healthy":
            return
        if state["Status"] in ("exited", "dead"):
            break
        time.sleep(2)
    raise RuntimeError(f"Desktop failed to become healthy:\n{docker('logs', name)[-10000:]}")


def check_persistent_state(home):
    config = json.loads((home / ".copilot/mcp-config.json").read_text())
    if not {"rea", "preserved-smoke-entry"} <= config["mcpServers"].keys():
        raise RuntimeError("Startup overwrote existing MCP configuration.")
    for directory in (".config/gh", ".copilot", ".local/share/keyrings"):
        fixture = home / directory / "devbox-persistence-fixture"
        if fixture.read_text() != "not-a-credential":
            raise RuntimeError(f"Persistent application state was lost: {fixture}")


def check_client_settings(name):
    pager = docker("exec", "--user", "abc", name, "gh", "config", "get", "pager").strip()
    quota = docker(
        "exec", "--user", "abc", name, "copilot", "config", "footer.showQuota"
    ).strip()
    if pager != "cat" or quota != "false":
        raise RuntimeError("GitHub/Copilot client settings did not persist.")


def check_keyring(name, create=False):
    script = """
import os
from pathlib import Path
import subprocess

pid = subprocess.check_output(
    ['pgrep', '-u', str(os.getuid()), '-x', 'cinnamon'], text=True
).splitlines()[0]
assert not any(
    value.startswith(b'PASSWORD=') and value != b'PASSWORD='
    for value in (Path('/proc') / pid / 'environ').read_bytes().split(b'\\0')
), 'Desktop applications inherited the web-login password'
address = next(
    value.split(b'=', 1)[1].decode()
    for value in (Path('/proc') / pid / 'environ').read_bytes().split(b'\\0')
    if value.startswith(b'DBUS_SESSION_BUS_ADDRESS=')
)
environment = {**os.environ, 'DBUS_SESSION_BUS_ADDRESS': address}

def run(*arguments, input_text=None):
    return subprocess.check_output(
        list(arguments), env=environment, input=input_text, text=True, timeout=15
    ).strip()

alias = run(
    'gdbus', 'call', '--session', '--dest', 'org.freedesktop.secrets',
    '--object-path', '/org/freedesktop/secrets', '--method',
    'org.freedesktop.Secret.Service.ReadAlias', 'default'
)
assert alias == "(objectpath '/org/freedesktop/secrets/collection/login',)", alias
locked = run(
    'gdbus', 'call', '--session', '--dest', 'org.freedesktop.secrets',
    '--object-path', '/org/freedesktop/secrets/collection/login', '--method',
    'org.freedesktop.DBus.Properties.Get', 'org.freedesktop.Secret.Collection', 'Locked'
)
assert locked == '(<false>,)', locked
if CREATE:
    run(
        'secret-tool', 'store', '--label=Devbox persistence test',
        'service', 'devbox-runtime-smoke', 'account', 'fixture',
        input_text='synthetic-keyring-test-value'
    )
value = run(
    'secret-tool', 'lookup', 'service', 'devbox-runtime-smoke', 'account', 'fixture'
)
assert value == 'synthetic-keyring-test-value'
data = (Path.home() / '.local/share/keyrings/login.keyring').read_bytes()
assert b'synthetic-keyring-test-value' not in data, 'Keyring item is stored as plaintext'
"""
    docker(
        "exec", "--interactive", "--user", "abc", name, "python3", "-",
        input_text=script.replace("CREATE", repr(create)),
        timeout=60,
    )


def launch_desktop(name, log, *arguments, wait=False):
    script = """
import os
from pathlib import Path
import subprocess
import sys

pid = subprocess.check_output(
    ['pgrep', '-u', str(os.getuid()), '-x', 'cinnamon'], text=True
).splitlines()[0]
environment = dict(
    entry.decode().split('=', 1)
    for entry in (Path('/proc') / pid / 'environ').read_bytes().split(b'\\0')
    if b'=' in entry
)
with open(sys.argv[1], 'w') as output:
    process = subprocess.Popen(
        sys.argv[3:], env=environment, stdout=output,
        stderr=subprocess.STDOUT, start_new_session=True,
    )
    if sys.argv[2] == '1':
        result = process.wait(timeout=30)
        if result:
            raise subprocess.CalledProcessError(result, process.args)
"""
    docker(
        "exec", "--user", "abc", name, "python3", "-c", script,
        log, "1" if wait else "0", *arguments,
    )


def check_cinnamon_panel(name):
    script = """
import ast
import subprocess
import time

def setting(key):
    return ast.literal_eval(subprocess.check_output(
        ['gsettings', 'get', 'org.cinnamon', key], text=True
    ).strip())

applets = []
deadline = time.monotonic() + 20
while time.monotonic() < deadline:
    applets = setting('enabled-applets')
    if setting('panels-enabled') and any('window-list@cinnamon.org' in item for item in applets):
        break
    time.sleep(1)
else:
    raise RuntimeError(f'Cinnamon running-window taskbar is missing: {applets}')
print('PASS: Cinnamon has a running-window taskbar')
"""
    log = "/tmp/cinnamon-panel-smoke.log"
    launch_desktop(name, log, "python3", "-c", script, wait=True)
    print(docker("exec", name, "cat", log).strip(), flush=True)


def check_cinnamon_appearance(name):
    script = """
import configparser
from pathlib import Path
import time
from xml.etree import ElementTree

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, GLib, Gtk

wallpaper = Path('/usr/share/desktop-base/lines-theme/wallpaper/gnome-background.xml')
background = Gio.Settings.new('org.cinnamon.desktop.background')
assert background.get_default_value('picture-uri').unpack() == wallpaper.as_uri()
if background.get_user_value('picture-uri') is None:
    assert background.get_string('picture-uri') == wallpaper.as_uri()
images = ElementTree.parse(wallpaper).findall('.//file/size')
assert images and all(Path(image.text).is_file() for image in images)

launcher = configparser.ConfigParser(interpolation=None)
launcher.read('/usr/share/applications/nemo.desktop')
icon = launcher['Desktop Entry']['Icon']
assert icon == 'folder', f'Files launcher uses {icon!r}, not a folder icon'
assert Gtk.IconTheme.get_default().lookup_icon(icon, 32, 0) is not None

interface = Gio.Settings.new('org.cinnamon.desktop.interface')
assert interface.get_default_value('gtk-theme').unpack() == 'Adwaita-dark'
for schema in ('org.x.apps.portal', 'org.gnome.desktop.interface'):
    assert Gio.Settings.new(schema).get_default_value('color-scheme').unpack() == 'prefer-dark'
if interface.get_user_value('gtk-theme') is None:
    deadline = time.monotonic() + 8
    while Gtk.Settings.get_default().props.gtk_theme_name != 'Adwaita-dark':
        if time.monotonic() >= deadline:
            raise RuntimeError('GTK did not inherit the dark theme from Cinnamon')
        while Gtk.events_pending():
            Gtk.main_iteration()
        time.sleep(0.1)
if Gio.Settings.new('org.x.apps.portal').get_user_value('color-scheme') is None:
    portal = Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None,
        'org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop',
        'org.freedesktop.portal.Settings', None,
    )
    color_scheme = portal.call_sync(
        'ReadOne', GLib.Variant('(ss)', ('org.freedesktop.appearance', 'color-scheme')),
        Gio.DBusCallFlags.NONE, 8000, None,
    )
    assert color_scheme.unpack() == (1,), color_scheme
print('PASS: Cinnamon defaults to Lines, a folder icon for Files, and dark mode')
"""
    log = "/tmp/cinnamon-appearance-smoke.log"
    try:
        launch_desktop(name, log, "python3", "-c", script, wait=True)
    finally:
        print(docker("exec", name, "cat", log).strip(), flush=True)


def check_gui_secret_backends(name):
    script = """
import os
from pathlib import Path
import shlex

applications = set()
for process in Path('/proc').iterdir():
    if not process.name.isdigit():
        continue
    try:
        if process.stat().st_uid != os.getuid():
            continue
        arguments = [
            os.fsdecode(value)
            for value in process.joinpath('cmdline').read_bytes().split(b'\\0')
            if value
        ]
        # Chromium can collapse its command line into argv[0].
        if len(arguments) == 1:
            arguments = shlex.split(arguments[0])
        if any(value.startswith('--type=') for value in arguments):
            continue
        if '--password-store=gnome-libsecret' in arguments:
            applications.add(process.joinpath('exe').resolve().name)
    except (FileNotFoundError, ProcessLookupError):
        continue
assert len(applications) >= 3, applications
print('PASS: Chrome, VS Code, and Copilot retain the GNOME encrypted-secret backend')
"""
    print(
        docker("exec", "--interactive", "--user", "abc", name, "python3", "-", input_text=script),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="devbox-cinnamon:latest")
    parser.add_argument("--network", default="debox_desktop")
    parser.add_argument("--ollama-host", default="desktop-ollama")
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--keep-on-failure", action="store_true")
    parser.add_argument("--data-parent", default=tempfile.gettempdir())
    parser.add_argument("--reuse-smoke-home", type=Path)
    parser.add_argument("--browser-check", type=Path)
    arguments = parser.parse_args()

    parent = Path(arguments.data_parent)
    parent.mkdir(parents=True, exist_ok=True)
    if arguments.reuse_smoke_home:
        home = arguments.reuse_smoke_home.resolve(strict=True)
        if home.parent != parent.resolve() or not home.name.startswith(".smoke-home-"):
            parser.error("--reuse-smoke-home must name a temporary smoke home under --data-parent")
        check_persistent_state(home)
    else:
        home = Path(tempfile.mkdtemp(prefix=".smoke-home-", dir=parent))
    name = f"devbox-smoke-{uuid.uuid4().hex[:8]}"
    password = "smoke-test-only: spaces $sign"
    command = [
        "run", "--detach", "--name", name,
        "--label", "devbox.smoke-test=true",
        "--network", arguments.network,
        "--tmpfs", "/run:exec,mode=0755",
        "--tmpfs", "/tmp:exec,mode=1777",
        "--shm-size", "1g",
        "--publish", "127.0.0.1::3000",
        "--publish", "127.0.0.1::3001",
        "--mount", f"type=bind,src={home},dst=/config",
    ]
    environment = {
        "PUID": str(os.getuid()),
        "PGID": str(os.getgid()),
        "CUSTOM_USER": "smoke",
        "PASSWORD": password,
        "SUBFOLDER": "/devbox/",
        "HOME": "/config",
        "XDG_CONFIG_HOME": "/config/.config",
        "XDG_DATA_HOME": "/config/.local/share",
        "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
        "GH_CONFIG_DIR": "/config/.config/gh",
        "COPILOT_HOME": "/config/.copilot",
        "OLLAMA_SERVER_HOST": arguments.ollama_host,
        "OLLAMA_SERVER_PORT": "11434",
    }
    if arguments.gpu:
        command.extend([
            "--runtime", "nvidia", "--gpus", "all",
            "--device", "/dev/dri:/dev/dri",
            "--device", "/dev/nvidia-modeset:/dev/nvidia-modeset",
        ])
        environment.update({
            "NVIDIA_VISIBLE_DEVICES": "all",
            "NVIDIA_DRIVER_CAPABILITIES": "all",
            "DRINODE": "/dev/dri/renderD128",
            "DRI_NODE": "/dev/dri/renderD128",
            "DISABLE_DRI3": "false",
            "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
        })
    for key, value in environment.items():
        command.extend(["--env", f"{key}={value}"])
    command.append(arguments.image)

    succeeded = False
    try:
        print(f"Starting {name} with temporary home {home}", flush=True)
        started = time.monotonic()
        docker(*command, timeout=900)
        print(f"Container created in {time.monotonic() - started:.1f}s", flush=True)
        healthy(name)
        print(f"Desktop healthy in {time.monotonic() - started:.1f}s total", flush=True)
        if arguments.reuse_smoke_home:
            check_persistent_state(home)
            check_client_settings(name)
            print("PASS: application state survives replacing the image/container", flush=True)
        check_keyring(name, create=True)
        print("PASS: encrypted default keyring is unlocked without a GUI password prompt", flush=True)
        check_cinnamon_panel(name)
        check_cinnamon_appearance(name)
        for scheme in ("http", "https"):
            handler = docker(
                "exec", "--user", "abc", name,
                "xdg-mime", "query", "default", f"x-scheme-handler/{scheme}",
            ).strip()
            if handler not in (
                "dev-chrome.desktop", "google-chrome.desktop", "com.google.Chrome.desktop"
            ):
                raise RuntimeError(f"The {scheme} default browser is not Google Chrome: {handler}")
            directory = (
                "/usr/local/share/applications"
                if handler == "dev-chrome.desktop"
                else "/usr/share/applications"
            )
            launcher = configparser.ConfigParser(interpolation=None)
            launcher.read_string(docker("exec", name, "cat", f"{directory}/{handler}"))
            if shlex.split(launcher["Desktop Entry"]["Exec"])[0] != "/usr/local/bin/chrome":
                raise RuntimeError(f"The {scheme} handler bypasses the Chrome container launcher.")
        print("PASS: HTTP and HTTPS default handlers use Google Chrome", flush=True)
        legacy = configparser.ConfigParser(interpolation=None)
        legacy.read_string(
            docker("exec", name, "cat", "/usr/share/applications/chromium.desktop")
        )
        if shlex.split(legacy["Desktop Entry"]["Exec"])[0] != "/usr/local/bin/chrome":
            raise RuntimeError("The legacy browser launcher does not open Google Chrome.")
        docker(
            "exec", name, "desktop-file-validate",
            "/usr/share/applications/chromium.desktop",
        )
        print("PASS: saved browser shortcuts resolve to Google Chrome", flush=True)
        port = docker("port", name, "3000/tcp").strip().rsplit(":", 1)[1]
        url = f"http://127.0.0.1:{port}/devbox/"
        try:
            urllib.request.urlopen(url, timeout=10)
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise
        else:
            raise RuntimeError("The desktop endpoint is accessible without authentication.")
        authorization = base64.b64encode(f"smoke:{password}".encode()).decode()
        request = urllib.request.Request(
            url, headers={"Authorization": f"Basic {authorization}"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            if b"<html" not in response.read().lower():
                raise RuntimeError("Authenticated prefix URL did not return the desktop HTML.")
        print("PASS: authenticated browser desktop at /devbox/", flush=True)
        https_port = docker("port", name, "3001/tcp").strip().rsplit(":", 1)[1]
        certificate = docker("exec", name, "cat", "/config/ssl/cert.pem")
        context = ssl.create_default_context(cadata=certificate)
        # Trust this fixture's certificate, whose generated name is not its random port/IP.
        context.check_hostname = False
        https_url = f"https://127.0.0.1:{https_port}/devbox/"
        try:
            urllib.request.urlopen(https_url, context=context, timeout=10)
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise
        else:
            raise RuntimeError("The HTTPS desktop endpoint bypasses authentication.")
        secure_request = urllib.request.Request(
            https_url, headers={"Authorization": f"Basic {authorization}"}
        )
        with urllib.request.urlopen(secure_request, context=context, timeout=10) as response:
            if response.status != 200 or b"<html" not in response.read().lower():
                raise RuntimeError("Authenticated HTTPS prefix did not return desktop HTML.")
        print("PASS: certificate-pinned HTTPS prefix requires authentication", flush=True)

        output = docker(
            "exec", "--user", "abc", name, "desktop-smoke-test",
            *(["--gpu"] if arguments.gpu else []),
            timeout=180,
        )
        print(output[-8000:], flush=True)
        print("PASS: development tools, REA MCP, and Ollama API", flush=True)

        docker("exec", "--user", "abc", name, "gh", "config", "set", "pager", "cat")
        docker(
            "exec", "--user", "abc", name, "copilot", "config", "footer.showQuota", "off"
        )
        script = """
import json
from pathlib import Path
for directory in ('.config/gh', '.copilot', '.local/share/keyrings'):
    path = Path('/config') / directory
    path.mkdir(parents=True, exist_ok=True)
    (path / 'devbox-persistence-fixture').write_text('not-a-credential')
path = Path('/config/.copilot/mcp-config.json')
config = json.loads(path.read_text())
config['mcpServers']['preserved-smoke-entry'] = {
    'type': 'local', 'command': '/bin/true', 'args': []
}
path.write_text(json.dumps(config))
"""
        docker("exec", "--user", "abc", name, "python3", "-c", script)
        docker("restart", name)
        healthy(name)
        check_persistent_state(home)
        check_client_settings(name)
        check_keyring(name)
        print("PASS: mounted authentication/configuration directories survive restart", flush=True)
        print("PASS: encrypted keyring survives restart and unlocks automatically", flush=True)

        launch_desktop(
            name, "/tmp/chrome-smoke.log", "chrome", "--no-first-run",
            "--disable-background-networking", "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port=9222", "--user-data-dir=/tmp/devbox-chrome-smoke",
        )
        result = docker(
            "exec", "--interactive", "--user", "abc", name, "node",
            input_text=Path(__file__).with_name("chrome_webgl.cjs").read_text(),
            timeout=90,
        )
        browser = json.loads(result)
        if not browser.get("startupUrl", "").startswith("https://www.google.com/"):
            raise RuntimeError(f"Chrome did not use the Google startup page: {browser}")
        renderer = browser.get("renderer")
        if not renderer:
            raise RuntimeError(f"Desktop Chrome could not initialize WebGL: {result}")
        if arguments.gpu and (
            "NVIDIA" not in renderer
            or "SwiftShader" in renderer
            or "llvmpipe" in renderer
        ):
            raise RuntimeError(f"Desktop Chrome is not using the NVIDIA GPU: {renderer}")
        print(f"PASS: Chrome WebGL: {renderer}", flush=True)
        print("PASS: official Google Chrome opens Google by default", flush=True)

        for launcher, title, launcher_arguments in (
            (
                "gnome-terminal", "Devbox terminal test",
                ("--title=Devbox terminal test", "--geometry=100x30", "--", "/bin/sh", "-c", "sleep 120"),
            ),
            ("code-desktop", "Visual Studio Code", ("--disable-gpu",)),
            ("copilot-desktop", "Copilot", ("--disable-gpu",)),
        ):
            log = f"/tmp/{launcher}-smoke.log"
            launch_desktop(name, log, launcher, *launcher_arguments)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                windows = docker("exec", "--user", "abc", name, "xwininfo", "-root", "-tree")
                visible = [
                    re.search(r"(\d+)x(\d+)\+", line)
                    for line in windows.splitlines()
                    if title.lower() in line.lower()
                ]
                if any(
                    size and int(size[1]) >= 600 and int(size[2]) >= 400
                    for size in visible
                ):
                    break
                time.sleep(2)
            else:
                raise RuntimeError(
                    f"{launcher} did not open a window:\n{docker('exec', name, 'cat', log)}"
                )
            print(f"PASS: {title} graphical window", flush=True)
        check_gui_secret_backends(name)
        if arguments.browser_check:
            subprocess.run(
                ["node", str(arguments.browser_check.resolve(strict=True)), name],
                check=True,
                timeout=90,
            )
        succeeded = True
    finally:
        if succeeded or not arguments.keep_on_failure:
            inspect = subprocess.run(
                ["docker", "container", "inspect", name], capture_output=True
            )
            if inspect.returncode == 0:
                subprocess.run(["docker", "rm", "--force", name], check=True)
            shutil.rmtree(home)
        else:
            print(f"Retained for diagnosis: container={name}, home={home}", flush=True)


if __name__ == "__main__":
    main()
