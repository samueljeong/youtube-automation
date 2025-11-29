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

  // 설정값 가져오기
  getConfig() {
    return {
      channelType: document.getElementById('channel-type')?.value || 'senior-nostalgia',
      contentType: document.getElementById('content-type')?.value || 'nostalgia',
      duration: document.getElementById('duration')?.value || '10min',
      aiModel: document.getElementById('ai-model')?.value || 'anthropic/claude-sonnet-4-5',
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

      const step1Data = await step1Response.json();
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

      const step2Data = await step2Response.json();
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
          selectedModel: config.aiModel
        })
      });

      const step3Data = await step3Response.json();
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
      'nostalgia': '시니어 향수 드라마',
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
      // 마크다운 형식으로 표시
      preview.innerHTML = this.formatContent(content);
      editor.value = content;

      // 메타데이터 표시
      if (metadata && this.currentScript) {
        metadata.innerHTML = `
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
      }

      // 결과 영역 표시
      resultArea.classList.remove('hidden');

      // 스크롤 이동
      resultArea.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  },

  // 콘텐츠 포맷팅 (간단한 마크다운 변환)
  formatContent(content) {
    if (!content) return '';

    return content
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
