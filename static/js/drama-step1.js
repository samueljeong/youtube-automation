/**
 * Drama Lab - Step1 대본 생성 모듈
 * 화면 기준 Step1: 대본 생성 (GPT 기획 → Claude 대본 완성)
 */

// ===== 대본 생성 관련 변수 =====
let step1Result = localStorage.getItem('_drama-step1-result') || '';
let aiModelSettings = JSON.parse(localStorage.getItem('_drama-ai-models') || 'null') || {
  step1: 'anthropic/claude-sonnet-4.5',
  step3: 'anthropic/claude-sonnet-4.5'
};

// 가이드 변수
let step1Guide = localStorage.getItem('_drama-step1-guide') || '';
let dramaJsonGuide = localStorage.getItem('_drama-json-guide') || '';

// 콘텐츠 유형별 프롬프트
let contentTypePrompts = {
  testimony: {
    name: '간증',
    style: '1인칭 고백 형식, 진솔하고 담담한 톤',
    structure: '7단계 구조 (인사→상황→갈등→심화→절망→개입→회복)',
    narration_ratio: { narration: 55, inner_monologue: 15, dialogue: 30 }
  },
  drama: {
    name: '드라마',
    style: '3인칭 서술, 극적인 장면 연출',
    structure: '기승전결 4막 구조',
    narration_ratio: { narration: 40, dialogue: 45, description: 15 }
  }
};

// ===== 대본 생성 메인 함수 =====
async function executeStep1() {
  // 화면에서 Step1 버튼을 누르면 실행되는 함수
  // 실제로는 executeStep3() 함수가 대본 생성을 담당

  // 기본 정보 수집
  const categorySelect = document.getElementById('drama-category');
  const durationLabel = (window.customDurationText || '').trim() ||
    (categorySelect ? categorySelect.options[categorySelect.selectedIndex].text : '10분');
  const videoCategory = window.selectedCategory || '간증';
  const mainCharacterInput = document.getElementById('main-character');
  const mainCharacter = mainCharacterInput ? mainCharacterInput.value : '';
  const benchmarkScript = document.getElementById('benchmark-script')?.value || '';
  const analysisResult = document.getElementById('analysis-result')?.textContent || '';

  // 가이드 값 가져오기
  const step1GuideTextarea = document.getElementById('modal-guide-step1');
  const currentStep1Guide = step1GuideTextarea ? step1GuideTextarea.value : step1Guide;
  const jsonGuideTextarea = document.getElementById('modal-guide-json');
  const currentJsonGuide = jsonGuideTextarea ? jsonGuideTextarea.value : dramaJsonGuide;

  // 콘텐츠 유형
  const contentType = document.getElementById('content-type')?.value || 'testimony';
  const promptData = contentTypePrompts[contentType] || contentTypePrompts.testimony;

  try {
    let gptPlanResult = '';

    // 1단계: GPT-4o-mini 스토리 기획
    showLoadingOverlay('GPT 기획 중 (1/3)', 'GPT-4o-mini가 스토리 컨셉을 기획하고 있습니다...');
    showStatus('🎯 Step1-1: GPT-4o-mini 스토리 기획 중...');

    const planStep1Response = await fetch('/api/drama/gpt-plan-step1', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        videoCategory: videoCategory,
        duration: durationLabel,
        customDirective: window.customDirective || ''
      })
    });

    const planStep1Data = await planStep1Response.json();
    if (!planStep1Data.ok) {
      throw new Error('GPT 기획 1단계 실패: ' + (planStep1Data.error || '알 수 없는 오류'));
    }

    console.log('[Step1-1] GPT 기획 완료');

    // 2단계: GPT-4o-mini 장면 구성
    showLoadingOverlay('GPT 구조화 중 (2/3)', 'GPT-4o-mini가 장면 구성을 만들고 있습니다...');
    showStatus('📐 Step1-2: GPT-4o-mini 장면 구조화 중...');

    const planStep2Response = await fetch('/api/drama/gpt-plan-step2', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        videoCategory: videoCategory,
        duration: durationLabel,
        customDirective: window.customDirective || '',
        step1Result: planStep1Data.result
      })
    });

    const planStep2Data = await planStep2Response.json();
    if (!planStep2Data.ok) {
      throw new Error('GPT 기획 2단계 실패: ' + (planStep2Data.error || '알 수 없는 오류'));
    }

    console.log('[Step1-2] 장면 구성 완료');

    // GPT 기획 결과 합치기
    gptPlanResult = `【 GPT-4o-mini 기획 결과 】\n\n`;
    gptPlanResult += `=== 스토리 컨셉 ===\n${planStep1Data.result}\n\n`;
    gptPlanResult += `=== 장면 구성 ===\n${planStep2Data.result}`;

    // 3단계: Claude로 최종 대본 작성
    showLoadingOverlay('Claude 대본 작성 중 (3/3)', 'Claude Sonnet 4.5가 대본을 작성하고 있습니다...');
    showStatus('🎬 Step1-3: Claude 대본 완성 중... (약 30-60초 소요)');

    const response = await fetch('/api/drama/claude-step3', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        category: durationLabel,
        videoCategory: videoCategory,
        customDirective: window.customDirective || '',
        draftContent: gptPlanResult,
        mainCharacter: { name: mainCharacter },
        benchmarkScript: benchmarkScript,
        aiAnalysis: analysisResult,
        step3Guide: currentStep1Guide,
        model: aiModelSettings.step1,
        contentType: contentType,
        contentTypePrompt: promptData,
        durationText: window.customDurationText || '',
        autoStoryMode: true,
        customJsonGuide: currentJsonGuide
      })
    });

    const data = await response.json();

    if (data.ok) {
      // 결과 저장 및 표시
      step1Result = data.result;
      localStorage.setItem('_drama-step1-result', step1Result);

      const resultTextarea = document.getElementById('step1-result') || document.getElementById('step3-result');
      const resultContainer = document.getElementById('step1-result-container') || document.getElementById('step3-result-container');

      if (resultTextarea && resultContainer) {
        resultTextarea.value = data.result;
        if (typeof autoResize === 'function') autoResize(resultTextarea);
        resultContainer.style.display = 'block';
        resultContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }

      // 세션에 저장
      if (typeof updateSession === 'function') {
        updateSession('step1.script', step1Result);
      }

      // 메타데이터 자동 생성
      if (typeof generateMetadataFromScript === 'function') {
        generateMetadataFromScript(step1Result, contentType);
      }

      showStatus('✅ Step1: 대본 생성 완료!');
      if (typeof updateProgressIndicator === 'function') {
        updateProgressIndicator('step1');
      }

      // 자동화 모드면 다음 Step 실행
      if (window.isFullAutoMode) {
        console.log('[Step1] 자동화 모드: Step2(이미지 생성) 시작...');
        setTimeout(() => {
          if (typeof generateAllAuto === 'function') {
            generateAllAuto(true);
          }
        }, 2000);
      }

      return data.result;

    } else {
      throw new Error(data.error || '대본 생성 실패');
    }

  } catch (err) {
    console.error('[Step1] 오류:', err);
    alert(`대본 생성 오류: ${err.message}`);
    showStatus('❌ Step1 실패');
  } finally {
    hideLoadingOverlay();
  }
}

// ===== 대본 뷰어 함수 =====
let isScriptViewerOpen = false;

function formatScriptToText(jsonStr) {
  try {
    const data = JSON.parse(jsonStr);
    let html = '';

    // 메타데이터
    if (data.metadata) {
      html += `<div style="background: #f0f9ff; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #3b82f6;">`;
      html += `<h2 style="margin: 0 0 .5rem 0; color: #1e40af;">📺 ${data.metadata.title || '제목 없음'}</h2>`;
      if (data.metadata.duration_minutes) html += `<div style="color: #64748b;">⏱️ 분량: ${data.metadata.duration_minutes}분</div>`;
      if (data.metadata.total_scenes) html += `<div style="color: #64748b;">🎬 총 씬: ${data.metadata.total_scenes}개</div>`;
      html += `</div>`;
    }

    // 등장인물
    if (data.characters && data.characters.length > 0) {
      html += `<div style="background: #fef3c7; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #f59e0b;">`;
      html += `<h3 style="margin: 0 0 .75rem 0; color: #b45309;">👥 등장인물</h3>`;
      data.characters.forEach(char => {
        html += `<div style="margin-bottom: .5rem;"><strong>${char.name || char.id}</strong>`;
        if (char.age) html += ` (${char.age})`;
        if (char.role) html += ` - ${char.role}`;
        html += `</div>`;
      });
      html += `</div>`;
    }

    // 하이라이트
    if (data.highlight && data.highlight.scenes) {
      html += `<div style="background: #fce7f3; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #ec4899;">`;
      html += `<h3 style="margin: 0 0 .75rem 0; color: #be185d;">✨ 하이라이트</h3>`;
      data.highlight.scenes.forEach((scene, idx) => {
        html += `<div style="margin-bottom: .5rem;">[${idx + 1}] "${scene.preview_text || scene.narration || ''}"</div>`;
      });
      html += `</div>`;
    }

    // 대본 (씬별)
    if (data.script && data.script.scenes) {
      html += `<div style="background: #ecfdf5; padding: 1rem; border-radius: 8px; border-left: 4px solid #10b981;">`;
      html += `<h3 style="margin: 0 0 1rem 0; color: #047857;">📜 대본</h3>`;

      data.script.scenes.forEach((scene, idx) => {
        html += `<div style="margin-bottom: 1.5rem; padding: 1rem; background: rgba(255,255,255,0.8); border-radius: 8px;">`;
        html += `<h4 style="margin: 0 0 .5rem 0; color: #065f46;">🎬 씬 ${idx + 1}</h4>`;
        if (scene.narration) {
          html += `<div style="line-height: 1.8; color: #1f2937;">${scene.narration}</div>`;
        }
        html += `</div>`;
      });
      html += `</div>`;
    }

    return html || '<div style="color: #999; text-align: center; padding: 2rem;">대본을 파싱할 수 없습니다.</div>';
  } catch (e) {
    return `<div style="color: #ef4444; text-align: center; padding: 2rem;">⚠️ JSON 파싱 오류: ${e.message}</div>`;
  }
}

function toggleScriptViewer() {
  const jsonTextarea = document.getElementById('step1-result') || document.getElementById('step3-result');
  const scriptViewer = document.getElementById('step1-script-viewer') || document.getElementById('step3-script-viewer');
  const scriptContent = document.getElementById('step1-script-content') || document.getElementById('step3-script-content');
  const toggleBtn = document.getElementById('btn-toggle-script-view');

  if (!jsonTextarea || !scriptViewer || !scriptContent) return;

  isScriptViewerOpen = !isScriptViewerOpen;

  if (isScriptViewerOpen) {
    const jsonStr = jsonTextarea.value;
    if (jsonStr.trim()) {
      scriptContent.innerHTML = formatScriptToText(jsonStr);
      jsonTextarea.style.display = 'none';
      scriptViewer.style.display = 'block';
      if (toggleBtn) {
        toggleBtn.textContent = '📄 JSON 보기';
        toggleBtn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
      }
    }
  } else {
    jsonTextarea.style.display = 'block';
    scriptViewer.style.display = 'none';
    if (toggleBtn) {
      toggleBtn.textContent = '📖 대본 보기';
      toggleBtn.style.background = 'linear-gradient(135deg, #667eea, #764ba2)';
    }
  }
}

// ===== 나레이션 추출 =====
function extractNarrationFromScript(script) {
  try {
    let data;
    const jsonMatch = script.match(/```json\s*([\s\S]*?)\s*```/);
    if (jsonMatch) {
      data = JSON.parse(jsonMatch[1]);
    } else {
      data = JSON.parse(script);
    }

    let narrationText = '';

    // 하이라이트
    if (data.highlight && data.highlight.scenes) {
      data.highlight.scenes.forEach(scene => {
        if (scene.preview_text) narrationText += scene.preview_text + '\n\n';
        if (scene.narration) narrationText += scene.narration + '\n\n';
      });
    }

    // 본문
    if (data.script && data.script.scenes) {
      data.script.scenes.forEach(scene => {
        if (scene.narration) narrationText += scene.narration + '\n\n';
      });
    }

    return narrationText.trim();
  } catch (e) {
    console.warn('[Step1] 나레이션 추출 실패:', e);
    return script;
  }
}

// ===== 이벤트 리스너 설정 =====
document.addEventListener('DOMContentLoaded', () => {
  // Step1 실행 버튼 (화면에서는 "대본 작성" 버튼)
  const btnExecuteStep1 = document.getElementById('btn-execute-step1') || document.getElementById('btn-execute-step3');
  if (btnExecuteStep1) {
    btnExecuteStep1.addEventListener('click', executeStep1);
  }

  // 대본 뷰어 토글
  const btnToggleView = document.getElementById('btn-toggle-script-view');
  if (btnToggleView) {
    btnToggleView.addEventListener('click', toggleScriptViewer);
  }

  // 결과 복사
  const btnCopyResult = document.getElementById('btn-copy-step1-result') || document.getElementById('btn-copy-step3-result');
  if (btnCopyResult) {
    btnCopyResult.addEventListener('click', () => {
      const textarea = document.getElementById('step1-result') || document.getElementById('step3-result');
      if (textarea && textarea.value) {
        navigator.clipboard.writeText(textarea.value);
        showStatus('✅ 복사 완료!');
        setTimeout(hideStatus, 2000);
      }
    });
  }

  // 결과 지우기
  const btnClearResult = document.getElementById('btn-clear-step1-result') || document.getElementById('btn-clear-step3-result');
  if (btnClearResult) {
    btnClearResult.addEventListener('click', () => {
      if (confirm('대본 결과를 지우시겠습니까?')) {
        const textarea = document.getElementById('step1-result') || document.getElementById('step3-result');
        const container = document.getElementById('step1-result-container') || document.getElementById('step3-result-container');
        if (textarea) textarea.value = '';
        if (container) container.style.display = 'none';
        step1Result = '';
        localStorage.removeItem('_drama-step1-result');
        showStatus('🗑️ 결과가 지워졌습니다.');
        setTimeout(hideStatus, 2000);
      }
    });
  }

  console.log('[DramaStep1] 초기화 완료');
});

// ===== 전역 노출 =====
window.DramaStep1 = {
  execute: executeStep1,
  formatScript: formatScriptToText,
  toggleViewer: toggleScriptViewer,
  extractNarration: extractNarrationFromScript,
  get result() { return step1Result; },
  get aiModelSettings() { return aiModelSettings; }
};

// 기존 코드 호환
window.executeStep1 = executeStep1;
window.executeStep3 = executeStep1;  // 이전 코드 호환
window.formatScriptToText = formatScriptToText;
window.extractNarrationFromScript = extractNarrationFromScript;
window.step1Result = step1Result;
window.step3Result = step1Result;  // 이전 코드 호환 (drama-app.js에서 step3Result로 참조)
window.aiModelSettings = aiModelSettings;
window.contentTypePrompts = contentTypePrompts;
window.step1Guide = step1Guide;
window.step3Guide = step1Guide;  // 이전 코드 호환
window.dramaJsonGuide = dramaJsonGuide;
