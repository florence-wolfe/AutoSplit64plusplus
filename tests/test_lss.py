import base64
import unittest

from autosplit64.core import lss

# A one pixel PNG
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def livesplit_icon(png=PNG):
    """ An icon as LiveSplit saves it: a serialized .NET bitmap around the PNG, in base64 """
    return base64.b64encode(b"\x00\x01\x00\x00\x00\xff\xff\xff\xff\x01" + b"\x00" * 150 + png + b"\x0b").decode()


class IconPngTest(unittest.TestCase):
    def test_the_png_in_livesplits_icon(self):
        self.assertEqual(lss.icon_png(livesplit_icon()), PNG)

    def test_base64_with_line_breaks(self):
        text = livesplit_icon()
        self.assertEqual(lss.icon_png("\n".join(text[i:i + 76] for i in range(0, len(text), 76))), PNG)

    def test_no_icon(self):
        for text in (None, "", "   \n"):
            with self.subTest(repr(text)):
                self.assertIsNone(lss.icon_png(text))

    def test_what_isnt_an_icon(self):
        for text in ("not base64 at all!", base64.b64encode(b"no picture in here").decode(),
                     livesplit_icon(PNG[:20])):
            with self.subTest(text[:12]):
                self.assertIsNone(lss.icon_png(text))


if __name__ == "__main__":
    unittest.main()
