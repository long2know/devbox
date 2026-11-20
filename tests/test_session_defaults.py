import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader(
    "devbox_session_init",
    str(ROOT / "root/usr/local/bin/devbox-session-init"),
)
spec = importlib.util.spec_from_loader(loader.name, loader)
session = importlib.util.module_from_spec(spec)
loader.exec_module(session)


class KeyringInitializationTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"XDG_RUNTIME_DIR": "/run/user/1000"})
        environment.start()
        self.addCleanup(environment.stop)

    def commands(self, default=None, locked=False):
        if default is None:
            default = f"(objectpath '{session.LOGIN_COLLECTION}',)"

        def result(*arguments, **_):
            if arguments[-1] == "Locked":
                return "(<true>,)" if locked else "(<false>,)"
            if arguments[-2:] == (
                "org.freedesktop.Secret.Service.ReadAlias",
                "default",
            ):
                return default
            return ""

        return patch.object(session, "command", side_effect=result)

    def test_password_is_sent_only_on_stdin(self):
        with self.commands() as run:
            session.initialize_keyring("Synthetic-test-password1!")
        unlock = next(
            call for call in run.call_args_list if call.args[:2] == ("gnome-keyring-daemon", "--unlock")
        )
        self.assertEqual(unlock.kwargs["input_text"], "Synthetic-test-password1!")
        for call in run.call_args_list:
            self.assertNotIn("Synthetic-test-password1!", call.args)

    def test_login_is_unlocked_before_starting_the_same_secret_service(self):
        with self.commands() as run:
            session.initialize_keyring("Synthetic-test-password1!")
        calls = [
            call for call in run.call_args_list if call.args[0] == "gnome-keyring-daemon"
        ]
        self.assertIn("--unlock", calls[0].args)
        self.assertIn("--start", calls[1].args)
        for call in calls:
            index = call.args.index("--control-directory")
            self.assertEqual(call.args[index + 1], "/run/user/1000/keyring")

    def test_keyring_setup_precedes_browser_commands_that_can_activate_it(self):
        order = []
        with patch.object(
            session, "initialize_keyring", side_effect=lambda _: order.append("keyring")
        ), patch.object(
            session, "initialize_browser", side_effect=lambda _: order.append("browser")
        ):
            self.assertEqual(session.main(), 0)
        self.assertEqual(order, ["keyring", "browser"])

    def test_new_login_keyring_becomes_default_without_resetting_others(self):
        with self.commands(default="(objectpath '/',)") as run:
            session.initialize_keyring("Synthetic-test-password1!")
        self.assertTrue(
            any(
                call.args[-3:] == (
                    "org.freedesktop.Secret.Service.SetAlias",
                    "default",
                    session.LOGIN_COLLECTION,
                )
                for call in run.call_args_list
            )
        )

    def test_existing_default_keyring_is_preserved_and_requires_explicit_setup(self):
        with self.commands(default="(objectpath '/org/freedesktop/secrets/collection/Existing',)") as run:
            with self.assertRaisesRegex(RuntimeError, "existing non-Login default keyring"):
                session.initialize_keyring("Synthetic-test-password1!")
        self.assertFalse(
            any("org.freedesktop.Secret.Service.SetAlias" in call.args for call in run.call_args_list)
        )

    def test_wrong_password_is_not_reported_as_success_or_reset(self):
        with self.commands(locked=True) as run:
            with self.assertRaisesRegex(RuntimeError, "could not be unlocked"):
                session.initialize_keyring("Synthetic-test-password1!")
        self.assertFalse(
            any("org.freedesktop.Secret.Service.SetAlias" in call.args for call in run.call_args_list)
        )


class BrowserInitializationTests(unittest.TestCase):
    def setUp(self):
        launcher = patch.object(session, "CHROME_LAUNCHER")
        self.launcher = launcher.start()
        self.launcher.is_file.return_value = True
        self.addCleanup(launcher.stop)

    def test_public_image_does_not_set_chrome_default_before_install(self):
        self.launcher.is_file.return_value = False
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch.object(session, "command") as run:
                session.initialize_browser(home)
                run.assert_not_called()
                self.assertFalse((home / ".local").exists())

                self.launcher.is_file.return_value = True
                session.initialize_browser(home)
                run.assert_called_once()

    def test_default_is_applied_once_so_later_user_choices_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch.object(session, "command", return_value="") as run:
                session.initialize_browser(home)
                session.initialize_browser(home)
            environment = {
                **os.environ,
                "XDG_CURRENT_DESKTOP": "X-Cinnamon",
            }
            environment.pop("PASSWORD", None)
            environment.pop("KDE_SESSION_VERSION", None)
            environment.pop("KDE_FULL_SESSION", None)
            run.assert_called_once_with(
                "xdg-settings",
                "set",
                "default-web-browser",
                "dev-chrome.desktop",
                environment=environment,
            )
            self.assertTrue(
                (home / ".local/state/devbox/google-browser-default-cinnamon-v1").is_file()
            )

    def test_previous_desktop_markers_do_not_skip_cinnamon_browser_setup(self):
        for marker in (
            "google-browser-default-v1",
            "google-browser-default-mate-v1",
            "google-browser-default-plasma-v1",
        ):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as directory:
                home = Path(directory)
                old_marker = home / ".local/state/devbox" / marker
                old_marker.parent.mkdir(parents=True)
                old_marker.touch()
                with patch.object(session, "command", return_value="") as run:
                    session.initialize_browser(home)
                    session.initialize_browser(home)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(
                    run.call_args.kwargs["environment"]["XDG_CURRENT_DESKTOP"], "X-Cinnamon"
                )
                self.assertTrue(old_marker.exists())

    def test_browser_setup_does_not_forward_the_web_login_password(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"PASSWORD": "Synthetic-test-password1!"}
        ), patch.object(session, "command", return_value="") as run:
            session.initialize_browser(Path(directory))
        self.assertNotIn("PASSWORD", run.call_args.kwargs["environment"])

    def test_cinnamon_browser_setup_does_not_inherit_kde_session_settings(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"KDE_SESSION_VERSION": "6", "KDE_FULL_SESSION": "true"}
        ), patch.object(session, "command", return_value="") as run:
            session.initialize_browser(Path(directory))
        environment = run.call_args.kwargs["environment"]
        self.assertNotIn("KDE_SESSION_VERSION", environment)
        self.assertNotIn("KDE_FULL_SESSION", environment)

    def test_failed_browser_setup_can_be_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch.object(
                session,
                "command",
                side_effect=subprocess.CalledProcessError(1, ["xdg-settings"]),
            ):
                with self.assertRaises(subprocess.CalledProcessError):
                    session.initialize_browser(home)
            self.assertFalse(
                (home / ".local/state/devbox/google-browser-default-cinnamon-v1").exists()
            )


if __name__ == "__main__":
    unittest.main()
