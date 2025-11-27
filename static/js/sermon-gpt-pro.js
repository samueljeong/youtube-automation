/**
 * sermon-gpt-pro.js
 * GPT PRO (Step3) 처리 기능
 *
 * 주요 함수:
 * - assembleGptProDraft()
 * - executeGptPro()
 * - 전체 복사 기능
 *
 * 이 파일은 sermon.html의 3137~3589줄 코드를 모듈화한 것입니다.
 */

// ===== GPT PRO 초안 구성 =====
function assembleGptProDraft() {
  const ref = document.getElementById('sermon-ref')?.value || '';
  const title = getSelectedTitle();
  const target = document.getElementById('sermon-target')?.value || '';
  const worshipType = document.getElementById('worship-type')?.value || '';
  const duration = document.getElementById('sermon-duration')?.value || '';
  const specialNotes = document.getElementById('special-notes')?.value || '';

  let draft = '';

  // 메타 정보
  draft += `【설교 정보】\n`;
  draft += `성경본문: ${ref}\n`;
  if (title) draft += `제목: ${title}\n`;
  if (target) draft += `대상: ${target}\n`;
  if (worshipType) draft += `예배유형: ${worshipType}\n`;
  if (duration) draft += `분량: ${duration}\n`;
  if (specialNotes) draft += `특별참고사항: ${specialNotes}\n`;
  draft += '\n';

  // Step 결과들
  const steps = getCurrentSteps();
  steps.forEach(step => {
    if (window.stepResults[step.id]) {
      const stepType = step.stepType || 'step1';
      const label = stepType === 'step1' ? 'Step1' : 'Step2';
      draft += `【${label}. ${step.name}】\n`;
      draft += window.stepResults[step.id] + '\n\n';
    }
  });

  return draft;
}

// ===== GPT PRO 실행 =====
async function executeGptPro() {
  const ref = document.getElementById('sermon-ref')?.value;
  if (!ref) {
    alert('성경본문을 입력하세요.');
    return;
  }

  if (!window.currentStyleId) {
    alert('설교 스타일을 선택하세요.');
    return;
  }

  // Step1, Step2 완료 확인
  const steps = getCurrentSteps();
  const step1Steps = steps.filter(s => (s.stepType || 'step1') === 'step1');
  const step2Steps = steps.filter(s => (s.stepType || 'step1') === 'step2');
  const step1Completed = step1Steps.length > 0 && step1Steps.every(s => window.stepResults[s.id]);
  const step2Completed = step2Steps.length > 0 && step2Steps.every(s => window.stepResults[s.id]);

  if (!step1Completed || !step2Completed) {
    alert('Step1, Step2를 먼저 완료해주세요.');
    return;
  }

  showGptLoading('GPT PRO 설교문 생성 중...');

  try {
    // Step1, Step2 결과 수집
    let step1Result = {};
    let step2Result = {};

    step1Steps.forEach(s => {
      if (window.stepResults[s.id]) {
        try {
          step1Result = JSON.parse(window.stepResults[s.id]);
        } catch (e) {
          step1Result = { raw: window.stepResults[s.id] };
        }
      }
    });

    step2Steps.forEach(s => {
      if (window.stepResults[s.id]) {
        try {
          step2Result = JSON.parse(window.stepResults[s.id]);
        } catch (e) {
          step2Result = { raw: window.stepResults[s.id] };
        }
      }
    });

    // 모델 설정
    const modelSettings = getModelSettings(window.currentCategory);
    const model = modelSettings?.gptPro || 'gpt-5';

    // 토큰 설정 (스타일별 또는 기본값)
    const catSettings = window.config.categorySettings[window.currentCategory];
    let maxTokens = modelSettings?.step3MaxTokens || 16000;
    if (catSettings?.styleTokens?.[window.currentStyleId]) {
      maxTokens = catSettings.styleTokens[window.currentStyleId];
    }

    // Step3 지침 로드
    const step3GuideKey = getGuideKey(window.currentCategory, 'step3');
    const step3Guide = localStorage.getItem(step3GuideKey) || '';

    const requestBody = {
      ref: ref,
      title: getSelectedTitle(),
      target: document.getElementById('sermon-target')?.value || '',
      worshipType: document.getElementById('worship-type')?.value || '',
      duration: document.getElementById('sermon-duration')?.value || '',
      specialNotes: document.getElementById('special-notes')?.value || '',
      styleName: getCurrentStyle()?.name || '',
      category: window.currentCategory,
      model: model,
      maxTokens: maxTokens,
      customPrompt: window.DEFAULT_STEP3_PROMPT,
      step1Result: step1Result,
      step2Result: step2Result
    };

    // Step3 지침이 있으면 추가
    if (step3Guide.trim()) {
      try {
        if (step3Guide.trim().startsWith('{')) {
          requestBody.step3Guide = JSON.parse(step3Guide);
        } else {
          requestBody.step3Guide = step3Guide;
        }
      } catch (e) {
        requestBody.step3Guide = step3Guide;
      }
    }

    const response = await fetch('/api/sermon/gpt-pro', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    if (data.error) {
      throw new Error(data.error);
    }

    // 결과 표시
    const resultTextarea = document.getElementById('gpt-pro-result');
    const resultContainer = document.getElementById('gpt-pro-result-container');

    if (resultTextarea) {
      resultTextarea.value = data.result;
      autoResize(resultTextarea);
    }
    if (resultContainer) {
      resultContainer.style.display = 'block';
    }

    // 토큰 사용량 표시
    if (data.usage) {
      const usageEl = document.getElementById('usage-step3');
      if (usageEl) {
        usageEl.textContent = `in(${data.usage.prompt_tokens?.toLocaleString() || 0}), out(${data.usage.completion_tokens?.toLocaleString() || 0}), ${data.costKRW || '0.0'}원`;
      }
    }

  } catch (error) {
    console.error('GPT PRO 실행 오류:', error);
    alert('GPT PRO 처리 중 오류가 발생했습니다: ' + error.message);
  } finally {
    hideGptLoading();
  }
}

// ===== 전체 복사 기능 =====
function copyAllResults() {
  const draft = assembleGptProDraft();
  navigator.clipboard.writeText(draft).then(() => {
    showStatus('✅ 전체 내용이 복사되었습니다!');
    setTimeout(hideStatus, 2000);
  }).catch(err => {
    console.error('복사 실패:', err);
    alert('복사에 실패했습니다.');
  });
}

// 전역 노출
window.assembleGptProDraft = assembleGptProDraft;
window.executeGptPro = executeGptPro;
window.copyAllResults = copyAllResults;
