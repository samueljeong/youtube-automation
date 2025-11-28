/**
 * Drama Lab - 유틸리티 함수 모듈
 * 화면 Step 기준: Step1(대본) → Step2(이미지) → Step3(TTS) → Step4(영상) → Step5(업로드)
 */

// ===== UI 유틸리티 =====
function showStatus(msg, type = 'info') {
  const bar = document.getElementById('status-bar');
  if (bar) {
    bar.textContent = msg;
    bar.className = 'status-bar show';
    if (type) bar.classList.add(`status-${type}`);
    bar.style.display = 'block';

    // 자동 숨김 (성공/정보는 3초, 에러/경고는 5초)
    const timeout = (type === 'error' || type === 'warning') ? 5000 : 3000;
    setTimeout(() => hideStatus(), timeout);
  }
}

function hideStatus() {
  const bar = document.getElementById('status-bar');
  if (bar) {
    bar.style.display = 'none';
  }
}

function showLoadingOverlay(text = 'AI 작업 중', subtext = '잠시만 기다려주세요...') {
  const overlay = document.getElementById('loading-overlay');
  const loadingText = overlay?.querySelector('.loading-text');
  const loadingSubtext = overlay?.querySelector('.loading-subtext');

  if (loadingText) loadingText.textContent = text;
  if (loadingSubtext) loadingSubtext.textContent = subtext;
  if (overlay) overlay.classList.add('show');
}

function hideLoadingOverlay() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) {
    overlay.classList.remove('show');
  }
}

function autoResize(el) {
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}

// ===== HTML 이스케이프 =====
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ===== 한글 → 영문 ID 자동 생성 =====
function koreanToId(korean) {
  const map = {
    '캐릭터': 'character', '스토리라인': 'storyline', '씬구성': 'scene',
    '대사': 'dialogue', '연출': 'direction', '대본': 'script',
    '설정': 'setup', '구성': 'structure', '분석': 'analysis',
    '감정': 'emotion', '톤': 'tone', '배경': 'background',
    '인물': 'person', '주제': 'topic', '플롯': 'plot'
  };

  for (const [ko, en] of Object.entries(map)) {
    if (korean.includes(ko)) return en;
  }

  return korean.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase() ||
         'step_' + Math.random().toString(36).substr(2, 6);
}

// ===== 카테고리/Step 레이블 =====
function getCategoryLabel(value) {
  const labels = { '10min': '10분', '20min': '20분', '30min': '30분', '2min': '2분', '5min': '5분' };
  return labels[value] || value;
}

function getStepName(stepId) {
  // 화면 기준 Step 이름 (step1=대본, step2=이미지, step3=TTS, step4=영상, step5=업로드)
  const names = {
    'step1': '대본 생성',
    'step2': '이미지 생성',
    'step3': 'TTS 음성합성',
    'step4': '영상 제작',
    'step5': '유튜브 업로드',
    // 구 버전 호환
    'character': '캐릭터', 'storyline': '스토리라인',
    'scene': '씬 구성', 'dialogue': '대사 작성'
  };
  return names[stepId] || stepId;
}

// ===== 비용 계산 =====
const modelPricing = {
  'anthropic/claude-sonnet-4': { input: 3.00, output: 15.00 },
  'anthropic/claude-3.5-sonnet': { input: 3.00, output: 15.00 },
  'anthropic/claude-sonnet-4.5': { input: 3.00, output: 15.00 },
  'openai/gpt-4o': { input: 2.50, output: 10.00 },
  'openai/gpt-4o-mini': { input: 0.15, output: 0.60 },
  'google/gemini-pro-1.5': { input: 1.25, output: 5.00 },
  'google/gemini-2.0-flash-001': { input: 0.10, output: 0.40 }
};

function calculateCost(modelId, inputTokens, outputTokens) {
  const pricing = modelPricing[modelId];
  if (!pricing) return null;

  const inputCost = (inputTokens / 1000000) * pricing.input;
  const outputCost = (outputTokens / 1000000) * pricing.output;
  const totalCostUSD = inputCost + outputCost;
  const totalCostKRW = Math.round(totalCostUSD * 1350);

  return { inputCost, outputCost, totalCostUSD, totalCostKRW };
}

// ===== 파일 다운로드 =====
function downloadFile(url, filename) {
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

// ===== 클립보드 복사 =====
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (err) {
    console.error('클립보드 복사 실패:', err);
    return false;
  }
}

function copyTextFromElement(element) {
  if (!element) return;
  const text = element.value || element.textContent;
  copyToClipboard(text).then(success => {
    if (success) {
      showStatus('✅ 복사 완료!');
      setTimeout(hideStatus, 2000);
    }
  });
}

// ===== 전역 노출 =====
window.DramaUtils = {
  showStatus,
  hideStatus,
  showLoading: showLoadingOverlay,
  hideLoading: hideLoadingOverlay,
  showLoadingOverlay,
  hideLoadingOverlay,
  autoResize,
  escapeHtml,
  koreanToId,
  getCategoryLabel,
  getStepName,
  calculateCost,
  modelPricing,
  downloadFile,
  blobToBase64,
  copyToClipboard,
  copyTextFromElement
};

// 전역 함수로도 노출 (기존 코드 호환)
window.showStatus = showStatus;
window.hideStatus = hideStatus;
window.showLoadingOverlay = showLoadingOverlay;
window.hideLoadingOverlay = hideLoadingOverlay;
window.autoResize = autoResize;
window.escapeHtml = escapeHtml;
window.getCategoryLabel = getCategoryLabel;
window.getStepName = getStepName;
window.calculateCost = calculateCost;
window.copyTextFromElement = copyTextFromElement;
