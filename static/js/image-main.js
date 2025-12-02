/**
 * Image Lab - 이미지 제작 (간소화 버전)
 * 대본 분석 → 썸네일 + 씬별 이미지 생성
 */

const ImageMain = {
  // 상태
  currentStep: 1,
  sessionId: null,
  analyzedData: null,
  thumbnailImage: null,
  sceneImages: {},

  /**
   * 초기화
   */
  init() {
    console.log('[ImageMain] Initializing...');
    this.sessionId = this.generateSessionId();
    this.updateSessionInfo();
    console.log('[ImageMain] Ready. Session:', this.sessionId);
  },

  /**
   * 세션 ID 생성
   */
  generateSessionId() {
    return 'img_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  },

  /**
   * 세션 정보 업데이트
   */
  updateSessionInfo() {
    const sessionInfo = document.getElementById('session-info');
    if (sessionInfo) {
      sessionInfo.textContent = `세션: ${this.sessionId.substring(0, 12)}...`;
    }
  },

  /**
   * 새 프로젝트
   */
  newSession() {
    if (confirm('새 프로젝트를 시작하시겠습니까?')) {
      location.reload();
    }
  },

  /**
   * 스텝 이동
   */
  goToStep(step) {
    if (step < 1 || step > 2) return;

    document.querySelectorAll('.step-item').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.step-container').forEach(c => c.classList.remove('active'));

    document.querySelector(`.step-item[data-step="${step}"]`).classList.add('active');
    document.getElementById(`step${step}-container`).classList.add('active');

    this.currentStep = step;
  },

  /**
   * Step 2로 이동
   */
  goToStep2() {
    if (!this.analyzedData || !this.analyzedData.scenes || this.analyzedData.scenes.length === 0) {
      this.showStatus('먼저 대본 분석을 완료해주세요.', 'warning');
      return;
    }

    // 입력값 수집
    this.collectSceneData();

    // Step 2 UI 준비
    this.prepareStep2UI();

    this.goToStep(2);
  },

  /**
   * 씬 데이터 수집 (수정된 값 반영)
   */
  collectSceneData() {
    // 썸네일 정보
    this.analyzedData.thumbnail = {
      title: document.getElementById('thumbnail-title').value,
      prompt: document.getElementById('thumbnail-prompt').value
    };

    // 씬 정보
    document.querySelectorAll('.scene-item').forEach((item, idx) => {
      const narration = item.querySelector('.scene-narration').value;
      const prompt = item.querySelector('.scene-prompt').value;
      if (this.analyzedData.scenes[idx]) {
        this.analyzedData.scenes[idx].narration = narration;
        this.analyzedData.scenes[idx].image_prompt = prompt;
      }
    });
  },

  /**
   * Step 2 UI 준비
   */
  prepareStep2UI() {
    const grid = document.getElementById('scene-images-grid');
    const scenes = this.analyzedData.scenes || [];

    let html = '';
    scenes.forEach((scene, idx) => {
      html += `
        <div class="scene-image-card" data-scene-idx="${idx}">
          <div class="scene-image-card-header">
            <span class="scene-badge">씬 ${idx + 1}</span>
            <button class="btn-small btn-generate" onclick="ImageMain.generateSceneImage(${idx})">생성</button>
          </div>
          <div class="scene-image-container" id="scene-img-container-${idx}">
            <div class="image-placeholder">
              <span>이미지 생성 대기</span>
            </div>
          </div>
          <div class="scene-image-narration">${(scene.narration || '').substring(0, 100)}...</div>
        </div>
      `;
    });

    grid.innerHTML = html || '<div class="empty-message">분석된 씬이 없습니다.</div>';

    // 썸네일 제목 표시
    const titleDisplay = document.getElementById('thumbnail-title-display');
    if (titleDisplay && this.analyzedData.thumbnail?.title) {
      titleDisplay.textContent = this.analyzedData.thumbnail.title;
    }
  },

  /**
   * 대본 분석 (AI)
   */
  async analyzeScript() {
    const script = document.getElementById('full-script').value.trim();
    if (!script) {
      this.showStatus('대본을 입력해주세요.', 'warning');
      return;
    }

    const contentType = document.getElementById('content-type').value;
    const imageStyle = document.getElementById('image-style').value;

    // 진행 상태
    document.getElementById('analysis-progress').classList.remove('hidden');
    document.getElementById('analysis-result').classList.add('hidden');
    document.getElementById('btn-next-step').classList.add('hidden');

    const progressBar = document.getElementById('analysis-progress-bar');
    const progressText = document.getElementById('analysis-progress-text');

    progressBar.style.width = '20%';
    progressText.textContent = 'AI가 대본을 분석하고 있습니다...';

    try {
      const response = await fetch('/api/image/analyze-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: script,
          content_type: contentType,
          image_style: imageStyle
        })
      });

      progressBar.style.width = '80%';

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || 'API 오류');
      }

      const data = await response.json();
      progressBar.style.width = '100%';

      this.analyzedData = data;
      this.renderAnalysisResult(data);

      document.getElementById('analysis-progress').classList.add('hidden');
      document.getElementById('analysis-result').classList.remove('hidden');
      document.getElementById('btn-next-step').classList.remove('hidden');

      this.showStatus('대본 분석 완료!', 'success');

    } catch (error) {
      console.error('[ImageMain] Analyze error:', error);
      document.getElementById('analysis-progress').classList.add('hidden');
      this.showStatus('분석 실패: ' + error.message, 'error');
    }
  },

  /**
   * 분석 결과 렌더링
   */
  renderAnalysisResult(data) {
    // 썸네일 정보
    if (data.thumbnail) {
      // 텍스트 라인 채우기
      const textLines = data.thumbnail.text_lines || [];
      for (let i = 0; i < 4; i++) {
        const input = document.getElementById(`thumb-line-${i}`);
        if (input) {
          input.value = textLines[i] || '';
        }
      }
      // 강조 줄 선택
      const highlightLine = data.thumbnail.highlight_line ?? 2;
      const radio = document.getElementById(`hl-${highlightLine}`);
      if (radio) radio.checked = true;

      // 프롬프트
      document.getElementById('thumbnail-prompt').value = data.thumbnail.prompt || '';
    }

    // 씬 목록
    const container = document.getElementById('scene-list');
    const scenes = data.scenes || [];

    let html = '';
    scenes.forEach((scene, idx) => {
      html += `
        <div class="scene-item" data-scene-idx="${idx}">
          <div class="scene-item-header">
            <span class="scene-badge">씬 ${idx + 1}</span>
          </div>
          <div class="form-group">
            <label>나레이션 (한글)</label>
            <textarea class="scene-narration" rows="2">${scene.narration || ''}</textarea>
          </div>
          <div class="form-group">
            <label>이미지 프롬프트 (영문)</label>
            <textarea class="scene-prompt" rows="2">${scene.image_prompt || ''}</textarea>
          </div>
        </div>
      `;
    });

    container.innerHTML = html || '<div class="empty-message">분석된 씬이 없습니다.</div>';
  },

  /**
   * 썸네일 텍스트 라인 가져오기
   */
  getThumbnailTextLines() {
    const lines = [];
    for (let i = 0; i < 4; i++) {
      const input = document.getElementById(`thumb-line-${i}`);
      if (input && input.value.trim()) {
        lines.push(input.value.trim());
      }
    }
    return lines;
  },

  /**
   * 강조할 줄 인덱스 가져오기
   */
  getHighlightLineIndex() {
    const checked = document.querySelector('input[name="highlight-line"]:checked');
    return checked ? parseInt(checked.value) : 2;
  },

  /**
   * 썸네일 이미지 생성 (이미지 + 텍스트 오버레이)
   */
  async generateThumbnail() {
    const prompt = document.getElementById('thumbnail-prompt')?.value || this.analyzedData?.thumbnail?.prompt;
    if (!prompt) {
      this.showStatus('썸네일 프롬프트가 없습니다.', 'warning');
      return;
    }

    const container = document.getElementById('thumbnail-container');
    container.innerHTML = '<div class="image-placeholder loading"><span>썸네일 이미지 생성 중...</span></div>';

    try {
      const model = document.getElementById('image-model').value;
      const ratio = document.getElementById('image-ratio').value;

      // 1단계: 이미지 생성
      const response = await fetch('/api/drama/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt,
          imageProvider: model,
          style: 'thumbnail',
          size: ratio
        })
      });

      const data = await response.json();
      if (!data.ok && data.error) {
        throw new Error(data.error);
      }
      if (!data.imageUrl) {
        throw new Error('이미지 URL이 없습니다.');
      }

      // 2단계: 텍스트 오버레이
      const textLines = this.getThumbnailTextLines();
      if (textLines.length > 0) {
        container.innerHTML = '<div class="image-placeholder loading"><span>텍스트 오버레이 적용 중...</span></div>';

        const highlightLine = this.getHighlightLineIndex();
        const overlayResponse = await fetch('/api/drama/thumbnail-overlay', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            imageUrl: data.imageUrl,
            textLines: textLines,
            highlightLines: [highlightLine],
            textColor: '#FFFFFF',
            highlightColor: '#FFD700',
            outlineColor: '#000000',
            outlineWidth: 4,
            fontSize: 60,
            position: 'left'
          })
        });

        const overlayData = await overlayResponse.json();
        if (overlayData.ok && overlayData.imageUrl) {
          container.innerHTML = `<img src="${overlayData.imageUrl}" alt="썸네일">`;
          this.thumbnailImage = overlayData.imageUrl;
        } else {
          // 오버레이 실패 시 원본 이미지 사용
          console.warn('[ImageMain] Overlay failed, using original:', overlayData.error);
          container.innerHTML = `<img src="${data.imageUrl}" alt="썸네일">`;
          this.thumbnailImage = data.imageUrl;
        }
      } else {
        // 텍스트 없으면 원본 이미지 사용
        container.innerHTML = `<img src="${data.imageUrl}" alt="썸네일">`;
        this.thumbnailImage = data.imageUrl;
      }

      this.updateDownloadSection();
      this.showStatus('썸네일 생성 완료!', 'success');

    } catch (error) {
      console.error('[ImageMain] Thumbnail error:', error);
      container.innerHTML = '<div class="image-placeholder"><span style="color:red;">생성 실패</span></div>';
      this.showStatus('썸네일 생성 실패: ' + error.message, 'error');
    }
  },

  /**
   * 단일 씬 이미지 생성
   */
  async generateSceneImage(idx) {
    const scene = this.analyzedData?.scenes?.[idx];
    if (!scene || !scene.image_prompt) {
      this.showStatus('이미지 프롬프트가 없습니다.', 'warning');
      return;
    }

    const container = document.getElementById(`scene-img-container-${idx}`);
    container.innerHTML = '<div class="image-placeholder loading"><span>생성 중...</span></div>';

    try {
      const model = document.getElementById('image-model').value;
      const ratio = document.getElementById('image-ratio').value;
      const style = document.getElementById('image-style')?.value || 'nostalgic';

      const response = await fetch('/api/drama/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: scene.image_prompt,
          imageProvider: model,
          style: style,
          size: ratio
        })
      });

      const data = await response.json();
      if (!data.ok && data.error) {
        throw new Error(data.error);
      }
      if (data.imageUrl) {
        container.innerHTML = `<img src="${data.imageUrl}" alt="씬 ${idx + 1}">`;
        this.sceneImages[idx] = data.imageUrl;
        this.updateDownloadSection();
      }

    } catch (error) {
      console.error('[ImageMain] Scene image error:', error);
      container.innerHTML = '<div class="image-placeholder"><span style="color:red;">실패</span></div>';
      this.showStatus(`씬 ${idx + 1} 이미지 생성 실패: ${error.message}`, 'error');
    }
  },

  /**
   * 전체 씬 이미지 생성
   */
  async generateAllSceneImages() {
    const scenes = this.analyzedData?.scenes || [];
    if (scenes.length === 0) return;

    const progressText = document.getElementById('scene-progress-text');

    for (let i = 0; i < scenes.length; i++) {
      progressText.textContent = `(${i + 1}/${scenes.length})`;
      await this.generateSceneImage(i);
      await this.sleep(500); // Rate limiting
    }

    progressText.textContent = '완료!';
    this.showStatus('모든 씬 이미지 생성 완료!', 'success');
  },

  /**
   * 다운로드 섹션 업데이트
   */
  updateDownloadSection() {
    const downloadSection = document.getElementById('download-section');
    const countEl = document.getElementById('download-count');

    const sceneCount = Object.keys(this.sceneImages).length;
    const totalCount = sceneCount + (this.thumbnailImage ? 1 : 0);

    if (totalCount > 0) {
      downloadSection.classList.remove('hidden');
      countEl.textContent = `생성된 이미지: ${totalCount}개 (썸네일: ${this.thumbnailImage ? 1 : 0}, 씬: ${sceneCount})`;
    }
  },

  /**
   * 전체 이미지 ZIP 다운로드
   */
  async downloadAllImages() {
    const images = [];

    if (this.thumbnailImage) {
      images.push({ name: 'thumbnail.png', url: this.thumbnailImage });
    }

    Object.entries(this.sceneImages).forEach(([idx, url]) => {
      images.push({ name: `scene_${parseInt(idx) + 1}.png`, url: url });
    });

    if (images.length === 0) {
      this.showStatus('다운로드할 이미지가 없습니다.', 'warning');
      return;
    }

    this.showStatus('이미지 ZIP 생성 중...', 'info');

    try {
      const response = await fetch('/api/image/download-zip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ images: images })
      });

      if (!response.ok) throw new Error('ZIP 생성 실패');

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `images_${this.sessionId}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      this.showStatus('다운로드 시작!', 'success');

    } catch (error) {
      console.error('[ImageMain] Download error:', error);
      // Fallback: 개별 다운로드
      this.downloadImagesIndividually(images);
    }
  },

  /**
   * 개별 이미지 다운로드 (Fallback)
   */
  downloadImagesIndividually(images) {
    images.forEach((img, idx) => {
      setTimeout(() => {
        const a = document.createElement('a');
        a.href = img.url;
        a.download = img.name;
        a.target = '_blank';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }, idx * 500);
    });

    this.showStatus(`${images.length}개 이미지 다운로드 중...`, 'info');
  },

  /**
   * 썸네일만 다운로드
   */
  downloadThumbnail() {
    if (!this.thumbnailImage) {
      this.showStatus('썸네일 이미지가 없습니다.', 'warning');
      return;
    }

    const a = document.createElement('a');
    a.href = this.thumbnailImage;
    a.download = 'thumbnail.png';
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    this.showStatus('썸네일 다운로드 시작!', 'success');
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
  ImageMain.init();
});
