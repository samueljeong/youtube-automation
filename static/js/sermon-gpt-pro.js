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
  const worshipType = document.getElementById('sermon-worship-type')?.value || '';
  const duration = document.getElementById('sermon-duration')?.value || '20분';
  const specialNotes = document.getElementById('special-notes')?.value || '';
  const style = getCurrentStyle();
  const styleName = style?.name || '';
  const categoryLabel = getCategoryLabel(window.currentCategory);
  const today = new Date().toLocaleDateString('ko-KR');

  let draft = '';

  // 헤더
  draft += `====================================\n`;
  draft += `📖 설교 초안 자료 (GPT-5.1 작성용)\n`;
  draft += `====================================\n\n`;

  // 최우선 지침
  draft += `==================================================\n`;
  draft += `【 ★★★ 최우선 지침 ★★★ 】\n`;
  draft += `==================================================\n\n`;

  if (duration) {
    draft += `🚨 분량: ${duration}\n`;
    draft += `   → 이 설교는 반드시 ${duration} 분량으로 작성하세요.\n`;
    draft += `   → 아래 초안이 길더라도 ${duration}에 맞춰 압축하세요.\n\n`;
  }

  if (worshipType) {
    draft += `🚨 예배/집회 유형: ${worshipType}\n`;
    draft += `   → '${worshipType}'에 적합한 톤과 내용으로 작성하세요.\n\n`;
  }

  if (target) {
    draft += `🚨 대상: ${target}\n\n`;
  }

  draft += `==================================================\n\n`;

  // 안내 문구
  draft += `⚠️ 중요: 이 자료는 gpt-4o-mini가 만든 '초안'입니다.\n`;
  draft += `GPT-5.1은 이 자료를 참고하되, 처음부터 새로 작성해주세요.\n`;
  draft += `mini가 만든 문장을 그대로 복사하지 말고, 자연스러운 설교문으로 재작성하세요.\n\n`;

  draft += `==================================================\n\n`;

  // 기본 정보
  draft += `📌 기본 정보\n`;
  draft += `- 카테고리: ${categoryLabel}\n`;
  if (styleName) draft += `- 스타일: ${styleName}\n`;
  draft += `- 성경구절: ${ref}\n`;
  if (title) draft += `- 제목: ${title}\n`;
  if (worshipType) draft += `- 예배·집회 유형: ${worshipType}\n`;
  if (duration) draft += `- 분량: ${duration}\n`;
  if (target) draft += `- 대상: ${target}\n`;
  draft += `- 작성일: ${today}\n`;
  if (specialNotes) draft += `- 특별참고사항: ${specialNotes}\n`;

  draft += `\n==================================================\n\n`;

  // Step 결과들
  const steps = getCurrentSteps();
  let stepNum = 1;
  steps.forEach(step => {
    if (window.stepResults[step.id]) {
      const stepType = step.stepType || 'step1';
      const label = stepType === 'step1' ? 'STEP 1' : 'STEP 2';
      draft += `【 ${stepNum}. ${label} — ${step.name} 】\n\n`;
      draft += window.stepResults[step.id] + '\n\n';
      draft += `==================================================\n\n`;
      stepNum++;
    }
  });

  // 최종 작성 지침
  draft += `==================================================\n`;
  draft += `📝 최종 작성 지침:\n`;
  draft += `==================================================\n`;
  draft += `위의 초안 자료를 참고하여, 완성도 높은 설교문을 처음부터 새로 작성해주세요.\n\n`;

  if (duration) {
    draft += `⚠️ 가장 중요: 반드시 ${duration} 분량을 지켜주세요!\n`;
  }
  if (worshipType) {
    draft += `⚠️ 예배 유형 '${worshipType}'에 맞는 톤으로 작성하세요.\n`;
  }

  draft += `\nmax_tokens를 16000으로 설정하고, ${duration || '20분'} 분량 내에서 충분히 상세하게 작성해주세요.\n`;

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

  // Step3 코드 검증
  const step3Code = prompt('Step3(AI 설교문 완성) 사용 코드를 입력하세요:');
  if (!step3Code) {
    return; // 취소됨
  }

  const codeResult = await verifyCode(step3Code);
  if (!codeResult.valid) {
    alert(codeResult.error);
    return;
  }

  // 코드 검증 성공 - 남은 횟수 안내
  if (codeResult.remaining !== undefined) {
    console.log(`[Step3] 코드 검증 성공. 남은 횟수: ${codeResult.remaining}`);
  }

  // Step1, Step2 완료 확인
  const steps = getCurrentSteps();
  console.log('[Step3] steps:', steps);
  const step1Steps = steps.filter(s => (s.stepType || 'step1') === 'step1');
  const step2Steps = steps.filter(s => (s.stepType || 'step1') === 'step2');
  console.log('[Step3] step1Steps:', step1Steps.length, 'step2Steps:', step2Steps.length);
  const step1Completed = step1Steps.length > 0 && step1Steps.every(s => window.stepResults[s.id]);
  const step2Completed = step2Steps.length > 0 && step2Steps.every(s => window.stepResults[s.id]);
  console.log('[Step3] step1Completed:', step1Completed, 'step2Completed:', step2Completed);

  if (!step1Completed || !step2Completed) {
    alert('Step1, Step2를 먼저 완료해주세요.');
    return;
  }

  console.log('[Step3] showGptLoading 호출');
  showGptLoading('GPT PRO 설교문 생성 중...', true);

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
      reference: ref,
      title: getSelectedTitle(),
      target: document.getElementById('sermon-target')?.value || '',
      worshipType: document.getElementById('sermon-worship-type')?.value || '',
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

    console.log('[Step3] API 호출 시작');
    const response = await fetch('/api/sermon/gpt-pro', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    });
    console.log('[Step3] API 응답 status:', response.status);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    console.log('[Step3] API 응답 data:', data);

    if (data.error) {
      throw new Error(data.error);
    }

    // 결과 표시
    console.log('[Step3] 결과 표시 시작');
    const resultTextarea = document.getElementById('gpt-pro-result');
    const resultContainer = document.getElementById('gpt-pro-result-container');
    const step12Area = document.getElementById('step12-result-area');
    console.log('[Step3] resultTextarea:', !!resultTextarea, 'resultContainer:', !!resultContainer);

    if (resultTextarea) {
      resultTextarea.value = data.result;
      autoResize(resultTextarea);
    }

    // Step1/2 결과 숨기고 Step3 결과 표시 (같은 자리)
    if (step12Area) {
      step12Area.style.display = 'none';
    }
    if (resultContainer) {
      resultContainer.style.display = 'block';
      console.log('[Step3] 결과 컨테이너 표시됨');
    }

    // 토큰 사용량 표시 (숫자만)
    if (data.usage) {
      const usageEl = document.getElementById('usage-step3');
      if (usageEl) {
        const inTokens = data.usage.prompt_tokens || 0;
        const outTokens = data.usage.completion_tokens || 0;
        const cost = data.costKRW || '0';
        usageEl.textContent = `in(${inTokens.toLocaleString()}), out(${outTokens.toLocaleString()}), ${cost}`;
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
