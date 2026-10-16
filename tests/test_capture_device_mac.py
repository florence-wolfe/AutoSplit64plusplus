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


if __name__ == "__main__":
    unittest.main()
