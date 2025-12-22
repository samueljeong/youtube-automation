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

// ===== 분량→글자 수 변환 함수 =====
function getDurationCharCount(durationStr) {
  /**
   * 분량(분)을 글자 수로 변환.
   *
   * 한국어 설교 말하기 속도: 약 270자/분 (공백 포함)
   * - 느린 속도: 250자/분
   * - 보통 속도: 270자/분
   * - 빠른 속도: 300자/분
   */
  const CHARS_PER_MIN = 270;

  // 숫자 추출
  let minutes = 20;
  if (typeof durationStr === 'number') {
    minutes = Math.floor(durationStr);
  } else if (typeof durationStr === 'string') {
    const match = durationStr.match(/(\d+)/);
    minutes = match ? parseInt(match[1], 10) : 20;
  }

  // 글자 수 계산 (±10% 여유)
  const targetChars = minutes * CHARS_PER_MIN;
  const minChars = Math.floor(targetChars * 0.9);
  const maxChars = Math.floor(targetChars * 1.1);

  return {
    minutes,
    minChars,
    maxChars,
    targetChars,
    charsPerMin: CHARS_PER_MIN
  };
}

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
  const styleId = window.currentStyleId || '';
  const categoryLabel = getCategoryLabel(window.currentCategory);
  const today = new Date().toLocaleDateString('ko-KR');

  // 분량→글자 수 변환
  const durationInfo = getDurationCharCount(duration);

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
    draft += `   → 목표 글자 수: ${durationInfo.targetChars.toLocaleString()}자 (공백 포함)\n`;
    draft += `   → 허용 범위: ${durationInfo.minChars.toLocaleString()}자 ~ ${durationInfo.maxChars.toLocaleString()}자\n`;
    draft += `   → 기준: 분당 ${durationInfo.charsPerMin}자 (한국어 설교 평균 속도)\n`;
    draft += `   → 이 글자 수를 반드시 지켜주세요. 짧으면 안 됩니다!\n`;
    if (durationInfo.minutes <= 10) {
      draft += `   → 짧은 설교이므로 핵심에 집중하되, 구조(서론/본론/결론)는 유지하세요.\n`;
    }
    draft += `\n`;
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

  // Step 결과들 + 추가 정보 (Strong's 원어 분석, 시대 컨텍스트)
  const steps = getCurrentSteps();
  let stepNum = 1;
  steps.forEach(step => {
    if (window.stepResults[step.id]) {
      const stepType = step.stepType || 'step1';
      const label = stepType === 'step1' ? 'STEP 1' : 'STEP 2';
      draft += `【 ${stepNum}. ${label} — ${step.name} 】\n\n`;
      draft += window.stepResults[step.id] + '\n\n';

      // Step1 추가 정보: Strong's 원어 분석
      const extraInfo = window.stepExtraInfo?.[step.id];
      if (stepType === 'step1' && extraInfo?.strongs_analysis) {
        const strongs = extraInfo.strongs_analysis;
        if (strongs.key_words && strongs.key_words.length > 0) {
          draft += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
          draft += `【 ★ Strong's 원어 분석 (Step1 보강) 】\n`;
          draft += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n`;
          if (strongs.text) {
            draft += `영문 (KJV): ${strongs.text}\n\n`;
          }
          draft += `▶ 핵심 원어 단어:\n`;
          strongs.key_words.forEach((word, i) => {
            const lemma = word.lemma || '';
            const translit = word.translit || '';
            const strongsNum = word.strongs || '';
            const definition = word.definition || '';
            draft += `  ${i + 1}. ${lemma} (${translit}, ${strongsNum})\n`;
            if (word.english) draft += `     → 영어: ${word.english}\n`;
            if (definition) draft += `     → 의미: ${definition.substring(0, 200)}${definition.length > 200 ? '...' : ''}\n`;
            draft += `\n`;
          });
        }
      }

      // Step2 추가 정보: 시대 컨텍스트
      if (stepType === 'step2' && extraInfo?.context_data) {
        const context = extraInfo.context_data;
        draft += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
        draft += `【 ★ 현재 시대 컨텍스트 (Step2 보강) 】\n`;
        draft += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n`;
        draft += `청중 유형: ${context.audience || '전체'}\n\n`;

        // 주요 뉴스 이슈
        if (context.news && Object.keys(context.news).length > 0) {
          draft += `▶ 주요 시사 이슈 (서론/예화에 활용)\n`;
          const catNames = { economy: '경제', politics: '정치', society: '사회', world: '국제', culture: '문화' };
          Object.entries(context.news).forEach(([cat, items]) => {
            if (items && items.length > 0) {
              draft += `  [${catNames[cat] || cat}]\n`;
              items.slice(0, 2).forEach(item => {
                const newsTitle = item.title?.length > 50 ? item.title.substring(0, 50) + '...' : item.title;
                draft += `  • ${newsTitle}\n`;
              });
            }
          });
          draft += `\n`;
        }

        // 사회 지표
        if (context.indicators && Object.keys(context.indicators).length > 0) {
          draft += `▶ 관련 사회 지표\n`;
          Object.entries(context.indicators).forEach(([cat, data]) => {
            if (typeof data === 'object') {
              Object.entries(data).forEach(([key, value]) => {
                if (key !== 'updated') draft += `  • ${key}: ${value}\n`;
              });
            }
          });
          draft += `\n`;
        }

        // 청중 관심사
        if (context.concerns && context.concerns.length > 0) {
          draft += `▶ 청중의 주요 관심사/고민\n`;
          context.concerns.forEach(concern => {
            draft += `  • ${concern}\n`;
          });
          draft += `\n`;
        }

        draft += `※ 위 시대 컨텍스트를 도입부/예화/적용에 활용하세요.\n\n`;
      }

      draft += `==================================================\n\n`;
      stepNum++;
    }
  });

  // 스타일별 작성 가이드
  if (styleName && window.DEFAULT_GUIDES?.[styleName]?.step3) {
    const step3Guide = window.DEFAULT_GUIDES[styleName].step3;

    draft += `==================================================\n`;
    draft += `【 ★★★ 스타일별 작성 가이드 (${styleName}) ★★★ 】\n`;
    draft += `==================================================\n\n`;

    // 가독성/문단 스타일
    if (step3Guide.writing_style) {
      const ws = step3Guide.writing_style;
      draft += `▶ ${ws.label || '문단/줄바꿈 스타일'}\n`;
      if (ws.core_principle) draft += `   핵심: ${ws.core_principle}\n`;
      if (ws.must_do) {
        draft += `   ✅ 해야 할 것:\n`;
        ws.must_do.forEach(item => draft += `      - ${item}\n`);
      }
      if (ws.must_not) {
        draft += `   ❌ 하지 말 것:\n`;
        ws.must_not.forEach(item => draft += `      - ${item}\n`);
      }
      draft += `\n`;
    }

    // 성경구절 인용 방식
    if (step3Guide.scripture_citation) {
      const sc = step3Guide.scripture_citation;
      draft += `▶ ${sc.label || '성경구절 인용 방식'}\n`;
      if (sc.core_principle) draft += `   핵심: ${sc.core_principle}\n`;
      if (sc.must_do) {
        draft += `   ✅ 해야 할 것:\n`;
        sc.must_do.forEach(item => draft += `      - ${item}\n`);
      }
      if (sc.good_examples) {
        draft += `   ✅ 올바른 예시:\n`;
        sc.good_examples.forEach(ex => draft += `      ${ex}\n`);
      }
      draft += `\n`;
    }

    draft += `==================================================\n\n`;
  }

  // 최종 작성 지침
  draft += `==================================================\n`;
  draft += `📝 최종 작성 지침:\n`;
  draft += `==================================================\n`;
  draft += `위의 초안 자료를 참고하여, 완성도 높은 설교문을 처음부터 새로 작성해주세요.\n\n`;

  draft += `✅ 필수 체크리스트:\n`;
  draft += `  □ Step1의 '핵심_메시지'가 설교 전체에 일관되게 흐르는가?\n`;
  draft += `  □ Step1의 '주요_절_해설'과 '핵심_단어_분석'을 활용했는가?\n`;
  draft += `  □ Step2의 설교 구조(서론, 대지, 결론)를 따랐는가?\n`;
  if (duration) draft += `  □ 분량이 ${duration} (${durationInfo.minChars.toLocaleString()}~${durationInfo.maxChars.toLocaleString()}자)에 맞는가?\n`;
  if (target) draft += `  □ 대상(${target})에 맞는 어조와 예시를 사용했는가?\n`;
  if (worshipType) draft += `  □ 예배 유형(${worshipType})에 맞는 톤인가?\n`;
  draft += `  □ 성경 구절이 가독성 가이드에 맞게 줄바꿈 처리되었는가?\n`;
  draft += `  □ 마크다운 없이 순수 텍스트로 작성했는가?\n`;
  draft += `  □ 복음과 소망, 하나님의 은혜가 분명하게 드러나는가?\n\n`;

  if (duration) {
    draft += `⚠️ 가장 중요: 반드시 ${durationInfo.targetChars.toLocaleString()}자 이상 작성하세요!\n`;
    draft += `   (허용 범위: ${durationInfo.minChars.toLocaleString()}자 ~ ${durationInfo.maxChars.toLocaleString()}자)\n`;
  }
  if (worshipType) {
    draft += `⚠️ 예배 유형 '${worshipType}'에 맞는 톤으로 작성하세요.\n`;
  }

  draft += `\n글자 수가 부족하면 안 됩니다. ${durationInfo.targetChars.toLocaleString()}자 목표로 충분히 상세하게 작성해주세요.\n`;

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

    // Step1, Step2 추가 정보 수집 (Strong's 원어 분석, 시대 컨텍스트)
    let step1ExtraInfo = null;
    let step2ExtraInfo = null;

    step1Steps.forEach(s => {
      if (window.stepExtraInfo?.[s.id]) {
        step1ExtraInfo = window.stepExtraInfo[s.id];
      }
    });

    step2Steps.forEach(s => {
      if (window.stepExtraInfo?.[s.id]) {
        step2ExtraInfo = window.stepExtraInfo[s.id];
      }
    });

    console.log('[Step3] step1ExtraInfo:', step1ExtraInfo ? Object.keys(step1ExtraInfo) : 'none');
    console.log('[Step3] step2ExtraInfo:', step2ExtraInfo ? Object.keys(step2ExtraInfo) : 'none');

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

    // DEFAULT_GUIDES에서 현재 스타일의 writing_style, scripture_citation 가져오기
    const styleName = getCurrentStyle()?.name || '';
    let writingStyleRules = null;
    let scriptureCitationRules = null;

    if (window.DEFAULT_GUIDES && styleName) {
      // 스타일 이름으로 직접 매칭 시도
      let styleGuide = window.DEFAULT_GUIDES[styleName];

      // 직접 매칭이 안 되면, 스타일 이름에 키워드가 포함되어 있는지 확인
      if (!styleGuide) {
        const guideKeys = Object.keys(window.DEFAULT_GUIDES);
        for (const key of guideKeys) {
          if (styleName.includes(key) || key.includes(styleName)) {
            styleGuide = window.DEFAULT_GUIDES[key];
            console.log(`[Step3] 스타일 '${styleName}'을 '${key}' 가이드에 매칭`);
            break;
          }
        }
      }

      if (styleGuide?.step3) {
        writingStyleRules = styleGuide.step3.writing_style || null;
        scriptureCitationRules = styleGuide.step3.scripture_citation || null;
      }
    }

    console.log('[Step3] 스타일:', styleName);
    console.log('[Step3] writing_style 규칙:', writingStyleRules ? '있음' : '없음');
    console.log('[Step3] scripture_citation 규칙:', scriptureCitationRules ? '있음' : '없음');

    const requestBody = {
      reference: ref,
      title: getSelectedTitle(),
      target: document.getElementById('sermon-target')?.value || '',
      worshipType: document.getElementById('sermon-worship-type')?.value || '',
      duration: document.getElementById('sermon-duration')?.value || '',
      specialNotes: document.getElementById('special-notes')?.value || '',
      styleName: styleName,
      category: window.currentCategory,
      model: model,
      maxTokens: maxTokens,
      customPrompt: window.DEFAULT_STEP3_PROMPT,
      step1Result: step1Result,
      step2Result: step2Result,
      step1ExtraInfo: step1ExtraInfo,
      step2ExtraInfo: step2ExtraInfo,
      writingStyle: writingStyleRules,
      scriptureCitation: scriptureCitationRules
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
