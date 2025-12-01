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
   */
  connectYouTube() {
    window.location.href = '/api/youtube/auth';
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
   * 5개 박스에서 데이터 수집
   */
  collectBoxData() {
    const box1 = document.getElementById('box1-protagonist')?.value?.trim() || '';
    const box2 = document.getElementById('box2-scene1')?.value?.trim() || '';
    const box3 = document.getElementById('box3-scene2')?.value?.trim() || '';
    const box4 = document.getElementById('box4-scene3')?.value?.trim() || '';
    const box5 = document.getElementById('box5-scene4')?.value?.trim() || '';

    return {
      protagonistAndPrompts: box1,
      scenes: [
        { id: 'scene_1', narration: box2 },
        { id: 'scene_2', narration: box3 },
        { id: 'scene_3', narration: box4 },
        { id: 'scene_4', narration: box5 }
      ].filter(s => s.narration.length > 0)
    };
  },

  /**
   * 이미지 프롬프트 파싱 (박스1에서 추출)
   */
  parseImagePrompts(text) {
    const prompts = [];

    // 씬1:, 씬2:, Scene1:, Scene2: 등의 패턴으로 분리
    const scenePattern = /(?:씬|Scene|장면)\s*(\d+)\s*[:\-]\s*(.+?)(?=(?:씬|Scene|장면)\s*\d+|$)/gis;
    let match;

    while ((match = scenePattern.exec(text)) !== null) {
      const sceneNum = parseInt(match[1]);
      const prompt = match[2].trim();
      if (prompt) {
        prompts[sceneNum - 1] = prompt;
      }
    }

    return prompts;
  },

  /**
   * 수동 입력 대본 저장
   */
  saveManualScript() {
    const config = this.getConfig();
    const boxData = this.collectBoxData();

    // 유효성 검사
    if (!boxData.protagonistAndPrompts) {
      DramaUtils.showStatus('박스 1 (주인공 & 이미지 프롬프트)을 입력해주세요.', 'error');
      return;
    }

    if (boxData.scenes.length === 0) {
      DramaUtils.showStatus('최소 1개 이상의 씬 나레이션을 입력해주세요.', 'error');
      return;
    }

    // 이미지 프롬프트 파싱
    const imagePrompts = this.parseImagePrompts(boxData.protagonistAndPrompts);

    console.log('[Step1] 저장 데이터:', {
      config,
      sceneCount: boxData.scenes.length,
      imagePromptsCount: imagePrompts.length
    });

    // 데이터 구조화
    this.currentScript = {
      type: 'manual',
      config: config,
      protagonistInfo: boxData.protagonistAndPrompts,
      imagePrompts: imagePrompts,
      scenes: boxData.scenes,
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

    // 박스 데이터 복원
    const box1 = document.getElementById('box1-protagonist');
    if (box1 && data.protagonistInfo) {
      box1.value = data.protagonistInfo;
    }

    // 씬 나레이션 복원
    if (data.scenes) {
      data.scenes.forEach((scene, idx) => {
        const boxId = `box${idx + 2}-scene${idx + 1}`;
        const box = document.getElementById(boxId);
        if (box && scene.narration) {
          box.value = scene.narration;
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
   * 박스 데이터 클리어
   */
  clearAll() {
    if (!confirm('모든 입력 내용을 지우시겠습니까?')) return;

    ['box1-protagonist', 'box2-scene1', 'box3-scene2', 'box4-scene3', 'box5-scene4'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });

    this.currentScript = null;
    DramaSession.setStepData('step1', null);

    const savedNotice = document.getElementById('step1-saved-notice');
    if (savedNotice) savedNotice.classList.add('hidden');

    DramaUtils.showStatus('입력 내용이 초기화되었습니다.', 'info');
  }
};
