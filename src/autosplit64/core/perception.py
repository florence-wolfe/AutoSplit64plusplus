"""
What split detection sees in a frame, apart from what it decides from it, so the same checks can run on every frame
the capture gets as well as on the frames split detection looks at.
"""
from dataclasses import dataclass

from .constants import FADEIN_REGION, LIFE_REGION, RESET_REGION, STAR_REGION
from .image_utils import is_black, is_white


@dataclass(frozen=True)
class Fade:
    # Both corners of the HUD, the star count's and the lives', are black, or white
    hud_black: bool
    hud_white: bool
    # The centre of the screen is black, which a fadeout splits on
    centre_black: bool
    # Where a fade-in clears last is still white
    fadein_white: bool


def fade(capture, black_threshold, white_threshold):
    """ The fade the capture's latest frame shows """
    star, life = capture.get_region(STAR_REGION), capture.get_region(LIFE_REGION)
    return Fade(
        hud_black=is_black(star, black_threshold) and is_black(life, black_threshold),
        hud_white=is_white(star, white_threshold) and is_white(life, white_threshold),
        centre_black=is_black(capture.get_region(RESET_REGION), black_threshold),
        fadein_white=is_white(capture.get_region(FADEIN_REGION), white_threshold),
    )
