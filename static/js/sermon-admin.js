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

  // localStorage에 지침이 없으면 DEFAULT_GUIDES에서 가져옴
  if (!stored && window.DEFAULT_GUIDES) {
    const style = getCurrentStyle();
    const styleName = style?.name || '';
    // stepId에서 stepType 추출 (step1-1 → step1, step3 → step3)
    const stepType = stepId.startsWith('step3') ? 'step3' :
                     stepId.startsWith('step2') ? 'step2' : 'step1';

    const defaultGuide = window.DEFAULT_GUIDES[styleName]?.[stepType];
    if (defaultGuide) {
      stored = JSON.stringify(defaultGuide, null, 2);
      console.log('[loadGuide] DEFAULT_GUIDES에서 지침 로드:', styleName, stepType);
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
  // 스타일 선택 드롭다운 업데이트
  updateAdminStyleSelect();

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

  // DEFAULT_GUIDES 키 순서대로 이름 자동 설정
  const guideKeys = Object.keys(window.DEFAULT_GUIDES || {});
  const existingNames = catSettings.styles.map(s => s.name);

  // 아직 사용되지 않은 첫 번째 가이드 키 찾기
  let newName = '새 스타일';
  for (const key of guideKeys) {
    if (!existingNames.includes(key)) {
      newName = key;
      break;
    }
  }

  const newId = 'style_' + Date.now().toString(36);
  catSettings.styles.push({
    id: newId,
    name: newName,
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

// ===== 관리자 공간 - 스타일 선택 =====
function updateAdminStyleSelect() {
  const select = document.getElementById('admin-style-select');
  if (!select) return;

  const catSettings = window.config.categorySettings[window.currentCategory];
  const styles = catSettings?.styles || [];

  let html = '<option value="">-- 스타일을 선택하세요 --</option>';
  styles.forEach(style => {
    const selected = style.id === window.currentStyleId ? 'selected' : '';
    html += `<option value="${style.id}" ${selected}>${style.name}</option>`;
  });

  select.innerHTML = html;
}

function bindAdminStyleSelect() {
  const select = document.getElementById('admin-style-select');
  if (!select) return;

  select.addEventListener('change', (e) => {
    window.currentStyleId = e.target.value;
    renderGuideTabs();
    if (window.currentStyleId && window.currentGuideStep) {
      loadGuide(window.currentCategory, window.currentGuideStep);
    }
  });
}

// ===== DEFAULT_GUIDES 동기화 =====
async function syncDefaultGuides() {
  if (!window.DEFAULT_GUIDES) {
    console.log('[syncDefaultGuides] DEFAULT_GUIDES가 없습니다.');
    return;
  }

  const catSettings = window.config.categorySettings[window.currentCategory];
  const styles = catSettings?.styles || [];
  let synced = 0;

  for (const style of styles) {
    const styleName = style.name;
    const defaultGuides = window.DEFAULT_GUIDES[styleName];
    if (!defaultGuides) continue;

    for (const [stepType, guideData] of Object.entries(defaultGuides)) {
      // stepType에 해당하는 stepId 찾기
      let stepId;
      if (stepType === 'step3') {
        stepId = 'step3';
      } else {
        const step = style.steps?.find(s => (s.stepType || 'step1') === stepType);
        stepId = step?.id || stepType;
      }

      const key = getGuideKey(window.currentCategory, stepId, style.id);
      const existing = localStorage.getItem(key);

      // 기존 저장값이 없을 때만 동기화
      if (!existing) {
        const value = JSON.stringify(guideData, null, 2);
        localStorage.setItem(key, value);
        await saveToFirebase(key, value);
        synced++;
        console.log(`[syncDefaultGuides] 동기화됨: ${styleName} - ${stepType}`);
      }
    }
  }

  if (synced > 0) {
    showStatus(`✅ ${synced}개 기본 지침 동기화됨`);
    setTimeout(hideStatus, 2000);
  }

  return synced;
}

// 전역 노출
window.loadMasterGuide = loadMasterGuide;
window.saveMasterGuide = saveMasterGuide;
window.loadGuide = loadGuide;
window.saveGuide = saveGuide;
window.renderGuideTabs = renderGuideTabs;
window.syncDefaultGuides = syncDefaultGuides;
window.renderCategoryManageList = renderCategoryManageList;
window.deleteCategory = deleteCategory;
window.addCategory = addCategory;
window.renderStylesManageList = renderStylesManageList;
window.addStyle = addStyle;
window.deleteStyle = deleteStyle;
window.updateAdminStyleSelect = updateAdminStyleSelect;
window.bindAdminStyleSelect = bindAdminStyleSelect;

// ===== Step3 사용 코드 관리 (관리자용 UI) =====
// 참고: CODES_KEY와 step3Codes는 sermon-qa.js에서 정의됨

function renderAdminCodeList() {
  const tbody = document.getElementById('code-list-body');
  if (!tbody) return;

  // sermon-qa.js에서 정의된 step3Codes 사용
  const codes = window.step3Codes || {};
  const codeNames = Object.keys(codes);

  if (codeNames.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="padding: 1rem; text-align: center; color: #999;">생성된 코드가 없습니다.</td></tr>';
    return;
  }

  codeNames.sort((a, b) => {
    const dateA = new Date(codes[a].createdAt || 0);
    const dateB = new Date(codes[b].createdAt || 0);
    return dateB - dateA;
  });

  tbody.innerHTML = codeNames.map(code => {
    const info = codes[code];
    const isExhausted = info.remaining <= 0;
    const statusText = isExhausted ? '소진' : '활성';
    const statusColor = isExhausted ? '#e74c3c' : '#27ae60';
    const statusBg = isExhausted ? '#fde8e8' : '#e8f8e8';

    return `
      <tr style="border-bottom: 1px solid #f0f0f0;">
        <td style="padding: .5rem; font-family: monospace; font-weight: 600;">${code}</td>
        <td style="padding: .5rem; text-align: center;">${info.remaining}/${info.limit}</td>
        <td style="padding: .5rem; text-align: center;">
          <span style="background: ${statusBg}; color: ${statusColor}; padding: 4px 8px; border-radius: 4px; font-size: .75rem; font-weight: 600;">${statusText}</span>
        </td>
        <td style="padding: .5rem; text-align: center;">
          <button onclick="deleteCode('${code}')" style="padding: 4px 8px; background: #e74c3c; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: .75rem;">삭제</button>
        </td>
      </tr>
    `;
  }).join('');
}

// 관리자용 코드 목록 렌더링 전역 노출
window.renderAdminCodeList = renderAdminCodeList;
