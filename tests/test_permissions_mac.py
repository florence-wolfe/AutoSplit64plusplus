import sys
import unittest
from unittest import mock

if sys.platform == "darwin":
    from autosplit64.core import capture_device_mac, capture_window_mac


@unittest.skipUnless(sys.platform == "darwin", "macOS permissions")
class RequestPermissionTest(unittest.TestCase):
    """ Asking for Screen Recording and the Camera: macOS only asks once, so the app forgets its decision first """

    def permissions(self):
        """ (module, tccutil's service, what shows macOS's prompt, the settings it opens) of each permission """
        # PyObjC's classes can't have their methods patched, so the modules' names for them are
        return [(capture_window_mac, "ScreenCapture", lambda: mock.patch.object(capture_window_mac.Quartz, "CGRequestScreenCaptureAccess"),
                 "Privacy_ScreenCapture"),
                (capture_device_mac, "Camera", lambda: mock.patch.object(capture_device_mac, "AV"), "Privacy_Camera")]

    def request(self, module, prompt, frozen=True, reset_fails=False):
        bundle = mock.Mock(bundleIdentifier=mock.Mock(return_value="local.autosplit64plusplus"))
        reset = mock.Mock(returncode=1 if reset_fails else 0, stderr="tccutil: No such bundle identifier\n")
        # Both are forgotten by capture_window_mac
        with mock.patch.object(capture_window_mac.sys, "frozen", frozen, create=True), \
             mock.patch.object(capture_window_mac, "NSBundle", mock.Mock(mainBundle=mock.Mock(return_value=bundle))), \
             mock.patch.object(capture_window_mac.subprocess, "run", return_value=reset) as run, \
             prompt() as shown:
            module.request_permission()
        if module is capture_device_mac:
            shown = shown.AVCaptureDevice.requestAccessForMediaType_completionHandler_
        return [call.args[0] for call in run.call_args_list], shown

    def test_forgets_the_decision_then_asks(self):
        for module, service, prompt, _ in self.permissions():
            with self.subTest(service):
                commands, shown = self.request(module, prompt)
                self.assertEqual(commands, [["tccutil", "reset", service, "local.autosplit64plusplus"]])
                shown.assert_called_once()

    def test_from_source_the_terminal_has_the_permission(self):
        for module, service, prompt, _ in self.permissions():
            with self.subTest(service):
                commands, shown = self.request(module, prompt, frozen=False)
                self.assertEqual(commands, [])
                shown.assert_called_once()

    def test_failing_to_forget_opens_the_settings(self):
        for module, service, prompt, pane in self.permissions():
            with self.subTest(service), self.assertLogs(".log", "WARNING") as logs:
                commands, shown = self.request(module, prompt, reset_fails=True)
            self.assertEqual(commands[-1], ["open", f"x-apple.systempreferences:com.apple.preference.security?{pane}"])
            shown.assert_not_called()
            self.assertIn("No such bundle identifier", logs.output[0])


if __name__ == "__main__":
    unittest.main()
