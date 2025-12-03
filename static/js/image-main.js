/**
 * Image Lab - 이미지 제작 (새 UI 버전)
 * 좌측: 대본 입력 + 유튜브 메타데이터
 * 우측: 썸네일 + 씬별 이미지 생성
 */

const ImageMain = {
  // 상태
  sessionId: null,
  analyzedData: null,
  thumbnailImages: [],   // 썸네일 이미지 URL 배열
  sceneImages: {},       // { index: imageUrl }
  selectedThumbnailText: null,  // 선택된 썸네일 텍스트

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
    const imageCount = parseInt(document.getElementById('image-count').value) || 4;

    // 분석 중 오버레이 표시
    document.getElementById('analyzing-overlay').classList.remove('hidden');
    document.getElementById('result-empty').style.display = 'none';
    document.getElementById('btn-analyze').disabled = true;

    try {
      const response = await fetch('/api/image/analyze-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: script,
          content_type: contentType,
          image_style: imageStyle,
          image_count: imageCount
        })
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || 'API 오류');
      }

      const data = await response.json();
      this.analyzedData = data;

      // 유튜브 메타데이터 렌더링
      this.renderYoutubeMetadata(data.youtube || {});

      // 씬 카드 렌더링
      this.renderSceneCards(data.scenes || []);

      // 썸네일 텍스트 옵션 렌더링
      this.renderThumbnailTextOptions(data.thumbnail || {});

      // 분석 완료
      document.getElementById('analyzing-overlay').classList.add('hidden');
      this.showStatus(`대본 분석 완료! ${data.scenes?.length || 0}개 씬 추출됨`, 'success');

    } catch (error) {
      console.error('[ImageMain] Analyze error:', error);
      document.getElementById('analyzing-overlay').classList.add('hidden');
      document.getElementById('result-empty').style.display = 'flex';
      this.showStatus('분석 실패: ' + error.message, 'error');
    } finally {
      document.getElementById('btn-analyze').disabled = false;
    }
  },

  /**
   * 유튜브 메타데이터 렌더링
   */
  renderYoutubeMetadata(youtube) {
    const section = document.getElementById('youtube-meta-section');
    const titlesContainer = document.getElementById('youtube-titles');
    const descriptionEl = document.getElementById('youtube-description');

    if (!youtube || (!youtube.titles && !youtube.description)) {
      section.classList.add('hidden');
      return;
    }

    // 제목 옵션 렌더링
    const titles = youtube.titles || [];
    let titlesHtml = '';
    titles.forEach((title, idx) => {
      titlesHtml += `
        <div class="title-option" onclick="ImageMain.selectTitle(${idx})">
          <input type="radio" name="youtube-title" value="${idx}" ${idx === 0 ? 'checked' : ''}>
          <span class="title-text">${this.escapeHtml(title)}</span>
          <button class="btn-copy-small" onclick="event.stopPropagation(); ImageMain.copyText('${this.escapeHtml(title).replace(/'/g, "\\'")}')">복사</button>
        </div>
      `;
    });
    titlesContainer.innerHTML = titlesHtml;

    // 설명란 렌더링
    descriptionEl.value = youtube.description || '';

    section.classList.remove('hidden');
  },

  /**
   * 제목 선택
   */
  selectTitle(idx) {
    document.querySelectorAll('.title-option').forEach((el, i) => {
      el.classList.toggle('selected', i === idx);
      el.querySelector('input').checked = (i === idx);
    });
  },

  /**
   * 썸네일 텍스트 옵션 렌더링
   */
  renderThumbnailTextOptions(thumbnail) {
    const section = document.getElementById('thumbnail-section');
    const optionsContainer = document.getElementById('thumbnail-text-options');
    const generateBtn = document.getElementById('btn-generate-with-text');

    if (!thumbnail || !thumbnail.text_options || thumbnail.text_options.length === 0) {
      // text_options가 없으면 기존 text_lines 사용 시도
      if (thumbnail.text_lines && thumbnail.text_lines.length > 0) {
        this.selectedThumbnailText = thumbnail.text_lines[0];
        generateBtn.disabled = false;
      }
      section.classList.remove('hidden');
      return;
    }

    const options = thumbnail.text_options;
    let optionsHtml = '';
    options.forEach((text, idx) => {
      optionsHtml += `
        <div class="text-option" onclick="ImageMain.selectThumbnailText(${idx}, '${this.escapeHtml(text).replace(/'/g, "\\'")}')">
          <input type="radio" name="thumbnail-text" value="${idx}">
          <span class="text-preview">${this.escapeHtml(text)}</span>
        </div>
      `;
    });
    optionsContainer.innerHTML = optionsHtml;

    section.classList.remove('hidden');
    generateBtn.disabled = true;  // 선택 전까지 비활성화
  },

  /**
   * 썸네일 텍스트 선택
   */
  selectThumbnailText(idx, text) {
    this.selectedThumbnailText = text;

    document.querySelectorAll('.text-option').forEach((el, i) => {
      el.classList.toggle('selected', i === idx);
      el.querySelector('input').checked = (i === idx);
    });

    // 생성 버튼 활성화
    document.getElementById('btn-generate-with-text').disabled = false;
  },

  /**
   * 선택한 텍스트로 썸네일 생성
   */
  async generateThumbnailsWithText() {
    if (!this.analyzedData) {
      this.showStatus('먼저 대본을 분석해주세요.', 'warning');
      return;
    }

    if (!this.selectedThumbnailText) {
      this.showStatus('썸네일 텍스트를 선택해주세요.', 'warning');
      return;
    }

    const thumbnailData = this.analyzedData.thumbnail || {};
    const prompt = thumbnailData.prompt || '';
    const textColor = thumbnailData.text_color || '#FFD700';
    const outlineColor = thumbnailData.outline_color || '#000000';

    if (!prompt) {
      this.showStatus('썸네일 프롬프트가 없습니다.', 'warning');
      return;
    }

    // 썸네일 그리드 표시
    document.getElementById('thumbnail-grid').style.display = 'flex';

    const model = document.getElementById('image-model').value;
    const textLines = [this.selectedThumbnailText];

    // 텍스트 미리보기 표시
    for (let i = 0; i < 2; i++) {
      const textEl = document.getElementById(`thumbnail-text-${i}`);
      if (textEl) {
        textEl.textContent = this.selectedThumbnailText;
      }
    }

    // 병렬 생성
    const promises = [0, 1].map(idx => this.generateSingleThumbnail(idx, prompt, textLines, model, textColor, outlineColor));
    await Promise.all(promises);

    this.showStatus('썸네일 2개 생성 완료!', 'success');
  },

  /**
   * 씬 카드 렌더링
   */
  renderSceneCards(scenes) {
    const container = document.getElementById('scene-cards');

    if (!scenes || scenes.length === 0) {
      container.style.display = 'none';
      document.getElementById('result-empty').style.display = 'flex';
      return;
    }

    let html = '';
    scenes.forEach((scene, idx) => {
      html += `
        <div class="scene-card" data-scene-idx="${idx}">
          <div class="scene-narration">
            <span class="scene-number">${idx + 1}</span>
            <div class="scene-text">${this.escapeHtml(scene.narration || '')}</div>
            <div class="scene-prompt">${this.escapeHtml(scene.image_prompt || '').substring(0, 100)}...</div>
          </div>
          <div class="scene-image-area">
            <div class="scene-image-box" id="scene-img-${idx}">
              <div class="placeholder">생성 대기</div>
            </div>
            <div class="scene-image-actions">
              <button class="btn-regenerate" onclick="ImageMain.generateSceneImage(${idx})">
                🎨 생성
              </button>
              <button class="btn-download-single" onclick="ImageMain.downloadSceneImage(${idx})" title="다운로드">
                💾
              </button>
            </div>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
    container.style.display = 'flex';
    document.getElementById('result-empty').style.display = 'none';

    // 전체 다운로드 버튼 표시
    document.getElementById('btn-download-all').classList.remove('hidden');
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

    const container = document.getElementById(`scene-img-${idx}`);
    container.innerHTML = '<div class="loading"><div class="spinner" style="width:24px;height:24px;border-width:2px;"></div></div>';

    try {
      const model = document.getElementById('image-model').value;
      const ratio = document.getElementById('image-ratio').value;
      const style = document.getElementById('image-style')?.value || 'realistic';

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
        this.showStatus(`씬 ${idx + 1} 이미지 생성 완료!`, 'success');
      }

    } catch (error) {
      console.error('[ImageMain] Scene image error:', error);
      container.innerHTML = '<div class="placeholder" style="color:red;">생성 실패</div>';
      this.showStatus(`씬 ${idx + 1} 이미지 생성 실패: ${error.message}`, 'error');
    }
  },

  /**
   * 단일 썸네일 생성 (시니어 가이드 적용)
   */
  async generateSingleThumbnail(idx, prompt, textLines, model, textColor, outlineColor) {
    const card = document.getElementById(`thumbnail-card-${idx}`);
    const imageBox = card.querySelector('.thumbnail-image-box');

    imageBox.innerHTML = '<div class="loading"><div class="spinner" style="width:24px;height:24px;border-width:2px;"></div> 생성중...</div>';

    try {
      // 두 번째 썸네일은 약간 다른 프롬프트 변형 사용
      let finalPrompt = prompt;
      if (idx === 1) {
        finalPrompt = prompt + ', different angle, alternative composition';
      }

      // 1단계: 이미지 생성
      const imageResponse = await fetch('/api/drama/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: finalPrompt,
          imageProvider: model,
          style: 'thumbnail',
          size: '16:9'
        })
      });

      const imageData = await imageResponse.json();
      if (!imageData.ok && imageData.error) {
        throw new Error(imageData.error);
      }
      if (!imageData.imageUrl) {
        throw new Error('이미지 URL이 없습니다.');
      }

      // 2단계: 텍스트 오버레이 (시니어 가이드: 노랑+검정)
      if (textLines && textLines.length > 0) {
        imageBox.innerHTML = '<div class="loading"><div class="spinner" style="width:24px;height:24px;border-width:2px;"></div> 텍스트 적용중...</div>';

        const overlayResponse = await fetch('/api/drama/thumbnail-overlay', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            imageUrl: imageData.imageUrl,
            textLines: textLines,
            highlightLines: [0],
            textColor: textColor,
            highlightColor: textColor,
            outlineColor: outlineColor,
            outlineWidth: 5,
            fontSize: 72,
            position: 'left'
          })
        });

        const overlayData = await overlayResponse.json();
        if (overlayData.ok && overlayData.imageUrl) {
          imageBox.innerHTML = `<img src="${overlayData.imageUrl}" alt="썸네일 ${idx + 1}">`;
          this.thumbnailImages[idx] = overlayData.imageUrl;
        } else {
          console.warn('[ImageMain] Overlay failed:', overlayData.error);
          imageBox.innerHTML = `<img src="${imageData.imageUrl}" alt="썸네일 ${idx + 1}">`;
          this.thumbnailImages[idx] = imageData.imageUrl;
        }
      } else {
        imageBox.innerHTML = `<img src="${imageData.imageUrl}" alt="썸네일 ${idx + 1}">`;
        this.thumbnailImages[idx] = imageData.imageUrl;
      }

    } catch (error) {
      console.error(`[ImageMain] Thumbnail ${idx} error:`, error);
      imageBox.innerHTML = '<div class="placeholder" style="color:red;">생성 실패</div>';
    }
  },

  /**
   * 클립보드에 복사
   */
  copyToClipboard(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const text = el.value || el.textContent;
    navigator.clipboard.writeText(text).then(() => {
      this.showStatus('클립보드에 복사됨!', 'success');
    }).catch(err => {
      console.error('Copy failed:', err);
      this.showStatus('복사 실패', 'error');
    });
  },

  /**
   * 텍스트 직접 복사
   */
  copyText(text) {
    navigator.clipboard.writeText(text).then(() => {
      this.showStatus('클립보드에 복사됨!', 'success');
    }).catch(err => {
      console.error('Copy failed:', err);
      this.showStatus('복사 실패', 'error');
    });
  },

  /**
   * 개별 씬 이미지 다운로드
   */
  downloadSceneImage(idx) {
    const imageUrl = this.sceneImages[idx];
    if (!imageUrl) {
      this.showStatus('다운로드할 이미지가 없습니다.', 'warning');
      return;
    }

    const a = document.createElement('a');
    a.href = imageUrl;
    a.download = `scene_${idx + 1}.png`;
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  },

  /**
   * 전체 이미지 ZIP 다운로드
   */
  async downloadAllImages() {
    const images = [];

    // 썸네일
    this.thumbnailImages.forEach((url, idx) => {
      if (url) {
        images.push({ name: `thumbnail_${idx + 1}.png`, url: url });
      }
    });

    // 씬 이미지
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
   * HTML 이스케이프
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
