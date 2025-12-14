/**
 * sermon-main.js
 * 전역 변수, 기본 설정, 초기화
 */

// ===== 패스워드 설정 =====
const GUIDE_PASSWORD = '5555';
const GPT_PRO_PASSWORD = '6039';
const MANAGE_PASSWORD = '6039';

// ===== 전역 변수 =====
window.guideUnlocked = false;
window.gptProUnlocked = false;
window.manageUnlocked = false;
window.pendingManageAction = null; // 'categories' or 'styles'
window.currentCategory = 'general';
window.currentStyleId = '';
window.currentGuideStep = '';
window.stepResults = {};
window.titleOptions = []; // 제목 후보 저장
window.selectedTitle = ''; // 선택된 제목 저장

// ===== 기본 설정 =====
window.config = {
  categories: [
    {value: "category1", label: "묵상메시지 작성"},
    {value: "general", label: "일반 설교"},
    {value: "series", label: "시리즈 설교"},
    {value: "education", label: "교육"},
    {value: "lecture", label: "강의"},
    {value: "design_helper", label: "🎨 디자인 도우미"}
  ],
  categorySettings: {
    general: {
      masterGuide: "",
      styles: [
        {
          id: "three_points",
          name: "3대지",
          description: "3대지 설교",
          steps: [
            {id: "analysis", name: "본문 분석", order: 1, stepType: "step1"},
            {id: "structure", name: "구조 설계", order: 2, stepType: "step2"}
          ]
        },
        {
          id: "topical",
          name: "주제설교",
          description: "주제 중심",
          steps: [
            {id: "analysis", name: "본문 분석", order: 1, stepType: "step1"},
            {id: "structure", name: "구조 설계", order: 2, stepType: "step2"}
          ]
        },
        {
          id: "expository",
          name: "강해설교",
          description: "본론 중심",
          steps: [
            {id: "analysis", name: "본문 분석", order: 1, stepType: "step1"},
            {id: "structure", name: "구조 설계", order: 2, stepType: "step2"}
          ]
        }
      ]
    },
    series: {
      masterGuide: "",
      styles: [
        {
          id: "series_continuous",
          name: "연속강해",
          description: "시리즈형 강해",
          steps: [
            {id: "analysis", name: "본문 분석", order: 1, stepType: "step1"},
            {id: "structure", name: "구조 설계", order: 2, stepType: "step2"}
          ]
        }
      ]
    },
    education: {
      masterGuide: "",
      styles: []
    },
    lecture: {
      masterGuide: "",
      styles: []
    }
  }
};

// ===== Step3 기본 지침 =====
const DEFAULT_STEP3_PROMPT = `당신은 한국어 설교 전문가입니다.
step1,2 자료는 참고용으로만 활용하고 문장은 처음부터 새로 구성하며,
묵직하고 명료한 어조로 신학적 통찰과 실제적 적용을 균형 있게 제시하세요.
마크다운 기호 대신 순수 텍스트만 사용합니다.

Step2의 설교 구조를 반드시 따라 작성하세요:
- Step2에서 제시한 구조를 그대로 사용
- Step2의 대지(포인트) 구성을 유지
- 각 섹션의 핵심 메시지를 확장하여 풍성하게 작성

⚠️ 중요: 충분히 길고 상세하며 풍성한 내용으로 작성해주세요.

【공통 요청 사항】
1. Step2의 설교 구조(서론, 본론, 결론)를 반드시 따라 작성하세요.
2. Step2의 대지(포인트) 구성을 유지하고 각 섹션의 핵심 메시지를 확장하세요.
3. 역사적 배경, 신학적 통찰, 실제 적용을 균형 있게 제시하세요.
4. 관련 성경구절을 적절히 인용하세요.
5. 가독성을 위해 각 섹션 사이에 빈 줄을 넣으세요.
6. 마크다운, 불릿 기호 대신 순수 텍스트 단락을 사용하세요.
7. 충분히 길고 상세하며 풍성한 내용으로 작성해주세요.

【서론 작성 시】
- Step2에서 아이스브레이킹이 있다면 반드시 서론 도입부에 포함하세요.
- 청중의 관심을 끌 수 있는 도입으로 시작하세요.

【결론 작성 시】
- 실천 사항은 간결하게 1-2개만 제시하세요.
- 기도제목도 간결하게 1-2개만 제시하세요.
- 마무리 기도문은 짧게 작성하세요.`;

window.DEFAULT_STEP3_PROMPT = DEFAULT_STEP3_PROMPT;

// ===== 모델 설정 관리 =====
function getModelSettings(category) {
  const settings = window.config.categorySettings[category];
  if (!settings) return null;

  if (!settings.modelSettings) {
    settings.modelSettings = {
      step1: 'gpt-4o',
      step2: 'gpt-4o',
      gptPro: 'gpt-5',
      step3MaxTokens: 16000,
      step3Prompt: DEFAULT_STEP3_PROMPT
    };
  }
  // 기존 설정에 새 필드가 없으면 추가
  if (!settings.modelSettings.step3MaxTokens) {
    settings.modelSettings.step3MaxTokens = 16000;
  }
  if (!settings.modelSettings.step3Prompt) {
    settings.modelSettings.step3Prompt = DEFAULT_STEP3_PROMPT;
  }
  return settings.modelSettings;
}

function loadModelSettings() {
  const modelSettings = getModelSettings(window.currentCategory);
  if (!modelSettings) return;

  const step1Select = document.getElementById('model-step1');
  const step2Select = document.getElementById('model-step2');
  const gptProSelect = document.getElementById('model-gpt-pro');
  const step3MaxTokensInput = document.getElementById('step3-max-tokens');

  if (step1Select) step1Select.value = modelSettings.step1;
  if (step2Select) step2Select.value = modelSettings.step2;
  if (gptProSelect) gptProSelect.value = modelSettings.gptPro;
  if (step3MaxTokensInput) step3MaxTokensInput.value = modelSettings.step3MaxTokens;
}

async function saveModelSettings() {
  const step1Select = document.getElementById('model-step1');
  const step2Select = document.getElementById('model-step2');
  const gptProSelect = document.getElementById('model-gpt-pro');
  const step3MaxTokensInput = document.getElementById('step3-max-tokens');

  const modelSettings = getModelSettings(window.currentCategory);
  if (!modelSettings) return;

  modelSettings.step1 = step1Select ? step1Select.value : 'gpt-4o';
  modelSettings.step2 = step2Select ? step2Select.value : 'gpt-4o';
  modelSettings.gptPro = gptProSelect ? gptProSelect.value : 'gpt-5';
  modelSettings.step3MaxTokens = step3MaxTokensInput ? parseInt(step3MaxTokensInput.value) || 16000 : 16000;

  await saveConfig();
}

// ===== 스타일별 토큰 설정 =====
let styleTokensExpanded = false;

function toggleStyleTokens() {
  styleTokensExpanded = !styleTokensExpanded;
  const container = document.getElementById('style-tokens-container');
  const toggle = document.getElementById('style-tokens-toggle');
  if (container) {
    container.style.display = styleTokensExpanded ? 'block' : 'none';
  }
  if (toggle) {
    toggle.textContent = styleTokensExpanded ? '▲ 접기' : '▼ 펼치기';
  }
  if (styleTokensExpanded) {
    renderStyleTokensList();
  }
}

function renderStyleTokensList() {
  const container = document.getElementById('style-tokens-list');
  if (!container) return;

  const catSettings = window.config.categorySettings[window.currentCategory];
  if (!catSettings || !catSettings.styles || catSettings.styles.length === 0) {
    container.innerHTML = '<div style="color: #999; font-size: .8rem; padding: .5rem;">설교 스타일이 없습니다. 먼저 스타일을 추가해주세요.</div>';
    return;
  }

  // styleTokens 초기화 (없으면)
  if (!catSettings.styleTokens) {
    catSettings.styleTokens = {};
  }

  const html = catSettings.styles.map((style, idx) => {
    const tokenValue = catSettings.styleTokens[style.id] || '';
    return `
      <div style="display: flex; align-items: center; gap: .5rem; padding: .4rem 0; border-bottom: 1px solid #f0f0f0;">
        <span style="flex: 1; font-size: .85rem; color: #333;">${style.name}</span>
        <input type="number"
          id="style-token-${style.id}"
          value="${tokenValue}"
          placeholder="기본값"
          min="1000" max="32000" step="1000"
          onchange="saveStyleToken('${style.id}', this.value)"
          style="width: 80px; padding: .3rem; border-radius: 4px; border: 1px solid #ddd; font-size: .8rem; text-align: center;">
        <span style="font-size: .7rem; color: #999; width: 30px;">토큰</span>
      </div>
    `;
  }).join('');

  container.innerHTML = html;
}

async function saveStyleToken(styleId, value) {
  const catSettings = window.config.categorySettings[window.currentCategory];
  if (!catSettings) return;

  if (!catSettings.styleTokens) {
    catSettings.styleTokens = {};
  }

  if (value && parseInt(value) > 0) {
    catSettings.styleTokens[styleId] = parseInt(value);
  } else {
    delete catSettings.styleTokens[styleId]; // 비워두면 삭제 (기본값 사용)
  }

  await saveConfig();
  showStatus('✅ 스타일 토큰 저장됨');
  setTimeout(hideStatus, 1500);
}

// 스타일 추가/삭제/이름변경 시 토큰 목록 동기화
function syncStyleTokens() {
  const catSettings = window.config.categorySettings[window.currentCategory];
  if (!catSettings || !catSettings.styles || !catSettings.styleTokens) return;

  // 존재하지 않는 스타일의 토큰 설정 제거
  const styleIds = catSettings.styles.map(s => s.id);
  Object.keys(catSettings.styleTokens).forEach(tokenStyleId => {
    if (!styleIds.includes(tokenStyleId)) {
      delete catSettings.styleTokens[tokenStyleId];
    }
  });
}

// ===== 제목 관리 함수 =====
function getSelectedTitle() {
  // 수동 입력 제목이 있으면 우선
  const manualTitle = document.getElementById('manual-title');
  if (manualTitle && manualTitle.value.trim()) {
    return manualTitle.value.trim();
  }
  // 그렇지 않으면 선택된 제목 반환
  return window.selectedTitle;
}

function displayTitleOptions(titles) {
  window.titleOptions = titles;
  const container = document.getElementById('title-options');
  const box = document.getElementById('title-selection-box');

  if (!container || !box) return;

  if (titles.length >= 3) {
    container.innerHTML = titles.slice(0, 3).map((title, idx) => `
      <label class="title-option-label">
        <input type="radio" name="selectedTitle" value="${idx}" style="margin-right: .5rem;" ${idx === 0 ? 'checked' : ''}>
        <span>${title}</span>
      </label>
    `).join('');

    // 첫 번째 제목을 기본 선택
    window.selectedTitle = titles[0];

    // 라디오 버튼 변경 이벤트
    container.querySelectorAll('input[type="radio"]').forEach(radio => {
      radio.addEventListener('change', (e) => {
        window.selectedTitle = window.titleOptions[parseInt(e.target.value)];
        console.log('선택된 제목:', window.selectedTitle);
      });
    });

    box.style.display = 'block';
  }
}

// 전역 노출
window.GUIDE_PASSWORD = GUIDE_PASSWORD;
window.GPT_PRO_PASSWORD = GPT_PRO_PASSWORD;
window.MANAGE_PASSWORD = MANAGE_PASSWORD;
window.getModelSettings = getModelSettings;
window.loadModelSettings = loadModelSettings;
window.saveModelSettings = saveModelSettings;
window.toggleStyleTokens = toggleStyleTokens;
window.renderStyleTokensList = renderStyleTokensList;
window.saveStyleToken = saveStyleToken;
window.syncStyleTokens = syncStyleTokens;
window.getSelectedTitle = getSelectedTitle;
window.displayTitleOptions = displayTitleOptions;
