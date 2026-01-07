"""
19화: 발해, 고구려를 잇다 - 전체 대본 조합
"""

from .scene_01_hook import SCENE_01
from .scene_02_after_goguryeo import SCENE_02
from .scene_03_daejoyeong import SCENE_03
from .scene_04_tianmenling import SCENE_04
from .scene_05_founding import SCENE_05
from .scene_06_muwang import SCENE_06
from .scene_07_munwang import SCENE_07
from .scene_08_succession import SCENE_08
from .scene_09_japan import SCENE_09
from .scene_10_fall import SCENE_10
from .scene_11_conclusion import SCENE_11


# 전체 대본 조합
FULL_SCRIPT = "\n\n---\n\n".join([
    SCENE_01,
    SCENE_02,
    SCENE_03,
    SCENE_04,
    SCENE_05,
    SCENE_06,
    SCENE_07,
    SCENE_08,
    SCENE_09,
    SCENE_10,
    SCENE_11,
])


if __name__ == "__main__":
    # 대본 길이 확인
    script_length = len(FULL_SCRIPT)
    print(f"전체 대본 길이: {script_length:,}자")
    print(f"예상 시간: {script_length / 910:.1f}분")

    # 씬별 길이
    scenes = [SCENE_01, SCENE_02, SCENE_03, SCENE_04, SCENE_05,
              SCENE_06, SCENE_07, SCENE_08, SCENE_09, SCENE_10, SCENE_11]
    for i, scene in enumerate(scenes, 1):
        print(f"  씬{i}: {len(scene):,}자")
