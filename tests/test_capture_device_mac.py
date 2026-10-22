import sys
import unittest
from unittest import mock

if sys.platform == "darwin":
    from autosplit64.core import capture_device_mac


@unittest.skipUnless(sys.platform == "darwin", "needs macOS")
class VideoOutputTest(unittest.TestCase):
    """ A device sends more frames than split detection reads, which are converted only when read """

    def test_frames_are_converted_when_read(self):
        output = capture_device_mac._VideoOutput.alloc().init()
        with mock.patch.object(capture_device_mac, "bgr_frame") as bgr_frame, \
             mock.patch.object(capture_device_mac, "CMSampleBufferGetImageBuffer", return_value=object()):
            for _ in range(5):
                output.captureOutput_didOutputSampleBuffer_fromConnection_(None, object(), None)
            bgr_frame.assert_not_called()
            self.assertTrue(output.frame_received.is_set())


@unittest.skipUnless(sys.platform == "darwin", "needs macOS")
class DisconnectedTest(unittest.TestCase):
    """ A device that was unplugged fails to capture, instead of showing its last frame for good """

    def setUp(self):
        self.addCleanup(setattr, capture_device_mac, "_active", None)
        self.device = mock.Mock()
        output = mock.Mock(sample_buffer="frame")
        output.frame_received.wait.return_value = True
        capture_device_mac._active = ("card", mock.Mock(), output, self.device)
        patcher = mock.patch.object(capture_device_mac, "bgr_frame", side_effect=lambda sample_buffer: sample_buffer)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_connected(self):
        self.device.isConnected.return_value = True
        self.assertEqual(capture_device_mac.capture("card"), "frame")

    def test_unplugged(self):
        self.device.isConnected.return_value = False
        with self.assertRaisesRegex(Exception, "disconnected"):
            capture_device_mac.capture("card")


if __name__ == "__main__":
    unittest.main()
