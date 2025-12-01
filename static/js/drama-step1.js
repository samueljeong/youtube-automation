/**
 * Drama Lab - Step 1: 대본 입력 (수동)
 * 업데이트: 2024-12-01
 * - YouTube 인증 상단 배치
 * - 5개 박스 수동 입력 (주인공+이미지 프롬프트, 씬1-4 나레이션)
 * - 주인공 성별 선택 → TTS 연동
 */

window.DramaStep1 = {
  // 상태
  currentScript: null,
  youtubeConnected: false,

  init() {
    console.log('[Step1] 대본 입력 모듈 초기화');
    this.checkYouTubeAuth();
    this.restoreFromSession();
  },

  /**
   * YouTube 인증 상태 확인
   */
  async checkYouTubeAuth() {
    const statusIcon = document.getElementById('yt-status-icon');
    const statusText = document.getElementById('yt-status-text');
    const connectBtn = document.getElementById('btn-yt-connect');

    try {
      const response = await fetch('/api/youtube/auth-status');
      const result = await response.json();

      if (result.ok && result.authenticated) {
        this.youtubeConnected = true;
        if (statusIcon) statusIcon.textContent = '✅';
        if (statusText) statusText.textContent = `YouTube 연결됨: ${result.channelName || '채널'}`;
        if (connectBtn) connectBtn.classList.add('hidden');

        // 전역 상태에도 저장
        dramaApp.session.youtubeConnected = true;
        dramaApp.session.youtubeChannel = result.channelName;
      } else {
        this.youtubeConnected = false;
        if (statusIcon) statusIcon.textContent = '🔗';
        if (statusText) statusText.textContent = 'YouTube 계정을 연결해주세요';
        if (connectBtn) connectBtn.classList.remove('hidden');
      }
    } catch (err) {
      console.error('[Step1] YouTube 인증 확인 실패:', err);
      if (statusIcon) statusIcon.textContent = '⚠️';
      if (statusText) statusText.textContent = 'YouTube 연결 확인 실패';
      if (connectBtn) connectBtn.classList.remove('hidden');
    }
  },

  /**
   * YouTube 연결 (OAuth)
   * 먼저 현재 상태를 확인하고, 이미 연결되어 있으면 OAuth를 건너뜀
   */
  async connectYouTube() {
    const statusIcon = document.getElementById('yt-status-icon');
    const statusText = document.getElementById('yt-status-text');
    const connectBtn = document.getElementById('btn-yt-connect');

    // 로딩 상태 표시
    if (statusIcon) statusIcon.textContent = '⏳';
    if (statusText) statusText.textContent = 'YouTube 연결 확인 중...';
    if (connectBtn) connectBtn.disabled = true;

    try {
      // 먼저 현재 인증 상태 확인
      const response = await fetch('/api/youtube/auth-status');
      const result = await response.json();

      if (result.authenticated) {
        // 이미 인증됨 - OAuth 불필요
        this.youtubeConnected = true;
        if (statusIcon) statusIcon.textContent = '✅';
        if (statusText) statusText.textContent = `YouTube 연결됨: ${result.channelName || '채널'}`;
        if (connectBtn) {
          connectBtn.classList.add('hidden');
          connectBtn.disabled = false;
        }

        dramaApp.session.youtubeConnected = true;
        dramaApp.session.youtubeChannel = result.channelName;

        DramaUtils.showStatus('YouTube가 이미 연결되어 있습니다!', 'success');
        return;
      }

      // 인증 필요 - OAuth 페이지로 이동
      // 서버에서 토큰이 유효하면 바로 리다이렉트됨
      window.location.href = '/api/youtube/auth';

    } catch (err) {
      console.error('[Step1] YouTube 연결 확인 실패:', err);
      if (statusIcon) statusIcon.textContent = '⚠️';
      if (statusText) statusText.textContent = '연결 확인 실패 - 다시 시도해주세요';
      if (connectBtn) connectBtn.disabled = false;
    }
  },

  /**
   * 설정값 가져오기
   */
  getConfig() {
    return {
      channelType: document.getElementById('channel-type')?.value || 'senior-nostalgia',
      protagonistGender: document.getElementById('protagonist-gender')?.value || 'female',
      ttsVoiceQuality: document.getElementById('tts-voice-quality')?.value || 'wavenet'
    };
  },

  /**
   * 모든 입력 필드에서 데이터 수집
   */
  collectBoxData() {
    // 주인공/캐릭터 정보
    const characterInfo = document.getElementById('character-info')?.value?.trim() || '';

    // 씬별 이미지 프롬프트와 나레이션 수집
    const scenes = [];
    const imagePrompts = [];

    for (let i = 1; i <= 4; i++) {
      const imagePrompt = document.getElementById(`scene${i}-image-prompt`)?.value?.trim() || '';
      const narration = document.getElementById(`scene${i}-narration`)?.value?.trim() || '';

      if (narration || imagePrompt) {
        scenes.push({
          id: `scene_${i}`,
          narration: narration,
          imagePrompt: imagePrompt
        });
        imagePrompts.push(imagePrompt);
        console.log(`[Step1] 씬 ${i}: 프롬프트=${imagePrompt.length}자, 나레이션=${narration.length}자`);
      }
    }

    return {
      characterInfo: characterInfo,
      scenes: scenes,
      imagePrompts: imagePrompts.filter(Boolean)
    };
  },

  /**
   * 수동 입력 대본 저장
   */
  saveManualScript() {
    const config = this.getConfig();
    const boxData = this.collectBoxData();

    // 유효성 검사
    if (!boxData.characterInfo) {
      DramaUtils.showStatus('주인공 정보를 입력해주세요.', 'error');
      return;
    }

    if (boxData.scenes.length === 0) {
      DramaUtils.showStatus('최소 1개 이상의 씬을 입력해주세요.', 'error');
      return;
    }

    // 이미지 프롬프트 검사 (씬에서 직접 가져옴)
    const scenesWithPrompts = boxData.scenes.filter(s => s.imagePrompt);
    if (scenesWithPrompts.length === 0) {
      DramaUtils.showStatus('최소 1개 이상의 이미지 프롬프트를 입력해주세요.', 'error');
      return;
    }

    console.log('[Step1] 저장 데이터:', {
      config,
      characterInfo: boxData.characterInfo.substring(0, 50) + '...',
      sceneCount: boxData.scenes.length,
      imagePromptsCount: boxData.imagePrompts.length
    });

    // 데이터 구조화 - 씬에 이미지 프롬프트가 직접 포함됨
    this.currentScript = {
      type: 'manual',
      config: config,
      characterInfo: boxData.characterInfo,
      scenes: boxData.scenes,  // 각 씬에 imagePrompt 필드 포함
      createdAt: new Date().toISOString()
    };

    // 전역 세션에 저장
    dramaApp.session.script = JSON.stringify(this.currentScript);
    dramaApp.session.scriptData = this.currentScript;
    dramaApp.session.protagonistGender = config.protagonistGender;
    dramaApp.session.ttsVoiceQuality = config.ttsVoiceQuality;
    dramaApp.session.channelType = config.channelType;

    // DramaSession에도 저장 (localStorage)
    DramaSession.setStepData('step1', this.currentScript);
    DramaMain.saveSessionToStorage();

    // 저장 완료 UI 표시
    const savedNotice = document.getElementById('step1-saved-notice');
    if (savedNotice) {
      savedNotice.classList.remove('hidden');
    }

    DramaUtils.showStatus(`대본 저장 완료! (${boxData.scenes.length}개 씬)`, 'success');

    // 다음 단계로 이동
    setTimeout(() => {
      DramaMain.completeStep(1);
      DramaMain.goToStep(2);
    }, 1000);
  },

  /**
   * 세션에서 데이터 복원
   */
  restoreFromSession() {
    const data = DramaSession.getStepData('step1');
    if (!data || data.type !== 'manual') return;

    console.log('[Step1] 세션에서 데이터 복원');

    // 캐릭터 정보 복원
    const charInfo = document.getElementById('character-info');
    if (charInfo && data.characterInfo) {
      charInfo.value = data.characterInfo;
    }

    // 씬별 이미지 프롬프트와 나레이션 복원
    if (data.scenes) {
      data.scenes.forEach((scene, idx) => {
        const sceneNum = idx + 1;
        const promptEl = document.getElementById(`scene${sceneNum}-image-prompt`);
        const narrationEl = document.getElementById(`scene${sceneNum}-narration`);

        if (promptEl && scene.imagePrompt) {
          promptEl.value = scene.imagePrompt;
        }
        if (narrationEl && scene.narration) {
          narrationEl.value = scene.narration;
        }
      });
    }

    // 설정 복원
    if (data.config) {
      const genderSelect = document.getElementById('protagonist-gender');
      const qualitySelect = document.getElementById('tts-voice-quality');
      const channelSelect = document.getElementById('channel-type');

      if (genderSelect && data.config.protagonistGender) {
        genderSelect.value = data.config.protagonistGender;
      }
      if (qualitySelect && data.config.ttsVoiceQuality) {
        qualitySelect.value = data.config.ttsVoiceQuality;
      }
      if (channelSelect && data.config.channelType) {
        channelSelect.value = data.config.channelType;
      }
    }

    this.currentScript = data;
  },

  /**
   * 모든 입력 데이터 클리어
   */
  clearAll() {
    if (!confirm('모든 입력 내용을 지우시겠습니까?')) return;

    // 캐릭터 정보 초기화
    const charInfo = document.getElementById('character-info');
    if (charInfo) charInfo.value = '';

    // 씬별 필드 초기화
    for (let i = 1; i <= 4; i++) {
      const promptEl = document.getElementById(`scene${i}-image-prompt`);
      const narrationEl = document.getElementById(`scene${i}-narration`);
      if (promptEl) promptEl.value = '';
      if (narrationEl) narrationEl.value = '';
    }

    this.currentScript = null;
    DramaSession.setStepData('step1', null);

    const savedNotice = document.getElementById('step1-saved-notice');
    if (savedNotice) savedNotice.classList.add('hidden');

    DramaUtils.showStatus('입력 내용이 초기화되었습니다.', 'info');
  }
};
