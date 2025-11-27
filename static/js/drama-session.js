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


// ===== 내보내기 (전역 접근용) =====
window.DramaSession = {
  // Q&A 대화 기록
  loadHistory: loadQAHistory,
  saveHistory: saveQAHistory,
  renderHistory: renderQAHistory,
  sendQuestion: sendQAQuestion,
  clearHistory: clearQAHistory
};

// 페이지 로드 시 히스토리 렌더링
document.addEventListener('DOMContentLoaded', () => {
  renderQAHistory();
  console.log('[DramaSession] Q&A 모듈 초기화 완료');
});
