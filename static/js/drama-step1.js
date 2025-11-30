/**
 * Drama Lab - Step 1: 대본 생성
 * 초기화됨: 2024-11-28
 */

// Step1 모듈
window.DramaStep1 = {
  // 상태
  currentScript: null,
  isGenerating: false,

  init() {
    console.log('[Step1] 대본 생성 모듈 초기화');
  },

  // JSON 응답 안전하게 파싱 (HTML 에러 페이지 방어)
  async safeJsonParse(response, stepName) {
    const text = await response.text();
    try {
      return JSON.parse(text);
    } catch (parseError) {
      console.error(`[${stepName}] JSON 파싱 실패:`, parseError);
      console.error(`[${stepName}] 응답 내용 (처음 500자):`, text.substring(0, 500));

      // HTML 에러 페이지인지 확인
      if (text.trim().startsWith('<')) {
        throw new Error(`서버에서 HTML 에러 페이지를 반환했습니다 (status: ${response.status}). 서버 로그를 확인해주세요.`);
      }
      throw new Error(`서버 응답을 파싱할 수 없습니다: ${parseError.message}`);
    }
  },

  // 설정값 가져오기
  getConfig() {
    return {
      channelType: document.getElementById('channel-type')?.value || 'senior-nostalgia',
      contentType: document.getElementById('content-type')?.value || 'nostalgia',
      duration: document.getElementById('duration')?.value || '10min',
      aiModel: document.getElementById('ai-model')?.value || 'anthropic/claude-sonnet-4.5',
      topic: document.getElementById('topic-input')?.value?.trim() || ''
    };
  },

  // duration 값을 분으로 변환
  durationToMinutes(duration) {
    const map = {
      '2min': '2분',
      '5min': '5분',
      '10min': '10분',
      '20min': '20분',
      '30min': '30분'
    };
    return map[duration] || '10분';
  },

  // 대본 생성 메인 함수
  async generateScript() {
    if (this.isGenerating) {
      DramaUtils.showStatus('이미 생성 중입니다...', 'warning');
      return;
    }

    const config = this.getConfig();
    console.log('[Step1] 대본 생성 시작:', config);

    this.isGenerating = true;
    const btn = document.getElementById('btn-generate-script');
    const originalText = btn.innerHTML;
    let totalTokens = 0;
    let totalCost = 0;

    try {
      // 버튼 상태 변경
      btn.innerHTML = '<span class="btn-icon">⏳</span> 생성 중...';
      btn.disabled = true;

      // === Step 1: GPT-4o-mini로 기획 생성 ===
      DramaUtils.showLoading('1/3 단계: 스토리 기획 중...', 'GPT-4o-mini가 기획을 작성합니다');

      const step1Response = await fetch('/api/drama/gpt-plan-step1', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videoCategory: this.getVideoCategory(config.contentType),
          duration: this.durationToMinutes(config.duration),
          customDirective: config.topic,
          aiModel: config.aiModel
        })
      });

      const step1Data = await this.safeJsonParse(step1Response, 'Step1-기획');
      console.log('[Step1] 기획 완료:', step1Data);

      if (!step1Data.ok) {
        throw new Error(step1Data.error || '기획 생성에 실패했습니다.');
      }
      totalTokens += step1Data.tokens || 0;
      totalCost += step1Data.cost || 0;

      // === Step 2: GPT-4o-mini로 구조화 ===
      DramaUtils.showLoading('2/3 단계: 장면 구조화 중...', 'GPT-4o-mini가 장면을 구성합니다');

      const step2Response = await fetch('/api/drama/gpt-plan-step2', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videoCategory: this.getVideoCategory(config.contentType),
          duration: this.durationToMinutes(config.duration),
          customDirective: config.topic,
          step1Result: step1Data.result
        })
      });

      const step2Data = await this.safeJsonParse(step2Response, 'Step1-구조화');
      console.log('[Step1] 구조화 완료:', step2Data);

      if (!step2Data.ok) {
        throw new Error(step2Data.error || '구조화에 실패했습니다.');
      }
      totalTokens += step2Data.tokens || 0;
      totalCost += step2Data.cost || 0;

      // === Step 3: Claude Sonnet 4.5로 대본 작성 ===
      DramaUtils.showLoading('3/3 단계: 대본 작성 중...', 'Claude Sonnet 4.5가 대본을 작성합니다 (약 1-2분 소요)');

      const step3Response = await fetch('/api/drama/claude-step3', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category: config.duration,  // "10min" 등
          durationText: this.durationToMinutes(config.duration),
          videoCategory: this.getVideoCategory(config.contentType),
          customDirective: config.topic,
          draftContent: step1Data.result + '\n\n' + step2Data.result,
          model: config.aiModel  // 백엔드는 'model' 파라미터를 기대함
        })
      });

      const step3Data = await this.safeJsonParse(step3Response, 'Step1-대본작성');
      console.log('[Step1] 대본 작성 완료:', step3Data);

      if (!step3Data.ok) {
        throw new Error(step3Data.error || '대본 작성에 실패했습니다.');
      }
      totalTokens += step3Data.tokens || 0;
      totalCost += step3Data.cost || 0;

      // 결과 저장
      this.currentScript = {
        content: step3Data.result,
        config: config,
        tokens: totalTokens,
        cost: totalCost,
        createdAt: new Date().toISOString(),
        // 중간 결과도 저장
        planning: step1Data.result,
        structure: step2Data.result
      };

      // 세션에 저장
      DramaSession.setStepData('step1', this.currentScript);

      // 메모리에도 저장 (Step5에서 사용 가능하게)
      dramaApp.session.script = step3Data.result;
      DramaMain.saveSessionToStorage();

      // 결과 표시
      this.displayResult(step3Data.result);

      // 성공 메시지
      DramaUtils.showStatus(`대본 생성 완료! (토큰: ${totalTokens}, 비용: ₩${totalCost})`, 'success');

    } catch (error) {
      console.error('[Step1] 오류:', error);
      DramaUtils.showStatus(`오류: ${error.message}`, 'error');
    } finally {
      // 버튼 복원
      btn.innerHTML = originalText;
      btn.disabled = false;
      this.isGenerating = false;
      DramaUtils.hideLoading();
    }
  },

  // 콘텐츠 유형을 비디오 카테고리로 변환
  getVideoCategory(contentType) {
    const map = {
      'nostalgia': '옛날이야기',  // 백엔드 video_category_prompts와 일치
      'testimony': '간증',
      'drama': '드라마'
    };
    return map[contentType] || '간증';
  },

  // 결과 표시
  displayResult(content) {
    const resultArea = document.getElementById('step1-result-area');
    const preview = document.getElementById('script-preview');
    const editor = document.getElementById('script-editor');
    const metadata = document.getElementById('script-metadata');

    if (resultArea && preview) {
      // JSON이면 읽기 좋은 형태로 변환, 아니면 마크다운 형식으로 표시
      const formattedContent = this.formatContent(content);
      preview.innerHTML = formattedContent.html;
      editor.value = content;

      // JSON 메타데이터가 있으면 표시
      if (metadata && this.currentScript) {
        let metaHtml = `
          <div class="metadata-item">
            <span class="label">생성 시간:</span>
            <span class="value">${new Date(this.currentScript.createdAt).toLocaleString('ko-KR')}</span>
          </div>
          <div class="metadata-item">
            <span class="label">토큰 사용:</span>
            <span class="value">${this.currentScript.tokens}</span>
          </div>
          <div class="metadata-item">
            <span class="label">예상 비용:</span>
            <span class="value">₩${this.currentScript.cost}</span>
          </div>
        `;

        // JSON에서 추출한 메타데이터 추가
        if (formattedContent.jsonMeta) {
          const jm = formattedContent.jsonMeta;
          if (jm.title) {
            metaHtml += `
              <div class="metadata-item">
                <span class="label">제목:</span>
                <span class="value">${jm.title}</span>
              </div>
            `;
          }
          if (jm.duration) {
            metaHtml += `
              <div class="metadata-item">
                <span class="label">영상 길이:</span>
                <span class="value">${jm.duration}</span>
              </div>
            `;
          }
        }
        metadata.innerHTML = metaHtml;
      }

      // 결과 영역 표시
      resultArea.classList.remove('hidden');

      // 스크롤 이동
      resultArea.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  },

  // 콘텐츠 포맷팅 (JSON이면 나레이션만 추출, 아니면 마크다운 변환)
  formatContent(content) {
    if (!content) return { html: '', jsonMeta: null };

    // JSON 형식인지 확인
    let jsonData = null;
    try {
      if (content.trim().startsWith('{')) {
        jsonData = JSON.parse(content);
        console.log('[Step1] JSON 대본 감지됨 - 읽기 좋은 형태로 변환');
      }
    } catch (e) {
      // JSON 파싱 실패 - 텍스트로 처리
    }

    // JSON이면 나레이션 중심으로 표시
    if (jsonData) {
      return this.formatJsonContent(jsonData);
    }

    // 텍스트면 기존 마크다운 변환
    const html = content
      // 제목 (### → h3)
      .replace(/^### (.+)$/gm, '<h4>$1</h4>')
      // 소제목 (## → h3)
      .replace(/^## (.+)$/gm, '<h3>$1</h3>')
      // 굵은 텍스트
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      // 리스트 아이템
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      // 숫자 리스트
      .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
      // 줄바꿈
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n/g, '<br>')
      // 감싸기
      .replace(/^/, '<p>')
      .replace(/$/, '</p>')
      // li 그룹화 (간단한 처리)
      .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
      .replace(/<\/ul>\s*<ul>/g, '');

    return { html, jsonMeta: null };
  },

  // JSON 대본을 읽기 좋은 HTML로 변환 (나레이션만 표시, 메타데이터는 내부 보관)
  formatJsonContent(jsonData) {
    let html = '';
    const jsonMeta = {};

    // 메타데이터 추출 (UI 상단 메타데이터 패널에만 표시)
    if (jsonData.metadata) {
      jsonMeta.title = jsonData.metadata.title;
      jsonMeta.duration = jsonData.metadata.duration;
      jsonMeta.target_age = jsonData.metadata.target_age;
    }
    if (jsonData.meta) {
      jsonMeta.title = jsonMeta.title || jsonData.meta.one_line_concept;
      jsonMeta.duration = jsonMeta.duration || `${jsonData.meta.target_length_minutes}분`;
    }

    // 하이라이트 프리뷰 (opening_hook 또는 highlight_preview)
    const openingHook = jsonData.highlight?.opening_hook || jsonData.highlight_preview?.narration;
    if (openingHook) {
      html += `<div class="script-opening">
        <p class="opening-hook">${this.escapeHtml(openingHook)}</p>
      </div>`;
    }

    // storyline 표시 (나레이션만)
    if (jsonData.storyline) {
      html += '<div class="script-storyline">';

      if (Array.isArray(jsonData.storyline)) {
        jsonData.storyline.forEach((scene, idx) => {
          html += this.formatSceneNarrationOnly(scene, idx + 1);
        });
      } else if (typeof jsonData.storyline === 'object') {
        const parts = [
          { key: 'opening', label: '도입' },
          { key: 'development', label: '전개' },
          { key: 'climax', label: '절정' },
          { key: 'resolution', label: '결말' },
          { key: 'ending', label: '마무리' }
        ];
        parts.forEach(({ key, label }) => {
          if (jsonData.storyline[key]) {
            html += `<div class="script-section">
              <h4 class="section-label">${label}</h4>
              ${this.formatSceneNarrationOnly(jsonData.storyline[key], null)}
            </div>`;
          }
        });
      }

      html += '</div>';
    }

    // scenes 배열 (나레이션만 추출)
    if (jsonData.scenes && Array.isArray(jsonData.scenes)) {
      html += '<div class="script-scenes">';
      jsonData.scenes.forEach((scene, idx) => {
        html += this.formatSceneNarrationOnly(scene, idx + 1);
      });
      html += '</div>';
    }

    // script 필드가 있는 경우
    if (jsonData.script) {
      html += '<div class="script-content">';
      if (typeof jsonData.script === 'string') {
        html += `<p>${this.escapeHtml(jsonData.script).replace(/\n/g, '<br>')}</p>`;
      } else if (jsonData.script.full_text) {
        html += `<p>${this.escapeHtml(jsonData.script.full_text).replace(/\n/g, '<br>')}</p>`;
      }
      html += '</div>';
    }

    // 하이라이트 key_message (있으면 마지막에)
    if (jsonData.highlight?.key_message) {
      html += `<div class="script-closing">
        <p class="key-message"><strong>핵심 메시지:</strong> ${this.escapeHtml(jsonData.highlight.key_message)}</p>
      </div>`;
    }

    // 내용이 없으면 JSON에서 텍스트만 추출 시도
    if (!html) {
      const extracted = this.extractAllNarrations(jsonData);
      if (extracted) {
        html = `<div class="script-content"><p>${this.escapeHtml(extracted).replace(/\n/g, '<br>')}</p></div>`;
      } else {
        html = `<pre class="json-fallback">${this.escapeHtml(JSON.stringify(jsonData, null, 2))}</pre>`;
      }
    }

    return { html, jsonMeta };
  },

  // 씬에서 나레이션만 추출 (메타데이터 제외)
  formatSceneNarrationOnly(scene, sceneNum) {
    if (!scene) return '';

    // 문자열이면 바로 표시
    if (typeof scene === 'string') {
      return `<div class="scene-block">
        ${sceneNum ? `<span class="scene-num">장면 ${sceneNum}</span>` : ''}
        <p>${this.escapeHtml(scene).replace(/\n/g, '<br>')}</p>
      </div>`;
    }

    // 객체면 나레이션 필드만 추출 (메타데이터 필드는 무시)
    let content = '';

    // 나레이션 필드 우선순위
    const narrationFields = ['narration', 'text', 'content', 'dialogue', 'script'];
    for (const field of narrationFields) {
      if (scene[field]) {
        if (typeof scene[field] === 'string') {
          content = scene[field];
          break;
        } else if (Array.isArray(scene[field])) {
          content = scene[field].join('\n\n');
          break;
        }
      }
    }

    // 나레이션이 없으면 빈 문자열 반환 (메타데이터만 있는 씬은 표시 안함)
    if (!content) return '';

    return `<div class="scene-block">
      ${sceneNum ? `<span class="scene-num">장면 ${sceneNum}</span>` : ''}
      <p>${this.escapeHtml(content).replace(/\n/g, '<br>')}</p>
    </div>`;
  },

  // JSON에서 모든 나레이션 텍스트 추출 (폴백용)
  extractAllNarrations(obj, depth = 0) {
    if (depth > 10) return ''; // 무한 재귀 방지
    if (!obj || typeof obj !== 'object') return '';

    let texts = [];

    // 배열이면 각 요소에서 추출
    if (Array.isArray(obj)) {
      obj.forEach(item => {
        const extracted = this.extractAllNarrations(item, depth + 1);
        if (extracted) texts.push(extracted);
      });
    } else {
      // 객체면 나레이션 필드 찾기
      const narrationFields = ['narration', 'text', 'content', 'dialogue', 'script', 'full_text'];
      for (const field of narrationFields) {
        if (obj[field] && typeof obj[field] === 'string') {
          texts.push(obj[field]);
        }
      }
      // 중첩 객체 탐색 (메타데이터 필드 제외)
      const skipFields = ['metadata', 'meta', 'checks', 'characters_in_scene', 'tts_notes', 'links_to_next_scene'];
      for (const key of Object.keys(obj)) {
        if (!skipFields.includes(key) && typeof obj[key] === 'object') {
          const extracted = this.extractAllNarrations(obj[key], depth + 1);
          if (extracted) texts.push(extracted);
        }
      }
    }

    return texts.join('\n\n');
  },

  // HTML 이스케이프
  escapeHtml(text) {
    if (!text) return '';
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  },

  // 대본 복사
  async copyScript() {
    if (!this.currentScript?.content) {
      DramaUtils.showStatus('복사할 대본이 없습니다.', 'warning');
      return;
    }

    try {
      await navigator.clipboard.writeText(this.currentScript.content);
      DramaUtils.showStatus('대본이 클립보드에 복사되었습니다.', 'success');
    } catch (error) {
      console.error('[Step1] 복사 실패:', error);
      DramaUtils.showStatus('복사에 실패했습니다.', 'error');
    }
  },

  // 대본 다운로드
  downloadScript() {
    if (!this.currentScript?.content) {
      DramaUtils.showStatus('다운로드할 대본이 없습니다.', 'warning');
      return;
    }

    const blob = new Blob([this.currentScript.content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `drama_script_${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    DramaUtils.showStatus('대본이 다운로드되었습니다.', 'success');
  },

  // 편집 모드 토글
  toggleEdit() {
    const preview = document.getElementById('script-preview');
    const editor = document.getElementById('script-editor');
    const editBtn = document.querySelector('.btn-edit');

    if (editor.classList.contains('hidden')) {
      // 편집 모드로 전환
      preview.classList.add('hidden');
      editor.classList.remove('hidden');
      editor.focus();
      editBtn.textContent = '미리보기';
    } else {
      // 미리보기 모드로 전환
      const editedContent = editor.value;
      this.currentScript.content = editedContent;
      preview.innerHTML = this.formatContent(editedContent);
      preview.classList.remove('hidden');
      editor.classList.add('hidden');
      editBtn.textContent = '편집';

      // 세션 업데이트
      DramaSession.setStepData('step1', this.currentScript);
    }
  },

  // 다시 생성
  regenerate() {
    // 확인 메시지
    if (this.currentScript && !confirm('현재 대본을 버리고 새로 생성하시겠습니까?')) {
      return;
    }

    // 결과 영역 숨기기
    const resultArea = document.getElementById('step1-result-area');
    if (resultArea) {
      resultArea.classList.add('hidden');
    }

    // 다시 생성
    this.generateScript();
  },

  // 세션에서 데이터 복원
  restore(data) {
    if (data) {
      this.currentScript = data;
      if (data.content) {
        this.displayResult(data.content);
      }
    }
  }
};
