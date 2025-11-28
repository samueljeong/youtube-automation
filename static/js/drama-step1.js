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

// ===== GPT 분석 프롬프트 저장 변수 =====
let gptAnalyzedPrompts = JSON.parse(localStorage.getItem('_drama-gpt-prompts') || 'null');

// ===== GPT 이미지 프롬프트 분석 함수 (Step 1.5) =====
async function analyzePromptsWithGPT(script, videoCategory) {
  try {
    showStatus('🔍 Step 1.5: GPT 대본 분석 및 이미지 프롬프트 생성 중...');
    if (typeof updateStepStatus === 'function') {
      updateStepStatus('step1_5', 'working', 'GPT 분석 중...');
    }
    if (typeof window.updateModelStatus === 'function') {
      window.updateModelStatus('step1_5', null, 'running');
    }

    const response = await fetch('/api/drama/gpt-analyze-prompts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        script: script,
        videoCategory: videoCategory
      })
    });

    const data = await response.json();

    if (data.ok && data.parsed) {
      gptAnalyzedPrompts = data.result;

      // localStorage에 안전하게 저장
      if (typeof window.safeLocalStorageSet === 'function') {
        window.safeLocalStorageSet('_drama-gpt-prompts', JSON.stringify(gptAnalyzedPrompts));
      } else {
        localStorage.setItem('_drama-gpt-prompts', JSON.stringify(gptAnalyzedPrompts));
      }
      if (typeof saveToFirebase === 'function') {
        saveToFirebase('_drama-gpt-prompts', JSON.stringify(gptAnalyzedPrompts));
      }

      console.log('[GPT-Analyze] 프롬프트 분석 완료:', {
        visualStyle: gptAnalyzedPrompts.visualStyle,
        characters: gptAnalyzedPrompts.characters?.length || 0,
        scenes: gptAnalyzedPrompts.scenes?.length || 0,
        thumbnail: gptAnalyzedPrompts.thumbnail ? '생성됨' : '없음'
      });

      // 💰 Step 1.5 비용 추가
      if (data.cost && typeof window.addCost === 'function') {
        window.addCost('step1_5', data.cost);
      }
      if (typeof window.updateModelStatus === 'function') {
        window.updateModelStatus('step1_5', null, 'completed');
      }

      // 썸네일 프롬프트 별도 저장
      if (gptAnalyzedPrompts.thumbnail) {
        if (typeof window.safeLocalStorageSet === 'function') {
          window.safeLocalStorageSet('_drama-thumbnail-prompt', JSON.stringify(gptAnalyzedPrompts.thumbnail));
        } else {
          localStorage.setItem('_drama-thumbnail-prompt', JSON.stringify(gptAnalyzedPrompts.thumbnail));
        }
        if (typeof saveToFirebase === 'function') {
          saveToFirebase('_drama-thumbnail-prompt', JSON.stringify(gptAnalyzedPrompts.thumbnail));
        }
        console.log('[GPT-Analyze] 썸네일 프롬프트 저장됨:', gptAnalyzedPrompts.thumbnail.concept);
      }

      const thumbnailInfo = gptAnalyzedPrompts.thumbnail ? ', 썸네일 프롬프트 생성' : '';
      showStatus(`✅ Step 1.5 완료: ${gptAnalyzedPrompts.characters?.length || 0}명의 인물, ${gptAnalyzedPrompts.scenes?.length || 0}개의 씬 프롬프트${thumbnailInfo}`);

      // 완료 상태 표시
      if (typeof updateStepStatus === 'function') {
        updateStepStatus('step1_5', 'completed', '프롬프트 생성 완료');
      }

      return gptAnalyzedPrompts;
    } else {
      console.warn('[GPT-Analyze] 분석 실패 또는 JSON 파싱 실패:', data);
      showStatus('⚠️ Step 1.5 실패 - 기본 분석 사용');
      if (typeof updateStepStatus === 'function') {
        updateStepStatus('step1_5', 'error', '분석 실패');
      }
      return null;
    }
  } catch (err) {
    console.error('[GPT-Analyze] 오류:', err);
    showStatus('⚠️ Step 1.5 오류 - 기본 분석 사용');
    if (typeof updateStepStatus === 'function') {
      updateStepStatus('step1_5', 'error', err.message.substring(0, 20));
    }
    return null;
  }
}

// 전역 노출
window.gptAnalyzedPrompts = gptAnalyzedPrompts;
window.analyzePromptsWithGPT = analyzePromptsWithGPT;

// ===== 새 대본 생성 시 기존 데이터 초기화 =====
function clearPreviousSessionData() {
  console.log('[Step1] 새 대본 생성 - 기존 이미지/데이터 초기화');

  // 이미지 관련 localStorage 삭제
  const keysToRemove = [
    '_drama-step4-characters',
    '_drama-step4-character-images',
    '_drama-step4-scenes',
    '_drama-step4-images',
    '_drama-gpt-prompts',
    '_drama-thumbnail',
    '_drama-thumbnail-prompt',
    '_drama-step3-audio-url',
    '_drama-step3-subtitle',
    '_drama-step4-video-url',
    '_drama-step4-video-file-url'
  ];

  keysToRemove.forEach(key => {
    localStorage.removeItem(key);
  });

  // 전역 변수 초기화
  if (typeof window.gptAnalyzedPrompts !== 'undefined') {
    window.gptAnalyzedPrompts = null;
  }

  // UI 이미지 그리드 초기화
  const imageGrid = document.getElementById('step4-image-grid');
  if (imageGrid) {
    imageGrid.innerHTML = '';
  }

  // 캐릭터 이미지 컨테이너 초기화
  const charContainer = document.getElementById('step4-character-container');
  if (charContainer) {
    charContainer.innerHTML = '<p style="color: #666; font-size: 0.9rem;">Step1.5 분석 후 인물 목록이 표시됩니다</p>';
  }

  // 썸네일 미리보기 초기화
  const thumbnailPreview = document.getElementById('step4-thumbnail-preview');
  if (thumbnailPreview) {
    thumbnailPreview.style.display = 'none';
  }
  const thumbnailImage = document.getElementById('step4-thumbnail-image');
  if (thumbnailImage) {
    thumbnailImage.src = '';
  }

  // Step2 전역 변수도 초기화 (있다면)
  if (typeof window.DramaStep2 !== 'undefined') {
    if (window.DramaStep2.characters) window.DramaStep2.characters = [];
    if (window.DramaStep2.scenes) window.DramaStep2.scenes = [];
    if (window.DramaStep2.characterImages) window.DramaStep2.characterImages = {};
    if (window.DramaStep2.generatedImages) window.DramaStep2.generatedImages = [];
  }

  // 비용 초기화
  if (typeof window.resetCosts === 'function') {
    window.resetCosts();
  }

  console.log('[Step1] 기존 데이터 초기화 완료');
}

window.clearPreviousSessionData = clearPreviousSessionData;

// ===== 대본 생성 메인 함수 =====
async function executeStep1() {
  // 화면에서 Step1 버튼을 누르면 실행되는 함수
  // 실제로는 executeStep3() 함수가 대본 생성을 담당

  // ⭐ 새 대본 생성 시 기존 이미지/데이터 초기화
  clearPreviousSessionData();

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

    // Step1 상태 업데이트
    if (typeof updateStepStatus === 'function') {
      updateStepStatus('step1', 'working', 'GPT 기획 중 (1/3)');
    }

    // 1단계: GPT-4o-mini 스토리 기획
    showLoadingOverlay('GPT 기획 중 (1/3)', 'GPT-4o-mini가 스토리 컨셉을 기획하고 있습니다...');
    showStatus('🎯 Step1-1: GPT-4o-mini 스토리 기획 중...');
    if (typeof window.updateModelStatus === 'function') {
      window.updateModelStatus('step1', 'plan', 'running');
    }

    const planStep1Response = await fetch('/api/drama/gpt-plan-step1', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        videoCategory: videoCategory,
        duration: durationLabel,
        customDirective: window.customDirective || '',
        testMode: window.testMode || false
      })
    });

    const planStep1Data = await planStep1Response.json();
    if (!planStep1Data.ok) {
      throw new Error('GPT 기획 1단계 실패: ' + (planStep1Data.error || '알 수 없는 오류'));
    }

    // 💰 Step1-1 GPT 비용 추가
    if (planStep1Data.cost && typeof window.addCost === 'function') {
      window.addCost('step1', planStep1Data.cost);
    }
    if (typeof window.updateModelStatus === 'function') {
      window.updateModelStatus('step1', 'plan', 'completed');
    }

    console.log('[Step1-1] GPT 기획 완료');

    // Step1 상태 업데이트
    if (typeof updateStepStatus === 'function') {
      updateStepStatus('step1', 'working', 'GPT 구조화 중 (2/3)');
    }

    // 2단계: GPT-4o-mini 장면 구성
    showLoadingOverlay('GPT 구조화 중 (2/3)', 'GPT-4o-mini가 장면 구성을 만들고 있습니다...');
    showStatus('📐 Step1-2: GPT-4o-mini 장면 구조화 중...');
    if (typeof window.updateModelStatus === 'function') {
      window.updateModelStatus('step1', 'struct', 'running');
    }

    const planStep2Response = await fetch('/api/drama/gpt-plan-step2', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        videoCategory: videoCategory,
        duration: durationLabel,
        customDirective: window.customDirective || '',
        step1Result: planStep1Data.result,
        testMode: window.testMode || false
      })
    });

    const planStep2Data = await planStep2Response.json();
    if (!planStep2Data.ok) {
      throw new Error('GPT 기획 2단계 실패: ' + (planStep2Data.error || '알 수 없는 오류'));
    }

    // 💰 Step1-2 GPT 비용 추가
    if (planStep2Data.cost && typeof window.addCost === 'function') {
      window.addCost('step1', planStep2Data.cost);
    }
    if (typeof window.updateModelStatus === 'function') {
      window.updateModelStatus('step1', 'struct', 'completed');
    }

    console.log('[Step1-2] 장면 구성 완료');

    // GPT 기획 결과 합치기
    gptPlanResult = `【 GPT-4o-mini 기획 결과 】\n\n`;
    gptPlanResult += `=== 스토리 컨셉 ===\n${planStep1Data.result}\n\n`;
    gptPlanResult += `=== 장면 구성 ===\n${planStep2Data.result}`;

    // Step1 상태 업데이트
    if (typeof updateStepStatus === 'function') {
      updateStepStatus('step1', 'working', 'Claude 대본 작성 중 (3/3)');
    }

    // 3단계: Claude로 최종 대본 작성
    showLoadingOverlay('Claude 대본 작성 중 (3/3)', 'Claude Sonnet 4.5가 대본을 작성하고 있습니다...');
    showStatus('🎬 Step1-3: Claude 대본 완성 중... (약 30-60초 소요)');
    if (typeof window.updateModelStatus === 'function') {
      window.updateModelStatus('step1', 'write', 'running');
    }

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
        customJsonGuide: currentJsonGuide,
        testMode: window.testMode || false
      })
    });

    const data = await response.json();

    if (data.ok) {
      // 결과 저장 및 표시
      step1Result = data.result;
      if (typeof window.safeLocalStorageSet === 'function') {
        window.safeLocalStorageSet('_drama-step1-result', step1Result);
      } else {
        localStorage.setItem('_drama-step1-result', step1Result);
      }

      // ⭐ Firebase에도 저장 (새로고침 후에도 유지)
      if (typeof saveToFirebase === 'function') {
        saveToFirebase('_drama-step1-result', step1Result);
        console.log('[Step1] Firebase에 대본 저장됨');
      }

      // 💰 Step1 비용 추가 (Claude Sonnet)
      if (data.cost && typeof window.addCost === 'function') {
        window.addCost('step1', data.cost);
      }
      if (typeof window.updateModelStatus === 'function') {
        window.updateModelStatus('step1', 'write', 'completed');
      }

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

      // ⭐ GPT 이미지 프롬프트 분석 실행 (Step2 전에)
      console.log('[Step1] GPT 이미지 프롬프트 분석 시작...');
      await analyzePromptsWithGPT(step1Result, videoCategory);

      // ⭐ Step1.5 완료 후 항상 Step2(이미지)와 Step3(TTS) 병렬 실행
      console.log('[Step1] Step1.5 완료 → Step2+Step3 병렬 시작...');
      setTimeout(() => {
        runStep2AndStep3InParallel();
      }, 2000);

      return data.result;

    } else {
      throw new Error(data.error || '대본 생성 실패');
    }

  } catch (err) {
    console.error('[Step1] 오류:', err);
    alert(`대본 생성 오류: ${err.message}`);
    showStatus('❌ Step1 실패');
    if (typeof updateStepStatus === 'function') {
      updateStepStatus('step1', 'error', err.message.substring(0, 30));
    }
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

// ===== 주인공 성별에 따른 TTS 음성 자동 선택 =====
function autoSelectTTSVoiceByGender() {
  try {
    // GPT 분석 결과에서 주인공 정보 가져오기
    const prompts = window.gptAnalyzedPrompts || JSON.parse(localStorage.getItem('_drama-gpt-prompts') || 'null');

    if (!prompts || !prompts.characters || prompts.characters.length === 0) {
      console.log('[TTS-Voice] 캐릭터 정보 없음 - 기본 음성 유지');
      return;
    }

    // 첫 번째 캐릭터(주인공)의 성별 확인
    const mainCharacter = prompts.characters[0];
    const gender = (mainCharacter.gender || mainCharacter.sex || '').toLowerCase();
    const name = mainCharacter.name || mainCharacter.nameKo || '';

    // 성별 판단 (이름이나 설명에서도 추측)
    let isFemale = false;
    if (gender.includes('female') || gender.includes('여') || gender.includes('woman') || gender.includes('girl')) {
      isFemale = true;
    } else if (gender.includes('male') || gender.includes('남') || gender.includes('man') || gender.includes('boy')) {
      isFemale = false;
    } else {
      // 이름에서 추측 (한국 이름)
      const femaleNameEndings = ['아', '이', '진', '미', '희', '영', '정', '숙', '자', '선'];
      const lastName = name.slice(-1);
      isFemale = femaleNameEndings.includes(lastName);
    }

    // 음성 선택: 여성 → 여성B (ko-KR-Wavenet-B), 남성 → 남성A (ko-KR-Wavenet-C)
    const selectedVoice = isFemale ? 'ko-KR-Wavenet-B' : 'ko-KR-Wavenet-C';

    console.log(`[TTS-Voice] 주인공: ${name}, 성별: ${isFemale ? '여성' : '남성'} → 음성: ${selectedVoice}`);

    // TTS 음성 설정 업데이트
    if (typeof window.step3SelectedVoice !== 'undefined') {
      window.step3SelectedVoice = selectedVoice;
    }

    // UI 업데이트 (음성 선택 버튼)
    const voiceOptions = document.querySelectorAll('.step5-voice-option[data-provider="google"]');
    voiceOptions.forEach(opt => {
      opt.classList.remove('selected');
      if (opt.dataset.voice === selectedVoice) {
        opt.classList.add('selected');
      }
    });

    // 전역 변수 업데이트
    localStorage.setItem('_drama-tts-voice', selectedVoice);

  } catch (err) {
    console.warn('[TTS-Voice] 자동 선택 실패:', err);
  }
}

window.autoSelectTTSVoiceByGender = autoSelectTTSVoiceByGender;

// ===== Step2(이미지)와 Step3(TTS) 병렬 실행 =====
async function runStep2AndStep3InParallel() {
  console.log('[PARALLEL] Step2(이미지) + Step3(TTS) 병렬 실행 시작...');
  showStatus('🚀 Step2(이미지) + Step3(TTS) 동시 생성 시작...');

  let step2Completed = false;
  let step3Completed = false;
  let step2Error = null;
  let step3Error = null;

  // Step2: 이미지 생성 (비동기)
  const step2Promise = (async () => {
    try {
      console.log('[PARALLEL] Step2 시작: 이미지 생성');
      showLoadingOverlay('Step2: 이미지 생성', 'Step3(TTS)와 동시에 진행 중...');

      if (typeof generateAllAuto === 'function') {
        await generateAllAuto(true);  // skipConfirm = true
      }
      step2Completed = true;
      console.log('[PARALLEL] Step2 완료: 이미지 생성 성공');
    } catch (err) {
      step2Error = err;
      console.error('[PARALLEL] Step2 오류:', err);
    }
  })();

  // Step3: TTS 음성 생성 (비동기) - Step2와 동시에 시작
  const step3Promise = (async () => {
    try {
      console.log('[PARALLEL] Step3 시작: TTS 음성 생성');

      // 잠시 대기 (DOM 업데이트 대기)
      await new Promise(resolve => setTimeout(resolve, 500));

      // ⭐ 주인공 성별에 따라 TTS 음성 자동 설정
      autoSelectTTSVoiceByGender();

      // 지문 추출 (TTS용 텍스트만)
      if (typeof extractNarrationForTTS === 'function') {
        extractNarrationForTTS();
      } else if (typeof extractNarration === 'function') {
        extractNarration();
      }
      await new Promise(resolve => setTimeout(resolve, 500));

      // TTS 생성
      if (typeof generateTTS === 'function') {
        await generateTTS();
      }
      step3Completed = true;
      console.log('[PARALLEL] Step3 완료: TTS 생성 성공');
    } catch (err) {
      step3Error = err;
      console.error('[PARALLEL] Step3 오류:', err);
    }
  })();

  // 두 작업 모두 완료 대기
  await Promise.allSettled([step2Promise, step3Promise]);

  hideLoadingOverlay();

  // 결과 확인
  if (step2Completed && step3Completed) {
    console.log('[PARALLEL] Step2 + Step3 모두 완료! Step4(영상) 시작...');
    showStatus('✅ Step2+Step3 완료! Step4(영상 생성) 시작...');

    // Step4: 영상 생성
    setTimeout(async () => {
      if (typeof window.DramaStep4 !== 'undefined') {
        // 이미지 자동 선택
        if (typeof window.DramaStep4.autoSelectImages === 'function') {
          await window.DramaStep4.autoSelectImages();
        }
        // 영상 생성
        if (typeof window.DramaStep4.generateVideoAuto === 'function') {
          await window.DramaStep4.generateVideoAuto();
        }
      }
    }, 2000);
  } else {
    const errors = [];
    if (step2Error) errors.push(`이미지: ${step2Error.message}`);
    if (step3Error) errors.push(`TTS: ${step3Error.message}`);
    showStatus(`⚠️ 일부 작업 실패 - ${errors.join(', ')}`);
  }

  // 자동화 모드 해제
  window.isFullAutoMode = false;
  if (typeof window.DramaStep2 !== 'undefined') {
    window.DramaStep2.isFullAutoMode = false;
  }
}

// 전역 노출
window.runStep2AndStep3InParallel = runStep2AndStep3InParallel;

// ===== 저장된 대본 결과 복원 =====
function restoreStep1Data() {
  const savedResult = localStorage.getItem('_drama-step1-result');
  if (savedResult && savedResult.trim()) {
    step1Result = savedResult;

    const resultTextarea = document.getElementById('step1-result') || document.getElementById('step3-result');
    const resultContainer = document.getElementById('step1-result-container') || document.getElementById('step3-result-container');

    if (resultTextarea) {
      resultTextarea.value = savedResult;
      if (typeof autoResize === 'function') autoResize(resultTextarea);
      console.log('[DramaStep1] 대본 결과 복원 완료 (길이: ' + savedResult.length + '자)');
    }

    if (resultContainer) {
      resultContainer.style.display = 'block';
    }

    // Step 완료 표시
    if (typeof updateProgressIndicator === 'function') {
      updateProgressIndicator('step1');
    }
    if (typeof updateStepNavCompleted === 'function') {
      updateStepNavCompleted('step1', true);
    }

    return true;
  }
  return false;
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

  // ⭐ 저장된 대본 결과 복원 (중요!)
  setTimeout(() => {
    const restored = restoreStep1Data();
    if (restored) {
      console.log('[DramaStep1] 이전 세션 대본 복원됨');
    }
  }, 300);

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
