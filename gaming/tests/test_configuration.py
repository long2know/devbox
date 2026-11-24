import json
import os
from pathlib import Path
import subprocess
import unittest


GAMING = Path(__file__).resolve().parents[1]


class GameboxConfigurationTests(unittest.TestCase):
    def compose(self, *, gpu=False, env_file=".env.example", **variables):
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("COMPOSE_", "GAMEBOX_"))
        }
        environment.update({"GAMEBOX_PASSWORD": "test-only: with spaces", **variables})
        files = ["-f", "compose.yaml"]
        if gpu:
            files += ["-f", "compose.gpu.yaml"]
        return subprocess.run(
            ["docker", "compose", *files, "--env-file", env_file,
             "config", "--format", "json"],
            cwd=GAMING,
            env=environment,
            text=True,
            capture_output=True,
        )

    def configuration(self, **options):
        result = self.compose(**options)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_default_is_an_independent_local_desktop(self):
        config = self.configuration()
        self.assertEqual(config["name"], "gamebox")
        self.assertEqual(set(config["services"]), {"gamebox"})
        desktop = config["services"]["gamebox"]
        self.assertEqual(desktop["image"], "gamebox-cinnamon:latest")
        self.assertEqual(desktop["container_name"], "gamebox")
        self.assertEqual(desktop["build"]["target"], "full")
        self.assertEqual(Path(desktop["build"]["context"]), GAMING.parent)
        self.assertEqual(desktop["build"]["dockerfile"], "gaming/Dockerfile")
        self.assertEqual(desktop["ports"][0]["host_ip"], "127.0.0.1")
        self.assertEqual(str(desktop["ports"][0]["published"]), "4201")
        self.assertEqual(desktop["ports"][0]["target"], 3001)
        self.assertEqual(
            {mount["target"]: Path(mount["source"]) for mount in desktop["volumes"]},
            {"/config": GAMING / "data/home", "/games": GAMING / "data/games"},
        )

    def test_prefixed_settings_configure_a_pulled_gpu_instance(self):
        config = self.configuration(
            gpu=True,
            GAMEBOX_IMAGE="ghcr.io/long2know/gamebox:latest",
            GAMEBOX_DATA_DIR="/fixture/home",
            GAMEBOX_USER="gamer",
            GAMEBOX_PUID="1234",
            GAMEBOX_PGID="1235",
            GAMEBOX_BIND_ADDRESS="192.0.2.12",
            GAMEBOX_PORT="5201",
            GAMEBOX_BASE_PATH="/gaming",
            GAMEBOX_INSTALL_VENDOR_APPS="1",
            GAMEBOX_GPU_RENDER_NODE="/dev/dri/renderD129",
        )
        desktop = config["services"]["gamebox"]
        self.assertEqual(desktop["image"], "ghcr.io/long2know/gamebox:latest")
        self.assertEqual(desktop["pull_policy"], "never")
        self.assertEqual(desktop["runtime"], "nvidia")
        self.assertEqual(desktop["ports"][0]["host_ip"], "192.0.2.12")
        self.assertEqual(str(desktop["ports"][0]["published"]), "5201")
        self.assertEqual(
            {mount["target"]: mount["source"] for mount in desktop["volumes"]},
            {"/config": "/fixture/home/home", "/games": "/fixture/home/games"},
        )
        environment = desktop["environment"]
        self.assertEqual(environment["PASSWORD"], "test-only: with spaces")
        self.assertEqual(environment["CUSTOM_USER"], "gamer")
        self.assertEqual(environment["PUID"], "1234")
        self.assertEqual(environment["PGID"], "1235")
        self.assertEqual(environment["SUBFOLDER"], "/gaming")
        self.assertEqual(environment["GAMEBOX_INSTALL_VENDOR_APPS"], "1")
        self.assertEqual(environment["DRINODE"], "/dev/dri/renderD129")
        self.assertEqual(environment["DRI_NODE"], "/dev/dri/renderD129")

    def test_gamebox_defaults_to_pacific_and_honors_timezone_override(self):
        for options, expected in (
            ({}, "America/Los_Angeles"),
            ({"env_file": "/dev/null"}, "America/Los_Angeles"),
            ({"GAMEBOX_TZ": "Asia/Tokyo"}, "Asia/Tokyo"),
        ):
            with self.subTest(options=options):
                desktop = self.configuration(**options)["services"]["gamebox"]
                self.assertEqual(desktop["environment"]["TZ"], expected)

    def test_empty_password_is_rejected(self):
        result = self.compose(GAMEBOX_PASSWORD="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set a strong GAMEBOX_PASSWORD", result.stderr)


class GameboxEntrypointTests(unittest.TestCase):
    def run_entrypoint(self, path):
        return subprocess.run(
            ["bash", "-c", 'exec() { printf "%s\\n" "$SUBFOLDER" "$@"; }; source "$1"',
             "--", str(GAMING / "root/usr/local/sbin/gamebox-entrypoint")],
            env={
                "PATH": os.defpath,
                "PASSWORD": "test-only",
                "SUBFOLDER": path,
                "APP_SANDBOX": "0",
                "GAMEBOX_INSTALL_VENDOR_APPS": "0",
            },
            text=True,
            capture_output=True,
        )

    def test_prefix_is_normalized_before_starting_s6(self):
        for path, expected in (("/gamebox", "/gamebox/"), ("/gaming/", "/gaming/"), ("/", "/")):
            with self.subTest(path=path):
                result = self.run_entrypoint(path)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines()[:2], [expected, "/init"])

    def test_invalid_prefix_does_not_start_s6(self):
        result = self.run_entrypoint("/gaming/../develop")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GAMEBOX_BASE_PATH", result.stderr)
        self.assertEqual(result.stdout, "")
