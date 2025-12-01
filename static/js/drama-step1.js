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
    this.restoreAnalyzedData();  // 분석 데이터 복원
    this.initVoiceSelection();
  },

  /**
   * 음성 선택 UI 초기화
   */
  initVoiceSelection() {
    const voiceCards = document.querySelectorAll('.voice-card');
    voiceCards.forEach(card => {
      card.addEventListener('click', (e) => {
        // 미리듣기 버튼 클릭은 제외
        if (e.target.classList.contains('btn-preview')) return;

        // 선택 상태 업데이트
        voiceCards.forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');

        // hidden input 값 업데이트
        const voice = card.dataset.voice;
        const quality = card.dataset.quality;
        const gender = card.dataset.gender;

        document.getElementById('selected-voice').value = voice;
        document.getElementById('tts-voice-quality').value = quality;
        document.getElementById('protagonist-gender').value = gender;

        // 세션에 즉시 저장 (Step3에서 바로 사용 가능하도록)
        if (typeof dramaApp !== 'undefined' && dramaApp.session) {
          dramaApp.session.ttsVoice = voice;
          dramaApp.session.ttsVoiceQuality = quality;
          dramaApp.session.protagonistGender = gender;
        }

        console.log(`[Step1] 음성 선택 및 세션 저장: ${voice} (${quality}, ${gender})`);
      });
    });
  },

  /**
   * 음성 미리듣기
   */
  async previewVoice(voiceId, gender) {
    const btn = event.target;
    const player = document.getElementById('voice-preview-player');

    // 이미 재생 중이면 중지
    if (!player.paused) {
      player.pause();
      player.currentTime = 0;
    }

    // 로딩 상태
    btn.classList.add('loading');
    btn.textContent = '';

    // 샘플 텍스트
    const sampleTexts = {
      female: '안녕하세요. 저는 이순자입니다. 오늘 제 이야기를 들려드릴게요.',
      male: '안녕하세요. 저는 박봉수입니다. 오늘 제 이야기를 들려드릴게요.'
    };
    const text = sampleTexts[gender] || sampleTexts.female;

    try {
      const response = await fetch('/api/drama/generate-tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: text,
          speaker: voiceId,
          speed: 1.0,
          pitch: 0,
          volume: 0,
          ttsProvider: 'google'
        })
      });

      const data = await response.json();

      if (data.ok && data.audioUrl) {
        player.src = data.audioUrl;
        player.play();
        DramaUtils.showStatus(`${voiceId} 미리듣기 재생 중...`, 'info');
      } else {
        throw new Error(data.error || 'TTS 생성 실패');
      }
    } catch (err) {
      console.error('[Step1] 음성 미리듣기 오류:', err);
      DramaUtils.showStatus('음성 미리듣기 실패: ' + err.message, 'error');
    } finally {
      btn.classList.remove('loading');
      btn.textContent = '▶';
    }
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
      ttsVoiceQuality: document.getElementById('tts-voice-quality')?.value || 'neural2',
      ttsVoice: document.getElementById('selected-voice')?.value || 'ko-KR-Neural2-A'
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
    dramaApp.session.ttsVoice = config.ttsVoice;
    dramaApp.session.channelType = config.channelType;

    console.log('[Step1] 선택된 TTS 음성:', config.ttsVoice);

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

    // 전체 대본 초기화
    const fullScript = document.getElementById('full-script');
    if (fullScript) fullScript.value = '';

    // 분석 결과 숨김
    const analysisResult = document.getElementById('analysis-result');
    if (analysisResult) analysisResult.classList.add('hidden');

    const saveBtn = document.getElementById('btn-save-script');
    if (saveBtn) saveBtn.classList.add('hidden');

    this.currentScript = null;
    this.analysisData = null;
    DramaSession.setStepData('step1', null);

    const savedNotice = document.getElementById('step1-saved-notice');
    if (savedNotice) savedNotice.classList.add('hidden');

    DramaUtils.showStatus('입력 내용이 초기화되었습니다.', 'info');
  },

  // ===== AI 대본 분석 기능 =====
  analysisData: null,

  /**
   * AI 대본 분석 시작
   */
  async analyzeScript() {
    const scriptTextarea = document.getElementById('full-script');
    const script = scriptTextarea?.value?.trim() || '';

    // 유효성 검사
    if (!script) {
      DramaUtils.showStatus('대본을 입력해주세요.', 'error');
      scriptTextarea?.focus();
      return;
    }

    if (script.length < 100) {
      DramaUtils.showStatus('대본이 너무 짧습니다. (최소 100자 이상)', 'error');
      return;
    }

    const config = this.getConfig();
    console.log('[Step1] AI 대본 분석 시작 - 길이:', script.length, '자');

    // UI 상태 변경
    const analyzeBtn = document.getElementById('btn-analyze-script');
    const progressPanel = document.getElementById('analysis-progress');
    const progressBar = document.getElementById('analysis-progress-bar');
    const progressText = document.getElementById('analysis-progress-text');
    const resultPanel = document.getElementById('analysis-result');

    if (analyzeBtn) {
      analyzeBtn.disabled = true;
      analyzeBtn.innerHTML = '<span class="btn-icon">⏳</span> 분석 중...';
    }
    if (progressPanel) progressPanel.classList.remove('hidden');
    if (progressBar) progressBar.style.width = '20%';
    if (progressText) progressText.textContent = 'AI가 대본을 읽고 있습니다...';

    try {
      // API 호출
      const response = await fetch('/api/drama/analyze-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: script,
          channelType: config.channelType,
          protagonistGender: config.protagonistGender
        })
      });

      if (progressBar) progressBar.style.width = '60%';
      if (progressText) progressText.textContent = '씬과 샷을 분리하고 있습니다...';

      const data = await response.json();

      if (!data.ok) {
        throw new Error(data.error || '대본 분석 실패');
      }

      // 분석 결과 저장
      this.analysisData = {
        character: data.character,
        scenes: data.scenes,
        thumbnailSuggestion: data.thumbnailSuggestion,
        totalShots: data.totalShots,
        originalScript: script
      };

      if (progressBar) progressBar.style.width = '100%';
      if (progressText) progressText.textContent = `분석 완료! (${data.scenes?.length || 0}개 씬, ${data.totalShots || 0}개 샷)`;

      console.log('[Step1] 분석 완료:', this.analysisData);

      // 결과 렌더링
      setTimeout(() => {
        if (progressPanel) progressPanel.classList.add('hidden');
        this.renderAnalysisResult();
      }, 1000);

      DramaUtils.showStatus(`대본 분석 완료! ${data.scenes?.length || 0}개 씬, ${data.totalShots || 0}개 샷`, 'success');

    } catch (error) {
      console.error('[Step1] 분석 오류:', error);
      if (progressBar) progressBar.style.width = '0%';
      if (progressText) progressText.textContent = `오류: ${error.message}`;
      DramaUtils.showStatus('대본 분석 실패: ' + error.message, 'error');
    } finally {
      if (analyzeBtn) {
        analyzeBtn.disabled = false;
        analyzeBtn.innerHTML = '<span class="btn-icon">🤖</span> AI 대본 분석하기';
      }
    }
  },

  /**
   * 분석 결과 UI 렌더링 (씬/샷 트리)
   */
  renderAnalysisResult() {
    const resultPanel = document.getElementById('analysis-result');
    const treeContainer = document.getElementById('scene-shot-tree');
    const saveBtn = document.getElementById('btn-save-script');

    if (!this.analysisData || !treeContainer) {
      console.error('[Step1] 분석 데이터 없음');
      return;
    }

    const { character, scenes, thumbnailSuggestion } = this.analysisData;

    // 캐릭터 정보 + 씬/샷 트리 구조 생성
    let html = '';

    // 캐릭터 카드
    if (character) {
      html += `
        <div class="character-summary">
          <h4>👤 주인공 정보</h4>
          <div class="character-detail">
            <span class="char-name">${character.name || '주인공'}</span>
            <span class="char-age">${character.age || '?'}세</span>
            <span class="char-gender">${character.gender === 'female' ? '여성' : '남성'}</span>
          </div>
          <p class="char-appearance">${character.appearance || ''}</p>
        </div>
      `;
    }

    // 씬/샷 트리
    if (scenes && scenes.length > 0) {
      html += '<div class="scene-tree">';

      scenes.forEach((scene, sceneIdx) => {
        const shots = scene.shots || [];
        html += `
          <div class="scene-node" data-scene-id="${scene.sceneId}">
            <div class="scene-header">
              <span class="scene-toggle" onclick="DramaStep1.toggleScene('${scene.sceneId}')">▼</span>
              <span class="scene-title">🎬 ${scene.title || `씬 ${sceneIdx + 1}`}</span>
              <span class="scene-shot-count">${shots.length}개 샷</span>
            </div>
            <div class="shot-list" id="shots-${scene.sceneId}">
        `;

        shots.forEach((shot, shotIdx) => {
          html += `
            <div class="shot-node" data-shot-id="${shot.shotId}">
              <div class="shot-header">
                <span class="shot-number">${shotIdx + 1}</span>
                <span class="shot-id">${shot.shotId}</span>
              </div>
              <div class="shot-content">
                <div class="shot-field">
                  <label>🖼️ 이미지 프롬프트 (영문)</label>
                  <textarea class="shot-prompt"
                            data-scene="${sceneIdx}"
                            data-shot="${shotIdx}"
                            rows="3">${shot.imagePrompt || ''}</textarea>
                </div>
                <div class="shot-field">
                  <label>🎙️ 나레이션 (한글)</label>
                  <textarea class="shot-narration"
                            data-scene="${sceneIdx}"
                            data-shot="${shotIdx}"
                            rows="2">${shot.narration || ''}</textarea>
                </div>
              </div>
            </div>
          `;
        });

        html += `
            </div>
          </div>
        `;
      });

      html += '</div>';
    }

    // 썸네일 제안
    if (thumbnailSuggestion) {
      html += `
        <div class="thumbnail-suggestion">
          <h4>🎨 썸네일 제안</h4>
          <p><strong>핵심 감정:</strong> ${thumbnailSuggestion.mainEmotion || '-'}</p>
          <p><strong>텍스트:</strong> ${thumbnailSuggestion.textSuggestion || '-'}</p>
        </div>
      `;
    }

    treeContainer.innerHTML = html;
    if (resultPanel) resultPanel.classList.remove('hidden');
    if (saveBtn) saveBtn.classList.remove('hidden');
  },

  /**
   * 씬 접기/펼치기 토글
   */
  toggleScene(sceneId) {
    const shotList = document.getElementById(`shots-${sceneId}`);
    const sceneNode = document.querySelector(`.scene-node[data-scene-id="${sceneId}"]`);
    const toggle = sceneNode?.querySelector('.scene-toggle');

    if (shotList) {
      const isCollapsed = shotList.classList.toggle('collapsed');
      if (toggle) toggle.textContent = isCollapsed ? '▶' : '▼';
    }
  },

  /**
   * 분석 결과 수정사항 수집
   */
  collectAnalysisData() {
    if (!this.analysisData) return null;

    // 수정된 데이터 수집
    const scenes = [...this.analysisData.scenes];

    // 각 샷의 수정된 내용 반영
    document.querySelectorAll('.shot-prompt').forEach(textarea => {
      const sceneIdx = parseInt(textarea.dataset.scene);
      const shotIdx = parseInt(textarea.dataset.shot);
      if (scenes[sceneIdx]?.shots?.[shotIdx]) {
        scenes[sceneIdx].shots[shotIdx].imagePrompt = textarea.value.trim();
      }
    });

    document.querySelectorAll('.shot-narration').forEach(textarea => {
      const sceneIdx = parseInt(textarea.dataset.scene);
      const shotIdx = parseInt(textarea.dataset.shot);
      if (scenes[sceneIdx]?.shots?.[shotIdx]) {
        scenes[sceneIdx].shots[shotIdx].narration = textarea.value.trim();
      }
    });

    return {
      ...this.analysisData,
      scenes: scenes
    };
  },

  /**
   * 분석 결과 저장 및 다음 단계 이동
   */
  saveAnalyzedScript() {
    const data = this.collectAnalysisData();
    if (!data) {
      DramaUtils.showStatus('분석 데이터가 없습니다. 먼저 대본을 분석해주세요.', 'error');
      return;
    }

    const config = this.getConfig();

    // 총 샷 수 계산
    const totalShots = data.scenes.reduce((sum, scene) => sum + (scene.shots?.length || 0), 0);

    if (totalShots === 0) {
      DramaUtils.showStatus('저장할 샷이 없습니다.', 'error');
      return;
    }

    console.log('[Step1] 분석 결과 저장:', {
      character: data.character?.name,
      sceneCount: data.scenes.length,
      totalShots: totalShots
    });

    // 데이터 구조화
    this.currentScript = {
      type: 'analyzed',
      config: config,
      character: data.character,
      scenes: data.scenes,
      thumbnailSuggestion: data.thumbnailSuggestion,
      originalScript: data.originalScript,
      createdAt: new Date().toISOString()
    };

    // 전역 세션에 저장
    dramaApp.session.script = JSON.stringify(this.currentScript);
    dramaApp.session.scriptData = this.currentScript;
    dramaApp.session.protagonistGender = config.protagonistGender;
    dramaApp.session.ttsVoiceQuality = config.ttsVoiceQuality;
    dramaApp.session.ttsVoice = config.ttsVoice;
    dramaApp.session.channelType = config.channelType;

    // DramaSession에도 저장 (localStorage)
    DramaSession.setStepData('step1', this.currentScript);
    DramaMain.saveSessionToStorage();

    // 저장 완료 UI 표시
    const savedNotice = document.getElementById('step1-saved-notice');
    if (savedNotice) savedNotice.classList.remove('hidden');

    DramaUtils.showStatus(`대본 저장 완료! (${data.scenes.length}개 씬, ${totalShots}개 샷)`, 'success');

    // 다음 단계로 이동
    setTimeout(() => {
      DramaMain.completeStep(1);
      DramaMain.goToStep(2);
    }, 1000);
  },

  /**
   * 세션에서 분석 데이터 복원
   */
  restoreAnalyzedData() {
    const data = DramaSession.getStepData('step1');
    if (!data || data.type !== 'analyzed') return;

    console.log('[Step1] 분석 데이터 복원');

    // 원본 대본 복원
    const fullScript = document.getElementById('full-script');
    if (fullScript && data.originalScript) {
      fullScript.value = data.originalScript;
    }

    // 분석 데이터 복원
    this.analysisData = {
      character: data.character,
      scenes: data.scenes,
      thumbnailSuggestion: data.thumbnailSuggestion,
      originalScript: data.originalScript
    };

    // UI 렌더링
    this.renderAnalysisResult();
    this.currentScript = data;
  }
};
