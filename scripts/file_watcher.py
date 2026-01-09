#!/usr/bin/env python3
"""
파일 감시 데몬 - 대본 파일 생성 시 자동 영상 생성

사용법:
    python scripts/file_watcher.py

감시 대상:
    - outputs/history/scripts/*.txt
    - outputs/isekai/EP*/EP*_script.txt
"""

import os
import sys
import time
import json
import re
import logging
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 감시 디렉토리
HISTORY_SCRIPTS_DIR = PROJECT_ROOT / "outputs" / "history" / "scripts"
ISEKAI_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "isekai"

# 처리 완료된 파일 추적
PROCESSED_FILE = PROJECT_ROOT / "data" / "processed_scripts.json"


def load_processed_files():
    """처리 완료된 파일 목록 로드"""
    try:
        if PROCESSED_FILE.exists():
            with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
    except Exception as e:
        logger.error(f"처리 목록 로드 실패: {e}")
    return set()


def save_processed_file(filepath):
    """처리 완료된 파일 저장"""
    try:
        processed = load_processed_files()
        processed.add(str(filepath))
        os.makedirs(PROCESSED_FILE.parent, exist_ok=True)
        with open(PROCESSED_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(processed), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"처리 목록 저장 실패: {e}")


def is_already_processed(filepath):
    """이미 처리된 파일인지 확인"""
    return str(filepath) in load_processed_files()


class HistoryScriptHandler(FileSystemEventHandler):
    """History 대본 파일 감시 핸들러"""

    def on_created(self, event):
        if event.is_directory:
            return

        filepath = Path(event.src_path)

        # .txt 파일만 처리
        if filepath.suffix != '.txt':
            return

        # 이미 처리된 파일 스킵
        if is_already_processed(filepath):
            logger.info(f"[HISTORY] 이미 처리됨, 스킵: {filepath.name}")
            return

        logger.info(f"[HISTORY] 새 대본 감지: {filepath.name}")
        self.process_history_script(filepath)

    def process_history_script(self, filepath):
        """History 대본 처리"""
        try:
            # 파일명에서 에피소드 정보 추출
            # 형식: ep001_광개토왕의_정복전쟁.txt
            filename = filepath.stem
            match = re.match(r'(ep\d+)_(.+)', filename)

            if not match:
                logger.warning(f"[HISTORY] 파일명 형식 불일치: {filename}")
                return

            episode_id = match.group(1)
            title = match.group(2).replace('_', ' ')

            logger.info(f"[HISTORY] 처리 시작: {episode_id} - {title}")

            # 대본 읽기
            with open(filepath, 'r', encoding='utf-8') as f:
                script = f.read()

            # History 파이프라인 실행
            from scripts.history_pipeline.workers import (
                generate_tts, generate_image, render_video, upload_youtube
            )

            # Step 1: TTS 생성
            logger.info(f"[HISTORY] Step 1: TTS 생성...")
            tts_result = generate_tts(episode_id, script)
            if not tts_result.get('ok'):
                logger.error(f"[HISTORY] TTS 실패: {tts_result.get('error')}")
                return

            # Step 2: 이미지 생성 (썸네일)
            logger.info(f"[HISTORY] Step 2: 이미지 생성...")
            # 이미지 프롬프트는 별도 파일에서 로드하거나 기본값 사용
            image_prompt = f"Korean historical scene about {title}, cinematic, detailed"
            image_result = generate_image(episode_id, image_prompt)

            # Step 3: 영상 렌더링
            logger.info(f"[HISTORY] Step 3: 영상 렌더링...")
            video_result = render_video(
                episode=episode_id,
                audio_path=tts_result.get('audio_path'),
                image_path=image_result.get('image_path'),
                srt_path=tts_result.get('srt_path')
            )

            if not video_result.get('ok'):
                logger.error(f"[HISTORY] 영상 렌더링 실패: {video_result.get('error')}")
                return

            # Step 4: YouTube 업로드
            logger.info(f"[HISTORY] Step 4: YouTube 업로드...")
            yt_result = upload_youtube(
                video_path=video_result.get('video_path'),
                title=f"[한국사] {title}",
                description=script[:500] + "...",
                tags=["한국사", "역사", title]
            )

            if yt_result.get('ok'):
                logger.info(f"[HISTORY] 완료! YouTube: {yt_result.get('video_url')}")
                save_processed_file(filepath)
            else:
                logger.error(f"[HISTORY] 업로드 실패: {yt_result.get('error')}")

        except Exception as e:
            logger.exception(f"[HISTORY] 처리 오류: {e}")


class IsekaiScriptHandler(FileSystemEventHandler):
    """Isekai 대본 파일 감시 핸들러"""

    def on_created(self, event):
        if event.is_directory:
            return

        filepath = Path(event.src_path)

        # EP*_script.txt 패턴만 처리
        if not re.match(r'EP\d+_script\.txt$', filepath.name):
            return

        # 이미 처리된 파일 스킵
        if is_already_processed(filepath):
            logger.info(f"[ISEKAI] 이미 처리됨, 스킵: {filepath.name}")
            return

        logger.info(f"[ISEKAI] 새 대본 감지: {filepath.name}")
        self.process_isekai_script(filepath)

    def process_isekai_script(self, filepath):
        """Isekai 대본 처리"""
        try:
            # 파일명에서 에피소드 번호 추출
            # 형식: EP001_script.txt
            match = re.match(r'EP(\d+)_script\.txt$', filepath.name)
            if not match:
                logger.warning(f"[ISEKAI] 파일명 형식 불일치: {filepath.name}")
                return

            episode = int(match.group(1))
            episode_dir = filepath.parent

            logger.info(f"[ISEKAI] 처리 시작: EP{episode:03d}")

            # 대본 읽기
            with open(filepath, 'r', encoding='utf-8') as f:
                script = f.read()

            # 메타데이터 로드 (있으면)
            metadata_file = episode_dir / f"EP{episode:03d}_metadata.json"
            metadata = {}
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

            # 이미지 프롬프트 로드 (있으면)
            prompt_file = episode_dir / f"EP{episode:03d}_image_prompts.json"
            image_prompt = "fantasy wuxia scene, cinematic"
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompts = json.load(f)
                    if prompts:
                        image_prompt = prompts[0] if isinstance(prompts, list) else prompts.get('thumbnail', image_prompt)

            # Isekai 파이프라인 실행
            from scripts.isekai_pipeline.run import execute_episode

            result = execute_episode(
                episode=episode,
                title=metadata.get('title', f'Episode {episode}'),
                script=script,
                image_prompt=image_prompt,
                metadata=metadata,
                generate_video=True,
                upload=True,
                privacy_status="private"  # 기본 비공개
            )

            if result.get('ok'):
                logger.info(f"[ISEKAI] 완료! YouTube: {result.get('video_url')}")
                save_processed_file(filepath)
            else:
                logger.error(f"[ISEKAI] 실패: {result.get('error')}")

        except Exception as e:
            logger.exception(f"[ISEKAI] 처리 오류: {e}")


def ensure_directories():
    """감시 디렉토리 생성"""
    HISTORY_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    ISEKAI_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"감시 디렉토리 확인 완료")


def main():
    """메인 함수"""
    logger.info("=" * 60)
    logger.info("파일 감시 데몬 시작")
    logger.info("=" * 60)

    ensure_directories()

    # Observer 설정
    observer = Observer()

    # History 감시
    history_handler = HistoryScriptHandler()
    observer.schedule(history_handler, str(HISTORY_SCRIPTS_DIR), recursive=False)
    logger.info(f"[HISTORY] 감시 중: {HISTORY_SCRIPTS_DIR}")

    # Isekai 감시 (하위 폴더 포함)
    isekai_handler = IsekaiScriptHandler()
    observer.schedule(isekai_handler, str(ISEKAI_OUTPUT_DIR), recursive=True)
    logger.info(f"[ISEKAI] 감시 중: {ISEKAI_OUTPUT_DIR}")

    observer.start()

    logger.info("-" * 60)
    logger.info("대본 파일 생성 대기 중... (Ctrl+C로 종료)")
    logger.info("-" * 60)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("종료 중...")
        observer.stop()

    observer.join()
    logger.info("파일 감시 데몬 종료")


if __name__ == "__main__":
    main()
