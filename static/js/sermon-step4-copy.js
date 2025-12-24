/**
 * sermon-step4-copy.js
 * Step4 "전체 복사" 프롬프트 조합 기능
 *
 * 주요 함수:
 * - assembleGptProDraft()
 * - executeGptPro()
 * - 전체 복사 기능
 *
 * 이 파일은 sermon.html의 3137~3589줄 코드를 모듈화한 것입니다.
 *
 * ★ 분량 규칙은 step3_prompt_builder.py에서 API로 가져옴
 */

// ===== GPT PRO 초안 구성 =====
async function assembleGptProDraft() {
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

  // ★ 분량→글자 수 변환 (API 호출 - step3_prompt_builder.py 단일 소스)
  let durationInfo = { minutes: 20, minChars: 6660, maxChars: 8140, targetChars: 7400, charsPerMin: 370 };
  try {
    const durationResponse = await fetch(`/api/sermon/duration-info/${encodeURIComponent(duration)}`);
    if (durationResponse.ok) {
      const data = await durationResponse.json();
      if (data.ok) {
        durationInfo = {
          minutes: data.minutes,
          minChars: data.min_chars,
          maxChars: data.max_chars,
          targetChars: data.target_chars,
          charsPerMin: data.chars_per_min
        };
      }
    }
  } catch (e) {
    console.warn('[Step4] 분량 정보 API 호출 실패:', e);
  }

  let draft = '';

  // 헤더
  draft += `====================================\n`;
  draft += `설교 초안 자료 (GPT-5.1 작성용)\n`;
  draft += `====================================\n\n`;

  // 최우선 지침
  draft += `==================================================\n`;
  draft += `[최우선 지침]\n`;
  draft += `==================================================\n\n`;

  // 존대어 사용 필수 (대상과 무관하게)
  draft += `[필수] 어체: 존대어 (경어체)\n`;
  draft += `   - 대상이 청소년/어린이여도 반드시 존대어로 작성하세요.\n`;
  draft += `   - "~합니다", "~입니다", "~하십시오" 형태를 사용하세요.\n`;
  draft += `   - 반말("~해", "~야") 사용 금지.\n\n`;

  if (duration) {
    draft += `[최우선 필수] 분량: ${duration} = ${durationInfo.targetChars.toLocaleString()}자\n`;
    draft += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
    draft += `   최소 글자 수: ${durationInfo.minChars.toLocaleString()}자 (이 미만은 불합격)\n`;
    draft += `   목표 글자 수: ${durationInfo.targetChars.toLocaleString()}자\n`;
    draft += `   최대 글자 수: ${durationInfo.maxChars.toLocaleString()}자\n`;
    draft += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
    draft += `   계산 기준: ${durationInfo.minutes}분 × ${durationInfo.charsPerMin}자/분 = ${durationInfo.targetChars.toLocaleString()}자\n`;
    draft += `\n`;
    draft += `   [분량 맞추기 전략]\n`;
    if (durationInfo.minutes >= 25) {
      draft += `   - 서론: 약 ${Math.round(durationInfo.targetChars * 0.15).toLocaleString()}자 (도입, 성경 배경)\n`;
      draft += `   - 본론: 약 ${Math.round(durationInfo.targetChars * 0.65).toLocaleString()}자 (대지별 설명)\n`;
      draft += `   - 결론: 약 ${Math.round(durationInfo.targetChars * 0.20).toLocaleString()}자 (요약 + 결단 촉구 + 기도)\n`;
    } else if (durationInfo.minutes >= 15) {
      draft += `   - 서론: 약 ${Math.round(durationInfo.targetChars * 0.15).toLocaleString()}자\n`;
      draft += `   - 본론: 약 ${Math.round(durationInfo.targetChars * 0.65).toLocaleString()}자 (대지별 설명)\n`;
      draft += `   - 결론: 약 ${Math.round(durationInfo.targetChars * 0.20).toLocaleString()}자\n`;
    } else {
      draft += `   - 짧은 설교이므로 핵심에 집중하되, 구조(서론/본론/결론)는 유지하세요.\n`;
    }
    draft += `\n`;
    draft += `   [경고] ${durationInfo.minChars.toLocaleString()}자 미만 작성 시 불합격 처리됩니다.\n`;
    draft += `   반드시 ${durationInfo.targetChars.toLocaleString()}자 이상 작성하세요!\n\n`;
  }

  if (worshipType) {
    draft += `[필수] 예배/집회 유형: ${worshipType}\n`;
    draft += `   - '${worshipType}'에 적합한 톤과 내용으로 작성하세요.\n\n`;
  }

  if (target) {
    draft += `[필수] 대상: ${target}\n`;
    draft += `   - 대상에 맞는 예시와 적용을 사용하되, 어체는 존대어를 유지하세요.\n\n`;
  }

  draft += `==================================================\n\n`;

  // 안내 문구
  draft += `[중요] 이 자료는 gpt-4o-mini가 만든 '초안'입니다.\n`;
  draft += `GPT-5.1은 이 자료를 참고하되, 처음부터 새로 작성해주세요.\n`;
  draft += `mini가 만든 문장을 그대로 복사하지 말고, 자연스러운 설교문으로 재작성하세요.\n\n`;

  draft += `==================================================\n\n`;

  // 기본 정보
  draft += `[기본 정보]\n`;
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

  // Step 결과들 + 추가 정보 (★ 토큰 절약을 위해 핵심 정보만 추출)
  const steps = getCurrentSteps();
  let stepNum = 1;
  steps.forEach(step => {
    if (window.stepResults[step.id]) {
      const stepType = step.stepType || 'step1';
      const label = stepType === 'step1' ? 'STEP 1 (핵심 요약)' : 'STEP 2 (핵심 요약)';
      draft += `【 ${stepNum}. ${label} — ${step.name} 】\n\n`;

      // ★ Step 결과를 요약하여 포함
      let stepResult = window.stepResults[step.id];
      try {
        const parsed = JSON.parse(stepResult);
        if (stepType === 'step1') {
          // Step1 핵심 요약
          let summary = '';
          if (parsed.core_message || parsed.핵심_메시지) {
            summary += `▶ 핵심 메시지:\n${parsed.core_message || parsed.핵심_메시지}\n\n`;
          }
          if (parsed.passage_overview?.one_paragraph_summary) {
            summary += `▶ 본문 요약:\n${parsed.passage_overview.one_paragraph_summary}\n\n`;
          }
          // anchors 상위 5개만
          if (parsed.anchors && Array.isArray(parsed.anchors)) {
            const anchors = parsed.anchors.slice(0, 5);
            summary += `▶ Anchors 핵심 근거 (상위 ${anchors.length}개):\n`;
            anchors.forEach((a, i) => {
              summary += `  ${i+1}. [${a.anchor_id || a.id || ''}] ${a.range || ''}: ${a.anchor_phrase || a.phrase || ''}\n`;
            });
            summary += '\n';
          }
          // guardrails 핵심만
          if (parsed.guardrails?.does_not_claim) {
            const claims = parsed.guardrails.does_not_claim.slice(0, 3);
            summary += `▶ 본문이 말하지 않는 것 (상위 3개):\n`;
            claims.forEach((c, i) => {
              const claimText = typeof c === 'object' ? (c.claim || c.text || JSON.stringify(c)) : c;
              summary += `  ${i+1}. ${claimText}\n`;
            });
            summary += '\n';
          }
          draft += summary || stepResult;
        } else if (stepType === 'step2') {
          // Step2 핵심 요약
          let summary = '';
          if (parsed.introduction || parsed.서론) {
            const intro = parsed.introduction || parsed.서론;
            summary += `▶ 서론:\n${typeof intro === 'object' ? JSON.stringify(intro).substring(0, 300) : intro}\n\n`;
          }
          // 본론 상위 3개
          const points = parsed.main_points || parsed.본론 || parsed.대지 || parsed.sections;
          if (points && Array.isArray(points)) {
            const limitedPoints = points.slice(0, 3);
            summary += `▶ 본론 (대지) - 상위 ${limitedPoints.length}개:\n`;
            limitedPoints.forEach((p, i) => {
              const title = p.title || p.제목 || p.point || p.theme || '';
              summary += `  ${i+1}. ${title}\n`;
            });
            summary += '\n';
          }
          if (parsed.conclusion || parsed.결론) {
            const conclusion = parsed.conclusion || parsed.결론;
            summary += `▶ 결론:\n${typeof conclusion === 'object' ? JSON.stringify(conclusion).substring(0, 200) : conclusion}\n\n`;
          }
          // 예화 상위 2개
          const illustrations = parsed.illustrations || parsed.예화;
          if (illustrations && Array.isArray(illustrations)) {
            summary += `▶ 예화 (상위 2개):\n`;
            illustrations.slice(0, 2).forEach((illust, i) => {
              const title = typeof illust === 'object' ? (illust.title || illust.제목 || '') : illust;
              summary += `  ${i+1}. ${title}\n`;
            });
            summary += '\n';
          }
          draft += summary || stepResult;
        } else {
          draft += stepResult + '\n\n';
        }
      } catch (e) {
        // JSON 파싱 실패 시 원본 텍스트 (길이 제한)
        if (stepResult.length > 2000) {
          draft += stepResult.substring(0, 2000) + '... (이하 생략)\n\n';
        } else {
          draft += stepResult + '\n\n';
        }
      }

      // Step1 추가 정보: Strong's 원어 분석 (★ 상위 3개만)
      const extraInfo = window.stepExtraInfo?.[step.id];
      if (stepType === 'step1' && extraInfo?.strongs_analysis) {
        const strongs = extraInfo.strongs_analysis;
        if (strongs.key_words && strongs.key_words.length > 0) {
          draft += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
          draft += `【 ★ Strong's 원어 분석 (상위 3개) 】\n`;
          draft += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n`;
          draft += `▶ 핵심 원어 단어:\n`;
          strongs.key_words.slice(0, 3).forEach((word, i) => {  // ★ 상위 3개만
            const lemma = word.lemma || '';
            const translit = word.translit || '';
            const strongsNum = word.strongs || '';
            const definition = word.definition || '';
            draft += `  ${i + 1}. ${lemma} (${translit}, ${strongsNum})\n`;
            if (definition) draft += `     → 의미: ${definition.substring(0, 100)}${definition.length > 100 ? '...' : ''}\n`;  // ★ 100자 제한
            draft += `\n`;
          });
        }
      }

      // Step2 추가 정보: 시대 컨텍스트 (★ 카테고리당 1개, 관심사 3개)
      if (stepType === 'step2' && extraInfo?.context_data) {
        const context = extraInfo.context_data;
        draft += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
        draft += `【 ★ 현재 시대 컨텍스트 (요약) 】\n`;
        draft += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n`;
        draft += `청중 유형: ${context.audience || '전체'}\n\n`;

        // 주요 뉴스 이슈 (★ 카테고리당 1개만, 최대 3개)
        if (context.news && Object.keys(context.news).length > 0) {
          draft += `▶ 주요 시사 이슈 (카테고리당 1개):\n`;
          const catNames = { economy: '경제', politics: '정치', society: '사회', world: '국제', culture: '문화' };
          let newsCount = 0;
          Object.entries(context.news).forEach(([cat, items]) => {
            if (items && items.length > 0 && newsCount < 3) {
              const item = items[0];  // ★ 첫 번째만
              const newsTitle = item.title?.length > 40 ? item.title.substring(0, 40) + '...' : item.title;
              draft += `  - [${catNames[cat] || cat}] ${newsTitle}\n`;
              newsCount++;
            }
          });
          draft += `\n`;
        }

        // 청중 관심사 (★ 상위 3개만)
        if (context.concerns && context.concerns.length > 0) {
          draft += `▶ 청중 관심사 (상위 3개):\n`;
          context.concerns.slice(0, 3).forEach(concern => {
            draft += `  • ${concern}\n`;
          });
          draft += `\n`;
        }
      }

      draft += `==================================================\n\n`;
      stepNum++;
    }
  });

  // 스타일별 작성 가이드 (★ three_points.py 등에서 API로 가져옴)
  if (styleId) {
    try {
      const guideResponse = await fetch(`/api/sermon/style-guide/${styleId}`);
      if (guideResponse.ok) {
        const guideData = await guideResponse.json();
        if (guideData.ok) {
          draft += `==================================================\n`;
          draft += `[스타일별 작성 가이드 (${guideData.style_name || styleName})]\n`;
          draft += `==================================================\n\n`;

          // ★ 핵심 작성 가이드 (소대지 규칙 등 포함)
          if (guideData.writing_guide) {
            draft += `▶ 작성 가이드:\n`;
            draft += `${guideData.writing_guide}\n\n`;
          }

          // ★ 예화 배치 가이드
          if (guideData.illustration_guide) {
            draft += `▶ 예화 배치 가이드:\n`;
            draft += `${guideData.illustration_guide}\n\n`;
          }

          // ★ 적용 가이드 (있는 경우)
          if (guideData.application_guide) {
            draft += `▶ 적용 가이드:\n`;
            draft += `${guideData.application_guide}\n\n`;
          }

          // ★ 체크리스트
          if (guideData.checklist && guideData.checklist.length > 0) {
            draft += `▶ 스타일 체크리스트:\n`;
            guideData.checklist.forEach((item, i) => {
              draft += `   ${i + 1}. ${item}\n`;
            });
            draft += `\n`;
          }

          draft += `==================================================\n\n`;
        }
      }
    } catch (e) {
      console.warn('[Step4] 스타일 가이드 API 호출 실패:', e);
      // API 실패 시 기본 가이드 사용 (fallback)
      if (styleName && window.DEFAULT_GUIDES?.[styleName]?.step3) {
        const step3Guide = window.DEFAULT_GUIDES[styleName].step3;
        draft += `==================================================\n`;
        draft += `[스타일별 작성 가이드 (${styleName})]\n`;
        draft += `==================================================\n\n`;
        if (step3Guide.writing_style) {
          const ws = step3Guide.writing_style;
          draft += `> ${ws.label || '문단/줄바꿈 스타일'}\n`;
          if (ws.core_principle) draft += `   핵심: ${ws.core_principle}\n`;
          draft += `\n`;
        }
        draft += `==================================================\n\n`;
      }
    }
  }

  // 최종 작성 지침
  draft += `==================================================\n`;
  draft += `[최종 작성 지침]\n`;
  draft += `==================================================\n`;
  draft += `위의 초안 자료를 참고하여, 완성도 높은 설교문을 처음부터 새로 작성해주세요.\n\n`;

  draft += `[필수 체크리스트]\n`;
  draft += `  - 존대어(경어체)로 작성했는가? (반말 금지)\n`;
  draft += `  - Step1의 '핵심_메시지'가 설교 전체에 일관되게 흐르는가?\n`;
  draft += `  - Step1의 '주요_절_해설'과 '핵심_단어_분석'을 활용했는가?\n`;
  draft += `  - Step2의 설교 구조(서론, 대지, 결론)를 따랐는가?\n`;
  if (duration) draft += `  - 분량이 ${duration} (${durationInfo.minChars.toLocaleString()}~${durationInfo.maxChars.toLocaleString()}자)에 맞는가?\n`;
  if (target) draft += `  - 대상(${target})에 맞는 예시와 적용을 사용했는가?\n`;
  if (worshipType) draft += `  - 예배 유형(${worshipType})에 맞는 톤인가?\n`;
  draft += `  - 성경 구절이 가독성 가이드에 맞게 줄바꿈 처리되었는가?\n`;
  draft += `  - 마크다운 없이 순수 텍스트로 작성했는가?\n`;
  draft += `  - 복음과 소망, 하나님의 은혜가 분명하게 드러나는가?\n\n`;

  if (duration) {
    draft += `\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
    draft += `[최종 분량 확인]\n`;
    draft += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
    draft += `${duration} 설교 = 최소 ${durationInfo.minChars.toLocaleString()}자 ~ 최대 ${durationInfo.maxChars.toLocaleString()}자\n`;
    draft += `목표: ${durationInfo.targetChars.toLocaleString()}자\n\n`;
    draft += `작성 완료 후 반드시 글자 수를 확인하세요.\n`;
    draft += `${durationInfo.minChars.toLocaleString()}자 미만이면 다시 작성해야 합니다.\n`;
    draft += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
  }
  if (worshipType) {
    draft += `\n[예배 유형] '${worshipType}'에 맞는 톤으로 작성하세요.\n`;
  }

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
      styleId: window.currentStyleId || '',  // ★ 스타일 ID 추가 (2025-12-23)
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
async function copyAllResults() {
  try {
    const draft = await assembleGptProDraft();
    await navigator.clipboard.writeText(draft);
    showStatus('✅ 전체 내용이 복사되었습니다!');
    setTimeout(hideStatus, 2000);
  } catch (err) {
    console.error('복사 실패:', err);
    alert('복사에 실패했습니다.');
  }
}

// 전역 노출
window.assembleGptProDraft = assembleGptProDraft;
window.executeGptPro = executeGptPro;
window.copyAllResults = copyAllResults;
