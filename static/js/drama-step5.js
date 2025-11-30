/**
 * Drama Lab - Step 5: 유튜브 업로드
 * 시니어 향수 채널 최적화 메타데이터 생성
 */

// Step5 모듈
window.DramaStep5 = {
  isInitialized: false,
  youtubeConnected: false,
  selectedThumbnailIndex: 0,

  /**
   * Step5 초기화
   */
  init() {
    console.log('[Step5] 유튜브 업로드 모듈 초기화');

    // 이전 스텝 데이터 로드 (localStorage → 메모리)
    this.loadPreviousStepData();

    this.checkYouTubeAuth();
    this.loadMetadataFromSession();
  },

  /**
   * 이전 스텝 데이터 로드 (Step1, Step4)
   */
  loadPreviousStepData() {
    // Step1 대본 데이터 로드
    const step1Data = DramaSession.getStepData('step1');
    if (step1Data?.content && !dramaApp.session.script) {
      dramaApp.session.script = step1Data.content;
      console.log('[Step5] Step1 대본 데이터 로드 완료');
    }

    // Step4 영상 데이터 로드
    const step4Data = DramaSession.getStepData('step4');
    if (step4Data) {
      if (step4Data.videoPath && !dramaApp.session.videoPath) {
        dramaApp.session.videoPath = step4Data.videoPath;
        console.log('[Step5] Step4 videoPath 로드 완료:', step4Data.videoPath);
      }
      if (step4Data.videoUrl && !dramaApp.session.videoUrl) {
        dramaApp.session.videoUrl = step4Data.videoUrl;
        console.log('[Step5] Step4 videoUrl 로드 완료:', step4Data.videoUrl);
      }
    }

    // Step2 이미지 데이터 로드
    const step2Data = DramaSession.getStepData('step2_images');
    if (step2Data?.images && !dramaApp.session.images) {
      dramaApp.session.images = step2Data.images.map((url, idx) => ({ url, id: idx }));
      console.log('[Step5] Step2 이미지 데이터 로드 완료:', step2Data.images.length, '개');
    }
  },

  /**
   * YouTube 인증 상태 확인
   */
  async checkYouTubeAuth() {
    const statusPanel = document.getElementById('youtube-auth-status');
    const statusIcon = statusPanel?.querySelector('.auth-status-icon');
    const statusText = statusPanel?.querySelector('.auth-status-text');
    const connectBtn = document.getElementById('btn-youtube-connect');

    try {
      const response = await fetch('/api/youtube/auth-status');
      const result = await response.json();

      if (result.ok && result.authenticated) {
        this.youtubeConnected = true;
        if (statusIcon) statusIcon.textContent = '✅';
        if (statusText) statusText.textContent = `YouTube 연결됨: ${result.channelName || '채널'}`;
        if (connectBtn) connectBtn.classList.add('hidden');

        // 메타데이터 및 썸네일 영역 표시
        this.showUploadForm();
      } else {
        this.youtubeConnected = false;
        if (statusIcon) statusIcon.textContent = '🔗';
        if (statusText) statusText.textContent = 'YouTube 계정을 연결해주세요';
        if (connectBtn) connectBtn.classList.remove('hidden');
      }
    } catch (err) {
      console.error('[Step5] YouTube 인증 확인 실패:', err);
      // 실패해도 업로드 폼은 표시 (오프라인 작업 가능)
      this.showUploadForm();
    }
  },

  /**
   * YouTube 연결
   */
  connectYouTube() {
    window.location.href = '/api/youtube/auth';
  },

  /**
   * 업로드 폼 표시
   */
  showUploadForm() {
    const thumbnailSection = document.getElementById('thumbnail-section');
    const uploadMetadata = document.getElementById('upload-metadata');

    if (thumbnailSection) thumbnailSection.classList.remove('hidden');
    if (uploadMetadata) uploadMetadata.classList.remove('hidden');

    // 썸네일이 있으면 표시
    if (dramaApp.session.thumbnails && dramaApp.session.thumbnails.length > 0) {
      this.renderThumbnails();
    }

    // 메타데이터 자동 생성
    if (!dramaApp.session.metadata && dramaApp.session.script) {
      this.generateMetadata();
    }
  },

  /**
   * 세션에서 메타데이터 로드
   */
  loadMetadataFromSession() {
    const metadata = dramaApp.session.metadata;
    if (metadata) {
      this.populateMetadataForm(metadata);
    }
  },

  /**
   * 메타데이터 자동 생성 (시니어 향수 채널 최적화)
   */
  async generateMetadata() {
    // 대본 데이터 가져오기 (메모리 → localStorage fallback)
    let script = dramaApp.session.script;
    if (!script) {
      const step1Data = DramaSession.getStepData('step1');
      script = step1Data?.content;
      if (script) {
        dramaApp.session.script = script; // 메모리에도 저장
        console.log('[Step5] fallback으로 Step1 대본 로드 완료');
      }
    }

    if (!script) {
      DramaUtils.showStatus('대본이 없습니다. Step1에서 대본을 생성해주세요.', 'error');
      return;
    }

    showLoadingOverlay('메타데이터 생성 중', '시니어 향수 채널에 최적화된 제목/설명/태그를 생성합니다...');

    try {
      const response = await fetch('/api/drama/generate-metadata', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: script,
          contentType: dramaApp.session.contentType,
          channelType: dramaApp.session.channelType  // 시니어 향수 채널 지정
        })
      });

      const result = await response.json();
      hideLoadingOverlay();

      if (result.ok) {
        dramaApp.session.metadata = result.metadata;
        this.populateMetadataForm(result.metadata);
        DramaMain.saveSessionToStorage();

        showStatus('메타데이터 생성 완료!');
        setTimeout(hideStatus, 2000);
      } else {
        throw new Error(result.error || '메타데이터 생성 실패');
      }
    } catch (err) {
      hideLoadingOverlay();
      console.error('[Step5] 메타데이터 생성 오류:', err);
      showStatus('메타데이터 생성 실패: ' + err.message);
      setTimeout(hideStatus, 3000);
    }
  },

  /**
   * 메타데이터 폼에 값 채우기
   */
  populateMetadataForm(metadata) {
    const titleInput = document.getElementById('video-title');
    const descInput = document.getElementById('video-description');
    const tagsInput = document.getElementById('video-tags');

    if (titleInput && metadata.title) {
      titleInput.value = metadata.title;
    }

    if (descInput && metadata.description) {
      descInput.value = metadata.description;
    }

    if (tagsInput && metadata.tags) {
      tagsInput.value = Array.isArray(metadata.tags) ? metadata.tags.join(', ') : metadata.tags;
    }

    // 썸네일 문구도 저장
    if (metadata.thumbnailTitle) {
      dramaApp.session.thumbnailTitle = metadata.thumbnailTitle;
    }
  },

  /**
   * 썸네일 생성 (3종)
   */
  async generateThumbnails() {
    showLoadingOverlay('썸네일 생성 중', '3가지 스타일의 썸네일을 생성합니다...');

    try {
      // 대본에서 첫 번째 씬 이미지 가져오기
      const baseImage = dramaApp.session.images?.[0]?.url || null;
      const thumbnailTitle = dramaApp.session.thumbnailTitle || dramaApp.session.metadata?.thumbnailTitle || '';

      const response = await fetch('/api/drama/generate-thumbnails', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          baseImageUrl: baseImage,
          title: thumbnailTitle,
          channelType: dramaApp.session.channelType,
          styles: ['warm', 'dramatic', 'nostalgic']  // 3가지 스타일
        })
      });

      const result = await response.json();
      hideLoadingOverlay();

      if (result.ok) {
        dramaApp.session.thumbnails = result.thumbnails;
        this.renderThumbnails();
        DramaMain.saveSessionToStorage();

        showStatus('썸네일 3종 생성 완료!');
        setTimeout(hideStatus, 2000);
      } else {
        throw new Error(result.error || '썸네일 생성 실패');
      }
    } catch (err) {
      hideLoadingOverlay();
      console.error('[Step5] 썸네일 생성 오류:', err);
      showStatus('썸네일 생성 실패: ' + err.message);
      setTimeout(hideStatus, 3000);
    }
  },

  /**
   * 썸네일 렌더링
   */
  renderThumbnails() {
    const container = document.getElementById('thumbnail-options');
    if (!container) return;

    const thumbnails = dramaApp.session.thumbnails || [];

    if (thumbnails.length === 0) {
      container.innerHTML = '<div class="thumbnail-placeholder">썸네일 생성 버튼을 클릭하세요</div>';
      return;
    }

    container.innerHTML = thumbnails.map((thumb, idx) => `
      <div class="thumbnail-option ${idx === this.selectedThumbnailIndex ? 'selected' : ''}"
           onclick="DramaStep5.selectThumbnail(${idx})">
        <img src="${thumb.url}" alt="썸네일 ${idx + 1}">
      </div>
    `).join('');
  },

  /**
   * 썸네일 선택
   */
  selectThumbnail(index) {
    this.selectedThumbnailIndex = index;
    this.renderThumbnails();
  },

  /**
   * YouTube에 업로드
   */
  async uploadToYouTube() {
    if (!this.youtubeConnected) {
      DramaUtils.showStatus('YouTube 계정을 먼저 연결해주세요.', 'warning');
      return;
    }

    // 영상 경로 가져오기 (메모리 → localStorage fallback)
    let videoPath = dramaApp.session.videoPath;
    if (!videoPath) {
      const step4Data = DramaSession.getStepData('step4');
      videoPath = step4Data?.videoPath;
      if (videoPath) {
        dramaApp.session.videoPath = videoPath; // 메모리에도 저장
        console.log('[Step5] fallback으로 Step4 videoPath 로드 완료');
      }
    }

    if (!videoPath) {
      DramaUtils.showStatus('업로드할 영상이 없습니다. Step4에서 영상을 제작해주세요.', 'error');
      return;
    }

    // 메타데이터 수집
    const title = document.getElementById('video-title')?.value?.trim();
    const description = document.getElementById('video-description')?.value?.trim();
    const tags = document.getElementById('video-tags')?.value?.split(',').map(t => t.trim()).filter(t => t);
    const category = document.getElementById('video-category')?.value || '27';
    const privacy = document.getElementById('video-privacy')?.value || 'private';

    if (!title) {
      showStatus('제목을 입력해주세요.');
      setTimeout(hideStatus, 2000);
      return;
    }

    // 업로드 진행 표시
    const uploadProgress = document.getElementById('upload-progress');
    const progressBar = document.getElementById('upload-progress-bar');
    const progressText = document.getElementById('upload-progress-text');

    if (uploadProgress) uploadProgress.classList.remove('hidden');
    if (progressBar) progressBar.style.width = '0%';
    if (progressText) progressText.textContent = '업로드 준비 중...';

    try {
      const response = await fetch('/api/youtube/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videoPath: videoPath,
          title: title,
          description: description,
          tags: tags,
          categoryId: category,
          privacyStatus: privacy,
          thumbnailPath: dramaApp.session.thumbnails?.[this.selectedThumbnailIndex]?.path
        })
      });

      const result = await response.json();

      if (result.ok) {
        // 업로드 완료
        if (progressBar) progressBar.style.width = '100%';
        if (progressText) progressText.textContent = '업로드 완료!';

        // 업로드 완료 패널 표시
        setTimeout(() => {
          if (uploadProgress) uploadProgress.classList.add('hidden');

          const uploadComplete = document.getElementById('upload-complete');
          const youtubeLink = document.getElementById('youtube-link');

          if (uploadComplete) uploadComplete.classList.remove('hidden');
          if (youtubeLink) {
            youtubeLink.href = result.videoUrl || `https://www.youtube.com/watch?v=${result.videoId}`;
          }

          dramaApp.session.youtubeVideoId = result.videoId;
          dramaApp.session.youtubeVideoUrl = result.videoUrl;
          DramaMain.saveSessionToStorage();
        }, 1000);
      } else {
        throw new Error(result.error || '업로드 실패');
      }
    } catch (err) {
      console.error('[Step5] 업로드 오류:', err);
      if (uploadProgress) uploadProgress.classList.add('hidden');
      showStatus('업로드 실패: ' + err.message);
      setTimeout(hideStatus, 3000);
    }
  },

  /**
   * YouTube 링크 복사
   */
  copyLink() {
    const youtubeLink = document.getElementById('youtube-link');
    if (youtubeLink) {
      navigator.clipboard.writeText(youtubeLink.href).then(() => {
        showStatus('링크가 복사되었습니다!');
        setTimeout(hideStatus, 2000);
      });
    }
  },

  /**
   * 카카오톡 공유
   */
  shareKakao() {
    const videoUrl = dramaApp.session.youtubeVideoUrl;
    const title = document.getElementById('video-title')?.value || '드라마 영상';

    if (window.Kakao && Kakao.isInitialized()) {
      Kakao.Link.sendDefault({
        objectType: 'feed',
        content: {
          title: title,
          description: '새로운 영상이 업로드되었습니다.',
          imageUrl: dramaApp.session.thumbnails?.[this.selectedThumbnailIndex]?.url || '',
          link: {
            mobileWebUrl: videoUrl,
            webUrl: videoUrl
          }
        },
        buttons: [{
          title: 'YouTube에서 보기',
          link: {
            mobileWebUrl: videoUrl,
            webUrl: videoUrl
          }
        }]
      });
    } else {
      // 카카오톡 SDK 없으면 기본 공유
      const shareUrl = `https://story.kakao.com/share?url=${encodeURIComponent(videoUrl)}`;
      window.open(shareUrl, '_blank');
    }
  },

  /**
   * 메타데이터 재생성
   */
  regenerateMetadata() {
    this.generateMetadata();
  }
};
