/**
 * Product Lab - 상품 영상 제작
 * Main JavaScript Module
 */

const ProductMain = {
  // 현재 상태
  currentStep: 1,
  sessionId: null,
  productData: null,
  analyzedScenes: null,
  generatedImages: {},
  generatedAudios: {},

  /**
   * 초기화
   */
  init() {
    console.log('[ProductMain] Initializing...');
    this.sessionId = this.generateSessionId();
    this.setupVoiceCardEvents();
    this.updateSessionInfo();
    console.log('[ProductMain] Ready. Session:', this.sessionId);
  },

  /**
   * 세션 ID 생성
   */
  generateSessionId() {
    return 'prod_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  },

  /**
   * 세션 정보 업데이트
   */
  updateSessionInfo() {
    const sessionInfo = document.getElementById('session-info');
    if (sessionInfo) {
      sessionInfo.textContent = `세션: ${this.sessionId.substring(0, 15)}...`;
    }
  },

  /**
   * 새 프로젝트 시작
   */
  newSession() {
    if (confirm('새 프로젝트를 시작하시겠습니까? 현재 작업 내용은 저장되지 않습니다.')) {
      location.reload();
    }
  },

  /**
   * 스텝 이동
   */
  goToStep(step) {
    if (step < 1 || step > 4) return;

    // 이전 스텝 비활성화
    document.querySelectorAll('.step-item').forEach(item => {
      item.classList.remove('active');
    });
    document.querySelectorAll('.step-container').forEach(container => {
      container.classList.remove('active');
    });

    // 새 스텝 활성화
    document.querySelector(`.step-item[data-step="${step}"]`).classList.add('active');
    document.getElementById(`step${step}-container`).classList.add('active');

    this.currentStep = step;
    console.log('[ProductMain] Moved to step', step);
  },

  /**
   * 음성 카드 이벤트 설정
   */
  setupVoiceCardEvents() {
    document.querySelectorAll('.voice-card').forEach(card => {
      card.addEventListener('click', (e) => {
        if (e.target.classList.contains('btn-preview')) return;

        document.querySelectorAll('.voice-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');

        const radio = card.querySelector('input[type="radio"]');
        if (radio) {
          radio.checked = true;
          document.getElementById('selected-voice').value = radio.value;
        }
      });
    });
  },

  /**
   * 음성 미리듣기
   */
  async previewVoice(voiceId, gender) {
    const sampleText = gender === 'female'
      ? '안녕하세요, 오늘 소개해드릴 제품입니다.'
      : '안녕하세요, 오늘 소개해드릴 제품입니다.';

    this.showStatus('음성 미리듣기 생성 중...', 'info');

    try {
      const response = await fetch('/api/drama/step3/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          texts: [sampleText],
          voice_id: voiceId,
          speed: 1.0
        })
      });

      if (!response.ok) throw new Error('TTS 생성 실패');

      const data = await response.json();
      if (data.audio_files && data.audio_files.length > 0) {
        const player = document.getElementById('voice-preview-player');
        player.src = data.audio_files[0];
        player.play();
        this.showStatus('음성 재생 중...', 'success');
      }
    } catch (error) {
      console.error('[ProductMain] Preview voice error:', error);
      this.showStatus('음성 미리듣기 실패: ' + error.message, 'error');
    }
  },

  /**
   * 대본 분석 (AI)
   */
  async analyzeScript() {
    const productName = document.getElementById('product-name').value.trim();
    const productCategory = document.getElementById('product-category').value;
    const script = document.getElementById('product-script').value.trim();

    if (!script) {
      this.showStatus('대본을 입력해주세요.', 'warning');
      return;
    }

    // 진행 상태 표시
    document.getElementById('analysis-progress').classList.remove('hidden');
    document.getElementById('analysis-result').classList.add('hidden');
    document.getElementById('btn-save-script').classList.add('hidden');

    const progressBar = document.getElementById('analysis-progress-bar');
    const progressText = document.getElementById('analysis-progress-text');

    progressBar.style.width = '20%';
    progressText.textContent = 'AI가 대본을 분석하고 있습니다...';

    try {
      const response = await fetch('/api/product/analyze-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_name: productName || '상품',
          category: productCategory,
          script: script
        })
      });

      progressBar.style.width = '80%';
      progressText.textContent = '분석 결과 처리 중...';

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || 'API 오류');
      }

      const data = await response.json();
      progressBar.style.width = '100%';

      // 분석 결과 저장
      this.analyzedScenes = data.scenes || [];
      this.productData = {
        name: productName,
        category: productCategory,
        script: script
      };

      // 결과 표시
      this.renderAnalysisResult(data);

      // UI 업데이트
      document.getElementById('analysis-progress').classList.add('hidden');
      document.getElementById('analysis-result').classList.remove('hidden');
      document.getElementById('btn-save-script').classList.remove('hidden');

      this.showStatus('대본 분석 완료!', 'success');

    } catch (error) {
      console.error('[ProductMain] Analyze script error:', error);
      document.getElementById('analysis-progress').classList.add('hidden');
      this.showStatus('분석 실패: ' + error.message, 'error');
    }
  },

  /**
   * 분석 결과 렌더링
   */
  renderAnalysisResult(data) {
    const container = document.getElementById('scene-shot-tree');
    const scenes = data.scenes || [];

    if (scenes.length === 0) {
      container.innerHTML = '<div class="empty-message">분석된 씬이 없습니다.</div>';
      return;
    }

    let html = '';
    scenes.forEach((scene, idx) => {
      html += `
        <div class="scene-block" data-scene-idx="${idx}">
          <div class="scene-header">
            <span class="scene-badge">씬 ${idx + 1}</span>
            <button class="btn-toggle" onclick="ProductMain.toggleScene(${idx})">접기/펼치기</button>
          </div>
          <div class="scene-content" id="scene-content-${idx}">
            <div class="form-group">
              <label>나레이션</label>
              <textarea class="scene-narration" rows="3" data-scene="${idx}">${scene.narration || ''}</textarea>
            </div>
            <div class="form-group">
              <label>이미지 프롬프트 (영문)</label>
              <textarea class="scene-prompt" rows="2" data-scene="${idx}">${scene.image_prompt || ''}</textarea>
            </div>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  },

  /**
   * 씬 접기/펼치기
   */
  toggleScene(idx) {
    const content = document.getElementById(`scene-content-${idx}`);
    if (content) {
      content.classList.toggle('collapsed');
    }
  },

  /**
   * 분석 결과 저장 및 다음 단계
   */
  saveAnalyzedScript() {
    // 수정된 내용 수집
    const scenes = [];
    document.querySelectorAll('.scene-block').forEach((block, idx) => {
      const narration = block.querySelector('.scene-narration').value;
      const prompt = block.querySelector('.scene-prompt').value;
      scenes.push({
        scene_number: idx + 1,
        narration: narration,
        image_prompt: prompt
      });
    });

    this.analyzedScenes = scenes;
    console.log('[ProductMain] Saved scenes:', scenes);

    // Step 2로 이동
    this.prepareStep2();
    this.goToStep(2);
    this.showStatus('대본 저장 완료! Step 2로 이동합니다.', 'success');
  },

  /**
   * Step 2 준비
   */
  prepareStep2() {
    const container = document.getElementById('scene-image-list');
    const scenes = this.analyzedScenes || [];

    if (scenes.length === 0) {
      container.innerHTML = '<div class="empty-message">분석된 씬이 없습니다.</div>';
      return;
    }

    let html = '';
    scenes.forEach((scene, idx) => {
      html += `
        <div class="scene-card product-scene-card" data-scene-idx="${idx}">
          <div class="scene-card-header">
            <span class="scene-badge">씬 ${idx + 1}</span>
          </div>
          <div class="scene-image-placeholder" id="scene-image-${idx}">
            <span>이미지 생성 대기 중</span>
          </div>
          <div class="scene-desc">${scene.narration || ''}</div>
          <div class="prompt-preview" title="${scene.image_prompt || ''}">${(scene.image_prompt || '').substring(0, 80)}...</div>
          <div class="scene-actions">
            <button class="btn-small" onclick="ProductMain.generateImage(${idx})">이미지 생성</button>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
    document.getElementById('scene-images-area').classList.remove('hidden');
  },

  /**
   * 단일 이미지 생성
   */
  async generateImage(idx) {
    const scene = this.analyzedScenes[idx];
    if (!scene) return;

    const placeholder = document.getElementById(`scene-image-${idx}`);
    placeholder.innerHTML = '<div class="loading-spinner-small"></div><span>생성 중...</span>';

    try {
      const model = document.getElementById('image-model').value;
      const style = document.getElementById('image-style').value;
      const ratio = document.getElementById('image-ratio').value;

      const response = await fetch('/api/drama/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: scene.image_prompt,
          model: model,
          style: style,
          ratio: ratio
        })
      });

      if (!response.ok) throw new Error('이미지 생성 실패');

      const data = await response.json();
      if (data.image_url) {
        placeholder.innerHTML = `<img src="${data.image_url}" alt="씬 ${idx + 1}" style="width:100%;height:100%;object-fit:cover;">`;
        this.generatedImages[idx] = data.image_url;
        this.checkStep2Complete();
      }

    } catch (error) {
      console.error('[ProductMain] Generate image error:', error);
      placeholder.innerHTML = `<span style="color:red;">생성 실패</span>`;
      this.showStatus('이미지 생성 실패: ' + error.message, 'error');
    }
  },

  /**
   * 모든 이미지 생성
   */
  async generateAllImages() {
    const scenes = this.analyzedScenes || [];
    this.showStatus('모든 이미지 생성 중...', 'info');

    for (let i = 0; i < scenes.length; i++) {
      await this.generateImage(i);
      await this.sleep(500); // Rate limiting
    }

    this.showStatus('모든 이미지 생성 완료!', 'success');
  },

  /**
   * Step 2 완료 체크
   */
  checkStep2Complete() {
    const scenes = this.analyzedScenes || [];
    const allDone = scenes.every((_, idx) => this.generatedImages[idx]);

    if (allDone) {
      document.getElementById('step2-next').classList.remove('hidden');
    }
  },

  /**
   * TTS 생성
   */
  async generateTTS() {
    const scenes = this.analyzedScenes || [];
    if (scenes.length === 0) {
      this.showStatus('먼저 대본 분석을 완료해주세요.', 'warning');
      return;
    }

    const voice = document.getElementById('selected-voice').value;
    const speed = parseFloat(document.getElementById('speech-rate').value);

    const progressPanel = document.getElementById('tts-progress');
    const progressBar = document.getElementById('tts-progress-bar');
    const progressText = document.getElementById('tts-progress-text');

    progressPanel.classList.remove('hidden');
    progressBar.style.width = '10%';
    progressText.textContent = '음성 생성 준비 중...';

    try {
      const texts = scenes.map(s => s.narration).filter(t => t);

      const response = await fetch('/api/drama/step3/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          texts: texts,
          voice_id: voice,
          speed: speed
        })
      });

      progressBar.style.width = '80%';

      if (!response.ok) throw new Error('TTS 생성 실패');

      const data = await response.json();
      progressBar.style.width = '100%';

      // 오디오 저장
      if (data.audio_files) {
        data.audio_files.forEach((url, idx) => {
          this.generatedAudios[idx] = url;
        });
      }

      // 결과 표시
      this.renderTTSResult(data.audio_files || []);

      progressPanel.classList.add('hidden');
      document.getElementById('tts-result-area').classList.remove('hidden');
      document.getElementById('step3-next').classList.remove('hidden');

      this.showStatus('음성 생성 완료!', 'success');

    } catch (error) {
      console.error('[ProductMain] TTS error:', error);
      progressPanel.classList.add('hidden');
      this.showStatus('TTS 생성 실패: ' + error.message, 'error');
    }
  },

  /**
   * TTS 결과 렌더링
   */
  renderTTSResult(audioFiles) {
    const container = document.getElementById('tts-audio-list');

    let html = '';
    audioFiles.forEach((url, idx) => {
      html += `
        <div class="tts-audio-item">
          <span class="audio-label">씬 ${idx + 1}</span>
          <audio controls src="${url}"></audio>
        </div>
      `;
    });

    container.innerHTML = html;
  },

  /**
   * 씬별 클립 생성
   */
  async createSceneClips() {
    const scenes = this.analyzedScenes || [];
    if (scenes.length === 0) {
      this.showStatus('먼저 대본 분석을 완료해주세요.', 'warning');
      return;
    }

    // 이미지와 오디오 체크
    const hasImages = Object.keys(this.generatedImages).length > 0;
    const hasAudios = Object.keys(this.generatedAudios).length > 0;

    if (!hasImages || !hasAudios) {
      this.showStatus('이미지와 음성을 먼저 생성해주세요.', 'warning');
      return;
    }

    const progressPanel = document.getElementById('clip-progress');
    const progressBar = document.getElementById('clip-progress-bar');
    const progressText = document.getElementById('clip-progress-text');

    progressPanel.classList.remove('hidden');
    progressBar.style.width = '10%';
    progressText.textContent = '클립 생성 준비 중...';

    try {
      // 클립 데이터 준비
      const clips = scenes.map((scene, idx) => ({
        scene_number: idx + 1,
        image_url: this.generatedImages[idx],
        audio_url: this.generatedAudios[idx],
        narration: scene.narration
      })).filter(c => c.image_url && c.audio_url);

      const response = await fetch('/api/drama/generate-scene-clips-zip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clips: clips })
      });

      progressBar.style.width = '90%';

      if (!response.ok) throw new Error('클립 생성 실패');

      // ZIP 다운로드
      const blob = await response.blob();
      this.zipBlob = blob;

      progressBar.style.width = '100%';
      progressPanel.classList.add('hidden');
      document.getElementById('clip-download-area').classList.remove('hidden');

      this.showStatus('클립 생성 완료! 다운로드 버튼을 클릭하세요.', 'success');

    } catch (error) {
      console.error('[ProductMain] Create clips error:', error);
      progressPanel.classList.add('hidden');
      this.showStatus('클립 생성 실패: ' + error.message, 'error');
    }
  },

  /**
   * ZIP 다운로드 트리거
   */
  triggerDownload() {
    if (!this.zipBlob) {
      this.showStatus('다운로드할 파일이 없습니다.', 'warning');
      return;
    }

    const url = URL.createObjectURL(this.zipBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `product_clips_${this.sessionId}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    this.showStatus('다운로드가 시작되었습니다.', 'success');
  },

  /**
   * 상태 메시지 표시
   */
  showStatus(message, type = 'info') {
    const statusBar = document.getElementById('status-bar');
    statusBar.textContent = message;
    statusBar.className = 'status-bar show status-' + type;

    setTimeout(() => {
      statusBar.classList.remove('show');
    }, 3000);
  },

  /**
   * 유틸: sleep
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
};

// DOM 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
  ProductMain.init();
});
