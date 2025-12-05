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
  selectedVoice: 'ko-KR-Neural2-C',  // 선택된 TTS 음성 (남성 중후한 목소리)
  assetZipUrl: null,     // 생성된 ZIP 다운로드 URL
  sceneMetadata: null,   // 영상 생성용 씬 메타데이터
  detectedLanguage: 'ko', // 감지된 언어
  videoUrl: null,        // 생성된 영상 URL (YouTube 업로드용)
  selectedTitle: '',     // 선택된 유튜브 제목
  selectedThumbnailIdx: null,  // 선택된 썸네일 인덱스 (YouTube 업로드용)
  privacyStatus: 'private',    // 공개 설정 (private, unlisted, public)
  scheduledTime: null,         // 예약 업로드 시간 (ISO 8601)
  selectedChannelId: null,     // 선택된 YouTube 채널 ID
  channels: [],                // 사용 가능한 채널 목록

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
   * 완료 후 자동으로 TTS 생성 시작
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

    // 씬 이미지 생성 (한 번에 2개씩 병렬 처리, 실패 시 3회 재시도)
    this.showStatus(`${scenes.length}개 씬 이미지 생성 중...`, 'info');

    const BATCH_SIZE = 2;  // 한 번에 2개씩만 생성
    let allSuccess = true;

    for (let i = 0; i < scenes.length; i += BATCH_SIZE) {
      const batch = scenes.slice(i, i + BATCH_SIZE);
      const batchPromises = batch.map((_, batchIdx) => this.generateSceneImage(i + batchIdx));
      const results = await Promise.all(batchPromises);

      // 실패한 이미지가 있는지 확인
      if (results.some(r => r === false)) {
        allSuccess = false;
      }

      this.showStatus(`씬 이미지 생성 중... (${Math.min(i + BATCH_SIZE, scenes.length)}/${scenes.length})`, 'info');
    }

    // 모든 이미지 생성 성공 시 자동으로 TTS 생성 시작
    const successCount = Object.keys(this.sceneImages).length;
    if (successCount === scenes.length) {
      this.showStatus(`✅ 씬 이미지 ${successCount}개 완료! TTS 생성 시작...`, 'success');

      // 1초 후 TTS 자동 시작
      await this.sleep(1000);
      await this.generateAssets();
    } else {
      this.showStatus(`⚠️ 이미지 ${successCount}/${scenes.length}개 완료. 실패한 이미지를 확인해주세요.`, 'warning');
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

    // 제목 옵션 렌더링 (수정 가능 + 선택 버튼 + 자동 저장)
    const titles = youtube.titles || [];
    let titlesHtml = '';
    titles.forEach((title, idx) => {
      const isSelected = idx === 0;
      titlesHtml += `
        <div class="title-option${isSelected ? ' selected' : ''}" data-idx="${idx}">
          <input type="text" class="title-input" id="title-input-${idx}" value="${this.escapeHtml(title)}" placeholder="제목 입력..."
                 oninput="ImageMain.onTitleInputChange(${idx})">
          <button class="btn-select-title${isSelected ? ' active' : ''}" onclick="ImageMain.selectTitle(${idx})">선택</button>
        </div>
      `;
    });
    titlesContainer.innerHTML = titlesHtml;

    // 첫 번째 제목 자동 선택
    if (titles.length > 0) {
      this.selectedTitle = titles[0];
    }

    // 설명란 렌더링
    descriptionEl.value = youtube.description || '';

    section.classList.remove('hidden');
  },

  /**
   * 제목 선택
   */
  selectTitle(idx) {
    // 입력된 제목 값 가져오기
    const inputEl = document.getElementById(`title-input-${idx}`);
    if (inputEl) {
      this.selectedTitle = inputEl.value.trim();
    }

    // UI 업데이트
    document.querySelectorAll('.title-option').forEach((el, i) => {
      const isSelected = i === idx;
      el.classList.toggle('selected', isSelected);
      el.querySelector('.btn-select-title').classList.toggle('active', isSelected);
    });

    this.showStatus(`제목 선택: "${this.selectedTitle.substring(0, 30)}..."`, 'success');
  },

  /**
   * 제목 입력 변경 시 자동 저장 (선택된 옵션만)
   */
  onTitleInputChange(idx) {
    const titleOption = document.querySelector(`.title-option[data-idx="${idx}"]`);
    if (titleOption && titleOption.classList.contains('selected')) {
      const inputEl = document.getElementById(`title-input-${idx}`);
      if (inputEl) {
        this.selectedTitle = inputEl.value.trim();
        console.log('[ImageMain] Title auto-saved:', this.selectedTitle.substring(0, 30));
      }
    }
  },

  /**
   * 썸네일 섹션 표시 (AI 추천 텍스트 없이 직접 입력만)
   */
  renderThumbnailTextOptions(thumbnail) {
    const section = document.getElementById('thumbnail-section');
    const generateBtn = document.getElementById('btn-generate-with-text');

    // 썸네일 프롬프트 저장 (이미지 생성 시 사용)
    if (thumbnail?.prompt) {
      this.thumbnailPrompt = thumbnail.prompt;
    }

    // 썸네일 섹션 표시
    section.classList.remove('hidden');
    generateBtn.disabled = false;

    console.log('[ImageMain] Thumbnail section shown (직접 입력 모드)');
  },

  /**
   * 줄별 스타일 UI 업데이트 (텍스트 입력 시 호출)
   */
  updateLineStyles() {
    const customTextEl = document.getElementById('thumbnail-custom-text');
    const container = document.getElementById('line-styles-list');
    if (!customTextEl || !container) return;

    const text = customTextEl.value.trim();
    const lines = text ? text.split('\n').filter(line => line.trim()) : [];

    // 기본 색상 배열 (줄마다 다른 색상)
    const defaultColors = ['#FFD700', '#FFFFFF', '#FF6B6B', '#4ECDC4', '#A78BFA'];

    let html = '';
    lines.forEach((line, idx) => {
      const defaultColor = defaultColors[idx % defaultColors.length];
      const defaultSize = idx === 0 ? 90 : 70;  // 첫 줄은 더 크게
      html += `
        <div class="line-style-row">
          <span class="line-num">${idx + 1}줄</span>
          <span class="line-text" title="${this.escapeHtml(line)}">${this.escapeHtml(line.substring(0, 20))}${line.length > 20 ? '...' : ''}</span>
          <label>색상</label>
          <input type="color" id="line-color-${idx}" value="${defaultColor}">
          <label>크기</label>
          <input type="number" id="line-size-${idx}" value="${defaultSize}" min="30" max="150">
        </div>
      `;
    });

    container.innerHTML = html || '<div style="color:#999; font-size:12px;">텍스트를 입력하면 줄별 스타일을 설정할 수 있습니다.</div>';
  },

  /**
   * 텍스트 언어 변경 시 placeholder 업데이트
   */
  onTextLanguageChange() {
    const langRadio = document.querySelector('input[name="thumb-text-lang"]:checked');
    const textArea = document.getElementById('thumbnail-custom-text');
    if (!langRadio || !textArea) return;

    const lang = langRadio.value;
    if (lang === 'en') {
      textArea.placeholder = "Example:\n4 hours of betrayal\nThat night's incident";
    } else {
      textArea.placeholder = "예:\n4시간의 배신\n그날 밤 일어난 일";
    }

    console.log(`[ImageMain] Thumbnail text language changed to: ${lang}`);
  },

  /**
   * 선택된 텍스트 언어 반환
   */
  getTextLanguage() {
    const langRadio = document.querySelector('input[name="thumb-text-lang"]:checked');
    return langRadio ? langRadio.value : 'ko';
  },

  /**
   * 줄별 스타일 수집
   */
  getLineStyles() {
    const customTextEl = document.getElementById('thumbnail-custom-text');
    if (!customTextEl) return [];

    const text = customTextEl.value.trim();
    const lines = text ? text.split('\n').filter(line => line.trim()) : [];

    const styles = [];
    lines.forEach((_, idx) => {
      const colorEl = document.getElementById(`line-color-${idx}`);
      const sizeEl = document.getElementById(`line-size-${idx}`);
      styles.push({
        color: colorEl?.value || '#FFD700',
        fontSize: parseInt(sizeEl?.value) || 70
      });
    });

    return styles;
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
    const outlineColor = document.getElementById('thumb-outline-color')?.value || '#000000';
    const position = document.getElementById('thumb-position')?.value || 'left';

    // 줄별 스타일 수집
    const lineStyles = this.getLineStyles();
    console.log('[ImageMain] Line styles:', lineStyles);

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

    // 병렬 생성 (줄별 스타일 전달)
    const promises = [0, 1].map(idx => this.generateSingleThumbnail(idx, prompt, textLines, model, outlineColor, position, lineStyles));
    await Promise.all(promises);

    this.showStatus('썸네일 2개 생성 완료! 원하는 썸네일을 선택하세요.', 'success');
  },

  /**
   * 썸네일 선택 (YouTube 업로드용)
   */
  selectThumbnail(idx) {
    this.selectedThumbnailIdx = idx;

    // UI 업데이트
    document.querySelectorAll('.thumbnail-card').forEach((card, i) => {
      const isSelected = i === idx;
      card.classList.toggle('selected', isSelected);
      const btn = card.querySelector('.btn-select-thumbnail');
      if (btn) {
        btn.classList.toggle('active', isSelected);
        btn.textContent = isSelected ? '✓ 선택됨' : '선택';
      }
    });

    this.showStatus(`썸네일 ${idx + 1} 선택됨`, 'success');
  },

  // ========== AI 썸네일 모드 ==========

  // AI 모드 상태
  thumbnailMode: 'manual',  // 'manual' or 'ai'
  aiThumbnailSession: null,
  aiThumbnailPrompts: null,
  aiThumbnailImageUrls: {},

  /**
   * 썸네일 모드 전환 (직접 입력 / AI)
   */
  setThumbnailMode(mode) {
    this.thumbnailMode = mode;

    // 버튼 상태 업데이트
    document.querySelectorAll('.thumb-mode-toggle .mode-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    // 섹션 표시/숨기기
    document.getElementById('manual-mode-section').style.display = mode === 'manual' ? 'block' : 'none';
    document.getElementById('ai-mode-section').style.display = mode === 'ai' ? 'block' : 'none';

    // AI 모드일 때 통계 로드
    if (mode === 'ai') {
      this.loadAIThumbnailStats();
    }

    console.log('[ImageMain] Thumbnail mode changed to:', mode);
  },

  /**
   * AI 썸네일 분석 (GPT-5.1)
   */
  async analyzeForThumbnail() {
    if (!this.analyzedData) {
      this.showStatus('먼저 대본을 분석해주세요.', 'warning');
      return;
    }

    const btn = document.getElementById('btn-ai-analyze');
    const loading = document.getElementById('ai-loading');
    const loadingText = document.getElementById('ai-loading-text');

    try {
      btn.disabled = true;
      loading.style.display = 'flex';
      loadingText.textContent = 'GPT-5.1이 대본을 분석하고 있습니다...';

      // 대본 텍스트 수집
      const scenes = this.analyzedData.scenes || [];
      const script = scenes.map(s => s.narration || '').join('\n\n');
      const title = document.getElementById('video-title')?.value || this.analyzedData.thumbnail?.title || '제목 없음';

      console.log('[ImageMain] AI Thumbnail analyze - title:', title, 'script length:', script.length);

      const response = await fetch('/api/thumbnail-ai/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: script,
          title: title,
          genre: '일반'
        })
      });

      const data = await response.json();

      if (!data.ok) {
        throw new Error(data.error || 'AI 분석 실패');
      }

      // 세션 및 프롬프트 저장
      this.aiThumbnailSession = data.session_id;
      this.aiThumbnailPrompts = data.prompts;

      // 컨셉 프리뷰 표시
      document.getElementById('ai-script-summary').textContent = data.script_summary || '-';
      document.getElementById('ai-thumbnail-concept').textContent = data.thumbnail_concept || '-';
      document.getElementById('ai-learning-count').textContent = `${data.learning_examples_used || 0}개 활용됨`;

      document.getElementById('ai-concept-preview').style.display = 'block';
      document.getElementById('btn-ai-generate').style.display = 'block';

      this.showStatus('AI 분석 완료! 이제 썸네일을 생성하세요.', 'success');

    } catch (error) {
      console.error('[ImageMain] AI analyze error:', error);
      this.showStatus('AI 분석 실패: ' + error.message, 'error');
    } finally {
      btn.disabled = false;
      loading.style.display = 'none';
    }
  },

  /**
   * AI 썸네일 생성 (Gemini 3 Pro Image)
   */
  async generateAIThumbnails() {
    if (!this.aiThumbnailSession || !this.aiThumbnailPrompts) {
      this.showStatus('먼저 AI 분석을 실행해주세요.', 'warning');
      return;
    }

    const btn = document.getElementById('btn-ai-generate');
    const loading = document.getElementById('ai-loading');
    const loadingText = document.getElementById('ai-loading-text');

    try {
      btn.disabled = true;
      loading.style.display = 'flex';
      loadingText.textContent = 'Gemini 3 Pro가 썸네일을 생성하고 있습니다... (약 30초)';

      const response = await fetch('/api/thumbnail-ai/generate-both', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.aiThumbnailSession,
          prompts: this.aiThumbnailPrompts
        })
      });

      const data = await response.json();

      if (!data.ok) {
        throw new Error(data.error || '썸네일 생성 실패');
      }

      // 결과 저장
      this.aiThumbnailImageUrls = {
        A: data.results.A?.image_url,
        B: data.results.B?.image_url
      };

      // UI 업데이트
      this.renderAIThumbnails(data.results);

      this.showStatus('A/B 썸네일 생성 완료! 마음에 드는 것을 선택하세요.', 'success');

    } catch (error) {
      console.error('[ImageMain] AI generate error:', error);
      this.showStatus('썸네일 생성 실패: ' + error.message, 'error');
    } finally {
      btn.disabled = false;
      loading.style.display = 'none';
    }
  },

  /**
   * AI 썸네일 렌더링
   */
  renderAIThumbnails(results) {
    const grid = document.getElementById('ai-thumbnail-grid');
    grid.style.display = 'grid';

    ['A', 'B'].forEach(variant => {
      const result = results[variant];
      const promptData = this.aiThumbnailPrompts[variant];

      const imgEl = document.getElementById(`ai-thumb-img-${variant}`);
      const descEl = document.getElementById(`ai-thumb-desc-${variant}`);
      const textEl = document.getElementById(`ai-thumb-text-${variant}`);

      if (result?.ok && result?.image_url) {
        imgEl.src = result.image_url;
        imgEl.style.display = 'block';
      } else {
        imgEl.style.display = 'none';
      }

      descEl.textContent = promptData?.description || '옵션 ' + variant;
      textEl.textContent = '텍스트: ' + (promptData?.text_overlay?.main || '-');
    });

    // 카드 선택 상태 초기화
    document.querySelectorAll('.ai-thumbnail-card').forEach(card => {
      card.classList.remove('selected');
    });
  },

  /**
   * AI 썸네일 선택 및 학습 데이터 저장
   */
  async selectAIThumbnail(variant) {
    if (!this.aiThumbnailSession) {
      this.showStatus('세션 정보가 없습니다.', 'error');
      return;
    }

    // 카드 선택 표시
    document.querySelectorAll('.ai-thumbnail-card').forEach(card => {
      card.classList.toggle('selected', card.dataset.variant === variant);
    });

    // 선택된 썸네일 URL 저장 (YouTube 업로드용)
    const selectedUrl = this.aiThumbnailImageUrls[variant];
    if (selectedUrl) {
      this.selectedAIThumbnailUrl = selectedUrl;
      this.selectedThumbnailIdx = variant === 'A' ? 0 : 1;
    }

    try {
      // 학습 데이터 저장
      const title = document.getElementById('video-title')?.value || '';
      const scriptSummary = document.getElementById('ai-script-summary')?.textContent || '';

      const response = await fetch('/api/thumbnail-ai/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.aiThumbnailSession,
          selected: variant,
          prompts: this.aiThumbnailPrompts,
          script_summary: scriptSummary,
          genre: '일반',
          title: title,
          selection_reason: '',  // 간단 모드에서는 이유 생략
          image_urls: this.aiThumbnailImageUrls
        })
      });

      const data = await response.json();

      if (data.ok) {
        // 성공 메시지 표시
        const successEl = document.getElementById('ai-success-message');
        successEl.style.display = 'block';
        setTimeout(() => {
          successEl.style.display = 'none';
        }, 3000);

        // 통계 업데이트
        this.loadAIThumbnailStats();

        this.showStatus(`옵션 ${variant} 선택됨! 학습 데이터가 저장되었습니다.`, 'success');
      }

    } catch (error) {
      console.error('[ImageMain] AI select error:', error);
      // 선택은 완료, 저장만 실패
      this.showStatus(`옵션 ${variant} 선택됨 (학습 데이터 저장 실패)`, 'warning');
    }
  },

  /**
   * AI 썸네일 학습 통계 로드
   */
  async loadAIThumbnailStats() {
    try {
      const response = await fetch('/api/thumbnail-ai/history?limit=100');
      const data = await response.json();

      if (data.ok && data.stats) {
        document.getElementById('ai-stat-total').textContent = data.stats.total || 0;
        document.getElementById('ai-stat-a').textContent = data.stats.a_selected || 0;
        document.getElementById('ai-stat-b').textContent = data.stats.b_selected || 0;
        document.getElementById('ai-stats').style.display = 'block';
      }
    } catch (error) {
      console.error('[ImageMain] Load stats error:', error);
    }
  },

  /**
   * 씬 카드 렌더링 (UI 개선)
   */
  renderSceneCards(scenes) {
    const container = document.getElementById('scene-cards');
    const imagesSection = document.getElementById('images-section');
    console.log('[ImageMain] renderSceneCards called with', scenes?.length || 0, 'scenes');

    if (!scenes || scenes.length === 0) {
      console.log('[ImageMain] No scenes, showing placeholder');
      container.style.display = 'none';
      if (imagesSection) imagesSection.style.display = 'none';
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
    if (imagesSection) imagesSection.style.display = 'block';
    document.getElementById('result-empty').style.display = 'none';

    // 전체 다운로드 버튼 표시
    document.getElementById('btn-download-all').classList.remove('hidden');

    // 에셋 섹션 표시
    this.showAssetSection();
  },

  /**
   * 단일 씬 이미지 생성 (3회 자동 재시도)
   */
  async generateSceneImage(idx, retryCount = 0) {
    const MAX_RETRIES = 3;
    const scene = this.analyzedData?.scenes?.[idx];
    if (!scene || !scene.image_prompt) {
      this.showStatus('이미지 프롬프트가 없습니다.', 'warning');
      return false;
    }

    const container = document.getElementById(`scene-img-${idx}`);
    const retryText = retryCount > 0 ? ` (재시도 ${retryCount}/${MAX_RETRIES})` : '';
    container.innerHTML = `<div class="placeholder"><div class="spinner"></div><span>생성 중...${retryText}</span></div>`;

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
        return true;  // 성공
      }
      throw new Error('이미지 URL 없음');

    } catch (error) {
      console.error(`[ImageMain] Scene ${idx + 1} image error (attempt ${retryCount + 1}):`, error);

      // 재시도 로직
      if (retryCount < MAX_RETRIES) {
        console.log(`[ImageMain] Retrying scene ${idx + 1}... (${retryCount + 1}/${MAX_RETRIES})`);
        await this.sleep(1000);  // 1초 대기 후 재시도
        return await this.generateSceneImage(idx, retryCount + 1);
      }

      // 최대 재시도 실패
      container.innerHTML = `<div class="placeholder error"><span>생성 실패 (${MAX_RETRIES}회 시도)</span><button onclick="ImageMain.generateSceneImage(${idx})">재시도</button></div>`;
      return false;
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
   * 단일 썸네일 생성 (줄별 스타일 적용)
   */
  async generateSingleThumbnail(idx, prompt, textLines, model, outlineColor, position = 'left', lineStyles = []) {
    const card = document.getElementById(`thumbnail-card-${idx}`);
    const imageBox = card.querySelector('.thumbnail-image-box');

    imageBox.innerHTML = '<div class="placeholder"><div class="spinner"></div><span>생성중...</span></div>';

    try {
      // 폰트 위치에 따라 캐릭터 배치 힌트 추가
      let positionHint = '';
      if (position === 'left') {
        positionHint = 'Character positioned on the RIGHT side of the image, leaving LEFT side empty for text overlay.';
      } else if (position === 'right') {
        positionHint = 'Character positioned on the LEFT side of the image, leaving RIGHT side empty for text overlay.';
      } else {
        positionHint = 'Character positioned at the bottom, leaving top/center for text overlay.';
      }

      let finalPrompt = `${prompt}. IMPORTANT: ${positionHint} Character face must be clearly visible with expressive emotion.`;

      // 두 번째 썸네일은 약간 다른 프롬프트 변형 사용
      if (idx === 1) {
        finalPrompt += ' Different angle, alternative composition.';
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

      // 2단계: 텍스트 오버레이 (줄별 스타일 적용)
      if (textLines && textLines.length > 0) {
        imageBox.innerHTML = '<div class="placeholder"><div class="spinner"></div><span>텍스트 적용중...</span></div>';

        const overlayResponse = await fetch('/api/drama/thumbnail-overlay', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            imageUrl: imageData.imageUrl,
            textLines: textLines,
            highlightLines: [],  // lineStyles로 대체
            textColor: '#FFD700',  // 기본값 (lineStyles가 우선)
            highlightColor: '#FFD700',
            outlineColor: outlineColor,
            outlineWidth: 6,
            fontSize: 70,  // 기본값 (lineStyles가 우선)
            position: position,
            lineStyles: lineStyles  // 줄별 색상/크기
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
      this.showStatus('✅ TTS 완료! 영상 생성 시작...', 'success');

      console.log('[ImageMain] Scene metadata saved:', this.sceneMetadata?.length, 'scenes, lang:', this.detectedLanguage);

      // ★★★ TTS 완료 후 자동으로 영상 생성 시작 ★★★
      await this.sleep(1000);
      await this.generateVideo();

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

            // 영상 URL 저장 및 YouTube 업로드 섹션 표시
            if (statusData.video_url) {
              this.videoUrl = statusData.video_url;

              // YouTube 업로드 섹션 표시
              const ytSection = document.getElementById('youtube-upload-section');
              if (ytSection) {
                ytSection.classList.remove('hidden');
                // 기본 예약 시간 설정 (내일 오전 9시)
                this.setDefaultScheduleTime();
                // 채널 목록 로드
                this.loadYouTubeChannels();
              }

              // 자동 다운로드
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
  },

  // ========== YouTube 업로드 ==========

  /**
   * YouTube 채널 목록 로드
   */
  async loadYouTubeChannels() {
    const container = document.getElementById('channel-select-area');
    if (!container) return;

    container.innerHTML = '<div class="channel-loading">채널 정보 로딩 중...</div>';

    try {
      const response = await fetch('/api/drama/youtube-channels');
      const data = await response.json();

      if (!data.success) {
        // 인증 필요
        if (data.need_reauth || data.error?.includes('인증')) {
          container.innerHTML = `
            <div class="channel-error">
              <p>YouTube 인증이 필요합니다.</p>
              <a href="/api/youtube/auth" target="_blank" class="btn-youtube-auth">🔗 YouTube 연결하기</a>
            </div>
          `;
        } else {
          container.innerHTML = `
            <div class="channel-error">
              <p>${data.error || '채널을 불러올 수 없습니다.'}</p>
              <a href="/api/youtube/auth" target="_blank" class="btn-youtube-auth">🔗 다시 연결하기</a>
            </div>
          `;
        }
        return;
      }

      this.channels = data.channels || [];

      if (this.channels.length === 0) {
        container.innerHTML = '<div class="no-channels">연결된 채널이 없습니다.</div>';
        return;
      }

      // 헤더: 새로고침 버튼 + 다른 계정 연결
      let html = `
        <div class="channel-header">
          <button class="btn-refresh-channels" onclick="ImageMain.loadYouTubeChannels()" title="채널 목록 새로고침">🔄 새로고침</button>
          <a href="/api/youtube/auth?force=1" target="_blank" class="btn-add-account">➕ 다른 계정 연결</a>
        </div>
        <div class="brand-channel-hint">
          💡 브랜드 채널로 업로드하려면 "다른 계정 연결" 클릭 후<br>
          Google 계정 선택 화면에서 브랜드 채널을 직접 선택하세요.
        </div>
        <div class="channel-options">
      `;

      // 이전에 선택된 채널 유지, 없으면 첫 번째 선택
      const previousSelectedId = this.selectedChannelId;
      let foundPrevious = false;

      this.channels.forEach((channel, idx) => {
        const isSelected = previousSelectedId ? (channel.id === previousSelectedId) : (idx === 0);
        if (isSelected) {
          this.selectedChannelId = channel.id;
          foundPrevious = true;
        }
        html += `
          <label class="channel-option${isSelected ? ' selected' : ''}" data-channel-id="${channel.id}">
            <input type="radio" name="youtube-channel" value="${channel.id}" ${isSelected ? 'checked' : ''}>
            <img class="channel-thumbnail" src="${channel.thumbnail || ''}" alt="${this.escapeHtml(channel.title)}" onerror="this.style.display='none'">
            <div class="channel-info">
              <div class="channel-name">${this.escapeHtml(channel.title)}</div>
              <div class="channel-id">${channel.id}</div>
            </div>
          </label>
        `;
      });

      // 이전 선택이 없으면 첫 번째 선택
      if (!foundPrevious && this.channels.length > 0) {
        this.selectedChannelId = this.channels[0].id;
      }

      html += '</div>';
      container.innerHTML = html;

      // 클릭 이벤트 바인딩
      container.querySelectorAll('.channel-option').forEach(el => {
        el.addEventListener('click', () => {
          const channelId = el.dataset.channelId;
          this.selectChannel(channelId);
        });
      });

    } catch (error) {
      console.error('[ImageMain] Load channels error:', error);
      container.innerHTML = `
        <div class="channel-error">
          <p>채널 정보를 불러오는 데 실패했습니다.</p>
          <button onclick="ImageMain.loadYouTubeChannels()" class="btn-retry">🔄 다시 시도</button>
          <a href="/api/youtube/auth" target="_blank" class="btn-youtube-auth">🔗 YouTube 연결하기</a>
        </div>
      `;
    }
  },

  /**
   * 채널 선택
   */
  selectChannel(channelId) {
    this.selectedChannelId = channelId;

    // UI 업데이트
    document.querySelectorAll('.channel-option').forEach(el => {
      const isSelected = el.dataset.channelId === channelId;
      el.classList.toggle('selected', isSelected);
      el.querySelector('input').checked = isSelected;
    });

    const channel = this.channels.find(c => c.id === channelId);
    if (channel) {
      this.showStatus(`채널 선택: ${channel.title}`, 'success');
    }
  },

  /**
   * 공개 설정 변경
   */
  setPrivacy(privacy) {
    this.privacyStatus = privacy;

    // UI 업데이트
    document.querySelectorAll('.privacy-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.privacy === privacy);
    });

    // 예약 업로드는 비공개 상태에서만 가능
    const scheduleCheckbox = document.getElementById('schedule-upload');
    if (privacy !== 'private') {
      scheduleCheckbox.checked = false;
      this.toggleSchedule();
      scheduleCheckbox.disabled = true;
    } else {
      scheduleCheckbox.disabled = false;
    }

    console.log('[ImageMain] Privacy set to:', privacy);
  },

  /**
   * 예약 업로드 토글
   */
  toggleSchedule() {
    const checkbox = document.getElementById('schedule-upload');
    const wrapper = document.getElementById('schedule-datetime-wrapper');

    if (checkbox.checked) {
      wrapper.classList.remove('hidden');
      // 기본 시간 설정
      this.setDefaultScheduleTime();
    } else {
      wrapper.classList.add('hidden');
      this.scheduledTime = null;
    }
  },

  /**
   * 기본 예약 시간 설정 (내일 오전 9시)
   */
  setDefaultScheduleTime() {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(9, 0, 0, 0);

    // datetime-local 형식으로 변환 (YYYY-MM-DDTHH:mm)
    const dateStr = tomorrow.toISOString().slice(0, 16);
    const input = document.getElementById('schedule-datetime');
    if (input && !input.value) {
      input.value = dateStr;
    }
  },

  /**
   * YouTube 업로드
   */
  async uploadToYouTube() {
    if (!this.videoUrl) {
      this.showStatus('업로드할 영상이 없습니다. 먼저 영상을 생성해주세요.', 'warning');
      return;
    }

    const btn = document.getElementById('btn-youtube-upload');
    btn.disabled = true;
    btn.textContent = '⏳ 업로드 중...';

    try {
      // 선택된 제목 사용 (없으면 현재 선택된 input에서 가져오기)
      let title = this.selectedTitle;
      if (!title) {
        const selectedOption = document.querySelector('.title-option.selected .title-input');
        title = selectedOption?.value?.trim() || `영상_${this.sessionId}`;
      }

      const description = document.getElementById('youtube-description')?.value?.trim() || '';

      // videoUrl에서 서버 경로 추출 (예: /outputs/img_xxx/video.mp4 → outputs/img_xxx/video.mp4)
      const videoPath = this.videoUrl.startsWith('/') ? this.videoUrl.substring(1) : this.videoUrl;

      // 선택된 썸네일 경로 (있으면 추가)
      let thumbnailUrl = null;
      if (this.selectedThumbnailIdx !== null && this.thumbnailImages[this.selectedThumbnailIdx]) {
        thumbnailUrl = this.thumbnailImages[this.selectedThumbnailIdx];
      }

      // 예약 업로드 시간 확인
      let publishAt = null;
      const scheduleCheckbox = document.getElementById('schedule-upload');
      if (scheduleCheckbox?.checked) {
        const datetimeInput = document.getElementById('schedule-datetime');
        if (datetimeInput?.value) {
          // ISO 8601 형식으로 변환
          const localDate = new Date(datetimeInput.value);
          publishAt = localDate.toISOString();

          // 과거 시간 체크
          if (localDate <= new Date()) {
            this.showStatus('예약 시간은 현재보다 미래여야 합니다.', 'warning');
            btn.disabled = false;
            btn.textContent = '📺 YouTube 업로드';
            return;
          }
        }
      }

      // 상태 메시지
      if (publishAt) {
        const scheduleDate = new Date(publishAt);
        const dateStr = scheduleDate.toLocaleDateString('ko-KR', {
          month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });
        this.showStatus(`YouTube 예약 업로드 중... (${dateStr} 공개 예정)`, 'info');
      } else {
        this.showStatus('YouTube 업로드 중...', 'info');
      }

      // 썸네일 경로 변환 (URL → 서버 경로)
      let thumbnailPath = null;
      if (thumbnailUrl) {
        thumbnailPath = thumbnailUrl.startsWith('/') ? thumbnailUrl.substring(1) : thumbnailUrl;
      }

      console.log('[ImageMain] Uploading to YouTube:', {
        title, thumbnailPath, privacy: this.privacyStatus, publishAt, channelId: this.selectedChannelId
      });

      const response = await fetch('/api/youtube/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videoPath: videoPath,
          title: title,
          description: description,
          tags: ['AI영상', '자동생성'],
          categoryId: '22',  // People & Blogs
          privacyStatus: publishAt ? 'private' : this.privacyStatus,  // 예약 시 비공개 필수
          publish_at: publishAt,  // 예약 시간 (ISO 8601) - 백엔드 snake_case
          thumbnailPath: thumbnailPath,  // 선택한 썸네일 (서버 경로)
          channelId: this.selectedChannelId  // 선택한 채널 ID
        })
      });

      const result = await response.json();

      if (result.ok) {
        const videoUrl = result.videoUrl || `https://www.youtube.com/watch?v=${result.videoId}`;
        btn.textContent = '✅ 업로드 완료';

        if (publishAt) {
          const scheduleDate = new Date(publishAt);
          const dateStr = scheduleDate.toLocaleDateString('ko-KR', {
            month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit'
          });
          this.showStatus(`예약 업로드 완료! ${dateStr}에 공개됩니다.`, 'success');
        } else {
          this.showStatus(`YouTube 업로드 완료! ${videoUrl}`, 'success');
        }

        // 링크 열기
        if (confirm('YouTube에 업로드되었습니다!\n영상 페이지를 열까요?')) {
          window.open(videoUrl, '_blank');
        }
      } else {
        throw new Error(result.error || 'YouTube 업로드 실패');
      }

    } catch (error) {
      console.error('[ImageMain] YouTube upload error:', error);
      btn.disabled = false;
      btn.textContent = '📺 YouTube 업로드';

      // 인증 필요한 경우
      if (error.message.includes('인증') || error.message.includes('auth')) {
        if (confirm('YouTube 계정 연결이 필요합니다.\n연결 페이지로 이동하시겠습니까?')) {
          window.location.href = '/api/youtube/auth';
        }
      } else {
        this.showStatus('업로드 실패: ' + error.message, 'error');
      }
    }
  }
};

// DOM 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
  ImageMain.init();
});
