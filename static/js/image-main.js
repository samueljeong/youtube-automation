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
  audience: 'senior',    // 타겟 시청자: 'senior' 또는 'general'
  selectedVoice: 'ko-KR-Neural2-A',  // 선택된 TTS 음성
  assetZipUrl: null,     // 생성된 ZIP 다운로드 URL
  sceneMetadata: null,   // 영상 생성용 씬 메타데이터
  detectedLanguage: 'ko', // 감지된 언어

  /**
   * 초기화
   */
  init() {
    console.log('[ImageMain] Initializing...');
    this.sessionId = this.generateSessionId();
    this.updateSessionInfo();

    // 폰트 크기 슬라이더 이벤트
    const fontSizeSlider = document.getElementById('thumb-font-size');
    const fontSizeValue = document.getElementById('thumb-font-size-value');
    if (fontSizeSlider && fontSizeValue) {
      fontSizeSlider.addEventListener('input', (e) => {
        fontSizeValue.textContent = e.target.value;
      });
    }

    console.log('[ImageMain] Ready. Session:', this.sessionId);
  },

  /**
   * 타겟 시청자 설정 (시니어/일반)
   */
  setAudience(audience) {
    this.audience = audience;
    console.log('[ImageMain] Audience set to:', audience);

    // 버튼 상태 업데이트
    document.querySelectorAll('.audience-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.audience === audience);
    });

    // 시니어/일반에 따른 힌트 업데이트
    const placeholder = document.getElementById('full-script');
    if (placeholder) {
      if (audience === 'senior') {
        placeholder.placeholder = `여기에 전체 대본을 붙여넣으세요...

예시 (시니어 드라마):
[주인공: 이순자, 75세, 한국인 할머니]

그날 새벽이었습니다.
작은 시골 마을, 안개가 자욱하게 깔린 논길을 할머니가 걸어갑니다.

60년 전, 그 시절의 기억이 밀려왔습니다.`;
      } else {
        placeholder.placeholder = `여기에 전체 대본을 붙여넣으세요...

예시 (일반 콘텐츠):
결국 터졌습니다.
많은 분들이 궁금해하셨던 그 사건의 전말을 공개합니다.

처음엔 아무도 몰랐습니다.
하지만 진실은 언제나 드러나기 마련입니다.`;
      }
    }
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
   * 대본 분석 (AI) - 분석 후 이미지 자동 생성
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
    const outputLanguage = document.getElementById('output-language')?.value || 'ko';

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
          image_count: imageCount,
          audience: this.audience,  // 시니어/일반 구분
          output_language: outputLanguage  // 출력 언어 (ko/en/ja/auto)
        })
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || 'API 오류');
      }

      const data = await response.json();
      this.analyzedData = data;

      console.log('[ImageMain] API Response:', data);
      console.log('[ImageMain] Scenes count:', data.scenes?.length || 0);
      console.log('[ImageMain] Thumbnail:', data.thumbnail);

      // 유튜브 메타데이터 렌더링
      this.renderYoutubeMetadata(data.youtube || {});

      // 씬 카드 렌더링
      console.log('[ImageMain] Rendering scene cards...');
      this.renderSceneCards(data.scenes || []);

      // 썸네일 텍스트 옵션 렌더링 + 첫 번째 자동 선택
      console.log('[ImageMain] Rendering thumbnail options...');
      this.renderThumbnailTextOptions(data.thumbnail || {});

      // 분석 완료
      document.getElementById('analyzing-overlay').classList.add('hidden');
      this.showStatus(`대본 분석 완료! ${data.scenes?.length || 0}개 씬 이미지 자동 생성 시작...`, 'success');

      // ★★★ 이미지 자동 생성 시작 ★★★
      await this.generateAllImages();

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
   * ★★★ 모든 이미지 자동 생성 (썸네일 + 씬 이미지) ★★★
   */
  async generateAllImages() {
    if (!this.analyzedData) return;

    const scenes = this.analyzedData.scenes || [];
    const thumbnail = this.analyzedData.thumbnail || {};

    // 썸네일 텍스트 옵션 준비 (자동 선택하지 않음 - 사용자가 직접 선택)
    if (thumbnail.text_options && thumbnail.text_options.length > 0) {
      // 첫 번째 옵션 UI만 선택 상태로 표시 (실제 생성은 안함)
      const firstOption = document.querySelector('.text-option');
      if (firstOption) {
        firstOption.classList.add('selected');
        const radio = firstOption.querySelector('input');
        if (radio) radio.checked = true;
      }
      this.selectedThumbnailText = thumbnail.text_options[0];
      document.getElementById('btn-generate-with-text').disabled = false;
    }

    // 씬 이미지 생성 (한 번에 2개씩 병렬 처리)
    this.showStatus(`${scenes.length}개 씬 이미지 생성 중...`, 'info');

    const BATCH_SIZE = 2;  // 한 번에 2개씩만 생성
    for (let i = 0; i < scenes.length; i += BATCH_SIZE) {
      const batch = scenes.slice(i, i + BATCH_SIZE);
      const batchPromises = batch.map((_, batchIdx) => this.generateSceneImage(i + batchIdx));
      await Promise.all(batchPromises);
      this.showStatus(`씬 이미지 생성 중... (${Math.min(i + BATCH_SIZE, scenes.length)}/${scenes.length})`, 'info');
    }

    // 썸네일은 자동 생성하지 않음 - 사용자가 텍스트 선택 후 버튼 클릭
    this.showStatus('씬 이미지 생성 완료! 썸네일 텍스트를 선택하고 생성 버튼을 눌러주세요.', 'success');
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
        <div class="title-option${idx === 0 ? ' selected' : ''}" onclick="ImageMain.selectTitle(${idx})">
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

    // 디버깅: thumbnail 객체 전체 내용 출력
    console.log('[ImageMain] Thumbnail object details:', JSON.stringify(thumbnail, null, 2));

    // text_options, text_lines, texts, options 등 다양한 필드명 폴백
    let options = thumbnail?.text_options
      || thumbnail?.text_lines
      || thumbnail?.texts
      || thumbnail?.options
      || thumbnail?.textOptions
      || [];

    // 객체 배열인 경우 텍스트만 추출
    if (options.length > 0 && typeof options[0] === 'object') {
      options = options.map(opt => opt.text || opt.content || opt.value || JSON.stringify(opt));
    }

    console.log('[ImageMain] Extracted text options:', options);

    if (options.length === 0) {
      section.classList.remove('hidden');
      optionsContainer.innerHTML = '<div class="no-options">썸네일 텍스트 옵션이 없습니다.</div>';
      return;
    }

    let optionsHtml = '';
    options.forEach((text, idx) => {
      // 첫 번째 옵션 자동 선택
      const isSelected = idx === 0;
      const escapedText = this.escapeHtml(text);
      optionsHtml += `
        <div class="text-option${isSelected ? ' selected' : ''}" data-idx="${idx}" data-text="${escapedText}">
          <input type="radio" name="thumbnail-text" value="${idx}" ${isSelected ? 'checked' : ''}>
          <span class="text-preview">${escapedText}</span>
        </div>
      `;
    });
    optionsContainer.innerHTML = optionsHtml;

    // 클릭 이벤트 바인딩 (onclick 대신)
    optionsContainer.querySelectorAll('.text-option').forEach(el => {
      el.addEventListener('click', () => {
        const idx = parseInt(el.dataset.idx);
        const text = el.dataset.text;
        this.selectThumbnailText(idx, text);
      });
    });

    // 첫 번째 옵션 자동 선택
    this.selectedThumbnailText = options[0];
    generateBtn.disabled = false;

    section.classList.remove('hidden');
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

    // 직접 입력한 텍스트 우선 사용
    const customTextEl = document.getElementById('thumbnail-custom-text');
    const customText = customTextEl?.value?.trim() || '';

    // 텍스트 결정: 직접 입력 > 선택한 옵션
    let textLines = [];
    if (customText) {
      // 줄바꿈으로 분리하여 여러 줄 지원
      textLines = customText.split('\n').filter(line => line.trim());
    } else if (this.selectedThumbnailText) {
      textLines = [this.selectedThumbnailText];
    }

    if (textLines.length === 0) {
      this.showStatus('썸네일 텍스트를 입력하거나 선택해주세요.', 'warning');
      return;
    }

    const thumbnailData = this.analyzedData.thumbnail || {};
    const prompt = thumbnailData.prompt || 'detailed anime background with simple white stickman, dramatic pose, Ghibli-inspired, NO realistic humans';

    // UI에서 스타일 값 읽기
    const textColor = document.getElementById('thumb-text-color')?.value || '#FFD700';
    const outlineColor = document.getElementById('thumb-outline-color')?.value || '#000000';
    const fontSize = parseInt(document.getElementById('thumb-font-size')?.value) || 100;
    const position = document.getElementById('thumb-position')?.value || 'left';

    // 썸네일 그리드 표시
    document.getElementById('thumbnail-grid').style.display = 'flex';

    const model = document.getElementById('image-model').value;
    const displayText = textLines.join('\n');

    // 텍스트 미리보기 표시
    for (let i = 0; i < 2; i++) {
      const textEl = document.getElementById(`thumbnail-text-${i}`);
      if (textEl) {
        textEl.textContent = displayText;
      }
    }

    // 병렬 생성
    const promises = [0, 1].map(idx => this.generateSingleThumbnail(idx, prompt, textLines, model, textColor, outlineColor, fontSize, position));
    await Promise.all(promises);

    this.showStatus('썸네일 2개 생성 완료!', 'success');
  },

  /**
   * 씬 카드 렌더링 (UI 개선)
   */
  renderSceneCards(scenes) {
    const container = document.getElementById('scene-cards');
    console.log('[ImageMain] renderSceneCards called with', scenes?.length || 0, 'scenes');

    if (!scenes || scenes.length === 0) {
      console.log('[ImageMain] No scenes, showing placeholder');
      container.style.display = 'none';
      document.getElementById('result-empty').style.display = 'flex';
      return;
    }

    let html = '';
    scenes.forEach((scene, idx) => {
      const narration = scene.narration || '(나레이션 없음)';
      // 나레이션 첫 60자만 표시
      const shortNarration = narration.length > 60 ? narration.substring(0, 60) + '...' : narration;

      html += `
        <div class="scene-card" data-scene-idx="${idx}">
          <div class="scene-image-box" id="scene-img-${idx}">
            <div class="placeholder">
              <div class="spinner"></div>
              <span>생성 중...</span>
            </div>
          </div>
          <div class="scene-info">
            <div class="scene-info-top">
              <span class="scene-number">${idx + 1}</span>
              <button class="btn-scene-regenerate" onclick="ImageMain.generateSceneImage(${idx})" title="다시 생성">🔄</button>
            </div>
            <p class="scene-narration" title="${this.escapeHtml(narration)}">${this.escapeHtml(shortNarration)}</p>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
    container.style.display = 'grid';
    document.getElementById('result-empty').style.display = 'none';

    // 전체 다운로드 버튼 표시
    document.getElementById('btn-download-all').classList.remove('hidden');

    // 에셋 섹션 표시
    this.showAssetSection();
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
    container.innerHTML = '<div class="placeholder"><div class="spinner"></div><span>생성 중...</span></div>';

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
        container.innerHTML = `<img src="${data.imageUrl}" alt="씬 ${idx + 1}" onclick="ImageMain.openImageModal('${data.imageUrl}')">`;
        this.sceneImages[idx] = data.imageUrl;
      }

    } catch (error) {
      console.error('[ImageMain] Scene image error:', error);
      container.innerHTML = `<div class="placeholder error"><span>생성 실패</span><button onclick="ImageMain.generateSceneImage(${idx})">재시도</button></div>`;
    }
  },

  /**
   * 이미지 모달 열기
   */
  openImageModal(imageUrl) {
    // 간단한 이미지 확대 보기
    const modal = document.createElement('div');
    modal.className = 'image-modal';
    modal.innerHTML = `
      <div class="image-modal-backdrop" onclick="this.parentElement.remove()"></div>
      <div class="image-modal-content">
        <img src="${imageUrl}" alt="확대 이미지">
        <button class="image-modal-close" onclick="this.parentElement.parentElement.remove()">✕</button>
      </div>
    `;
    document.body.appendChild(modal);
  },

  /**
   * 단일 썸네일 생성 (사용자 설정 적용)
   */
  async generateSingleThumbnail(idx, prompt, textLines, model, textColor, outlineColor, fontSize = 100, position = 'left') {
    const card = document.getElementById(`thumbnail-card-${idx}`);
    const imageBox = card.querySelector('.thumbnail-image-box');

    imageBox.innerHTML = '<div class="placeholder"><div class="spinner"></div><span>생성중...</span></div>';

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

      // 2단계: 텍스트 오버레이 (사용자가 지정한 스타일 적용)
      if (textLines && textLines.length > 0) {
        imageBox.innerHTML = '<div class="placeholder"><div class="spinner"></div><span>텍스트 적용중...</span></div>';

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
            outlineWidth: 6,
            fontSize: fontSize,
            position: position
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
      imageBox.innerHTML = '<div class="placeholder error"><span>생성 실패</span></div>';
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
  },

  // ========== 에셋 생성 (TTS + ZIP) ==========

  /**
   * 음성 선택
   */
  selectVoice(btn) {
    this.selectedVoice = btn.dataset.voice;
    console.log('[ImageMain] Voice selected:', this.selectedVoice);

    // 버튼 상태 업데이트
    document.querySelectorAll('.voice-btn').forEach(b => {
      b.classList.toggle('active', b === btn);
    });
  },

  /**
   * 에셋 섹션 표시 (이미지 생성 완료 후 호출)
   */
  showAssetSection() {
    const section = document.getElementById('asset-section');
    if (section) {
      section.classList.remove('hidden');
    }
  },

  /**
   * 에셋 생성 (TTS + 이미지 → ZIP 패키지)
   */
  async generateAssets() {
    if (!this.analyzedData || !this.analyzedData.scenes) {
      this.showStatus('먼저 대본을 분석해주세요.', 'warning');
      return;
    }

    // 이미지가 모두 생성되었는지 확인
    const scenes = this.analyzedData.scenes;
    const generatedImages = Object.keys(this.sceneImages).length;
    if (generatedImages < scenes.length) {
      this.showStatus(`이미지를 먼저 모두 생성해주세요. (${generatedImages}/${scenes.length})`, 'warning');
      return;
    }

    const btn = document.getElementById('btn-generate-assets');
    const progressDiv = document.getElementById('asset-progress');
    const progressFill = document.getElementById('asset-progress-fill');
    const progressText = document.getElementById('asset-progress-text');

    btn.disabled = true;
    btn.textContent = '⏳ 생성 중...';
    progressDiv.classList.remove('hidden');
    progressFill.style.width = '10%';
    progressText.textContent = 'TTS 음성 생성 중...';

    try {
      // 나레이션 텍스트 수집
      const narrations = scenes.map((s, idx) => ({
        scene_number: idx + 1,
        text: s.narration,
        image_url: this.sceneImages[idx] || ''
      }));

      progressFill.style.width = '30%';
      progressText.textContent = 'TTS 음성 생성 중...';

      // API 호출 - 에셋 ZIP 생성
      const response = await fetch('/api/image/generate-assets-zip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.sessionId,
          voice: this.selectedVoice,
          scenes: narrations
        })
      });

      progressFill.style.width = '80%';
      progressText.textContent = 'ZIP 파일 생성 중...';

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || 'API 오류');
      }

      const data = await response.json();

      progressFill.style.width = '100%';
      progressText.textContent = '완료!';

      // 결과 표시
      this.assetZipUrl = data.zip_url;
      this.sceneMetadata = data.scene_metadata;  // 영상 생성용 메타데이터 저장
      this.detectedLanguage = data.detected_language || 'ko';  // 감지된 언어 저장

      document.getElementById('asset-image-count').textContent = `이미지 ${data.image_count}개`;
      document.getElementById('asset-audio-info').textContent = `오디오 ${data.audio_duration}`;
      document.getElementById('asset-preview').classList.remove('hidden');
      document.getElementById('btn-download-assets').classList.remove('hidden');
      document.getElementById('btn-generate-video').classList.remove('hidden');  // 영상 생성 버튼 표시

      btn.textContent = '✅ 생성 완료';
      this.showStatus('CapCut 에셋이 준비되었습니다!', 'success');

      console.log('[ImageMain] Scene metadata saved:', this.sceneMetadata?.length, 'scenes, lang:', this.detectedLanguage);

    } catch (error) {
      console.error('[ImageMain] Asset generation error:', error);
      this.showStatus('에셋 생성 실패: ' + error.message, 'error');
      btn.disabled = false;
      btn.textContent = '📦 CapCut 에셋 생성';
      progressDiv.classList.add('hidden');
    }
  },

  /**
   * 에셋 ZIP 다운로드
   */
  downloadAssets() {
    if (!this.assetZipUrl) {
      this.showStatus('먼저 에셋을 생성해주세요.', 'warning');
      return;
    }

    const a = document.createElement('a');
    a.href = this.assetZipUrl;
    a.download = `capcut_assets_${this.sessionId}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    this.showStatus('ZIP 파일 다운로드 중...', 'info');
  },

  /**
   * 영상 생성 (백그라운드 처리 + 폴링)
   */
  async generateVideo() {
    if (!this.sceneMetadata || this.sceneMetadata.length === 0) {
      this.showStatus('먼저 에셋을 생성해주세요.', 'warning');
      return;
    }

    const btn = document.getElementById('btn-generate-video');
    const progressDiv = document.getElementById('asset-progress');
    const progressFill = document.getElementById('asset-progress-fill');
    const progressText = document.getElementById('asset-progress-text');

    btn.disabled = true;
    btn.textContent = '⏳ 시작 중...';
    progressDiv.classList.remove('hidden');
    progressFill.style.width = '5%';
    progressText.textContent = '영상 생성 작업 시작 중...';

    try {
      // 1. 영상 생성 작업 시작
      const scenes = this.sceneMetadata.map(sm => ({
        image_url: sm.image_url,
        audio_url: sm.audio_url,
        duration: sm.duration,
        subtitles: sm.subtitles
      }));

      console.log('[ImageMain] Starting video generation with', scenes.length, 'scenes');

      const startResponse = await fetch('/api/image/generate-video', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.sessionId,
          scenes: scenes,
          language: this.detectedLanguage
        })
      });

      if (!startResponse.ok) {
        const errData = await startResponse.json();
        throw new Error(errData.error || '작업 시작 실패');
      }

      const startData = await startResponse.json();
      const jobId = startData.job_id;

      console.log('[ImageMain] Job started:', jobId, startData.estimated_time);
      btn.textContent = '⏳ 처리 중...';
      progressText.textContent = `작업 시작됨 (${startData.estimated_time})`;

      // 2. 상태 폴링
      const pollInterval = 2000; // 2초마다 확인
      const maxPolls = 900; // 최대 30분 (900 * 2초)
      let polls = 0;

      const pollStatus = async () => {
        try {
          const statusResponse = await fetch(`/api/image/video-status/${jobId}`);
          const statusData = await statusResponse.json();

          if (!statusData.ok) {
            throw new Error(statusData.error || '상태 확인 실패');
          }

          // 진행률 업데이트
          progressFill.style.width = `${statusData.progress}%`;
          progressText.textContent = statusData.message;
          btn.textContent = `⏳ ${statusData.progress}%`;

          if (statusData.status === 'completed') {
            // 완료!
            progressFill.style.width = '100%';
            progressText.textContent = '완료!';
            btn.textContent = '✅ 영상 완료';

            this.showStatus(`영상 생성 완료! (${statusData.duration}, 자막 ${statusData.subtitle_count}개)`, 'success');

            // 다운로드
            if (statusData.video_url) {
              const a = document.createElement('a');
              a.href = statusData.video_url;
              a.download = `video_${this.sessionId}.mp4`;
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
            }
            return;

          } else if (statusData.status === 'failed') {
            throw new Error(statusData.error || '영상 생성 실패');

          } else {
            // 계속 폴링
            polls++;
            if (polls < maxPolls) {
              setTimeout(pollStatus, pollInterval);
            } else {
              throw new Error('시간 초과 (30분)');
            }
          }

        } catch (error) {
          console.error('[ImageMain] Poll error:', error);
          this.showStatus('영상 생성 실패: ' + error.message, 'error');
          btn.disabled = false;
          btn.textContent = '🎬 영상 생성';
          progressDiv.classList.add('hidden');
        }
      };

      // 폴링 시작
      setTimeout(pollStatus, pollInterval);

    } catch (error) {
      console.error('[ImageMain] Video generation error:', error);
      this.showStatus('영상 생성 실패: ' + error.message, 'error');
      btn.disabled = false;
      btn.textContent = '🎬 영상 생성';
      progressDiv.classList.add('hidden');
    }
  }
};

// DOM 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
  ImageMain.init();
});
