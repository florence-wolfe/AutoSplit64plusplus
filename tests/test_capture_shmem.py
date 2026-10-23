import unittest
from unittest import mock

import numpy as np

from autosplit64.core import capture_shmem
from autosplit64.core.capture_shmem import SharedMemoryCapture


class FakeSharedMemory:
    """ What the OBS plugin shares: a 16 byte header of width, height, line size and frame counter, then BGRA rows """
    def __init__(self):
        self.data = b""
        self.maps = []

    def write(self, frame):
        height, width = frame.shape[:2]
        self.data = np.array([width, height, width * 4, 0], np.uint32).tobytes() + frame.tobytes()

    def close_connection(self):
        """ What the plugin writes when OBS stops it """
        self.data = np.array([-1, -1, -1, 0], np.int32).view(np.uint32).tobytes() + self.data[16:]

    def mmap(self, fileno, length, tagname=None, access=None):
        assert tagname == capture_shmem.SHMEM_NAME
        mapping = FakeMapping(self, length)
        self.maps.append(mapping)
        return mapping


class FakeMapping:
    """ A view of the first length bytes of the shared memory, as mmap maps it """
    def __init__(self, memory, length):
        self.memory, self.length, self.position, self.closed = memory, length, 0, False

    def seek(self, position):
        self.position = position

    def read(self, size):
        end = min(self.position + size, self.length)
        data = self.memory.data[self.position:end]
        self.position = end
        return data

    def close(self):
        self.closed = True


def bgra(width, height):
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, (height, width, 4), np.uint8)


class SharedMemoryCaptureTest(unittest.TestCase):
    def setUp(self):
        self.memory = FakeSharedMemory()
        self.kernel32 = mock.Mock(OpenFileMappingW=mock.Mock(return_value=1234))
        # Only Windows has windll and named mappings
        for patcher in [mock.patch.object(capture_shmem.ctypes, "windll", mock.Mock(kernel32=self.kernel32), create=True),
                        mock.patch.object(capture_shmem.mmap, "mmap", self.memory.mmap)]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.capture = SharedMemoryCapture()

    def test_frame_is_bgr(self):
        frame = bgra(8, 6)
        self.memory.write(frame)
        self.capture.open_shmem()
        np.testing.assert_array_equal(self.capture.capture(), frame[:, :, :3])
        self.assertEqual(self.capture.get_capture_size(), (8, 6))

    def test_frame_size_changing_maps_the_new_size(self):
        self.memory.write(bgra(8, 6))
        self.capture.open_shmem()
        self.capture.capture()
        bigger = bgra(16, 12)
        self.memory.write(bigger)
        np.testing.assert_array_equal(self.capture.capture(), bigger[:, :, :3])
        self.assertEqual(self.capture.get_capture_size(), (16, 12))

    def test_obs_closing_the_connection(self):
        self.memory.write(bgra(8, 6))
        self.capture.open_shmem()
        self.memory.close_connection()
        with self.assertRaisesRegex(Exception, "OBS closed the connection"):
            self.capture.capture()

    def test_no_plugin(self):
        self.kernel32.OpenFileMappingW.return_value = 0
        with self.assertRaisesRegex(Exception, "Could not find OBS Grabber Plugin"):
            self.capture.open_shmem()

    def test_closing(self):
        self.memory.write(bgra(8, 6))
        self.capture.open_shmem()
        frame_mapping = self.capture.shmem
        self.capture.close_shmem()
        self.assertTrue(frame_mapping.closed)
        self.kernel32.CloseHandle.assert_called_once_with(1234)
        self.assertIsNone(self.capture.shmem_handle)


if __name__ == "__main__":
    unittest.main()
