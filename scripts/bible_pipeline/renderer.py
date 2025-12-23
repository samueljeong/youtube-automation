"""
성경통독 영상 렌더링 모듈

- 배경 이미지 생성 (구약: 파란색, 신약: 빨간색)
- 자막 렌더링 (절 번호 + 말씀)
- 페이드 인/아웃 효과
"""

import os
import math
from typing import Dict, List, Any, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

from .config import (
    BIBLE_BOOKS,
    get_book_by_name,
)


# ============================================================
# 색상 팔레트 (구약 파란색 계열, 신약 빨간색 계열)
# ============================================================

# 구약 색상 팔레트 (39권 - 파란색/청록색 계열)
OLD_TESTAMENT_COLORS = {
    # 모세오경 (1-5): 진한 네이비
    "창세기": {"bg1": "#1a237e", "bg2": "#283593", "accent": "#5c6bc0"},
    "출애굽기": {"bg1": "#1a237e", "bg2": "#303f9f", "accent": "#7986cb"},
    "레위기": {"bg1": "#0d47a1", "bg2": "#1565c0", "accent": "#64b5f6"},
    "민수기": {"bg1": "#0d47a1", "bg2": "#1976d2", "accent": "#90caf9"},
    "신명기": {"bg1": "#01579b", "bg2": "#0277bd", "accent": "#4fc3f7"},

    # 역사서 (6-17): 청록색
    "여호수아": {"bg1": "#006064", "bg2": "#00838f", "accent": "#4dd0e1"},
    "사사기": {"bg1": "#006064", "bg2": "#0097a7", "accent": "#80deea"},
    "룻기": {"bg1": "#004d40", "bg2": "#00695c", "accent": "#4db6ac"},
    "사무엘상": {"bg1": "#004d40", "bg2": "#00796b", "accent": "#80cbc4"},
    "사무엘하": {"bg1": "#1b5e20", "bg2": "#2e7d32", "accent": "#81c784"},
    "열왕기상": {"bg1": "#1b5e20", "bg2": "#388e3c", "accent": "#a5d6a7"},
    "열왕기하": {"bg1": "#33691e", "bg2": "#558b2f", "accent": "#aed581"},
    "역대상": {"bg1": "#33691e", "bg2": "#689f38", "accent": "#c5e1a5"},
    "역대하": {"bg1": "#827717", "bg2": "#9e9d24", "accent": "#dce775"},
    "에스라": {"bg1": "#f57f17", "bg2": "#f9a825", "accent": "#fff176"},
    "느헤미야": {"bg1": "#ff6f00", "bg2": "#ff8f00", "accent": "#ffca28"},
    "에스더": {"bg1": "#e65100", "bg2": "#ef6c00", "accent": "#ffb74d"},

    # 시가서 (18-22): 보라색
    "욥기": {"bg1": "#4a148c", "bg2": "#6a1b9a", "accent": "#ba68c8"},
    "시편": {"bg1": "#4a148c", "bg2": "#7b1fa2", "accent": "#ce93d8"},
    "잠언": {"bg1": "#311b92", "bg2": "#4527a0", "accent": "#9575cd"},
    "전도서": {"bg1": "#311b92", "bg2": "#512da8", "accent": "#b39ddb"},
    "아가": {"bg1": "#880e4f", "bg2": "#ad1457", "accent": "#f48fb1"},

    # 대선지서 (23-27): 진한 파랑
    "이사야": {"bg1": "#0d47a1", "bg2": "#1565c0", "accent": "#42a5f5"},
    "예레미야": {"bg1": "#1565c0", "bg2": "#1976d2", "accent": "#64b5f6"},
    "예레미야애가": {"bg1": "#1976d2", "bg2": "#1e88e5", "accent": "#90caf9"},
    "에스겔": {"bg1": "#1e88e5", "bg2": "#2196f3", "accent": "#bbdefb"},
    "다니엘": {"bg1": "#2196f3", "bg2": "#42a5f5", "accent": "#e3f2fd"},

    # 소선지서 (28-39): 하늘색
    "호세아": {"bg1": "#0277bd", "bg2": "#0288d1", "accent": "#4fc3f7"},
    "요엘": {"bg1": "#0288d1", "bg2": "#039be5", "accent": "#81d4fa"},
    "아모스": {"bg1": "#039be5", "bg2": "#03a9f4", "accent": "#b3e5fc"},
    "오바댜": {"bg1": "#00838f", "bg2": "#0097a7", "accent": "#80deea"},
    "요나": {"bg1": "#0097a7", "bg2": "#00acc1", "accent": "#b2ebf2"},
    "미가": {"bg1": "#00acc1", "bg2": "#00bcd4", "accent": "#e0f7fa"},
    "나훔": {"bg1": "#00695c", "bg2": "#00796b", "accent": "#80cbc4"},
    "하박국": {"bg1": "#00796b", "bg2": "#00897b", "accent": "#a7ffeb"},
    "스바냐": {"bg1": "#00897b", "bg2": "#009688", "accent": "#b2dfdb"},
    "학개": {"bg1": "#2e7d32", "bg2": "#388e3c", "accent": "#a5d6a7"},
    "스가랴": {"bg1": "#388e3c", "bg2": "#43a047", "accent": "#c8e6c9"},
    "말라기": {"bg1": "#43a047", "bg2": "#4caf50", "accent": "#e8f5e9"},
}

# 신약 색상 팔레트 (27권 - 빨간색/주황색 계열)
NEW_TESTAMENT_COLORS = {
    # 복음서 (40-43): 진한 빨강
    "마태복음": {"bg1": "#b71c1c", "bg2": "#c62828", "accent": "#ef5350"},
    "마가복음": {"bg1": "#c62828", "bg2": "#d32f2f", "accent": "#e57373"},
    "누가복음": {"bg1": "#d32f2f", "bg2": "#e53935", "accent": "#ef9a9a"},
    "요한복음": {"bg1": "#e53935", "bg2": "#f44336", "accent": "#ffcdd2"},

    # 역사서 (44): 주황색
    "사도행전": {"bg1": "#e65100", "bg2": "#ef6c00", "accent": "#ffb74d"},

    # 바울서신 (45-57): 빨강-주황 그라데이션
    "로마서": {"bg1": "#bf360c", "bg2": "#d84315", "accent": "#ff8a65"},
    "고린도전서": {"bg1": "#d84315", "bg2": "#e64a19", "accent": "#ffab91"},
    "고린도후서": {"bg1": "#e64a19", "bg2": "#f4511e", "accent": "#ffccbc"},
    "갈라디아서": {"bg1": "#ff5722", "bg2": "#ff6e40", "accent": "#fbe9e7"},
    "에베소서": {"bg1": "#ff6f00", "bg2": "#ff8f00", "accent": "#ffe0b2"},
    "빌립보서": {"bg1": "#ff8f00", "bg2": "#ffa000", "accent": "#ffecb3"},
    "골로새서": {"bg1": "#ffa000", "bg2": "#ffb300", "accent": "#fff8e1"},
    "데살로니가전서": {"bg1": "#ffb300", "bg2": "#ffc107", "accent": "#fffde7"},
    "데살로니가후서": {"bg1": "#ffc107", "bg2": "#ffca28", "accent": "#fff9c4"},
    "디모데전서": {"bg1": "#ff6f00", "bg2": "#ff8f00", "accent": "#ffe0b2"},
    "디모데후서": {"bg1": "#e65100", "bg2": "#ef6c00", "accent": "#ffcc80"},
    "디도서": {"bg1": "#bf360c", "bg2": "#d84315", "accent": "#ffab91"},
    "빌레몬서": {"bg1": "#8d6e63", "bg2": "#a1887f", "accent": "#d7ccc8"},

    # 일반서신 (58-65): 분홍-자주색
    "히브리서": {"bg1": "#880e4f", "bg2": "#ad1457", "accent": "#f48fb1"},
    "야고보서": {"bg1": "#ad1457", "bg2": "#c2185b", "accent": "#f8bbd9"},
    "베드로전서": {"bg1": "#c2185b", "bg2": "#d81b60", "accent": "#fce4ec"},
    "베드로후서": {"bg1": "#d81b60", "bg2": "#e91e63", "accent": "#f8bbd0"},
    "요한일서": {"bg1": "#7b1fa2", "bg2": "#8e24aa", "accent": "#e1bee7"},
    "요한이서": {"bg1": "#8e24aa", "bg2": "#9c27b0", "accent": "#f3e5f5"},
    "요한삼서": {"bg1": "#6a1b9a", "bg2": "#7b1fa2", "accent": "#ce93d8"},
    "유다서": {"bg1": "#4a148c", "bg2": "#6a1b9a", "accent": "#d1c4e9"},

    # 예언서 (66): 진한 자주색
    "요한계시록": {"bg1": "#311b92", "bg2": "#4527a0", "accent": "#b39ddb"},
}


def get_book_colors(book_name: str) -> Dict[str, str]:
    """책 이름으로 색상 팔레트 가져오기"""
    if book_name in OLD_TESTAMENT_COLORS:
        return OLD_TESTAMENT_COLORS[book_name]
    elif book_name in NEW_TESTAMENT_COLORS:
        return NEW_TESTAMENT_COLORS[book_name]
    else:
        # 기본값 (파란색)
        return {"bg1": "#1a237e", "bg2": "#283593", "accent": "#5c6bc0"}


def get_testament(book_name: str) -> str:
    """구약/신약 구분"""
    book = get_book_by_name(book_name)
    if book:
        return book.get("testament", "구약")
    return "구약"


# ============================================================
# 배경 이미지 생성
# ============================================================

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """HEX 색상을 RGB로 변환"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def create_gradient_background(
    width: int = 1920,
    height: int = 1080,
    color1: str = "#1a237e",
    color2: str = "#283593",
    direction: str = "diagonal"  # diagonal, vertical, horizontal
) -> Image.Image:
    """
    그라데이션 배경 이미지 생성

    Args:
        width: 이미지 너비
        height: 이미지 높이
        color1: 시작 색상 (HEX)
        color2: 끝 색상 (HEX)
        direction: 그라데이션 방향

    Returns:
        PIL Image 객체
    """
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)

    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)

    if direction == "vertical":
        for y in range(height):
            ratio = y / height
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

    elif direction == "horizontal":
        for x in range(width):
            ratio = x / width
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            draw.line([(x, 0), (x, height)], fill=(r, g, b))

    else:  # diagonal
        for y in range(height):
            for x in range(width):
                # 대각선 비율 계산
                ratio = (x / width + y / height) / 2
                r = int(r1 + (r2 - r1) * ratio)
                g = int(g1 + (g2 - g1) * ratio)
                b = int(b1 + (b2 - b1) * ratio)
                img.putpixel((x, y), (r, g, b))

    return img


def add_modern_effects(
    img: Image.Image,
    accent_color: str = "#5c6bc0",
    opacity: float = 0.2
) -> Image.Image:
    """
    2025 모던 스타일 효과 추가 (글로우 + 보케 + 빛줄기)

    Args:
        img: 원본 이미지
        accent_color: 악센트 색상
        opacity: 투명도 (0-1)

    Returns:
        효과가 추가된 이미지
    """
    width, height = img.size
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    r, g, b = hex_to_rgb(accent_color)

    # 1. 중앙 글로우 효과 (빛나는 중심)
    center_x, center_y = width // 2, height // 2
    for radius in range(300, 50, -30):
        alpha = int(30 * (1 - radius / 300))
        if alpha > 0:
            draw.ellipse(
                [center_x - radius, center_y - radius,
                 center_x + radius, center_y + radius],
                fill=(r, g, b, alpha)
            )

    # 2. 상단 빛줄기 효과
    for i in range(5):
        x_offset = width * (0.2 + i * 0.15)
        ray_alpha = 15
        points = [
            (x_offset - 100, 0),
            (x_offset + 100, 0),
            (x_offset + 200, height // 2),
            (x_offset - 200, height // 2),
        ]
        draw.polygon(points, fill=(255, 255, 255, ray_alpha))

    # 3. 보케 효과 (반투명 원)
    import random
    random.seed(42)  # 일관된 결과
    for _ in range(8):
        bx = random.randint(0, width)
        by = random.randint(0, height)
        br = random.randint(50, 150)
        ba = random.randint(5, 20)
        draw.ellipse([bx - br, by - br, bx + br, by + br], fill=(255, 255, 255, ba))

    # 4. 하단 비네팅 (어두운 가장자리)
    for y in range(height - 200, height):
        progress = (y - (height - 200)) / 200
        alpha = int(100 * progress)
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

    # 상단 비네팅
    for y in range(0, 100):
        progress = 1 - (y / 100)
        alpha = int(60 * progress)
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

    # 원본 이미지와 합성
    img = img.convert('RGBA')
    return Image.alpha_composite(img, overlay)


def create_bible_background(
    book_name: str,
    width: int = 1920,
    height: int = 1080,
    add_effects: bool = True
) -> Image.Image:
    """
    성경 책에 맞는 배경 이미지 생성 (2025 모던 스타일)

    Args:
        book_name: 성경 책 이름 (예: 창세기)
        width: 이미지 너비
        height: 이미지 높이
        add_effects: 모던 효과 추가 여부

    Returns:
        PIL Image 객체
    """
    colors = get_book_colors(book_name)

    # 그라데이션 배경 생성
    img = create_gradient_background(
        width=width,
        height=height,
        color1=colors["bg1"],
        color2=colors["bg2"],
        direction="diagonal"
    )

    # 모던 효과 추가 (글로우, 보케, 빛줄기)
    if add_effects:
        img = add_modern_effects(img, accent_color=colors["accent"])

    return img.convert('RGB')


# ============================================================
# 자막 렌더링
# ============================================================

def get_font(font_size: int = 60) -> ImageFont.FreeTypeFont:
    """
    폰트 로드 (NanumSquareRound 우선)

    Args:
        font_size: 폰트 크기

    Returns:
        ImageFont 객체
    """
    # 폰트 경로 우선순위
    font_paths = [
        # 프로젝트 내 폰트
        os.path.join(os.path.dirname(__file__), '..', '..', 'fonts', 'NanumSquareRoundB.ttf'),
        os.path.join(os.path.dirname(__file__), '..', '..', 'fonts', 'NanumGothicBold.ttf'),
        # 시스템 폰트
        '/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
    ]

    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, font_size)
            except Exception:
                continue

    # 기본 폰트 (폴백)
    return ImageFont.load_default()


def wrap_text(text: str, max_chars_per_line: int = 25) -> List[str]:
    """
    텍스트를 여러 줄로 나누기 (가독성 향상)

    Args:
        text: 원본 텍스트
        max_chars_per_line: 한 줄 최대 글자 수

    Returns:
        줄 단위 리스트
    """
    words = text.split(' ')
    lines = []
    current_line = ""

    for word in words:
        if len(current_line + word) <= max_chars_per_line:
            current_line += word + " "
        else:
            if current_line:
                lines.append(current_line.strip())
            current_line = word + " "

    if current_line:
        lines.append(current_line.strip())

    return lines


def render_verse_frame(
    book_name: str,
    chapter: int,
    verse: int,
    text: str,
    width: int = 1920,
    height: int = 1080,
    background_img: Optional[Image.Image] = None
) -> Image.Image:
    """
    성경 절 프레임 렌더링

    형식:
        신명기 1장 3절
        마흔째 해 열한째 달 그 달 첫째 날에
        모세가 이스라엘 자손에게
        여호와께서 그들을 위하여
        자기에게 주신 명령을 다 알렸으니

    Args:
        book_name: 책 이름
        chapter: 장 번호
        verse: 절 번호
        text: 말씀 내용
        width: 이미지 너비
        height: 이미지 높이
        background_img: 배경 이미지 (없으면 자동 생성)

    Returns:
        렌더링된 프레임 이미지
    """
    # 배경 이미지
    if background_img is None:
        img = create_bible_background(book_name, width, height)
    else:
        img = background_img.copy()

    draw = ImageDraw.Draw(img)

    # 폰트 설정
    reference_font = get_font(48)  # 참조 (신명기 1장 3절)
    verse_font = get_font(56)      # 본문

    # 색상
    colors = get_book_colors(book_name)
    reference_color = colors.get("accent", "#ffffff")
    text_color = "#ffffff"

    # 참조 텍스트 (상단 중앙)
    reference_text = f"{book_name} {chapter}장 {verse}절"
    ref_bbox = draw.textbbox((0, 0), reference_text, font=reference_font)
    ref_width = ref_bbox[2] - ref_bbox[0]
    ref_x = (width - ref_width) // 2
    ref_y = height * 0.15

    # 참조 텍스트 그리기 (그림자 효과)
    shadow_offset = 2
    draw.text((ref_x + shadow_offset, ref_y + shadow_offset), reference_text,
              font=reference_font, fill="#000000")
    draw.text((ref_x, ref_y), reference_text, font=reference_font, fill=reference_color)

    # 본문 텍스트 (중앙)
    lines = wrap_text(text, max_chars_per_line=22)
    line_height = 80
    total_text_height = len(lines) * line_height
    start_y = (height - total_text_height) // 2 + 50  # 참조 아래로

    for i, line in enumerate(lines):
        line_bbox = draw.textbbox((0, 0), line, font=verse_font)
        line_width = line_bbox[2] - line_bbox[0]
        line_x = (width - line_width) // 2
        line_y = start_y + i * line_height

        # 그림자 효과
        draw.text((line_x + shadow_offset, line_y + shadow_offset), line,
                  font=verse_font, fill="#000000")
        # 본문
        draw.text((line_x, line_y), line, font=verse_font, fill=text_color)

    return img


# ============================================================
# 영상 효과 설정
# ============================================================

# 전환 효과 설정 (FFmpeg용)
TRANSITION_EFFECTS = {
    "fade": {
        "filter": "fade=t=out:st={end_time}:d={duration},fade=t=in:st=0:d={duration}",
        "duration": 0.5,  # 초
    },
    "crossfade": {
        "filter": "xfade=transition=fade:duration={duration}:offset={offset}",
        "duration": 0.5,
    },
    "dissolve": {
        "filter": "xfade=transition=dissolve:duration={duration}:offset={offset}",
        "duration": 0.8,
    },
}


def get_ffmpeg_fade_filter(duration: float, fade_duration: float = 0.5) -> str:
    """
    FFmpeg 페이드 인/아웃 필터 생성

    Args:
        duration: 클립 총 길이 (초)
        fade_duration: 페이드 효과 길이 (초)

    Returns:
        FFmpeg 필터 문자열
    """
    fade_out_start = duration - fade_duration
    return f"fade=t=in:st=0:d={fade_duration},fade=t=out:st={fade_out_start}:d={fade_duration}"


# ============================================================
# SRT 자막 생성
# ============================================================

def format_srt_time(seconds: float) -> str:
    """초를 SRT 시간 형식으로 변환 (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_verse_srt(
    subtitles: List[Dict[str, Any]],
    verse_durations: List[float],
    output_path: str,
    include_reference: bool = True
) -> str:
    """
    절별 SRT 자막 파일 생성

    Args:
        subtitles: Episode.subtitles 리스트 (verse, text, reference 등)
        verse_durations: 각 절의 TTS 재생 시간 (초)
        output_path: SRT 파일 저장 경로
        include_reference: 참조(신명기 1장 3절) 포함 여부

    Returns:
        저장된 파일 경로
    """
    srt_lines = []
    current_time = 0.0

    for i, (subtitle, duration) in enumerate(zip(subtitles, verse_durations)):
        start_time = current_time
        end_time = current_time + duration

        # SRT 인덱스 (1부터 시작)
        srt_lines.append(str(i + 1))

        # 시간 범위
        srt_lines.append(f"{format_srt_time(start_time)} --> {format_srt_time(end_time)}")

        # 자막 텍스트
        if include_reference:
            # "창세기 1장 1절" + 줄바꿈 + "(1) 태초에..."
            reference = f"{subtitle['book']} {subtitle['chapter']}장 {subtitle['verse']}절"
            srt_lines.append(reference)
            srt_lines.append(subtitle['text'])
        else:
            # "(1) 태초에..." 만
            srt_lines.append(subtitle['text'])

        srt_lines.append("")  # 빈 줄로 구분

        current_time = end_time

    # 파일 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(srt_lines))

    print(f"[RENDER] SRT 저장: {output_path}")
    return output_path


def generate_ass_subtitle(
    subtitles: List[Dict[str, Any]],
    verse_durations: List[float],
    output_path: str,
    font_name: str = "NanumSquareRound",
    font_size: int = 96,
    primary_color: str = "&H00FFFFFF",  # 흰색
    outline_color: str = "&H00000000",  # 검정
    fade_duration_ms: int = 300,
    chapter_title_duration: float = 2.5  # 챕터 타이틀 표시 시간 (초)
) -> str:
    """
    ASS 자막 파일 생성 (페이드 효과 + 챕터 구분 포함)

    Args:
        subtitles: Episode.subtitles 리스트
        verse_durations: 각 절의 TTS 재생 시간 (초)
        output_path: ASS 파일 저장 경로
        font_name: 폰트 이름
        font_size: 폰트 크기 (YouTube용 72px 권장)
        primary_color: 텍스트 색상 (ASS 형식)
        outline_color: 외곽선 색상
        fade_duration_ms: 페이드 효과 시간 (밀리초)
        chapter_title_duration: 챕터 타이틀 표시 시간 (초)

    Returns:
        저장된 파일 경로
    """
    # ASS 헤더 - 2025 모던 스타일
    # Reference: 상단 가운데, 골드색, 크게
    # Verse: 중앙, 흰색, 매우 크게
    # ChapterTitle: 화면 중앙, 큰 폰트, 챕터 전환용
    ass_header = f"""[Script Info]
Title: Bible Reading Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Reference,{font_name},{int(font_size * 0.75)},&H0000D7FF,&H000000FF,&H00000000,&HCC000000,1,0,0,0,100,100,2,0,1,4,3,8,50,50,120,1
Style: Verse,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},&HCC000000,1,0,0,0,100,100,3,0,1,5,4,5,100,100,80,1
Style: ChapterTitle,{font_name},{int(font_size * 1.3)},&H0000D7FF,&H000000FF,&H00000000,&HCC000000,1,0,0,0,100,100,5,0,1,6,5,5,50,50,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def format_ass_time(seconds: float) -> str:
        """ASS 시간 형식 (H:MM:SS.cc)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"

    events = []
    current_time = 0.0
    prev_chapter = None
    prev_book = None

    for i, (subtitle, duration) in enumerate(zip(subtitles, verse_durations)):
        current_book = subtitle['book']
        current_chapter = subtitle['chapter']

        # 챕터 전환 감지 (첫 절 또는 장이 바뀔 때)
        is_chapter_change = (prev_chapter is None or
                            prev_chapter != current_chapter or
                            prev_book != current_book)

        if is_chapter_change and i > 0:
            # 챕터 타이틀 카드 추가 (첫 절 제외, 장이 바뀔 때만)
            # 이전 절 끝나고 챕터 타이틀 표시
            chapter_title = f"{current_book} {current_chapter}장"
            title_start = current_time
            title_end = current_time + chapter_title_duration

            # 페이드 인/아웃 효과와 함께 챕터 타이틀 표시
            title_fade_ms = 500  # 챕터 타이틀은 좀 더 긴 페이드
            title_text = f"{{\\fad({title_fade_ms},{title_fade_ms})}}{chapter_title}"
            events.append(
                f"Dialogue: 1,{format_ass_time(title_start)},{format_ass_time(title_end)},ChapterTitle,,0,0,0,,{title_text}"
            )

            # 타이틀 시간만큼 현재 시간 이동 (TTS에는 이미 장 시작 멘트가 포함되어 있으므로 실제 추가 시간은 없음)
            # 단, 자막 타이밍은 TTS와 동기화되어야 하므로 별도의 시간 추가 없이 오버레이로 표시

        start_time = current_time
        end_time = current_time + duration

        # 참조 텍스트 (상단): "창세기 1장" (절 번호 제외)
        reference = f"{current_book} {current_chapter}장"
        # 페이드 효과: {\\fad(시작,끝)}
        ref_text = f"{{\\fad({fade_duration_ms},{fade_duration_ms})}}{reference}"
        events.append(
            f"Dialogue: 0,{format_ass_time(start_time)},{format_ass_time(end_time)},Reference,,0,0,0,,{ref_text}"
        )

        # 본문 텍스트 (중앙): "(1) 태초에 하나님이..."
        # 긴 텍스트는 줄바꿈 처리 (큰 폰트에 맞게 20자 기준)
        verse_text = subtitle['text']
        if len(verse_text) > 20:
            # 20자 이상이면 줄바꿈 (큰 폰트 기준)
            lines = wrap_text(verse_text, max_chars_per_line=20)
            verse_text = "\\N".join(lines)  # ASS 줄바꿈

        verse_with_fade = f"{{\\fad({fade_duration_ms},{fade_duration_ms})}}{verse_text}"
        events.append(
            f"Dialogue: 0,{format_ass_time(start_time)},{format_ass_time(end_time)},Verse,,0,0,0,,{verse_with_fade}"
        )

        current_time = end_time
        prev_chapter = current_chapter
        prev_book = current_book

    # 파일 저장
    ass_content = ass_header + '\n'.join(events) + '\n'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)

    print(f"[RENDER] ASS 저장: {output_path}")
    return output_path


# ============================================================
# 영상 렌더링 (FFmpeg)
# ============================================================

def generate_ffmpeg_command(
    background_path: str,
    audio_path: str,
    subtitle_path: str,
    output_path: str,
    duration: float,
    subtitle_type: str = "ass"  # "ass" or "srt"
) -> List[str]:
    """
    FFmpeg 명령어 생성

    Args:
        background_path: 배경 이미지 경로
        audio_path: TTS 오디오 파일 경로
        subtitle_path: 자막 파일 경로 (ASS 또는 SRT)
        output_path: 출력 영상 경로
        duration: 영상 길이 (초)
        subtitle_type: 자막 타입

    Returns:
        FFmpeg 명령어 리스트
    """
    # 기본 명령어
    cmd = [
        'ffmpeg', '-y',
        '-loop', '1',
        '-i', background_path,
        '-i', audio_path,
        '-c:v', 'libx264',
        '-tune', 'stillimage',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-shortest',
        '-t', str(duration),
    ]

    # 자막 필터
    if subtitle_type == "ass":
        # ASS 자막 (스타일 포함)
        cmd.extend([
            '-vf', f"ass={subtitle_path}",
        ])
    else:
        # SRT 자막
        cmd.extend([
            '-vf', f"subtitles={subtitle_path}:force_style='FontName=NanumSquareRound,FontSize=48,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=1,Outline=3,Shadow=2'",
        ])

    cmd.append(output_path)

    return cmd


def render_episode_video(
    episode,
    audio_path: str,
    verse_durations: List[float],
    output_dir: str,
    background_path: Optional[str] = None,
    use_ass: bool = True
) -> Dict[str, Any]:
    """
    에피소드 영상 렌더링

    Args:
        episode: Episode 객체
        audio_path: TTS 오디오 파일 경로
        verse_durations: 각 절의 TTS 재생 시간 (초)
        output_dir: 출력 디렉토리
        background_path: 배경 이미지 경로 (None이면 자동 생성)
        use_ass: True면 ASS 자막, False면 SRT

    Returns:
        {"ok": True, "video_path": str, "duration": float} 또는
        {"ok": False, "error": str}
    """
    import subprocess
    import re
    import time
    import sys

    os.makedirs(output_dir, exist_ok=True)

    # 파일 경로 생성
    video_filename = f"day_{episode.day_number:03d}.mp4"
    video_path = os.path.join(output_dir, video_filename)
    subtitle_ext = "ass" if use_ass else "srt"
    subtitle_path = os.path.join(output_dir, f"day_{episode.day_number:03d}.{subtitle_ext}")

    # 배경 이미지 확인/생성
    print(f"[RENDER] 배경 이미지 확인 중...", flush=True)
    if background_path is None:
        from .background import get_background_path, generate_book_background
        background_path = get_background_path(episode.book)
        if not background_path:
            print(f"[RENDER] 배경 이미지 생성 중: {episode.book}", flush=True)
            result = generate_book_background(episode.book)
            if not result.get("ok"):
                return {"ok": False, "error": f"배경 생성 실패: {result.get('error')}"}
            background_path = result.get("image_path")
            print(f"[RENDER] 배경 이미지 생성 완료: {background_path}", flush=True)
        else:
            print(f"[RENDER] 기존 배경 이미지 사용: {background_path}", flush=True)
    else:
        print(f"[RENDER] 제공된 배경 이미지 사용: {background_path}", flush=True)

    # 자막 생성
    print(f"[RENDER] 자막 파일 생성 중... ({len(episode.subtitles)}개 절)", flush=True)
    if use_ass:
        generate_ass_subtitle(episode.subtitles, verse_durations, subtitle_path)
    else:
        generate_verse_srt(episode.subtitles, verse_durations, subtitle_path)
    print(f"[RENDER] 자막 파일 생성 완료: {subtitle_path}", flush=True)

    # 총 재생 시간 계산
    total_duration = sum(verse_durations)
    print(f"[RENDER] 예상 영상 길이: {total_duration:.1f}초 ({total_duration/60:.1f}분)", flush=True)

    # FFmpeg 명령어 생성 및 실행
    cmd = generate_ffmpeg_command(
        background_path=background_path,
        audio_path=audio_path,
        subtitle_path=subtitle_path,
        output_path=video_path,
        duration=total_duration,
        subtitle_type=subtitle_ext
    )

    # 타임아웃 계산: 영상 길이의 2배 + 5분 (최소 15분, 최대 60분)
    # Render 1vCPU에서 실시간의 약 1.5-2배 소요
    timeout_seconds = min(max(int(total_duration * 2 + 300), 900), 3600)
    print(f"[RENDER] FFmpeg 실행 시작: Day {episode.day_number} (타임아웃: {timeout_seconds//60}분)", flush=True)
    print(f"[RENDER] 명령어: {' '.join(cmd[:10])}...", flush=True)

    try:
        import select
        import threading

        # FFmpeg에 -progress pipe:1 추가하여 진행 정보를 stdout으로 출력
        cmd_with_progress = cmd[:-1] + ['-progress', 'pipe:1', cmd[-1]]

        process = subprocess.Popen(
            cmd_with_progress,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        start_time = time.time()
        last_progress_time = time.time()
        stderr_lines = []
        current_time_sec = 0

        def read_stderr():
            """stderr를 백그라운드에서 읽어 저장"""
            for line in process.stderr:
                stderr_lines.append(line)

        # stderr를 별도 스레드에서 읽기 (블로킹 방지)
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()

        # stdout에서 진행 정보 읽기 (FFmpeg -progress 출력)
        while True:
            # 타임아웃 체크
            if time.time() - start_time > timeout_seconds:
                process.kill()
                return {"ok": False, "error": f"FFmpeg 타임아웃 ({timeout_seconds//60}분 초과)"}

            # 프로세스 종료 체크
            if process.poll() is not None:
                break

            try:
                line = process.stdout.readline()
                if not line:
                    time.sleep(0.1)
                    continue

                # out_time_ms=12345678 형식에서 시간 추출
                if line.startswith('out_time_ms='):
                    try:
                        ms = int(line.split('=')[1].strip())
                        current_time_sec = ms / 1000000.0
                    except:
                        pass

                # out_time=00:01:23.456789 형식
                elif line.startswith('out_time='):
                    time_str = line.split('=')[1].strip()
                    time_match = re.match(r'(\d+):(\d+):(\d+\.?\d*)', time_str)
                    if time_match:
                        hours = int(time_match.group(1))
                        minutes = int(time_match.group(2))
                        seconds = float(time_match.group(3))
                        current_time_sec = hours * 3600 + minutes * 60 + seconds

                # 30초마다 진행 상황 출력
                if time.time() - last_progress_time >= 30:
                    progress_pct = (current_time_sec / total_duration * 100) if total_duration > 0 else 0
                    elapsed = time.time() - start_time
                    print(f"[RENDER] FFmpeg 진행: {current_time_sec:.0f}초/{total_duration:.0f}초 ({progress_pct:.1f}%) - 경과: {elapsed/60:.1f}분", flush=True)
                    last_progress_time = time.time()

            except Exception as e:
                time.sleep(0.1)

        # 프로세스 완료 대기
        process.wait(timeout=60)
        stderr_thread.join(timeout=5)

        if process.returncode != 0:
            error_text = ''.join(stderr_lines[-30:]) if stderr_lines else "No stderr"
            return {
                "ok": False,
                "error": f"FFmpeg 오류 (code {process.returncode}): {error_text[:500]}"
            }

        elapsed = time.time() - start_time
        print(f"[RENDER] FFmpeg 완료! 총 {current_time_sec:.0f}초 렌더링됨 (소요: {elapsed/60:.1f}분)", flush=True)
        print(f"[RENDER] 영상 생성 완료: {video_path}", flush=True)

        return {
            "ok": True,
            "video_path": video_path,
            "subtitle_path": subtitle_path,
            "duration": total_duration
        }

    except subprocess.TimeoutExpired:
        process.kill()
        return {"ok": False, "error": f"FFmpeg 타임아웃 ({timeout_seconds//60}분 초과)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":
    # 테스트: 창세기 1장 1절 프레임 생성
    print("배경 이미지 생성 테스트...")

    # 구약 테스트 (파란색 계열)
    frame = render_verse_frame(
        book_name="창세기",
        chapter=1,
        verse=1,
        text="태초에 하나님이 천지를 창조하시니라"
    )
    frame.save("/tmp/bible_test_genesis.png")
    print("저장: /tmp/bible_test_genesis.png")

    # 신약 테스트 (빨간색 계열)
    frame = render_verse_frame(
        book_name="마태복음",
        chapter=1,
        verse=1,
        text="아브라함과 다윗의 자손 예수 그리스도의 계보라"
    )
    frame.save("/tmp/bible_test_matthew.png")
    print("저장: /tmp/bible_test_matthew.png")

    # 긴 텍스트 테스트
    frame = render_verse_frame(
        book_name="신명기",
        chapter=1,
        verse=3,
        text="마흔째 해 열한째 달 그 달 첫째 날에 모세가 이스라엘 자손에게 여호와께서 그들을 위하여 자기에게 주신 명령을 다 알렸으니"
    )
    frame.save("/tmp/bible_test_deut.png")
    print("저장: /tmp/bible_test_deut.png")

    print("\n테스트 완료!")
