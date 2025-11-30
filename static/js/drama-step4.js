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
  notFoundRetryCount: 0, // 404 응답 재시도 카운터
  maxNotFoundRetries: 5, // 최대 재시도 횟수 (Render 동기화 대기)

  init() {
    console.log('[Step4] 영상 제작 모듈 초기화');
  },

  // JSON 응답 안전하게 파싱 (HTML 에러 페이지 방어)
  async safeJsonParse(response, stepName) {
    const text = await response.text();
    try {
      return JSON.parse(text);
    } catch (parseError) {
      console.error(`[${stepName}] JSON 파싱 실패:`, parseError);
      console.error(`[${stepName}] 응답 내용 (처음 500자):`, text.substring(0, 500));

      // HTML 에러 페이지인지 확인
      if (text.trim().startsWith('<')) {
        throw new Error(`서버에서 HTML 에러 페이지를 반환했습니다 (status: ${response.status}). 서버 로그를 확인해주세요.`);
      }
      throw new Error(`서버 응답을 파싱할 수 없습니다: ${parseError.message}`);
    }
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
    // step2_images: 생성된 씬 이미지 URL 배열
    const step2ImagesData = DramaSession.getStepData('step2_images');
    const step3Data = DramaSession.getStepData('step3');

    console.log('[Step4] step2_images 데이터:', step2ImagesData);
    console.log('[Step4] step3 데이터:', step3Data);

    const images = step2ImagesData?.images || [];
    const audios = step3Data?.audios || [];

    // 각 씬별 이미지-오디오 매칭하여 cuts 배열 생성
    const cuts = [];
    const maxCuts = Math.max(images.length, audios.length);

    for (let i = 0; i < maxCuts; i++) {
      const imageUrl = images[i] || images[images.length - 1] || ''; // 이미지 없으면 마지막 이미지 사용
      const audio = audios[i] || audios[0] || {}; // 오디오 없으면 첫 번째 오디오 사용

      cuts.push({
        cutId: i + 1,
        imageUrl: imageUrl,
        audioUrl: audio.audioUrl || '',
        duration: audio.duration || 10
      });
    }

    console.log('[Step4] 생성된 cuts:', cuts.length, '개');

    return {
      images: images,
      audios: audios,
      cuts: cuts
    };
  },

  // 영상 제작
  async createVideo() {
    if (this.isCreating) {
      DramaUtils.showStatus('이미 제작 중입니다...', 'warning');
      return;
    }

    const { images, audios, cuts } = this.getPreviousStepData();

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

      console.log('[Step4] 영상 제작 요청 - cuts:', cuts.length, '개');

      // 이미지 존재 여부 사전 검증
      if (progressText) progressText.textContent = '이미지 파일 확인 중...';
      console.log('[Step4] 이미지 존재 여부 확인 시작');

      try {
        const checkResponse = await fetch('/api/drama/check-images', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ imageUrls: images })
        });
        const checkResult = await checkResponse.json();
        console.log('[Step4] 이미지 검증 결과:', checkResult);

        if (checkResult.ok && !checkResult.allValid) {
          const missingCount = checkResult.totalCount - checkResult.validCount;
          console.error('[Step4] 누락된 이미지 파일:', checkResult.missingFiles);
          throw new Error(`${missingCount}개의 이미지 파일이 서버에 존재하지 않습니다. Step 2에서 이미지를 다시 생성해주세요.`);
        }
      } catch (checkError) {
        if (checkError.message.includes('이미지 파일이 서버에 존재하지 않습니다')) {
          throw checkError;
        }
        console.warn('[Step4] 이미지 검증 API 오류 (무시하고 진행):', checkError);
      }

      // 요청 데이터 준비
      const requestData = {
        images: images,
        cuts: cuts,  // 씬별 이미지-오디오 매칭 배열
        audioUrl: audios[0]?.audioUrl || '', // fallback: 첫 번째 오디오
        subtitleData: null, // 추후 구현
        burnSubtitle: config.subtitleStyle !== 'none',
        resolution: resolutionMap[config.resolution] || '1920x1080',
        fps: 30,
        transition: 'fade'
      };

      // 요청 크기 확인 (디버깅)
      const requestBody = JSON.stringify(requestData);
      const requestSizeKB = (requestBody.length / 1024).toFixed(1);
      console.log(`[Step4] 요청 데이터 크기: ${requestSizeKB} KB`);

      // 이미지 URL 타입 확인 및 상세 로깅
      if (images.length > 0) {
        const firstImg = images[0] || '';
        let imgType = 'Unknown';
        if (firstImg.startsWith('data:')) {
          imgType = 'Base64';
        } else if (firstImg.startsWith('http')) {
          imgType = 'HTTP URL';
        } else if (firstImg.startsWith('/static/')) {
          imgType = 'Local Path';
        } else if (firstImg.startsWith('/')) {
          imgType = 'Relative Path';
        }
        console.log(`[Step4] 이미지 타입: ${imgType}, 첫 이미지 길이: ${firstImg.length}`);
        console.log(`[Step4] 첫 이미지 URL: ${firstImg}`);

        // 모든 이미지 URL 상태 확인
        images.forEach((img, idx) => {
          const len = img?.length || 0;
          const preview = img ? (img.length > 60 ? img.substring(0, 60) + '...' : img) : '(empty)';
          console.log(`[Step4] cuts[${idx}] 이미지: ${preview} (${len}자)`);
        });
      } else {
        console.warn('[Step4] 이미지 배열이 비어있음!');
      }

      // 영상 생성 API 호출 (cuts 배열 전송 - 각 씬별 이미지+오디오 매칭)
      const response = await fetch('/api/drama/generate-video', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: requestBody
      });

      const data = await this.safeJsonParse(response, 'Step4-영상제작');
      console.log('[Step4] 영상 제작 응답:', data);

      if (!data.ok && !data.jobId) {
        throw new Error(data.error || '영상 제작 요청 실패');
      }

      this.currentJobId = data.jobId;
      this.notFoundRetryCount = 0; // 재시도 카운터 초기화

      // 동기식 응답: 이미 완료된 경우 바로 처리
      if (data.status === 'completed') {
        console.log('[Step4] 동기식 영상 생성 완료');
        this.videoUrl = data.videoUrl;
        this.onVideoComplete(data);
        return;
      }

      // 동기식 응답: 실패한 경우 바로 처리
      if (data.status === 'failed') {
        console.log('[Step4] 동기식 영상 생성 실패');
        this.onVideoFailed(data.error || '영상 제작 실패');
        return;
      }

      // 비동기 응답: 작업 상태 폴링 시작
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
      const data = await this.safeJsonParse(response, 'Step4-상태확인');

      const progressBar = document.getElementById('video-progress-bar');
      const progressText = document.getElementById('video-progress-text');

      console.log('[Step4] 상태 확인:', data.status, 'workerAlive:', data.workerAlive, 'progress:', data.progress);

      if (data.ok) {
        // 진행률 업데이트
        if (progressBar) progressBar.style.width = `${data.progress}%`;

        // 상태별 메시지 표시
        if (data.status === 'pending') {
          if (progressText) progressText.textContent = data.message || '작업 대기 중...';
          // 워커가 죽어있으면 경고 표시
          if (data.workerAlive === false) {
            if (progressText) progressText.textContent = '⚠️ 워커 비활성 - 서버 재시작 필요';
          }
        } else if (data.status === 'processing') {
          if (progressText) progressText.textContent = data.message || `영상 인코딩 중... ${data.progress}%`;
        } else if (data.status === 'completed') {
          // 완료
          this.stopPolling();
          this.videoUrl = data.videoUrl;
          this.onVideoComplete(data);
        } else if (data.status === 'failed') {
          // 실패
          this.stopPolling();
          this.onVideoFailed(data.error || '영상 제작 실패');
        }
      } else {
        // API 오류 (예: 404)
        console.error('[Step4] 상태 확인 API 오류:', data.error);

        // 404 응답 시 재시도 (Render 환경에서 job 동기화 지연 대응)
        this.notFoundRetryCount++;
        console.log(`[Step4] 404 재시도 ${this.notFoundRetryCount}/${this.maxNotFoundRetries}`);

        if (this.notFoundRetryCount < this.maxNotFoundRetries) {
          // 아직 재시도 가능 - 폴링 계속
          const progressText = document.getElementById('video-progress-text');
          if (progressText) {
            progressText.textContent = `작업 동기화 대기 중... (${this.notFoundRetryCount}/${this.maxNotFoundRetries})`;
          }
          return; // 폴링 계속
        }

        // 최대 재시도 횟수 초과
        this.stopPolling();
        this.onVideoFailed(data.error || '작업을 찾을 수 없습니다. 서버를 확인해주세요.');
      }
    } catch (error) {
      console.error('[Step4] 상태 확인 오류:', error);
      // 네트워크 오류 시 폴링 중지하지 않음 (재시도)
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

    // 메모리에도 저장 (Step5에서 사용 가능하게)
    dramaApp.session.videoPath = data.videoPath;
    dramaApp.session.videoUrl = data.videoUrl;
    DramaMain.saveSessionToStorage();

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
