/**
 * sermon-step.js
 * Step1/Step2/Step3 처리 기능
 *
 * 주요 함수:
 * - executeStep(stepId)
 *
 * 이 파일은 sermon.html의 4166~4356줄 코드를 모듈화한 것입니다.
 * 전체 코드 마이그레이션이 필요합니다.
 */

// ===== 처리 단계 실행 =====
async function executeStep(stepId) {
  const step = getCurrentSteps().find(s => s.id === stepId);
  if (!step) return;

  const ref = document.getElementById('sermon-ref')?.value || '';
  const target = document.getElementById('sermon-target')?.value || '';
  const worshipType = document.getElementById('sermon-worship-type')?.value || '';
  const duration = document.getElementById('sermon-duration')?.value || '';
  const specialNotes = document.getElementById('special-notes')?.value || '';

  // 지침 로드
  const guideKey = getGuideKey(window.currentCategory, stepId);
  const guide = localStorage.getItem(guideKey) || '';
  const masterGuide = window.config.categorySettings[window.currentCategory]?.masterGuide || '';

  // 스타일 정보
  const style = getCurrentStyle();
  const styleName = style?.name || '';

  // 모델 설정
  const modelSettings = getModelSettings(window.currentCategory);
  const stepType = step.stepType || 'step1';
  const modelKey = stepType === 'step1' ? 'step1' : 'step2';
  const model = modelSettings?.[modelKey] || 'gpt-4o';

  // Step1 결과 (Step2에서 필요)
  let step1Results = {};
  if (stepType === 'step2') {
    const steps = getCurrentSteps();
    const step1Steps = steps.filter(s => (s.stepType || 'step1') === 'step1');
    step1Steps.forEach(s => {
      if (window.stepResults[s.id]) {
        step1Results[s.id] = window.stepResults[s.id];
      }
    });
  }

  const requestBody = {
    step: stepId,
    stepName: step.name,
    stepType: stepType,
    ref: ref,
    target: target,
    worshipType: worshipType,
    duration: duration,
    specialNotes: specialNotes,
    guide: guide,
    masterGuide: masterGuide,
    styleName: styleName,
    model: model,
    step1Results: step1Results,
    category: window.currentCategory
  };

  try {
    const response = await fetch('/api/sermon/process', {
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

    // 결과 저장
    window.stepResults[stepId] = data.result;

    // 토큰 사용량 저장
    if (data.usage) {
      window.stepUsage = window.stepUsage || {};
      window.stepUsage[stepId] = {
        inputTokens: data.usage.prompt_tokens,
        outputTokens: data.usage.completion_tokens,
        costKRW: data.costKRW || '0.0'
      };
    }

    // UI 업데이트
    const textarea = document.getElementById(`result-${stepId}`);
    if (textarea) {
      textarea.value = truncateResult(data.result, stepType);
    }

    // 제목 추출 (step1에서)
    if (stepType === 'step1' && data.result) {
      try {
        const parsed = JSON.parse(data.result);
        if (parsed.title_options && Array.isArray(parsed.title_options)) {
          displayTitleOptions(parsed.title_options);
        }
      } catch (e) {
        // JSON 파싱 실패 무시
      }
    }

    // 자동 저장
    autoSaveStepResults();

    return data.result;

  } catch (error) {
    console.error(`Step ${stepId} 실행 오류:`, error);
    throw error;
  }
}

// 지침 키 생성
function getGuideKey(category, stepId, styleId = window.currentStyleId) {
  const stylePart = styleId || 'default';
  return `guide-${category}-${stylePart}-${stepId}`;
}

// 전역 노출
window.executeStep = executeStep;
window.getGuideKey = getGuideKey;
