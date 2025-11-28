/**
 * Drama Lab - 메인 모듈
 * 스텝 전환, 세션 관리, 전역 상태 관리
 */

// ===== 전역 상태 =====
window.dramaApp = {
  currentStep: 1,
  maxReachedStep: 1,
  session: {
    id: null,
    channelType: 'senior-nostalgia',
    contentType: 'nostalgia',
    duration: '10min',
    model: 'google/gemini-2.0-flash-001',
    script: null,
    scriptData: null,  // JSON 파싱된 대본 데이터
    characters: [],
    images: [],
    ttsAudios: [],
    videoPath: null,
    metadata: null,
    thumbnails: []
  }
};

// ===== DramaMain 모듈 =====
window.DramaMain = {
  /**
   * 앱 초기화
   */
  init() {
    console.log('[DramaMain] 앱 초기화');
    this.setupStepNavigation();
    this.loadSessionFromStorage();
    this.updateSessionInfo();

    // 채널 타입 변경 시 콘텐츠 타입 자동 연동
    const channelTypeSelect = document.getElementById('channel-type');
    if (channelTypeSelect) {
      channelTypeSelect.addEventListener('change', (e) => {
        this.onChannelTypeChange(e.target.value);
      });
    }
  },

  /**
   * 채널 타입 변경 시 콘텐츠 타입 자동 설정
   */
  onChannelTypeChange(channelType) {
    const contentTypeSelect = document.getElementById('content-type');
    if (!contentTypeSelect) return;

    dramaApp.session.channelType = channelType;

    switch (channelType) {
      case 'senior-nostalgia':
        contentTypeSelect.value = 'nostalgia';
        dramaApp.session.contentType = 'nostalgia';
        break;
      case 'testimony':
        contentTypeSelect.value = 'testimony';
        dramaApp.session.contentType = 'testimony';
        break;
      case 'default':
        contentTypeSelect.value = 'drama';
        dramaApp.session.contentType = 'drama';
        break;
    }
  },

  /**
   * 스텝 네비게이션 설정
   */
  setupStepNavigation() {
    const stepItems = document.querySelectorAll('.step-item');
    stepItems.forEach(item => {
      item.addEventListener('click', () => {
        const step = parseInt(item.dataset.step);
        if (step <= dramaApp.maxReachedStep) {
          this.goToStep(step);
        } else {
          showStatus('이전 단계를 먼저 완료해주세요.');
          setTimeout(hideStatus, 2000);
        }
      });
    });
  },

  /**
   * 특정 스텝으로 이동
   */
  goToStep(step) {
    if (step < 1 || step > 5) return;

    // 현재 스텝 비활성화
    const currentContainer = document.getElementById(`step${dramaApp.currentStep}-container`);
    if (currentContainer) {
      currentContainer.classList.remove('active');
    }

    // 새 스텝 활성화
    const newContainer = document.getElementById(`step${step}-container`);
    if (newContainer) {
      newContainer.classList.add('active');
    }

    // 프로그레스 바 업데이트
    this.updateProgressBar(step);

    // 상태 업데이트
    dramaApp.currentStep = step;
    if (step > dramaApp.maxReachedStep) {
      dramaApp.maxReachedStep = step;
    }

    // 스텝별 초기화
    this.onStepEnter(step);

    console.log(`[DramaMain] Step ${step}로 이동`);
  },

  /**
   * 프로그레스 바 업데이트
   */
  updateProgressBar(currentStep) {
    const stepItems = document.querySelectorAll('.step-item');
    const connectors = document.querySelectorAll('.step-connector');

    stepItems.forEach((item, idx) => {
      const stepNum = idx + 1;
      item.classList.remove('active', 'completed');

      if (stepNum === currentStep) {
        item.classList.add('active');
      } else if (stepNum < currentStep) {
        item.classList.add('completed');
      }
    });

    connectors.forEach((connector, idx) => {
      connector.classList.remove('active');
      if (idx < currentStep - 1) {
        connector.classList.add('active');
      }
    });
  },

  /**
   * 스텝 진입 시 처리
   */
  onStepEnter(step) {
    switch (step) {
      case 1:
        // Step1: 대본 생성 초기화
        if (DramaStep1 && DramaStep1.init) {
          DramaStep1.init();
        }
        break;
      case 2:
        // Step2: 이미지 생성 초기화
        if (DramaStep2 && DramaStep2.init) {
          DramaStep2.init();
        }
        break;
      case 3:
        // Step3: TTS 초기화
        if (DramaStep3 && DramaStep3.init) {
          DramaStep3.init();
        }
        break;
      case 4:
        // Step4: 영상 제작 초기화
        if (DramaStep4 && DramaStep4.init) {
          DramaStep4.init();
        }
        break;
      case 5:
        // Step5: 업로드 초기화
        if (DramaStep5 && DramaStep5.init) {
          DramaStep5.init();
        }
        break;
    }
  },

  /**
   * 새 세션 시작
   */
  newSession() {
    if (!confirm('새 프로젝트를 시작하시겠습니까?\n현재 작업 중인 내용은 저장되지 않습니다.')) {
      return;
    }

    // 세션 초기화
    dramaApp.session = {
      id: Date.now().toString(36) + Math.random().toString(36).substr(2, 5),
      channelType: 'senior-nostalgia',
      contentType: 'nostalgia',
      duration: '10min',
      model: 'google/gemini-2.0-flash-001',
      script: null,
      scriptData: null,
      characters: [],
      images: [],
      ttsAudios: [],
      videoPath: null,
      metadata: null,
      thumbnails: []
    };

    dramaApp.currentStep = 1;
    dramaApp.maxReachedStep = 1;

    // UI 초기화
    this.goToStep(1);
    this.resetAllStepUI();
    this.updateSessionInfo();
    this.saveSessionToStorage();

    showStatus('새 프로젝트가 시작되었습니다.');
    setTimeout(hideStatus, 2000);
  },

  /**
   * 모든 스텝 UI 초기화
   */
  resetAllStepUI() {
    // Step1 결과 숨기기
    const step1Result = document.getElementById('step1-result-area');
    if (step1Result) step1Result.classList.add('hidden');

    // Step2 결과 숨기기
    const characterAnalysis = document.getElementById('character-analysis');
    const sceneImagesArea = document.getElementById('scene-images-area');
    const step2Next = document.getElementById('step2-next');
    if (characterAnalysis) characterAnalysis.classList.add('hidden');
    if (sceneImagesArea) sceneImagesArea.classList.add('hidden');
    if (step2Next) step2Next.classList.add('hidden');

    // Step3 결과 숨기기
    const voiceAssignment = document.getElementById('voice-assignment');
    const ttsProgress = document.getElementById('tts-progress');
    const ttsResultArea = document.getElementById('tts-result-area');
    const step3Next = document.getElementById('step3-next');
    if (voiceAssignment) voiceAssignment.classList.add('hidden');
    if (ttsProgress) ttsProgress.classList.add('hidden');
    if (ttsResultArea) ttsResultArea.classList.add('hidden');
    if (step3Next) step3Next.classList.add('hidden');

    // Step4 결과 숨기기
    const timelinePreview = document.getElementById('timeline-preview');
    const videoProgress = document.getElementById('video-progress');
    const videoPreviewArea = document.getElementById('video-preview-area');
    const step4Next = document.getElementById('step4-next');
    if (timelinePreview) timelinePreview.classList.add('hidden');
    if (videoProgress) videoProgress.classList.add('hidden');
    if (videoPreviewArea) videoPreviewArea.classList.add('hidden');
    if (step4Next) step4Next.classList.add('hidden');

    // Step5 결과 숨기기
    const thumbnailSection = document.getElementById('thumbnail-section');
    const uploadMetadata = document.getElementById('upload-metadata');
    const uploadProgress = document.getElementById('upload-progress');
    const uploadComplete = document.getElementById('upload-complete');
    if (thumbnailSection) thumbnailSection.classList.add('hidden');
    if (uploadMetadata) uploadMetadata.classList.add('hidden');
    if (uploadProgress) uploadProgress.classList.add('hidden');
    if (uploadComplete) uploadComplete.classList.add('hidden');

    // 입력 필드 초기화
    const topicInput = document.getElementById('topic-input');
    if (topicInput) topicInput.value = '';
  },

  /**
   * 세션 정보 UI 업데이트
   */
  updateSessionInfo() {
    const sessionInfo = document.getElementById('session-info');
    if (sessionInfo && dramaApp.session.id) {
      const channelName = {
        'senior-nostalgia': '시니어 향수',
        'testimony': '신앙 간증',
        'default': '일반 드라마'
      }[dramaApp.session.channelType] || dramaApp.session.channelType;

      sessionInfo.textContent = `${channelName} | ${dramaApp.session.duration}`;
    }
  },

  /**
   * 세션을 로컬 스토리지에 저장
   */
  saveSessionToStorage() {
    try {
      const saveData = {
        ...dramaApp.session,
        currentStep: dramaApp.currentStep,
        maxReachedStep: dramaApp.maxReachedStep,
        savedAt: new Date().toISOString()
      };
      localStorage.setItem('_drama_session', JSON.stringify(saveData));
    } catch (e) {
      console.error('[DramaMain] 세션 저장 실패:', e);
    }
  },

  /**
   * 로컬 스토리지에서 세션 로드
   */
  loadSessionFromStorage() {
    try {
      const saved = localStorage.getItem('_drama_session');
      if (saved) {
        const data = JSON.parse(saved);
        // 1시간 이내의 세션만 복원
        const savedTime = new Date(data.savedAt);
        const now = new Date();
        if (now - savedTime < 60 * 60 * 1000) {
          dramaApp.session = { ...dramaApp.session, ...data };
          dramaApp.currentStep = data.currentStep || 1;
          dramaApp.maxReachedStep = data.maxReachedStep || 1;
          console.log('[DramaMain] 이전 세션 복원됨');
        }
      }
    } catch (e) {
      console.error('[DramaMain] 세션 로드 실패:', e);
    }
  },

  /**
   * 스텝 완료 처리
   */
  completeStep(step) {
    if (step >= dramaApp.maxReachedStep) {
      dramaApp.maxReachedStep = step + 1;
    }
    this.saveSessionToStorage();
  }
};

// ===== 초기화 =====
document.addEventListener('DOMContentLoaded', () => {
  console.log('[DramaMain] DOM 로드 완료');
  DramaMain.init();
});
