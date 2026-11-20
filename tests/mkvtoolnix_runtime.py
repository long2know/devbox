"""Verify MKVToolNix and the legacy Chrome launcher in a disposable desktop."""

import argparse
import re
import subprocess
import time
import uuid

from runtime_smoke import docker, healthy, launch_desktop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="devbox-cinnamon:latest")
    arguments = parser.parse_args()
    name = f"devbox-mkv-smoke-{uuid.uuid4().hex[:8]}"
    try:
        docker(
            "run", "--detach", "--pull", "never", "--name", name,
            "--label", "devbox.mkv-smoke=true",
            "--network", "none",
            "--tmpfs", "/run:exec,mode=0755",
            "--tmpfs", "/tmp:exec,mode=1777",
            "--tmpfs", "/config:uid=1000,gid=1000,mode=0700",
            "--shm-size", "512m",
            "--env", "PUID=1000",
            "--env", "PGID=1000",
            "--env", "CUSTOM_USER=smoke",
            "--env", "PASSWORD=synthetic-desktop-test1!",
            arguments.image,
        )
        healthy(name)
        print(docker("exec", "--user", "abc", name, "desktop-media-smoke-test"), flush=True)
        docker(
            "exec", name, "desktop-file-validate",
            "/usr/share/applications/chromium.desktop",
        )
        launch_desktop(
            name, "/tmp/chrome-legacy-launch.log",
            "gio", "launch", "/usr/share/applications/chromium.desktop", wait=True,
        )
        print("PASS: the legacy browser launcher dispatches Google Chrome", flush=True)
        launch_desktop(name, "/tmp/mkvtoolnix-gui.log", "mkvtoolnix-gui")
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            windows = docker("exec", "--user", "abc", name, "xwininfo", "-root", "-tree")
            for line in windows.splitlines():
                size = re.search(r"(\d+)x(\d+)\+", line)
                if "mkvtoolnix" in line.lower() and size and int(size[1]) >= 400 and int(size[2]) >= 300:
                    print("PASS: MKVToolNix GUI opens a desktop window", flush=True)
                    return
            time.sleep(1)
        log = docker("exec", name, "cat", "/tmp/mkvtoolnix-gui.log")
        raise RuntimeError(f"MKVToolNix GUI did not open:\n{log}")
    finally:
        result = subprocess.run(
            ["docker", "container", "inspect", name], capture_output=True
        )
        if result.returncode == 0:
            docker("rm", "--force", "--volumes", name)


if __name__ == "__main__":
    main()
