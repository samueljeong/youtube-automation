/**
 * Drama Lab - Step 4: 영상 제작
 * 초기화됨: 2024-11-28
 */

// Step4 모듈
window.DramaStep4 = {
  // 상태
  currentJobId: null,
  videoUrl: null,
  isCreating: false,
  pollInterval: null,

  init() {
    console.log('[Step4] 영상 제작 모듈 초기화');
  },

  // 설정값 가져오기
  getConfig() {
    return {
      resolution: document.getElementById('video-resolution')?.value || '1080p',
      subtitleStyle: document.getElementById('subtitle-style')?.value || 'bottom',
      bgmStyle: document.getElementById('bgm-style')?.value || 'calm'
    };
  },

  // 이전 단계 데이터 가져오기
  getPreviousStepData() {
    const step2Data = DramaSession.getStepData('step2_analysis');
    const step3Data = DramaSession.getStepData('step3');

    return {
      images: step2Data?.scenes?.map(s => s.imageUrl).filter(Boolean) || [],
      audios: step3Data?.audios || []
    };
  },

  // 영상 제작
  async createVideo() {
    if (this.isCreating) {
      DramaUtils.showStatus('이미 제작 중입니다...', 'warning');
      return;
    }

    const { images, audios } = this.getPreviousStepData();

    // 이미지와 오디오 확인
    if (images.length === 0) {
      DramaUtils.showStatus('먼저 Step 2에서 이미지를 생성해주세요.', 'error');
      return;
    }

    if (audios.length === 0) {
      DramaUtils.showStatus('먼저 Step 3에서 음성을 생성해주세요.', 'error');
      return;
    }

    this.isCreating = true;

    const btn = document.getElementById('btn-create-video');
    const originalText = btn?.innerHTML;
    const config = this.getConfig();

    try {
      if (btn) {
        btn.innerHTML = '<span class="btn-icon">⏳</span> 제작 중...';
        btn.disabled = true;
      }

      // 진행 상황 표시
      const progressPanel = document.getElementById('video-progress');
      const progressBar = document.getElementById('video-progress-bar');
      const progressText = document.getElementById('video-progress-text');

      if (progressPanel) progressPanel.classList.remove('hidden');
      if (progressBar) progressBar.style.width = '0%';
      if (progressText) progressText.textContent = '영상 제작 요청 중...';

      // 해상도 변환
      const resolutionMap = {
        '1080p': '1920x1080',
        '720p': '1280x720',
        '4k': '3840x2160'
      };

      console.log('[Step4] 영상 제작 요청');

      // 영상 생성 API 호출
      const response = await fetch('/api/drama/generate-video', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          images: images,
          audioUrl: audios[0]?.audioUrl || '', // 첫 번째 오디오 사용
          subtitleData: null, // 추후 구현
          burnSubtitle: config.subtitleStyle !== 'none',
          resolution: resolutionMap[config.resolution] || '1920x1080',
          fps: 30,
          transition: 'fade'
        })
      });

      const data = await response.json();
      console.log('[Step4] 영상 제작 응답:', data);

      if (!data.ok) {
        throw new Error(data.error || '영상 제작 요청 실패');
      }

      this.currentJobId = data.jobId;

      // 작업 상태 폴링 시작
      if (progressText) progressText.textContent = '영상 렌더링 중...';
      this.startPolling();

    } catch (error) {
      console.error('[Step4] 영상 제작 오류:', error);
      DramaUtils.showStatus(`오류: ${error.message}`, 'error');

      if (btn) {
        btn.innerHTML = originalText;
        btn.disabled = false;
      }
      this.isCreating = false;
    }
  },

  // 작업 상태 폴링
  startPolling() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
    }

    this.pollInterval = setInterval(async () => {
      await this.checkJobStatus();
    }, 3000); // 3초마다 확인
  },

  // 작업 상태 확인
  async checkJobStatus() {
    if (!this.currentJobId) return;

    try {
      const response = await fetch(`/api/drama/video-status/${this.currentJobId}`);
      const data = await response.json();

      const progressBar = document.getElementById('video-progress-bar');
      const progressText = document.getElementById('video-progress-text');

      if (data.ok) {
        // 진행률 업데이트
        if (progressBar) progressBar.style.width = `${data.progress}%`;
        if (progressText) progressText.textContent = data.message || `진행 중... ${data.progress}%`;

        if (data.status === 'completed') {
          // 완료
          this.stopPolling();
          this.videoUrl = data.videoUrl;
          this.onVideoComplete(data);
        } else if (data.status === 'failed') {
          // 실패
          this.stopPolling();
          this.onVideoFailed(data.error || '영상 제작 실패');
        }
      }
    } catch (error) {
      console.error('[Step4] 상태 확인 오류:', error);
    }
  },

  // 폴링 중지
  stopPolling() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  },

  // 영상 제작 완료
  onVideoComplete(data) {
    const btn = document.getElementById('btn-create-video');
    const progressPanel = document.getElementById('video-progress');
    const previewArea = document.getElementById('video-preview-area');
    const videoPlayer = document.getElementById('video-player');
    const videoDuration = document.getElementById('video-duration');
    const videoSize = document.getElementById('video-size');

    if (btn) {
      btn.innerHTML = '<span class="btn-icon">🎬</span> 영상 제작하기';
      btn.disabled = false;
    }

    if (progressPanel) progressPanel.classList.add('hidden');

    // 영상 미리보기 표시
    if (previewArea) previewArea.classList.remove('hidden');
    if (videoPlayer && data.videoUrl) {
      videoPlayer.src = data.videoUrl;
    }
    if (videoDuration && data.duration) {
      videoDuration.textContent = `영상 길이: ${Math.floor(data.duration / 60)}분 ${Math.floor(data.duration % 60)}초`;
    }
    if (videoSize && data.fileSize) {
      videoSize.textContent = `파일 크기: ${(data.fileSize / (1024 * 1024)).toFixed(1)}MB`;
    }

    // 세션에 저장
    DramaSession.setStepData('step4', {
      videoUrl: data.videoUrl,
      videoPath: data.videoPath,
      duration: data.duration
    });

    // 다음 단계 버튼 표시
    const nextButtons = document.getElementById('step4-next');
    if (nextButtons) nextButtons.classList.remove('hidden');

    this.isCreating = false;
    DramaUtils.showStatus('영상 제작 완료!', 'success');
  },

  // 영상 제작 실패
  onVideoFailed(error) {
    const btn = document.getElementById('btn-create-video');
    const progressPanel = document.getElementById('video-progress');

    if (btn) {
      btn.innerHTML = '<span class="btn-icon">🎬</span> 영상 제작하기';
      btn.disabled = false;
    }

    if (progressPanel) progressPanel.classList.add('hidden');

    this.isCreating = false;
    DramaUtils.showStatus(`영상 제작 실패: ${error}`, 'error');
  },

  // 영상 다운로드
  downloadVideo() {
    if (!this.videoUrl) {
      DramaUtils.showStatus('다운로드할 영상이 없습니다.', 'warning');
      return;
    }

    const a = document.createElement('a');
    a.href = this.videoUrl;
    a.download = `drama_video_${Date.now()}.mp4`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    DramaUtils.showStatus('영상 다운로드 시작', 'success');
  },

  // 세션에서 데이터 복원
  restore(data) {
    if (data?.videoUrl) {
      this.videoUrl = data.videoUrl;

      const previewArea = document.getElementById('video-preview-area');
      const videoPlayer = document.getElementById('video-player');

      if (previewArea) previewArea.classList.remove('hidden');
      if (videoPlayer) videoPlayer.src = data.videoUrl;

      const nextButtons = document.getElementById('step4-next');
      if (nextButtons) nextButtons.classList.remove('hidden');
    }
  }
};
