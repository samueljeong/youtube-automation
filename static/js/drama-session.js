/**
 * Drama Lab - Q&A 대화 기록 저장 모듈
 * 분리됨: 2024-11-27
 *
 * 기존 workflowSession과 충돌하지 않도록 Q&A 기능만 포함
 */

// ===== Q&A 대화 기록 저장 시스템 =====
const QA_STORAGE_KEY = '_drama-qa-history';
const MAX_QA_HISTORY = 50; // 최대 저장 개수

// Q&A 히스토리 로드
function loadQAHistory() {
  try {
    const history = localStorage.getItem(QA_STORAGE_KEY);
    return history ? JSON.parse(history) : [];
  } catch (e) {
    console.error('[Q&A] 히스토리 로드 실패:', e);
    return [];
  }
}

// Q&A 히스토리 저장
function saveQAHistory(history) {
  try {
    // 최대 개수 제한
    if (history.length > MAX_QA_HISTORY) {
      history = history.slice(-MAX_QA_HISTORY);
    }
    localStorage.setItem(QA_STORAGE_KEY, JSON.stringify(history));
  } catch (e) {
    console.error('[Q&A] 히스토리 저장 실패:', e);
  }
}

// Q&A 히스토리 렌더링
function renderQAHistory() {
  const qaHistory = document.getElementById('qa-history');
  if (!qaHistory) return;

  const history = loadQAHistory();

  if (history.length === 0) {
    qaHistory.innerHTML = '<div class="qa-empty-state">아직 대화가 없습니다.<br>대본이나 작업에 대해 궁금한 점을 물어보세요.</div>';
    return;
  }

  qaHistory.innerHTML = history.map(item => {
    const userMsg = `
      <div class="qa-message user">
        <div class="qa-message-label">질문</div>
        <div class="qa-message-content">${escapeHtmlForQA(item.question)}</div>
      </div>
    `;
    const assistantMsg = `
      <div class="qa-message assistant">
        <div class="qa-message-label">답변</div>
        <div class="qa-message-content">${escapeHtmlForQA(item.answer)}</div>
      </div>
    `;
    return userMsg + assistantMsg;
  }).join('');

  // 스크롤을 맨 아래로
  qaHistory.scrollTop = qaHistory.scrollHeight;
}

// HTML 이스케이프 (Q&A용)
function escapeHtmlForQA(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Q&A 질문 전송
async function sendQAQuestion() {
  const input = document.getElementById('qa-input');
  const question = input?.value?.trim();

  if (!question) {
    alert('질문을 입력해주세요.');
    return;
  }

  // 현재 대본/컨텍스트 수집
  const step3Result = document.getElementById('step3-result')?.value || '';

  // 세션 컨텍스트 (기존 workflowSession 사용)
  let sessionContext = '';
  if (typeof workflowSession !== 'undefined') {
    sessionContext = `【 현재 작업 세션 정보 】
- 카테고리: ${workflowSession.category || '10min'}
- 콘텐츠 유형: ${workflowSession.contentType === 'testimony' ? '간증' : '드라마'}
- 제목: ${workflowSession.metadata?.title || '(미생성)'}`;
  }

  // UI 업데이트: 질문 추가 (로딩 상태)
  let history = loadQAHistory();
  history.push({
    id: Date.now(),
    timestamp: new Date().toISOString(),
    question: question,
    answer: '답변을 생성 중입니다...'
  });
  saveQAHistory(history);
  renderQAHistory();

  // 입력창 비우기
  input.value = '';

  // 로딩 표시
  if (typeof showLoadingOverlay === 'function') {
    showLoadingOverlay('AI 답변 생성 중', '잠시만 기다려주세요...');
  }

  try {
    if (typeof showStatus === 'function') {
      showStatus('🤔 답변 생성 중...');
    }

    const response = await fetch('/api/drama/qa', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        question: question,
        script: step3Result,
        sessionContext: sessionContext,
        history: history.slice(-5) // 최근 5개 대화만 컨텍스트로
      })
    });

    const result = await response.json();

    if (typeof hideLoadingOverlay === 'function') {
      hideLoadingOverlay();
    }
    if (typeof hideStatus === 'function') {
      hideStatus();
    }

    if (result.ok) {
      // 마지막 항목의 답변 업데이트
      history = loadQAHistory();
      if (history.length > 0) {
        history[history.length - 1].answer = result.answer;
        saveQAHistory(history);
        renderQAHistory();
      }
    } else {
      alert('답변 생성 실패: ' + (result.error || '알 수 없는 오류'));
      // 실패한 항목 제거
      history = loadQAHistory();
      history.pop();
      saveQAHistory(history);
      renderQAHistory();
    }
  } catch (err) {
    if (typeof hideLoadingOverlay === 'function') {
      hideLoadingOverlay();
    }
    if (typeof hideStatus === 'function') {
      hideStatus();
    }
    console.error('[Q&A] 요청 실패:', err);
    alert('답변 생성 중 오류가 발생했습니다.');
    // 실패한 항목 제거
    history = loadQAHistory();
    history.pop();
    saveQAHistory(history);
    renderQAHistory();
  }
}

// Q&A 히스토리 초기화
function clearQAHistory() {
  if (confirm('대화 기록을 모두 삭제하시겠습니까?')) {
    localStorage.removeItem(QA_STORAGE_KEY);
    renderQAHistory();
    if (typeof showStatus === 'function') {
      showStatus('🗑️ 대화 기록이 삭제되었습니다.');
      setTimeout(() => {
        if (typeof hideStatus === 'function') hideStatus();
      }, 2000);
    }
  }
}


// ===== Step 데이터 저장 시스템 =====
const STEP_STORAGE_KEY = '_drama-step-data';

// ★ 메모리 기반 저장소 (B 방식) - Base64 데이터 손실 방지
// localStorage는 메타데이터만, 실제 데이터는 메모리에
window._dramaMemoryStore = window._dramaMemoryStore || {};

function getStepData(stepId) {
  // 1. 메모리에서 먼저 찾기 (Base64 포함 완전한 데이터)
  if (window._dramaMemoryStore[stepId]) {
    console.log(`[Session] ${stepId} 메모리에서 로드`);
    return window._dramaMemoryStore[stepId];
  }

  // 2. 메모리에 없으면 localStorage에서 (새로고침 후 복구용)
  try {
    const data = localStorage.getItem(STEP_STORAGE_KEY);
    if (!data) return null;
    const parsed = JSON.parse(data);
    return parsed[stepId] || null;
  } catch (e) {
    console.error('[Session] Step 데이터 로드 실패:', e);
    return null;
  }
}

// 저장 시 제외할 대용량 필드 목록
const EXCLUDED_FIELDS = ['fullScript', 'rawJson', 'debug', 'audioBase64', 'imageBase64', 'base64Data', 'raw_response', 'rawContent', 'originalContent'];

// 대용량 필드를 제거하고 데이터 경량화
// ⚠️ 예외: 'imageUrl', 'audioUrl' 등 필수 URL 필드는 보존 (단, 실제 URL만)
const PRESERVE_URL_FIELDS = ['imageUrl', 'audioUrl', 'videoUrl'];

// 최대 저장 가능 크기 (500KB per step)
const MAX_STEP_SIZE_KB = 500;

function sanitizeForStorage(data, fieldName = '', depth = 0) {
  if (!data || typeof data !== 'object') return data;

  // 배열인 경우
  if (Array.isArray(data)) {
    // images, audios 배열은 URL만 추출하여 경량화
    if (fieldName === 'images' || fieldName === 'audios') {
      return data.map(item => {
        if (typeof item === 'string') {
          // Base64 제외, URL만 보존
          if (item.startsWith('data:') || item.length > 1000) {
            console.log(`[Session] ${fieldName} 배열에서 Base64 제외`);
            return null;
          }
          return item;
        }
        if (typeof item === 'object' && item !== null) {
          // 객체에서 URL만 추출
          const urlItem = {};
          if (item.id) urlItem.id = item.id;
          if (item.audioUrl && !item.audioUrl.startsWith('data:')) urlItem.audioUrl = item.audioUrl;
          if (item.imageUrl && !item.imageUrl.startsWith('data:')) urlItem.imageUrl = item.imageUrl;
          if (item.url && !item.url.startsWith('data:')) urlItem.url = item.url;
          if (item.duration) urlItem.duration = item.duration;
          if (item.text) urlItem.text = item.text.substring(0, 100);
          return Object.keys(urlItem).length > 0 ? urlItem : null;
        }
        return item;
      }).filter(Boolean);
    }
    return data.map(item => sanitizeForStorage(item, fieldName, depth + 1));
  }

  // 객체인 경우 대용량 필드 제거
  const sanitized = {};
  for (const key of Object.keys(data)) {
    // 제외 필드 스킵
    if (EXCLUDED_FIELDS.includes(key)) {
      console.log(`[Session] 대용량 필드 제외: ${key}`);
      continue;
    }

    const value = data[key];

    // null/undefined 스킵
    if (value === null || value === undefined) continue;

    // URL 보존 필드는 URL만 유지 (Base64 제외)
    if (PRESERVE_URL_FIELDS.includes(key)) {
      if (typeof value === 'string' && !value.startsWith('data:') && value.length < 500) {
        sanitized[key] = value;
      }
      continue;
    }

    // 문자열 처리
    if (typeof value === 'string') {
      // Base64 데이터는 완전 제외
      if (value.startsWith('data:') || (value.length > 1000 && value.match(/^[A-Za-z0-9+/=]{1000,}$/))) {
        console.log(`[Session] Base64 데이터 제외: ${key} (${(value.length/1024).toFixed(1)}KB)`);
        continue;
      }
      // content 필드는 5KB로 제한 (대본 내용)
      if (key === 'content' && value.length > 5000) {
        sanitized[key] = value.substring(0, 5000) + '... (truncated for storage)';
        console.log(`[Session] content 필드 축소: ${(value.length/1024).toFixed(1)}KB -> 5KB`);
        continue;
      }
      // 일반 문자열은 2KB로 제한
      if (value.length > 2000) {
        sanitized[key] = value.substring(0, 2000) + '...';
        continue;
      }
      sanitized[key] = value;
    } else if (typeof value === 'object') {
      // 깊이 제한 (5단계까지만)
      if (depth > 5) {
        console.log(`[Session] 깊이 제한 초과: ${key}`);
        continue;
      }
      // 중첩 객체 재귀 처리
      sanitized[key] = sanitizeForStorage(value, key, depth + 1);
    } else {
      // 숫자, 불린 등
      sanitized[key] = value;
    }
  }
  return sanitized;
}

// 데이터 크기 측정 (KB)
function getDataSizeKB(data) {
  try {
    return JSON.stringify(data).length / 1024;
  } catch (e) {
    return 0;
  }
}

function setStepData(stepId, data) {
  // ★ 1. 메모리에 원본 데이터 저장 (Base64 포함 - 손실 없음)
  window._dramaMemoryStore[stepId] = data;
  console.log(`[Session] ${stepId} 메모리에 저장 완료`);

  // 2. localStorage에는 경량화 버전 저장 (새로고침 복구용)
  try {
    // 데이터 경량화
    const sanitizedData = sanitizeForStorage(data);
    const stepSizeKB = getDataSizeKB(sanitizedData);
    console.log(`[Session] ${stepId} localStorage용 경량화: ${stepSizeKB.toFixed(1)}KB`);

    // 2. 크기 제한 초과 시 추가 축소
    let finalData = sanitizedData;
    if (stepSizeKB > MAX_STEP_SIZE_KB) {
      console.warn(`[Session] ${stepId} 크기 초과 (${stepSizeKB.toFixed(1)}KB > ${MAX_STEP_SIZE_KB}KB), 추가 축소`);
      finalData = aggressiveSanitize(sanitizedData);
      console.log(`[Session] 추가 축소 후: ${getDataSizeKB(finalData).toFixed(1)}KB`);
    }

    // 3. 기존 데이터 로드
    const existing = localStorage.getItem(STEP_STORAGE_KEY);
    const parsed = existing ? JSON.parse(existing) : {};
    parsed[stepId] = finalData;

    const jsonString = JSON.stringify(parsed);
    const totalSizeKB = jsonString.length / 1024;
    console.log(`[Session] 저장 시도: ${stepId} (전체 ${totalSizeKB.toFixed(1)}KB)`);

    // 4. 전체 크기가 너무 크면 오래된 step 제거
    if (totalSizeKB > 2000) {
      console.warn('[Session] 전체 크기 초과, 오래된 스텝 제거');
      // 현재 스텝 번호 추출 (step1, step2, ...)
      const currentStepNum = parseInt(stepId.replace('step', '')) || 0;
      // 2단계 이전 데이터 삭제
      for (let i = 1; i < currentStepNum - 1; i++) {
        delete parsed[`step${i}`];
        console.log(`[Session] step${i} 제거`);
      }
    }

    localStorage.setItem(STEP_STORAGE_KEY, JSON.stringify(parsed));
    console.log(`[Session] 저장 성공: ${stepId}`);
  } catch (e) {
    // QuotaExceededError 처리
    if (e.name === 'QuotaExceededError' || e.message.includes('quota')) {
      console.warn('[Session] localStorage 용량 초과, 최소 데이터만 저장...');

      try {
        // localStorage 전체 정리
        localStorage.removeItem(STEP_STORAGE_KEY);
        localStorage.removeItem(QA_STORAGE_KEY);

        // 최소 필수 데이터만 저장
        const minimalData = aggressiveSanitize(data);
        const newData = { [stepId]: minimalData };
        localStorage.setItem(STEP_STORAGE_KEY, JSON.stringify(newData));
        console.log('[Session] 최소 데이터로 저장 성공');
      } catch (e2) {
        console.error('[Session] 저장 완전 실패, 메모리에만 유지:', e2);
        // 메모리에만 저장 (페이지 리로드 시 손실)
        window._dramaStepData = window._dramaStepData || {};
        window._dramaStepData[stepId] = data;
      }
    } else {
      console.error('[Session] Step 데이터 저장 실패:', e);
    }
  }
}

// 극단적 축소 (최소 필수 정보만)
function aggressiveSanitize(data) {
  if (!data || typeof data !== 'object') return data;

  const minimal = {};

  // 필수 필드만 보존
  const essentialFields = ['id', 'title', 'audioUrl', 'imageUrl', 'videoUrl', 'duration', 'status', 'config'];

  for (const key of Object.keys(data)) {
    const value = data[key];

    if (essentialFields.includes(key)) {
      if (typeof value === 'string' && value.length < 500) {
        minimal[key] = value;
      } else if (typeof value === 'number' || typeof value === 'boolean') {
        minimal[key] = value;
      } else if (typeof value === 'object' && !Array.isArray(value)) {
        minimal[key] = value;
      }
    }

    // audios 배열은 URL만 추출
    if (key === 'audios' && Array.isArray(value)) {
      minimal.audios = value.map(a => ({
        id: a.id,
        audioUrl: a.audioUrl,
        duration: a.duration
      })).filter(a => a.audioUrl);
    }

    // images 배열은 URL만 추출
    if (key === 'images' && Array.isArray(value)) {
      minimal.images = value.map(img => {
        if (typeof img === 'string' && !img.startsWith('data:')) return img;
        if (img.imageUrl && !img.imageUrl.startsWith('data:')) return img.imageUrl;
        if (img.url && !img.url.startsWith('data:')) return img.url;
        return null;
      }).filter(Boolean);
    }
  }

  return minimal;
}

function clearStepData() {
  localStorage.removeItem(STEP_STORAGE_KEY);
}

function getAllStepData() {
  try {
    const data = localStorage.getItem(STEP_STORAGE_KEY);
    return data ? JSON.parse(data) : {};
  } catch (e) {
    return {};
  }
}

// ===== 내보내기 (전역 접근용) =====
window.DramaSession = {
  // Q&A 대화 기록
  loadHistory: loadQAHistory,
  saveHistory: saveQAHistory,
  renderHistory: renderQAHistory,
  sendQuestion: sendQAQuestion,
  clearHistory: clearQAHistory,

  // Step 데이터 저장
  getStepData,
  setStepData,
  clearStepData,
  getAllStepData
};

// 페이지 로드 시 히스토리 렌더링
document.addEventListener('DOMContentLoaded', () => {
  renderQAHistory();
  console.log('[DramaSession] Q&A 모듈 초기화 완료');
});
