/**
 * sermon-render.js
 * UI 렌더링 함수 모음
 *
 * 주요 함수:
 * - renderCategories()
 * - switchCategoryContent()
 * - renderStyles()
 * - updateAnalysisUI()
 * - updateProgressStatus()
 * - startAutoAnalysis()
 * - renderProcessingSteps()
 * - renderResultBoxes()
 * - updateAdminStyleSelect()
 * - bindAdminStyleSelect()
 * - renderGuideTabs()
 *
 * 이 파일은 sermon.html의 3589~4166줄 코드를 모듈화한 것입니다.
 * 전체 코드는 sermon.html에서 추출하여 여기에 배치해야 합니다.
 */

// 분석 진행 상태
let analysisInProgress = false;

// 토큰 사용량 저장
let stepUsage = {};

// ===== 카테고리 렌더링 =====
function renderCategories() {
  const select = document.getElementById('sermon-category');
  const buttonsContainer = document.getElementById('category-buttons');

  if (!select) return;

  const current = select.value;
  select.innerHTML = window.config.categories.map(c =>
    `<option value="${c.value}">${c.label}</option>`
  ).join('');

  if (current && window.config.categories.find(c => c.value === current)) {
    select.value = current;
  } else {
    select.value = window.config.categories[0].value;
  }
  window.currentCategory = select.value;

  // 카테고리 버튼 렌더링
  if (buttonsContainer) {
    buttonsContainer.innerHTML = window.config.categories.map(c =>
      `<span class="category-chip ${c.value === window.currentCategory ? 'active' : ''}" data-category="${c.value}">${c.label}</span>`
    ).join('');

    // 클릭 이벤트 추가
    buttonsContainer.querySelectorAll('.category-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const categoryValue = chip.dataset.category;
        select.value = categoryValue;
        window.currentCategory = categoryValue;
        window.currentStyleId = '';
        window.stepResults = {};
        stepUsage = {};
        window.titleOptions = [];
        window.selectedTitle = '';

        const titleBox = document.getElementById('title-selection-box');
        if (titleBox) titleBox.style.display = 'none';
        const gptProContainer = document.getElementById('gpt-pro-result-container');
        if (gptProContainer) gptProContainer.style.display = 'none';

        // 버튼 활성화 상태 업데이트
        buttonsContainer.querySelectorAll('.category-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');

        if (typeof loadMasterGuide === 'function') loadMasterGuide(window.currentCategory);
        if (typeof loadModelSettings === 'function') loadModelSettings();
        renderStyles();
        renderProcessingSteps();
        renderResultBoxes();
        if (typeof renderGuideTabs === 'function') renderGuideTabs();
        updateAnalysisUI();

        const seriesBox = document.getElementById('series-box');
        if (seriesBox) {
          seriesBox.style.display = window.currentCategory === 'series' ? 'block' : 'none';
        }

        // 카테고리별 UI 전환
        switchCategoryContent(categoryValue);
      });
    });
  }

  // 초기 로드 시 카테고리별 UI 전환
  switchCategoryContent(window.currentCategory);
}

// ===== 카테고리별 콘텐츠 전환 =====
function switchCategoryContent(category) {
  const sermonContent = document.getElementById('sermon-content');
  const meditationContent = document.getElementById('meditation-content');
  const bibleKnowledgeContent = document.getElementById('bible-knowledge-content');
  const emptyContent = document.getElementById('empty-content');
  const designHelperContent = document.getElementById('design-helper-content');

  // 모든 콘텐츠 숨기기
  if (sermonContent) sermonContent.style.display = 'none';
  if (meditationContent) meditationContent.style.display = 'none';
  if (bibleKnowledgeContent) bibleKnowledgeContent.style.display = 'none';
  if (emptyContent) emptyContent.style.display = 'none';
  if (designHelperContent) designHelperContent.style.display = 'none';

  // 카테고리 label 가져오기
  const catConfig = window.config.categories.find(c => c.value === category);
  const label = catConfig ? catConfig.label : '';

  // 카테고리에 따라 해당 콘텐츠만 표시
  if (category === 'category1' || label.includes('묵상')) {
    if (meditationContent) meditationContent.style.display = 'block';
    if (typeof initMeditationDate === 'function') {
      initMeditationDate();
    }
  } else if (label.includes('배경지식')) {
    if (bibleKnowledgeContent) bibleKnowledgeContent.style.display = 'block';
  } else if (category === 'design_helper' || label.includes('디자인')) {
    const password = prompt('디자인 도우미는 테스트 중입니다.\n접근 비밀번호를 입력하세요:');
    if (password === '6039') {
      if (designHelperContent) designHelperContent.style.display = 'block';
      if (typeof initDesignHelper === 'function') initDesignHelper();
    } else {
      alert('비밀번호가 틀렸습니다.');
      if (emptyContent) emptyContent.style.display = 'block';
      return;
    }
  } else if (label.includes('설교') || category.startsWith('step_') ||
             ['general', 'series', 'education', 'lecture'].includes(category)) {
    if (sermonContent) sermonContent.style.display = 'block';
  } else {
    if (emptyContent) emptyContent.style.display = 'block';
  }
}

// ===== 스타일 렌더링 =====
function renderStyles() {
  console.log('[renderStyles] 호출됨');
  console.log('[renderStyles] currentCategory:', window.currentCategory);
  console.log('[renderStyles] currentStyleId:', window.currentStyleId);

  // 카테고리 설정이 없으면 생성
  if (!window.config.categorySettings[window.currentCategory]) {
    console.log('[renderStyles] 카테고리 설정 생성:', window.currentCategory);
    window.config.categorySettings[window.currentCategory] = {
      masterGuide: '',
      styles: []
    };
  }

  const settings = window.config.categorySettings[window.currentCategory];
  let styles = (settings && settings.styles) ? settings.styles : [];

  // 스타일이 없으면 기본 스타일 복구
  if (styles.length === 0 && window.DEFAULT_STYLES) {
    // 현재 카테고리의 기본 스타일이 있으면 사용, 없으면 general 스타일 사용
    const defaultStyles = window.DEFAULT_STYLES[window.currentCategory] || window.DEFAULT_STYLES['general'];
    if (defaultStyles && defaultStyles.length > 0) {
      console.log('[renderStyles] 기본 스타일 복구:', window.currentCategory, '(using:', window.DEFAULT_STYLES[window.currentCategory] ? 'own' : 'general', ')');
      settings.styles = JSON.parse(JSON.stringify(defaultStyles));
      styles = settings.styles;
      // 비동기로 저장
      if (typeof saveConfig === 'function') {
        setTimeout(() => saveConfig(), 100);
      }
    }
  }

  const container = document.getElementById('styles-list');

  console.log('[renderStyles] 스타일 수:', styles.length);
  if (styles.length > 0) {
    console.log('[renderStyles] 스타일 목록:', styles.map(s => s.id + '(' + s.name + ')').join(', '));
  }

  if (!container) {
    console.warn('[renderStyles] styles-list 컨테이너를 찾을 수 없습니다');
    return;
  }

  if (styles.length === 0) {
    container.innerHTML = '<p style="color: #999; font-size: .85rem; text-align: center;">스타일을 추가하세요. (관리 버튼 클릭)</p>';
    console.log('[renderStyles] 스타일이 없어서 안내 메시지 표시');
    // 스타일이 없으면 UI 업데이트
    updateAnalysisUI();
    return;
  }

  container.style.display = 'flex';
  container.style.flexWrap = 'wrap';
  container.style.gap = '.5rem';

  container.innerHTML = styles.map(style =>
    `<div class="style-item ${style.id === window.currentStyleId ? 'active' : ''}" data-style="${style.id}" style="flex: 1 1 auto; min-width: 80px; text-align: center; padding: .5rem .75rem;">
      <div style="font-weight: 600; font-size: .85rem;">${style.name}</div>
    </div>`
  ).join('');

  container.querySelectorAll('.style-item').forEach(item => {
    item.addEventListener('click', () => {
      console.log('[renderStyles] 스타일 클릭:', item.dataset.style);
      window.currentStyleId = item.dataset.style;
      window.stepResults = {};
      window.titleOptions = [];
      window.selectedTitle = '';
      const titleBox = document.getElementById('title-selection-box');
      if (titleBox) titleBox.style.display = 'none';
      const gptProContainer = document.getElementById('gpt-pro-result-container');
      if (gptProContainer) gptProContainer.style.display = 'none';
      renderStyles();
      renderProcessingSteps();
      renderResultBoxes();
      if (typeof renderGuideTabs === 'function') renderGuideTabs();
      updateAnalysisUI();
    });
  });

  // 스타일이 선택되어 있지 않으면 첫 번째 스타일 자동 선택
  if (!window.currentStyleId && styles.length > 0) {
    window.currentStyleId = styles[0].id;
    console.log('[renderStyles] 첫 번째 스타일 자동 선택:', window.currentStyleId);
    renderStyles();
    renderProcessingSteps();
  } else {
    console.log('[renderStyles] 현재 선택된 스타일:', window.currentStyleId);
  }
}

// ===== 분석 UI 업데이트 =====
function updateAnalysisUI() {
  console.log('[updateAnalysisUI] 호출됨');

  const statusContainer = document.getElementById('analysis-status');
  const startBtn = document.getElementById('btn-start-analysis');
  const guideDiv = document.getElementById('start-analysis-guide');
  const step3Box = document.getElementById('step3-box');
  const step4Box = document.getElementById('step4-box');
  const ref = document.getElementById('sermon-ref')?.value?.trim();

  console.log('[updateAnalysisUI] 버튼 찾음:', !!startBtn);
  console.log('[updateAnalysisUI] ref:', ref ? `있음(${ref})` : '없음');
  console.log('[updateAnalysisUI] currentStyleId:', window.currentStyleId);
  console.log('[updateAnalysisUI] analysisInProgress:', analysisInProgress);

  if (!startBtn) {
    console.warn('[updateAnalysisUI] btn-start-analysis 버튼을 찾을 수 없습니다');
    return;
  }

  // 스타일이 선택되어 있지 않으면 자동 선택 시도
  if (!window.currentStyleId && typeof ensureStyleSelected === 'function') {
    console.log('[updateAnalysisUI] 스타일 자동 선택 시도');
    ensureStyleSelected();
    console.log('[updateAnalysisUI] 자동 선택 후 currentStyleId:', window.currentStyleId);
  }

  const steps = getCurrentSteps();
  console.log('[updateAnalysisUI] 처리 단계 수:', steps.length);

  const step1Steps = steps.filter(s => (s.stepType || 'step1') === 'step1');
  const step2Steps = steps.filter(s => (s.stepType || 'step1') === 'step2');
  const step1Completed = step1Steps.length > 0 && step1Steps.every(s => window.stepResults[s.id]);
  const step2Completed = step2Steps.length > 0 && step2Steps.every(s => window.stepResults[s.id]);
  const allCompleted = step1Completed && step2Completed;

  console.log('[updateAnalysisUI] step1Steps:', step1Steps.length, 'completed:', step1Completed);
  console.log('[updateAnalysisUI] step2Steps:', step2Steps.length, 'completed:', step2Completed);
  console.log('[updateAnalysisUI] allCompleted:', allCompleted);

  // 안내 문구 업데이트 헬퍼 함수
  function setGuideMessage(message, isReady = false) {
    if (!guideDiv) return;
    guideDiv.style.display = 'block';
    if (isReady) {
      guideDiv.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
      guideDiv.style.border = 'none';
      guideDiv.innerHTML = `<span style="font-size: .9rem; font-weight: 700; color: white;">${message}</span>`;
    } else {
      guideDiv.style.background = '#f8f9ff';
      guideDiv.style.border = '2px dashed #667eea';
      guideDiv.innerHTML = `<span style="font-size: .9rem; font-weight: 700; color: #667eea;">${message}</span>`;
    }
  }

  // 버튼 표시 조건 결정
  let buttonAction = '';

  if (allCompleted) {
    buttonAction = 'hide (allCompleted)';
    if (step3Box) { step3Box.style.opacity = '1'; step3Box.style.pointerEvents = 'auto'; }
    if (step4Box) { step4Box.style.opacity = '1'; step4Box.style.pointerEvents = 'auto'; }
    startBtn.style.display = 'none';
    if (guideDiv) guideDiv.style.display = 'none';
  } else if (!ref) {
    buttonAction = 'hide (no ref)';
    startBtn.style.display = 'none';
    setGuideMessage('📖 성경본문을 입력해주세요');
    if (step3Box) { step3Box.style.opacity = '0.5'; step3Box.style.pointerEvents = 'none'; }
    if (step4Box) { step4Box.style.opacity = '0.5'; step4Box.style.pointerEvents = 'none'; }
  } else if (!window.currentStyleId) {
    // ref는 있지만 스타일이 선택되지 않음
    buttonAction = 'hide (no style selected)';
    startBtn.style.display = 'none';
    setGuideMessage('👆 위에서 설교 스타일을 선택해주세요');
    if (step3Box) { step3Box.style.opacity = '0.5'; step3Box.style.pointerEvents = 'none'; }
    if (step4Box) { step4Box.style.opacity = '0.5'; step4Box.style.pointerEvents = 'none'; }
  } else if (!analysisInProgress) {
    buttonAction = 'SHOW (ref + style + not processing)';
    startBtn.style.display = 'block';
    if (guideDiv) guideDiv.style.display = 'none';
    if (step3Box) { step3Box.style.opacity = '0.5'; step3Box.style.pointerEvents = 'none'; }
    if (step4Box) { step4Box.style.opacity = '0.5'; step4Box.style.pointerEvents = 'none'; }
  } else {
    buttonAction = 'hide (processing)';
    startBtn.style.display = 'none';
    // 처리 중에는 guideDiv가 진행상황을 표시하므로 건드리지 않음
    if (step3Box) { step3Box.style.opacity = '0.5'; step3Box.style.pointerEvents = 'none'; }
    if (step4Box) { step4Box.style.opacity = '0.5'; step4Box.style.pointerEvents = 'none'; }
  }

  console.log('[updateAnalysisUI] 버튼 상태:', buttonAction);
}

// ===== 진행 상태 표시 =====
function updateProgressStatus(statuses) {
  const guideDiv = document.getElementById('start-analysis-guide');
  if (!guideDiv) return;

  const statusIcons = {
    pending: '⏸️',
    running: '⏳',
    done: '✅',
    error: '❌'
  };

  guideDiv.style.display = 'block';
  guideDiv.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
  guideDiv.style.border = 'none';
  guideDiv.style.padding = '.8rem';
  guideDiv.style.textAlign = 'left';

  let html = '<div style="color: white; font-weight: 700; font-size: .85rem; margin-bottom: .5rem; text-align: center;">BIBLE LAB을 이용해 주셔서 감사합니다.</div>';
  html += '<div style="border-top: 1px solid rgba(255,255,255,0.3); padding-top: .5rem;">';

  statuses.forEach(s => {
    const icon = statusIcons[s.status] || '⏸️';
    let statusText = '';
    let opacity = '0.6';

    if (s.status === 'done') { statusText = '완료'; opacity = '1'; }
    else if (s.status === 'running') { statusText = '처리 중...'; opacity = '1'; }
    else if (s.status === 'pending') { statusText = '대기'; opacity = '0.6'; }
    else if (s.status === 'error') { statusText = '오류'; opacity = '1'; }

    html += `<div style="font-size: .8rem; color: white; padding: .2rem 0; opacity: ${opacity};">${icon} ${s.name} ${statusText}</div>`;
  });

  html += '</div>';
  guideDiv.innerHTML = html;
}

// ===== 자동 분석 실행 =====
async function startAutoAnalysis() {
  const ref = document.getElementById('sermon-ref').value;
  if (!ref) {
    alert('성경본문을 입력하세요.');
    return;
  }
  if (!window.currentStyleId) {
    alert('설교 스타일을 선택하세요.');
    return;
  }

  analysisInProgress = true;
  const startBtn = document.getElementById('btn-start-analysis');
  if (startBtn) startBtn.style.display = 'none';

  const steps = getCurrentSteps();
  const step1Steps = steps.filter(s => (s.stepType || 'step1') === 'step1');
  const step2Steps = steps.filter(s => (s.stepType || 'step1') === 'step2');

  const allStatuses = [
    ...step1Steps.map(s => ({ id: s.id, name: s.name, status: 'pending' })),
    ...step2Steps.map(s => ({ id: s.id, name: s.name, status: 'pending' }))
  ];
  updateProgressStatus(allStatuses);

  try {
    // Step1 병렬 실행
    const step1Promises = step1Steps.map(async (step) => {
      const idx = allStatuses.findIndex(s => s.id === step.id);
      allStatuses[idx].status = 'running';
      updateProgressStatus(allStatuses);

      try {
        await executeStep(step.id);
        allStatuses[idx].status = 'done';
      } catch (e) {
        allStatuses[idx].status = 'error';
      }
      updateProgressStatus(allStatuses);
    });

    await Promise.all(step1Promises);

    // Step2 순차 실행
    for (const step of step2Steps) {
      const idx = allStatuses.findIndex(s => s.id === step.id);
      allStatuses[idx].status = 'running';
      updateProgressStatus(allStatuses);

      try {
        await executeStep(step.id);
        allStatuses[idx].status = 'done';
      } catch (e) {
        allStatuses[idx].status = 'error';
      }
      updateProgressStatus(allStatuses);
    }

    updateAnalysisUI();

  } catch (error) {
    console.error('분석 실행 오류:', error);
    alert('분석 중 오류가 발생했습니다.');
  } finally {
    analysisInProgress = false;
  }
}

// ===== 처리 단계 렌더링 =====
function renderProcessingSteps() {
  const container = document.getElementById('processing-steps');
  if (container) {
    container.style.display = 'none';
    container.innerHTML = '';
  }
}

// ===== 결과 박스 렌더링 =====
function renderResultBoxes() {
  const steps = getCurrentSteps();
  const container = document.getElementById('result-boxes');
  const modelSettings = getModelSettings(window.currentCategory);

  if (!container) return;

  container.innerHTML = steps.map(step => {
    const stepType = step.stepType || 'step1';
    const stepLabel = stepType === 'step1' ? 'Step1' : 'Step2';
    const usage = stepUsage[step.id];
    const usageHtml = usage ? `
      <span id="usage-${step.id}" style="font-size: .75rem; color: #888;">
        in(${usage.inputTokens?.toLocaleString() || 0}), out(${usage.outputTokens?.toLocaleString() || 0}), ${usage.costKRW || '0.0'}
      </span>
    ` : `<span id="usage-${step.id}" style="font-size: .75rem; color: #888;"></span>`;

    return `
      <div class="box step2-box">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: .35rem;">
          <label class="label" style="margin: 0;">${stepLabel}. ${step.name}</label>
          ${usageHtml}
        </div>
        <div class="step2-content-wrapper">
          <textarea id="result-${step.id}" class="autosize" style="min-height: 100px; max-height: 150px;" readonly placeholder="${step.name} 결과가 표시됩니다."></textarea>
          <div class="step2-gradient-overlay"></div>
        </div>
        <div style="text-align: center; color: #999; font-size: .85rem; padding: .5rem; border-top: 1px dashed #ddd; margin-top: .3rem;">
          -<br>-<br>-<br>
          <span style="font-size: .75rem;">이하 내용 생략</span>
        </div>
      </div>
    `;
  }).join('');

  // 결과 복원
  steps.forEach(step => {
    if (window.stepResults[step.id]) {
      const textarea = document.getElementById(`result-${step.id}`);
      if (textarea) {
        const stepType = step.stepType || 'step1';
        textarea.value = truncateResult(window.stepResults[step.id], stepType);
      }
    }
  });

  // 입력 이벤트
  container.querySelectorAll('textarea').forEach(textarea => {
    textarea.addEventListener('input', () => {
      autoResize(textarea);
      const stepId = textarea.id.replace('result-', '');
      window.stepResults[stepId] = textarea.value;
      autoSaveStepResults();
    });
  });
}

// 전역 노출
window.analysisInProgress = analysisInProgress;
window.stepUsage = stepUsage;
window.renderCategories = renderCategories;
window.switchCategoryContent = switchCategoryContent;
window.renderStyles = renderStyles;
window.updateAnalysisUI = updateAnalysisUI;
window.updateProgressStatus = updateProgressStatus;
window.startAutoAnalysis = startAutoAnalysis;
window.renderProcessingSteps = renderProcessingSteps;
window.renderResultBoxes = renderResultBoxes;
