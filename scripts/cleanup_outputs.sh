#!/bin/bash
# outputs 폴더에서 final/ 제외하고 7일 지난 파일 삭제

BASE_DIR="/Users/samueljeong/Desktop/youtube-automation/outputs"
LOG_FILE="$BASE_DIR/cleanup.log"

echo "$(date): Cleanup started" >> "$LOG_FILE"

# 모든 파이프라인 폴더 순회 (history, isekai, audio, subtitles 등)
for pipeline_dir in "$BASE_DIR"/*; do
    if [ -d "$pipeline_dir" ]; then
        # 에피소드 폴더 순회 (ep018, EP001 등)
        for ep_dir in "$pipeline_dir"/*; do
            if [ -d "$ep_dir" ]; then
                # final 폴더 제외하고 7일 지난 파일 삭제
                find "$ep_dir" -type f -mtime +7 ! -path "*/final/*" -delete 2>/dev/null
                
                # 빈 폴더 정리 (final 제외)
                find "$ep_dir" -type d -empty ! -name "final" -delete 2>/dev/null
                
                echo "  Cleaned: $ep_dir" >> "$LOG_FILE"
            fi
        done
    fi
done

echo "$(date): Cleanup completed" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
