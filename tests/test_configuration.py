import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ComposeConfigurationTests(unittest.TestCase):
    def compose(
        self,
        *options,
        password="example-only: with spaces and-symbols",
        host_port="4200",
        backend_port=None,
        base_path="/",
        env_file=None,
    ):
        environment = {
            **os.environ,
            "DESKTOP_PASSWORD": password,
            "NORDVPN_USERNAME": "example-service-user",
            "NORDVPN_PASSWORD": "example-service-password",
            "GH_TOKEN": "",
            "COPILOT_GITHUB_TOKEN": "",
            "BASE_PATH": base_path,
        }
        environment.pop("DEVBOX_IMAGE", None)
        environment.pop("DEVBOX_CONTAINER_NAME", None)
        environment.pop("DEVBOX_DATA_DIR", None)
        if host_port is None:
            environment.pop("DESKTOP_PORT", None)
        else:
            environment["DESKTOP_PORT"] = host_port
        if backend_port is None:
            environment.pop("DESKTOP_BACKEND_PORT", None)
        else:
            environment["DESKTOP_BACKEND_PORT"] = backend_port
        return subprocess.run(
            [
                str(ROOT / "compose.sh"),
                *options,
                "--env-file",
                str(env_file or ROOT / ".env.example"),
                "config",
                "--format",
                "json",
            ],
            env=environment,
            text=True,
            capture_output=True,
        )

    def test_cpu_and_gpu_with_optional_local_ollama(self):
        for gpu in (False, True):
            for ollama in (False, True):
                with self.subTest(gpu=gpu, ollama=ollama):
                    options = (["--gpu"] if gpu else []) + (
                        ["--ollama"] if ollama else []
                    )
                    result = self.compose(*options)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    services = json.loads(result.stdout)["services"]
                    desktop = services["devbox"]
                    self.assertEqual(desktop["image"], "devbox-cinnamon:latest")
                    self.assertEqual(desktop["pull_policy"], "never")
                    self.assertEqual(desktop["container_name"], "debox")
                    self.assertEqual(
                        desktop["environment"]["PASSWORD"],
                        "example-only: with spaces and-symbols",
                    )
                    self.assertEqual(desktop["ports"][0]["host_ip"], "127.0.0.1")
                    self.assertEqual(
                        {
                            port["target"]: (port["host_ip"], str(port["published"]))
                            for port in desktop["ports"]
                        },
                        {3001: ("127.0.0.1", "4200")},
                    )
                    self.assertEqual(desktop["volumes"][0]["target"], "/config")
                    self.assertEqual(
                        Path(desktop["volumes"][0]["source"]), ROOT / "data/home"
                    )
                    self.assertTrue(
                        any(
                            mount.startswith("/run:") and "exec" in mount.split(":")[1].split(",")
                            for mount in desktop["tmpfs"]
                        ),
                        "s6 must be able to execute its init binary from /run",
                    )
                    for key in (
                        "GH_CONFIG_DIR",
                        "COPILOT_HOME",
                        "XDG_CONFIG_HOME",
                        "XDG_DATA_HOME",
                    ):
                        self.assertTrue(
                            desktop["environment"][key].startswith("/config/"), key
                        )
                    self.assertNotIn("privileged", desktop)
                    self.assertNotIn("cap_add", desktop)
                    self.assertEqual("desktop-ollama" in services, ollama)
                    if ollama:
                        server = services["desktop-ollama"]
                        self.assertFalse(server.get("ports"))
                        self.assertEqual(
                            Path(server["volumes"][0]["source"]), ROOT / "data/ollama"
                        )
                    if gpu:
                        self.assertEqual(desktop["runtime"], "nvidia")
                        self.assertTrue(desktop["gpus"])
                        self.assertEqual(
                            desktop["environment"]["DISABLE_DRI3"], "false"
                        )
                        if ollama:
                            self.assertEqual(
                                services["desktop-ollama"]["runtime"], "nvidia"
                            )

    def test_vpn_moves_ports_and_network_namespace_to_gluetun(self):
        for gpu in (False, True):
            for ollama in (False, True):
                with self.subTest(gpu=gpu, ollama=ollama):
                    options = (
                        ["--vpn"]
                        + (["--gpu"] if gpu else [])
                        + (["--ollama"] if ollama else [])
                    )
                    result = self.compose(*options)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    services = json.loads(result.stdout)["services"]
                    desktop, vpn = services["devbox"], services["vpn"]
                    self.assertEqual(desktop["network_mode"], "service:vpn")
                    self.assertFalse(desktop.get("ports"))
                    self.assertFalse(desktop.get("networks"))
                    self.assertEqual(
                        Path(vpn["volumes"][0]["source"]), ROOT / "data/gluetun"
                    )
                    self.assertNotIn("cap_add", desktop)
                    self.assertEqual(vpn["cap_add"], ["NET_ADMIN"])
                    self.assertEqual(vpn["ports"][0]["host_ip"], "127.0.0.1")
                    self.assertEqual(
                        {
                            port["target"]: (port["host_ip"], str(port["published"]))
                            for port in vpn["ports"]
                        },
                        {3001: ("127.0.0.1", "4200")},
                    )
                    self.assertEqual(
                        set(vpn["environment"]["FIREWALL_INPUT_PORTS"].split(",")),
                        {"3001"},
                    )
                    self.assertEqual(
                        vpn["environment"]["OPENVPN_USER"], "example-service-user"
                    )
                    self.assertEqual(
                        vpn["environment"]["OPENVPN_PASSWORD"],
                        "example-service-password",
                    )
                    self.assertEqual(
                        desktop["depends_on"]["vpn"]["condition"], "service_healthy"
                    )
                    self.assertNotIn(
                        "0.0.0.0/0", vpn["environment"]["FIREWALL_OUTBOUND_SUBNETS"]
                    )
                    if ollama:
                        self.assertFalse(services["desktop-ollama"].get("ports"))

    def test_empty_desktop_password_is_rejected(self):
        result = self.compose(password="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DESKTOP_PASSWORD", result.stderr)

    def test_single_https_port_is_configurable_with_and_without_vpn(self):
        for options, service in (([], "devbox"), (["--vpn"], "vpn")):
            with self.subTest(service=service):
                result = self.compose(*options, host_port="4300")
                self.assertEqual(result.returncode, 0, result.stderr)
                ports = json.loads(result.stdout)["services"][service]["ports"]
                self.assertEqual(
                    [(port["target"], str(port["published"])) for port in ports],
                    [(3001, "4300")],
                )

    def test_direct_https_defaults_to_4200_without_an_env_file_override(self):
        for options, service in (([], "devbox"), (["--vpn"], "vpn")):
            with self.subTest(service=service):
                result = self.compose(*options, host_port=None, env_file="/dev/null")
                self.assertEqual(result.returncode, 0, result.stderr)
                services = json.loads(result.stdout)["services"]
                ports = services[service]["ports"]
                self.assertEqual(
                    [(port["target"], str(port["published"])) for port in ports],
                    [(3001, "4200")],
                )
                self.assertEqual(
                    services["devbox"]["image"],
                    "devbox-cinnamon:latest",
                )

    def test_http_backend_can_be_selected_for_an_https_proxy(self):
        for options, service in (([], "devbox"), (["--vpn"], "vpn")):
            with self.subTest(service=service):
                result = self.compose(
                    *options, backend_port="3000", base_path="/devbox/"
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                services = json.loads(result.stdout)["services"]
                ports = services[service]["ports"]
                self.assertEqual(
                    [
                        (port["target"], str(port["published"]), port["host_ip"])
                        for port in ports
                    ],
                    [(3000, "4200", "127.0.0.1")],
                )
                self.assertEqual(
                    services["devbox"]["environment"]["SUBFOLDER"], "/devbox/"
                )
                if service == "vpn":
                    self.assertEqual(
                        services["vpn"]["environment"]["FIREWALL_INPUT_PORTS"],
                        "3000",
                    )

    def test_proxy_path_prefix_is_configurable_with_and_without_vpn(self):
        for options in ([], ["--vpn"]):
            for prefix in ("/", "/devbox/", "/tools/devbox/"):
                with self.subTest(options=options, prefix=prefix):
                    result = self.compose(
                        *options, base_path=prefix, backend_port="3000"
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    service = json.loads(result.stdout)["services"]["devbox"]
                    self.assertEqual(service["environment"]["SUBFOLDER"], prefix)


class LauncherTests(unittest.TestCase):
    def run_script(self, script, *arguments, **environment):
        with tempfile.TemporaryDirectory() as directory:
            docker = Path(directory) / "docker"
            docker.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "if sys.argv[1:] == ['context', 'show']:\n"
                "    print('devbox-test-context')\n"
                "else:\n"
                "    print(json.dumps(sys.argv[1:]))\n"
                "if sys.argv[1:2] == ['build']:\n"
                "    sys.exit(int(os.environ.get('DOCKER_BUILD_EXIT_CODE', '0')))\n"
            )
            docker.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{directory}:{os.environ['PATH']}",
                "DEVBOX_IMAGE": "local/custom-desktop:test",
                "DOCKER_BUILD_EXIT_CODE": "0",
            }
            env.pop("DEVBOX_PRUNE_BUILD_CACHE", None)
            env.update(environment)
            return subprocess.run(
                [str(ROOT / script), *arguments],
                cwd=directory,
                env=env,
                text=True,
                capture_output=True,
            )

    def test_successful_build_outside_project_runs_scoped_cleanup(self):
        result = self.run_script(
            "build.sh", "--build-arg", "REA_VERSION=6.9.0"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            [json.loads(line) for line in result.stdout.splitlines()],
            [
                [
                    "build",
                    "--pull",
                    "--tag",
                    "local/custom-desktop:test",
                    "--build-arg",
                    "REA_VERSION=6.9.0",
                    str(ROOT),
                ],
                ["image", "prune", "--force", "--filter", "label=io.debox.managed=true"],
            ],
        )

    def test_failed_build_does_not_run_cleanup(self):
        result = self.run_script("build.sh", DOCKER_BUILD_EXIT_CODE="17")
        self.assertEqual(result.returncode, 17)
        commands = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][0], "build")

    def test_shared_cache_trim_requires_opt_in(self):
        result = self.run_script("cleanup.sh", DEVBOX_PRUNE_BUILD_CACHE="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(
            commands,
            [
                ["image", "prune", "--force", "--filter", "label=io.debox.managed=true"],
                [
                    "buildx", "prune", "--builder", "devbox-test-context",
                    "--all", "--force", "--max-used-space", "8GB",
                ],
            ],
        )

    def test_help_checks_and_intermediate_targets_do_not_run_cleanup(self):
        for arguments in (
            ["--help"],
            ["-h"],
            ["--check"],
            ["--call=check"],
            ["--call", "outline"],
            ["--target", "node"],
        ):
            with self.subTest(arguments=arguments):
                result = self.run_script("build.sh", *arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                commands = [json.loads(line) for line in result.stdout.splitlines()]
                self.assertEqual(len(commands), 1)
                self.assertEqual(commands[0][0], "build")

    def test_cleanup_rejects_invalid_opt_out_before_pruning(self):
        result = self.run_script("cleanup.sh", DEVBOX_PRUNE_BUILD_CACHE="invalid")
        self.assertEqual(result.returncode, 2)
        self.assertIn("DEVBOX_PRUNE_BUILD_CACHE must be 0 or 1", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_cleanup_help_does_not_prune(self):
        result = self.run_script("cleanup.sh", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Usage:", result.stdout)
        self.assertNotIn('"prune"', result.stdout)

    def test_compose_requires_a_command(self):
        result = subprocess.run(
            [str(ROOT / "compose.sh")], text=True, capture_output=True
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Compose command is required", result.stderr)


@unittest.skipIf(os.getuid() == 0, "setup.sh requires a non-root host user")
class FirstRunTests(unittest.TestCase):
    def test_setup_creates_private_project_configuration_and_preserves_it(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / "fresh checkout"
            checkout.mkdir()
            for name in ("setup.sh", ".env.example"):
                shutil.copy2(ROOT / name, checkout / name)
            config = checkout / ".env"

            def setup():
                return subprocess.run(
                    [str(checkout / "setup.sh")],
                    cwd=directory,
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout

            first = setup()
            settings = config.read_text()
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            self.assertIn(f"\nPUID={os.getuid()}\n", settings)
            self.assertIn(f"\nPGID={os.getgid()}\n", settings)
            match = re.search(r"^DESKTOP_PASSWORD=([0-9a-f]{48})$", settings, re.M)
            self.assertIsNotNone(match, "setup did not write a random desktop password")
            self.assertNotIn(match[1], first)
            self.assertIn("left unchanged", setup())
            self.assertTrue(config.read_text() == settings, "setup rewrote the existing .env")


if __name__ == "__main__":
    unittest.main()
