import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import psutil

from autosplit64.core import updater

REPO = "florence-wolfe/AutoSplit64plusplus"


def release_json(tag, platforms=("macos-arm64", "windows-x64"), checksums=True):
    names = [f"AutoSplit64plusplus-{tag}-{p}.zip" for p in platforms] + (["SHA256SUMS"] if checksums else [])
    return {"tag_name": tag, "html_url": f"https://github.com/{REPO}/releases/tag/{tag}",
            "assets": [{"name": n, "browser_download_url": f"https://example.com/{n}"} for n in names]}


def api_answering(data):
    return mock.patch.object(updater.requests, "get", return_value=mock.Mock(json=mock.Mock(return_value=data)))


class VersionTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(updater.parse_version("v0.4.0"), (0, 4, 0))
        self.assertEqual(updater.parse_version("0.10.2"), (0, 10, 2))
        for version in ("dev", "0.4.0-3-gabc1234", "0.4.0-rc.1", "0.4.0-dirty", ""):
            self.assertIsNone(updater.parse_version(version), version)


@mock.patch.object(updater.sys, "platform", "darwin")
class NewerReleaseTest(unittest.TestCase):
    def test_newer(self):
        with api_answering(release_json("v0.5.0")):
            release = updater.newer_release(REPO, "0.4.0")
        self.assertEqual((release.version, release.asset_name), ("0.5.0", "AutoSplit64plusplus-v0.5.0-macos-arm64.zip"))
        self.assertEqual(release.checksums_url, "https://example.com/SHA256SUMS")

    def test_same_or_older(self):
        for tag in ("v0.4.0", "v0.3.9"):
            with api_answering(release_json(tag)):
                self.assertIsNone(updater.newer_release(REPO, "0.4.0"), tag)

    def test_compares_numbers_not_text(self):
        with api_answering(release_json("v0.10.0")):
            self.assertIsNotNone(updater.newer_release(REPO, "0.9.0"))

    def test_development_version_doesnt_check(self):
        with api_answering(release_json("v9.0.0")) as get:
            self.assertIsNone(updater.newer_release(REPO, "dev"))
            self.assertIsNone(updater.newer_release(REPO, "0.4.0-3-gabc1234"))
        get.assert_not_called()

    def test_release_without_app_for_this_platform_or_checksums(self):
        for data in (release_json("v0.5.0", platforms=("windows-x64",)), release_json("v0.5.0", checksums=False)):
            with api_answering(data):
                self.assertIsNone(updater.newer_release(REPO, "0.4.0"))


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.release = updater.Release("0.5.0", "app.zip", "https://example.com/app.zip", "https://example.com/SHA256SUMS", "")
        self.content = b"x" * 3000

    def download(self, checksum):
        app = mock.MagicMock(headers={"Content-Length": str(len(self.content))})
        app.__enter__.return_value = app
        app.iter_content.return_value = [self.content[:1000], self.content[1000:]]
        sums = mock.Mock(text=f"{'0' * 64}  other.zip\n{checksum}  app.zip\n")
        progress = []
        with mock.patch.object(updater.requests, "get", side_effect=[app, sums]):
            path = updater.download(self.release, self.dir, lambda done, total: progress.append((done, total)))
        return path, progress

    def test_download_matching_checksum(self):
        path, progress = self.download(hashlib.sha256(self.content).hexdigest())
        self.assertEqual(path.read_bytes(), self.content)
        self.assertEqual(progress, [(1000, 3000), (3000, 3000)])

    def test_checksum_mismatch(self):
        with self.assertRaises(updater.UpdateError):
            self.download("f" * 64)
        self.assertEqual(list(self.dir.iterdir()), [])


class InstallTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(self.remove_dir)

    def remove_dir(self):
        # Windows refuses for a moment after an exe in it ran, while antivirus looks at it
        for _ in range(50):
            try:
                shutil.rmtree(self.dir)
                return
            except PermissionError:
                time.sleep(0.2)
        shutil.rmtree(self.dir)

    def running_process(self):
        """ A process standing in for AutoSplit64++, which quits shortly """
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.5)"])
        # Reap it when it exits, like launchd does for the app; an unreaped process still looks alive
        reaper = threading.Thread(target=process.wait)
        reaper.start()
        self.addCleanup(reaper.join)
        return process.pid

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


class FailedUpdateNoticeTest(InstallTestCase):
    def test_told_once(self):
        # As the Windows install script writes it, with a byte order mark
        (self.dir / updater.FAILED_UPDATE_FILE).write_text("A file was in use.\n", encoding="utf-8-sig")
        self.assertEqual(updater.take_failed_update_notice(self.dir), "A file was in use.")
        self.assertIsNone(updater.take_failed_update_notice(self.dir))

    def test_none(self):
        self.assertIsNone(updater.take_failed_update_notice(self.dir))


@unittest.skipUnless(sys.platform == "darwin", "installs a macOS app")
class MacInstallTest(InstallTestCase):
    def setUp(self):
        super().setUp()
        # Installed under a name the user chose
        self.app = self.dir / "Installed" / "My AS64.app"
        self.write(self.app / "Contents" / "MacOS" / "AutoSplit64++", "old")
        self.write(self.dir / "build" / "AutoSplit64++.app" / "Contents" / "MacOS" / "AutoSplit64++", "new")
        self.zip = self.dir / "update.zip"
        subprocess.run(["ditto", "-c", "-k", "--keepParent", self.dir / "build" / "AutoSplit64++.app", self.zip], check=True)

    def install(self, zip_path):
        with mock.patch.object(updater.sys, "platform", "darwin"):
            process = updater.install_on_exit(zip_path, relaunch=False, pid=self.running_process(), install_path=self.app,
                                              notice=self.dir / "notice.txt")
        process.wait(10)
        return process

    def test_replaces_app_after_it_quits(self):
        self.install(self.zip)
        self.assertEqual((self.app / "Contents" / "MacOS" / "AutoSplit64++").read_text(), "new")
        self.assertEqual(sorted(p.name for p in self.app.parent.iterdir()), ["My AS64.app"])
        self.assertFalse((self.dir / "notice.txt").exists())

    def test_broken_update_keeps_app_and_logs_why(self):
        broken = self.dir / "broken.zip"
        broken.write_bytes(b"not a zip")
        process = self.install(broken)
        self.assertEqual((self.app / "Contents" / "MacOS" / "AutoSplit64++").read_text(), "old")
        self.assertIn("ditto", process.log_path.read_text())
        # For the app to tell about, the next time it starts
        notice = (self.dir / "notice.txt").read_text()
        self.assertIn("Couldn't unpack the update", notice)
        self.assertIn(str(process.log_path), notice)


@unittest.skipUnless(sys.platform == "win32", "installs a Windows app")
class WindowsInstallTest(InstallTestCase):
    def test_replaces_app_files_and_keeps_user_files(self):
        install = self.dir / "AutoSplit64++"
        for path, text in [("AutoSplit64++.exe", "old exe"), ("libraries/old.dll", "old"), ("config.ini", "settings"),
                           ("routes/mine.as64", "my route"), ("templates/generated_reset_one.jpg", "my template")]:
            self.write(install / path, text)

        zip_path = self.dir / "update.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            for path, text in [("AutoSplit64++.exe", "new exe"), ("defaults.ini", "defaults"), ("libraries/new.dll", "new"),
                               ("routes/16_lblj.as64", "shipped route"), ("templates/generated_reset_one.jpg", "shipped"),
                               ("templates/default_reset_one.jpg", "default")]:
                archive.writestr(f"AutoSplit64++/{path}", text)

        process = updater.install_on_exit(zip_path, relaunch=False, pid=self.running_process(), install_path=install)
        process.wait(60)

        log = process.log_path.read_text() if process.log_path.exists() else "(no log)"
        self.assertEqual((install / "AutoSplit64++.exe").read_text(), "new exe", log)
        self.assertEqual(sorted(p.name for p in (install / "libraries").iterdir()), ["new.dll"])
        self.assertEqual((install / "config.ini").read_text(), "settings")
        self.assertEqual((install / "routes" / "mine.as64").read_text(), "my route")
        self.assertEqual((install / "routes" / "16_lblj.as64").read_text(), "shipped route")
        self.assertEqual((install / "templates" / "generated_reset_one.jpg").read_text(), "my template")
        self.assertEqual((install / "templates" / "default_reset_one.jpg").read_text(), "default")

    def old_app_and_update(self):
        """ An installed app and an update for it: (the app's folder, the update's zip) """
        install = self.dir / "AutoSplit64++"
        for path, text in [("AutoSplit64++.exe", "old exe"), ("libraries/old.dll", "old"), ("resources/old.png", "old"),
                           ("config.ini", "settings")]:
            self.write(install / path, text)
        zip_path = self.dir / "update.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            for path, text in [("AutoSplit64++.exe", "new exe"), ("libraries/new.dll", "new"), ("resources/new.png", "new")]:
                archive.writestr(f"AutoSplit64++/{path}", text)
        return install, zip_path

    def test_file_in_use_leaves_the_app_as_it_was(self):
        # e.g. another AutoSplit64++ from the same folder, or antivirus scanning it, which once left half the app deleted
        install, zip_path = self.old_app_and_update()
        notice = self.dir / "notice.txt"
        # Past libraries, which the update replaced first, before it failed on this
        with open(install / "resources" / "old.png"):
            process = updater.install_on_exit(zip_path, relaunch=False, pid=self.running_process(), install_path=install,
                                              notice=notice)
            process.wait(60)

        log = process.log_path.read_text()
        self.assertEqual(process.returncode, 1, log)
        self.assertIn("Install failed", log)
        self.assertEqual((install / "AutoSplit64++.exe").read_text(), "old exe")
        self.assertEqual(sorted(p.name for p in (install / "libraries").iterdir()), ["old.dll"])
        self.assertEqual(sorted(p.name for p in (install / "resources").iterdir()), ["old.png"])
        self.assertEqual(sorted(p.name for p in install.iterdir()), ["AutoSplit64++.exe", "config.ini", "libraries", "resources"])
        # For the app to tell about, the next time it starts
        text = notice.read_text(encoding="utf-8-sig")
        self.assertIn("resources", text)
        self.assertIn(str(process.log_path), text)

    def test_failing_after_copying_the_update_leaves_the_app_as_it_was(self):
        install, zip_path = self.old_app_and_update()
        # Its files outside the folders, which then fail to copy, after the update's folders were
        (install / "AutoSplit64++.exe").unlink()
        (install / "config.ini").unlink()
        user = f"{os.environ['USERDOMAIN']}\\{os.environ['USERNAME']}"
        subprocess.run(["icacls", install, "/deny", f"{user}:(WD)"], check=True, capture_output=True)
        self.addCleanup(subprocess.run, ["icacls", install, "/remove:d", user], capture_output=True)

        process = updater.install_on_exit(zip_path, relaunch=False, pid=self.running_process(), install_path=install,
                                          notice=self.dir / "notice.txt")
        process.wait(60)

        log = process.log_path.read_text()
        self.assertEqual(process.returncode, 1, log)
        # Copying the exe, after the update's folders
        self.assertIn("AutoSplit64++.exe", log.split("Install failed")[1].split("\n\n")[0])
        self.assertEqual(sorted(p.name for p in (install / "libraries").iterdir()), ["old.dll"], log)
        self.assertEqual(sorted(p.name for p in (install / "resources").iterdir()), ["old.png"], log)
        self.assertEqual(sorted(p.name for p in install.iterdir()), ["libraries", "resources"], log)
        self.assertTrue((self.dir / "notice.txt").exists())

    def test_waits_for_another_instance_from_the_same_folder(self):
        install, zip_path = self.old_app_and_update()
        # Another AutoSplit64++ running for a while, which is Windows' ping as the app's exe
        shutil.copy(Path(os.environ["SystemRoot"]) / "System32" / "PING.EXE", install / "AutoSplit64++.exe")
        running = subprocess.Popen([install / "AutoSplit64++.exe", "-n", "15", "127.0.0.1"], stdout=subprocess.DEVNULL)
        self.addCleanup(running.wait)

        process = updater.install_on_exit(zip_path, relaunch=False, pid=self.running_process(), install_path=install)
        process.wait(60)

        log = process.log_path.read_text()
        self.assertIsNotNone(running.poll(), "The update didn't wait for the other instance")
        self.assertEqual((install / "AutoSplit64++.exe").read_text(), "new exe", log)
        self.assertEqual(sorted(p.name for p in (install / "libraries").iterdir()), ["new.dll"])
        self.assertFalse(list(install.glob("*.old*")))

    def app_exe(self, marker):
        """ An exe that keeps running when it's opened, Windows' cmd, told apart by the marker at its end """
        return (Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe").read_bytes() + marker

    def reopened(self, exe):
        """ The process opened from exe after the update, if one was, which is then ended """
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            for process in psutil.process_iter(["exe"]):
                if process.info["exe"] and Path(process.info["exe"]) == exe:
                    process.kill()
                    # Before the test's folder is deleted, which Windows refuses while the exe runs
                    process.wait(10)
                    return process
            time.sleep(0.2)
        return None

    def test_restart_now_opens_the_update(self):
        install, zip_path = self.old_app_and_update()
        (install / "AutoSplit64++.exe").write_bytes(self.app_exe(b"old"))
        with zipfile.ZipFile(zip_path, "a") as archive:
            archive.writestr("AutoSplit64++/AutoSplit64++.exe", self.app_exe(b"new"))
        process = updater.install_on_exit(zip_path, relaunch=True, pid=self.running_process(), install_path=install,
                                          notice=self.dir / "notice.txt")
        process.wait(60)

        self.assertIsNotNone(self.reopened(install / "AutoSplit64++.exe"), process.log_path.read_text())
        self.assertTrue((install / "AutoSplit64++.exe").read_bytes().endswith(b"new"))
        self.assertFalse((self.dir / "notice.txt").exists())

    def test_restart_now_opens_the_app_as_it_was_when_the_update_fails(self):
        install, zip_path = self.old_app_and_update()
        (install / "AutoSplit64++.exe").write_bytes(self.app_exe(b"old"))
        with open(install / "resources" / "old.png"):
            process = updater.install_on_exit(zip_path, relaunch=True, pid=self.running_process(), install_path=install,
                                              notice=self.dir / "notice.txt")
            process.wait(60)

        self.assertIsNotNone(self.reopened(install / "AutoSplit64++.exe"), process.log_path.read_text())
        self.assertTrue((install / "AutoSplit64++.exe").read_bytes().endswith(b"old"))
        self.assertTrue((self.dir / "notice.txt").exists())


if __name__ == "__main__":
    unittest.main()
