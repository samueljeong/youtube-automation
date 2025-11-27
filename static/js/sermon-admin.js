/**
 * sermon-admin.js
 * 관리자 기능 (카테고리/스타일/스텝/지침 관리)
 *
 * 주요 함수:
 * - renderCategoryManageList()
 * - renderStylesManageList()
 * - renderStepsManageList()
 * - loadGuide(), saveGuide()
 * - loadMasterGuide(), saveMasterGuide()
 * - renderGuideTabs()
 *
 * 이 파일은 sermon.html의 4793~5350줄 코드를 모듈화한 것입니다.
 * 전체 코드 마이그레이션이 필요합니다.
 */

// ===== 총괄 지침 관리 =====
function loadMasterGuide(category) {
  const settings = window.config.categorySettings[category];
  const textarea = document.getElementById('master-guide-text');
  if (textarea) {
    if (settings && settings.masterGuide) {
      textarea.value = settings.masterGuide;
    } else {
      textarea.value = '';
    }
    autoResize(textarea);
  }
}

async function saveMasterGuide() {
  const textarea = document.getElementById('master-guide-text');
  if (!textarea) return;

  const settings = window.config.categorySettings[window.currentCategory];
  if (settings) {
    settings.masterGuide = textarea.value;
    await saveConfig();
    showStatus('✅ 총괄 지침 저장됨');
    setTimeout(hideStatus, 1500);
  }
}

// ===== 지침 관리 =====
function loadGuide(category, stepId) {
  const key = getGuideKey(category, stepId);
  const legacyKey = `guide-${category}-${stepId}`;
  const migrationKey = `guide-migrated-${category}`;
  let stored = localStorage.getItem(key);

  if (!stored) {
    const legacyValue = localStorage.getItem(legacyKey);
    const migrationTarget = localStorage.getItem(migrationKey);

    if (legacyValue && (!migrationTarget || migrationTarget === window.currentStyleId)) {
      stored = legacyValue;
      localStorage.setItem(key, stored);
      saveToFirebase(key, stored);

      if (!migrationTarget) {
        const targetStyle = window.currentStyleId || 'default';
        localStorage.setItem(migrationKey, targetStyle);
        saveToFirebase(migrationKey, targetStyle);
      }
    }
  }

  stored = stored || '';
  const textarea = document.getElementById('guide-text');
  if (textarea) {
    textarea.value = stored;
    autoResize(textarea);
  }

  let info = `카테고리: ${getCategoryLabel(category)} | 단계: ${getStepName(stepId)}`;
  const infoEl = document.getElementById('current-guide-info');
  if (infoEl) {
    infoEl.textContent = info;
  }

  // JSON 디버그 패널 업데이트
  if (typeof updateJsonDebugPanel === 'function') {
    updateJsonDebugPanel(stored);
  }
}

async function saveGuide() {
  const textarea = document.getElementById('guide-text');
  if (!textarea || !window.currentGuideStep) return;

  const key = getGuideKey(window.currentCategory, window.currentGuideStep);
  const value = textarea.value;

  localStorage.setItem(key, value);
  const success = await saveToFirebase(key, value);

  if (success) {
    showStatus('✅ 지침 저장됨');
  } else {
    showStatus('⚠️ 로컬만 저장됨');
  }
  setTimeout(hideStatus, 1500);

  // JSON 디버그 패널 업데이트
  if (typeof updateJsonDebugPanel === 'function') {
    updateJsonDebugPanel(value);
  }
}

// ===== 지침 탭 렌더링 =====
function renderGuideTabs() {
  const container = document.getElementById('guide-tabs');
  if (!container) return;

  const steps = getCurrentSteps();
  if (steps.length === 0) {
    container.innerHTML = '<span style="color: #999; font-size: .85rem;">스타일을 선택하세요</span>';
    return;
  }

  // Step1, Step2, Step3 탭 생성
  let tabs = [];

  // Step1 탭들
  const step1Steps = steps.filter(s => (s.stepType || 'step1') === 'step1');
  step1Steps.forEach(s => {
    tabs.push({ id: s.id, name: `Step1: ${s.name}`, type: 'step1' });
  });

  // Step2 탭들
  const step2Steps = steps.filter(s => (s.stepType || 'step1') === 'step2');
  step2Steps.forEach(s => {
    tabs.push({ id: s.id, name: `Step2: ${s.name}`, type: 'step2' });
  });

  // Step3 탭
  tabs.push({ id: 'step3', name: 'Step3: 설교문 작성', type: 'step3' });

  container.innerHTML = tabs.map(tab =>
    `<button class="guide-tab ${tab.id === window.currentGuideStep ? 'active' : ''}" data-step="${tab.id}" style="padding: .35rem .6rem; margin-right: .25rem; font-size: .8rem; ${tab.type === 'step3' ? 'background: #f5576c; color: white;' : ''}">${tab.name}</button>`
  ).join('');

  // 탭 클릭 이벤트
  container.querySelectorAll('.guide-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      window.currentGuideStep = btn.dataset.step;
      container.querySelectorAll('.guide-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      loadGuide(window.currentCategory, window.currentGuideStep);
    });
  });

  // 첫 번째 탭 자동 선택
  if (!window.currentGuideStep && tabs.length > 0) {
    window.currentGuideStep = tabs[0].id;
    loadGuide(window.currentCategory, window.currentGuideStep);
  }
}

// ===== 카테고리 관리 =====
function renderCategoryManageList() {
  const container = document.getElementById('category-manage-list');
  if (!container) return;

  container.innerHTML = window.config.categories.map((cat, idx) => `
    <div class="storage-item" data-category="${cat.value}">
      <input type="text" value="${cat.label}" style="flex: 1; padding: .35rem; border: 1px solid #ddd; border-radius: 4px;" data-idx="${idx}">
      <button onclick="deleteCategory('${cat.value}')" style="background: #e74c3c; color: white; border: none; padding: .35rem .6rem;">삭제</button>
    </div>
  `).join('');

  // 이름 변경 이벤트
  container.querySelectorAll('input').forEach(input => {
    input.addEventListener('change', async () => {
      const idx = parseInt(input.dataset.idx);
      window.config.categories[idx].label = input.value;
      await saveConfig();
      renderCategories();
    });
  });
}

async function deleteCategory(value) {
  if (window.config.categories.length <= 1) {
    alert('최소 1개의 카테고리가 필요합니다.');
    return;
  }

  if (!confirm('이 카테고리를 삭제하시겠습니까?')) return;

  window.config.categories = window.config.categories.filter(c => c.value !== value);
  delete window.config.categorySettings[value];

  await saveConfig();
  renderCategories();
  renderCategoryManageList();
}

async function addCategory() {
  const newId = generateCategoryId();
  window.config.categories.push({
    value: newId,
    label: '새 카테고리'
  });
  window.config.categorySettings[newId] = {
    masterGuide: '',
    styles: []
  };

  await saveConfig();
  renderCategories();
  renderCategoryManageList();
}

// ===== 스타일 관리 =====
function renderStylesManageList() {
  const container = document.getElementById('styles-manage-list');
  if (!container) return;

  const catSettings = window.config.categorySettings[window.currentCategory];
  const styles = catSettings?.styles || [];

  if (styles.length === 0) {
    container.innerHTML = '<p style="color: #999; font-size: .85rem;">스타일이 없습니다.</p>';
    return;
  }

  container.innerHTML = styles.map((style, idx) => `
    <div class="storage-item" data-style="${style.id}">
      <input type="text" value="${style.name}" style="flex: 1; padding: .35rem; border: 1px solid #ddd; border-radius: 4px;" data-idx="${idx}">
      <button onclick="editStyleSteps('${style.id}')" style="background: #4a90e2; color: white; border: none; padding: .35rem .6rem;">스텝</button>
      <button onclick="deleteStyle('${style.id}')" style="background: #e74c3c; color: white; border: none; padding: .35rem .6rem;">삭제</button>
    </div>
  `).join('');

  // 이름 변경 이벤트
  container.querySelectorAll('input').forEach(input => {
    input.addEventListener('change', async () => {
      const idx = parseInt(input.dataset.idx);
      catSettings.styles[idx].name = input.value;
      await saveConfig();
      renderStyles();
    });
  });
}

async function addStyle() {
  const catSettings = window.config.categorySettings[window.currentCategory];
  if (!catSettings.styles) catSettings.styles = [];

  const newId = 'style_' + Date.now().toString(36);
  catSettings.styles.push({
    id: newId,
    name: '새 스타일',
    description: '',
    steps: [
      { id: 'step1', name: 'Step1', stepType: 'step1', order: 1 },
      { id: 'step2', name: 'Step2', stepType: 'step2', order: 2 }
    ]
  });

  await saveConfig();
  renderStyles();
  renderStylesManageList();
  syncStyleTokens();
}

async function deleteStyle(styleId) {
  if (!confirm('이 스타일을 삭제하시겠습니까?')) return;

  const catSettings = window.config.categorySettings[window.currentCategory];
  catSettings.styles = catSettings.styles.filter(s => s.id !== styleId);

  if (window.currentStyleId === styleId) {
    window.currentStyleId = catSettings.styles[0]?.id || '';
  }

  await saveConfig();
  renderStyles();
  renderStylesManageList();
  syncStyleTokens();
}

// 전역 노출
window.loadMasterGuide = loadMasterGuide;
window.saveMasterGuide = saveMasterGuide;
window.loadGuide = loadGuide;
window.saveGuide = saveGuide;
window.renderGuideTabs = renderGuideTabs;
window.renderCategoryManageList = renderCategoryManageList;
window.deleteCategory = deleteCategory;
window.addCategory = addCategory;
window.renderStylesManageList = renderStylesManageList;
window.addStyle = addStyle;
window.deleteStyle = deleteStyle;
