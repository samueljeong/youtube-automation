/**
 * sermon-qa.js
 * Q&A, 챗봇, 본문 추천, Step3 코드 관리 기능
 *
 * 주요 함수:
 * - loadQAHistory(), saveQAHistory(), renderQAHistory()
 * - sendQAQuestion()
 * - searchScripture() - 본문 추천
 * - addSermonChatMessage(), sendSermonChatMessage() - 챗봇
 * - loadStep3Codes(), createNewCode(), verifyCode() - Step3 코드 관리
 *
 * 이 파일은 sermon.html의 Q&A 관련 코드를 모듈화한 것입니다.
 */

// ===== Q&A 기능 =====
const QA_STORAGE_KEY = 'sermon-qa-history';

function loadQAHistory() {
  try {
    const history = sessionStorage.getItem(QA_STORAGE_KEY);
    return history ? JSON.parse(history) : [];
  } catch (e) {
    console.error('Q&A 히스토리 로드 실패:', e);
    return [];
  }
}

function saveQAHistory(history) {
  try {
    sessionStorage.setItem(QA_STORAGE_KEY, JSON.stringify(history));
  } catch (e) {
    console.error('Q&A 히스토리 저장 실패:', e);
  }
}

function renderQAHistory() {
  const qaHistory = document.getElementById('qa-history');
  if (!qaHistory) return;

  const history = loadQAHistory();

  if (history.length === 0) {
    qaHistory.innerHTML = '<div class="qa-empty-state">아직 질문이 없습니다.<br>처리 단계 결과나 본문에 대해 궁금한 점을 물어보세요.</div>';
    return;
  }

  qaHistory.innerHTML = history.map(item => {
    const userMsg = `
      <div class="qa-message user">
        <div class="qa-message-label">질문</div>
        <div class="qa-message-content">${escapeHtml(item.question)}</div>
      </div>
    `;
    const assistantMsg = `
      <div class="qa-message assistant">
        <div class="qa-message-label">답변</div>
        <div class="qa-message-content">${escapeHtml(item.answer)}</div>
      </div>
    `;
    return userMsg + assistantMsg;
  }).join('');

  // 스크롤을 맨 아래로
  qaHistory.scrollTop = qaHistory.scrollHeight;
}

async function sendQAQuestion() {
  const input = document.getElementById('qa-input');
  const question = input.value.trim();

  if (!question) {
    alert('질문을 입력해주세요.');
    return;
  }

  const reference = document.getElementById('sermon-ref').value.trim();

  // 현재 처리 단계 결과들 수집
  const contextStepResults = {};
  for (const [stepId, stepData] of Object.entries(window.stepResults)) {
    if (stepData) {
      const result = typeof stepData === 'string' ? stepData : (stepData.result || '');
      const name = typeof stepData === 'string' ? getStepName(stepId) : (stepData.name || stepId);
      if (result) {
        contextStepResults[stepId] = {
          name: name,
          result: result
        };
      }
    }
  }

  // UI 업데이트: 질문 추가
  const history = loadQAHistory();
  history.push({
    question: question,
    answer: '답변을 생성 중입니다...'
  });
  saveQAHistory(history);
  renderQAHistory();

  // 입력창 비우기
  input.value = '';

  showGptLoading();

  try {
    showStatus('🤔 답변 생성 중...');

    const response = await fetch('/api/sermon/qa', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        question: question,
        reference: reference,
        stepResults: contextStepResults
      })
    });

    const result = await response.json();
    hideGptLoading();
    hideStatus();

    if (result.ok) {
      history[history.length - 1].answer = result.answer;
      saveQAHistory(history);
      renderQAHistory();
    } else {
      alert('답변 생성 실패: ' + (result.error || '알 수 없는 오류'));
      history.pop();
      saveQAHistory(history);
      renderQAHistory();
    }
  } catch (err) {
    hideGptLoading();
    hideStatus();
    console.error('Q&A 요청 실패:', err);
    alert('답변 생성 중 오류가 발생했습니다.');
    history.pop();
    saveQAHistory(history);
    renderQAHistory();
  }
}

// ===== 본문 추천 기능 =====
async function searchScripture() {
  const searchInput = document.getElementById('scripture-search');
  const recommendationsDiv = document.getElementById('scripture-recommendations');
  const scriptureList = document.getElementById('scripture-list');

  const query = searchInput.value.trim();
  if (!query) {
    alert('상황을 입력해주세요. (예: 이사심방, 구국기도회)');
    return;
  }

  showStatus('📖 본문 추천 중...');
  showGptLoading();

  try {
    const response = await fetch('/api/sermon/recommend-scripture', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ query: query })
    });

    const data = await response.json();
    hideGptLoading();

    if (data.ok && data.recommendations) {
      scriptureList.innerHTML = data.recommendations.map((rec, idx) => `
        <div class="scripture-item" data-scripture="${rec.scripture}" style="background: #f8f9fa; padding: .75rem; border-radius: 8px; cursor: pointer; border: 2px solid transparent; transition: all 0.2s; margin-bottom: .5rem;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: .4rem;">
            <div style="font-weight: 700; color: #333; font-size: .95rem;">${idx + 1}. ${rec.scripture}</div>
            ${rec.title ? `<span style="font-size: .75rem; background: #667eea; color: white; padding: .15rem .4rem; border-radius: 4px;">${rec.title}</span>` : ''}
          </div>
          <div style="font-size: .85rem; color: #666; line-height: 1.4;">${rec.reason || ''}</div>
        </div>
      `).join('');

      // 클릭 이벤트 추가
      scriptureList.querySelectorAll('.scripture-item').forEach(item => {
        item.addEventListener('click', () => {
          const scripture = item.dataset.scripture;
          document.getElementById('sermon-ref').value = scripture;

          // 검색 키워드도 저장
          const searchKeyword = document.getElementById('scripture-search').value.trim();
          if (searchKeyword) {
            document.getElementById('special-notes').value = searchKeyword;
          }

          // 선택 표시
          scriptureList.querySelectorAll('.scripture-item').forEach(i => {
            i.style.border = '2px solid transparent';
          });
          item.style.border = '2px solid #667eea';

          showStatus('✅ 본문이 선택되었습니다!');
          setTimeout(hideStatus, 1500);
        });
      });

      recommendationsDiv.style.display = 'block';
      showStatus('✅ 추천 완료!');
      setTimeout(hideStatus, 1500);
    } else {
      alert('추천 실패: ' + (data.error || '알 수 없는 오류'));
      hideStatus();
    }
  } catch (err) {
    hideGptLoading();
    hideStatus();
    alert('네트워크 오류: ' + err.message);
  }
}

// ===== 설교 챗봇 =====
let lastSermonError = null;

function addSermonChatMessage(type, content) {
  const sermonChatMessages = document.getElementById('sermon-chat-messages');
  if (!sermonChatMessages) return;

  // 환영 메시지 제거
  const welcome = sermonChatMessages.querySelector('.chat-welcome');
  if (welcome) welcome.remove();

  const msgDiv = document.createElement('div');
  msgDiv.style.cssText = `
    margin-bottom: .75rem; padding: .6rem .8rem; border-radius: 8px;
    ${type === 'user'
      ? 'background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; margin-left: 20%; text-align: right;'
      : 'background: white; color: #333; margin-right: 20%; box-shadow: 0 1px 3px rgba(0,0,0,0.1);'}
  `;
  msgDiv.innerHTML = `<div style="font-size: .85rem; line-height: 1.5; white-space: pre-wrap;">${content}</div>`;
  sermonChatMessages.appendChild(msgDiv);
  sermonChatMessages.scrollTop = sermonChatMessages.scrollHeight;
}

function collectSermonContext() {
  const context = {};

  // Step 결과들 (window.stepResults에서 가져오기)
  if (window.stepResults) {
    const steps = typeof getCurrentSteps === 'function' ? getCurrentSteps() : [];
    steps.forEach(step => {
      const stepType = step.stepType || 'step1';
      if (window.stepResults[step.id]) {
        if (stepType === 'step1') {
          context.step1Result = (context.step1Result || '') + window.stepResults[step.id] + '\n';
        } else if (stepType === 'step2') {
          context.step2Result = (context.step2Result || '') + window.stepResults[step.id] + '\n';
        }
      }
    });
  }

  // 성경 본문
  const bibleRef = document.getElementById('sermon-ref')?.value;
  if (bibleRef) context.bibleRef = bibleRef;

  // 설교 스타일
  if (typeof getCurrentStyle === 'function') {
    const style = getCurrentStyle();
    if (style) context.sermonStyle = style.name;
  }

  // 마지막 오류
  if (lastSermonError) context.lastError = lastSermonError;

  return context;
}

async function sendSermonChatMessage() {
  const sermonChatInput = document.getElementById('sermon-chat-input');
  const sermonChatMessages = document.getElementById('sermon-chat-messages');
  if (!sermonChatInput || !sermonChatMessages) return;

  const question = sermonChatInput.value.trim();
  if (!question) return;

  // 사용자 메시지 추가
  addSermonChatMessage('user', question);
  sermonChatInput.value = '';

  // 선택된 모델 가져오기
  const modelSelect = document.getElementById('sermon-chat-model');
  const selectedModel = modelSelect ? modelSelect.value : 'gpt-4o-mini';

  // 로딩 표시
  const loadingDiv = document.createElement('div');
  loadingDiv.id = 'sermon-chat-loading';
  loadingDiv.style.cssText = 'margin-bottom: .75rem; padding: .6rem .8rem; background: white; border-radius: 8px; margin-right: 20%; box-shadow: 0 1px 3px rgba(0,0,0,0.1);';
  loadingDiv.innerHTML = `<div style="font-size: .85rem; color: #999;">🤔 ${selectedModel}로 생각 중...</div>`;
  sermonChatMessages.appendChild(loadingDiv);
  sermonChatMessages.scrollTop = sermonChatMessages.scrollHeight;

  try {
    const response = await fetch('/api/sermon/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        question: question,
        context: collectSermonContext(),
        model: selectedModel
      })
    });

    const data = await response.json();
    loadingDiv.remove();

    if (data.ok) {
      addSermonChatMessage('ai', data.answer);
    } else {
      addSermonChatMessage('ai', '❌ 오류: ' + data.error);
    }
  } catch (err) {
    loadingDiv.remove();
    addSermonChatMessage('ai', '❌ 네트워크 오류: ' + err.message);
  }
}

function setLastSermonError(error) {
  lastSermonError = error;
}

// ===== Step3 사용 코드 관리 시스템 =====
const CODES_KEY = '_sermon-step3-codes';
let step3Codes = {};

async function loadStep3Codes() {
  const saved = localStorage.getItem(CODES_KEY);
  console.log('[Step3Codes] localStorage 데이터:', saved);
  if (saved) {
    try {
      step3Codes = JSON.parse(saved);
      console.log('[Step3Codes] 로드된 코드:', step3Codes);
      console.log('[Step3Codes] 코드 개수:', Object.keys(step3Codes).length);
    } catch (e) {
      console.error('[Step3Codes] 파싱 오류:', e);
      step3Codes = {};
    }
  } else {
    console.log('[Step3Codes] 저장된 코드 없음');
  }
  renderCodeList();
}

async function saveStep3Codes() {
  localStorage.setItem(CODES_KEY, JSON.stringify(step3Codes));
  await saveToFirebase(CODES_KEY, JSON.stringify(step3Codes));
}

function generateRandomCode() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let code = '';
  for (let i = 0; i < 6; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return code;
}

async function createNewCode() {
  const nameInput = document.getElementById('new-code-name');
  const limitInput = document.getElementById('new-code-limit');

  let codeName = nameInput.value.trim().toUpperCase();
  const limit = parseInt(limitInput.value) || 3;

  // 코드명이 비어있으면 자동 생성
  if (!codeName) {
    do {
      codeName = generateRandomCode();
    } while (step3Codes[codeName]);
  }

  // 이미 존재하는 코드 체크
  if (step3Codes[codeName]) {
    alert(`'${codeName}' 코드가 이미 존재합니다.`);
    return;
  }

  step3Codes[codeName] = {
    limit: limit,
    remaining: limit,
    createdAt: new Date().toISOString()
  };

  await saveStep3Codes();
  renderCodeList();

  // 입력 필드 초기화
  nameInput.value = '';
  limitInput.value = '3';

  showStatus(`✅ 코드 '${codeName}' 생성됨!`);
  setTimeout(hideStatus, 2000);
}

async function deleteCode(codeName) {
  if (!confirm(`코드 '${codeName}'을(를) 삭제하시겠습니까?`)) return;

  delete step3Codes[codeName];
  await saveStep3Codes();
  renderCodeList();
}

function renderCodeList() {
  const container = document.getElementById('step3-codes-list');
  if (!container) return;

  const codes = Object.entries(step3Codes);

  if (codes.length === 0) {
    container.innerHTML = '<div style="color: #999; font-size: .85rem; text-align: center; padding: 1rem;">등록된 코드가 없습니다.</div>';
    return;
  }

  container.innerHTML = codes.map(([name, data]) => `
    <div style="display: flex; align-items: center; gap: .5rem; padding: .5rem; background: #f8f9fa; border-radius: 6px; margin-bottom: .5rem;">
      <span style="flex: 1; font-weight: 600; font-size: .9rem;">${name}</span>
      <span style="font-size: .8rem; color: #666;">${data.remaining}/${data.limit}회 남음</span>
      <button onclick="deleteCode('${name}')" style="background: #fee2e2; color: #dc2626; border: none; padding: .3rem .5rem; border-radius: 4px; cursor: pointer; font-size: .75rem;">삭제</button>
    </div>
  `).join('');
}

async function verifyCode(code) {
  const upperCode = code.toUpperCase();

  if (!step3Codes[upperCode]) {
    return { valid: false, error: '존재하지 않는 코드입니다.' };
  }

  if (step3Codes[upperCode].remaining <= 0) {
    return { valid: false, error: '사용 횟수가 소진된 코드입니다.' };
  }

  // 사용 횟수 차감
  step3Codes[upperCode].remaining--;
  await saveStep3Codes();
  renderCodeList();

  return { valid: true, remaining: step3Codes[upperCode].remaining };
}

// ===== 이벤트 리스너 초기화 =====
function initQAEvents() {
  // Q&A 전송 버튼
  const btnSendQA = document.getElementById('btn-send-qa');
  if (btnSendQA) {
    btnSendQA.addEventListener('click', sendQAQuestion);
  }

  // Q&A 입력 엔터키
  const qaInput = document.getElementById('qa-input');
  if (qaInput) {
    qaInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') sendQAQuestion();
    });
  }

  // 본문 추천 버튼
  const btnSearchScripture = document.getElementById('btn-search-scripture');
  if (btnSearchScripture) {
    btnSearchScripture.addEventListener('click', searchScripture);
  }

  // 본문 추천 엔터키
  const scriptureSearchInput = document.getElementById('scripture-search');
  if (scriptureSearchInput) {
    scriptureSearchInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') searchScripture();
    });
  }

  // 챗봇 모달 열기/닫기
  const btnSermonChatbot = document.getElementById('btn-sermon-chatbot');
  const sermonChatModal = document.getElementById('sermon-chat-modal');
  const btnCloseSermonChatbot = document.getElementById('btn-close-sermon-chatbot');

  if (btnSermonChatbot && sermonChatModal) {
    btnSermonChatbot.addEventListener('click', () => {
      sermonChatModal.classList.add('show');
    });
  }
  if (btnCloseSermonChatbot && sermonChatModal) {
    btnCloseSermonChatbot.addEventListener('click', () => {
      sermonChatModal.classList.remove('show');
    });
  }

  // 챗봇 메시지 전송
  const sermonChatSendBtn = document.getElementById('sermon-chat-send');
  const sermonChatInput = document.getElementById('sermon-chat-input');

  if (sermonChatSendBtn) {
    sermonChatSendBtn.addEventListener('click', sendSermonChatMessage);
  }
  if (sermonChatInput) {
    sermonChatInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') sendSermonChatMessage();
    });
  }

  // Step3 코드 로드
  loadStep3Codes();
}

// 전역 노출
window.QA_STORAGE_KEY = QA_STORAGE_KEY;
window.loadQAHistory = loadQAHistory;
window.saveQAHistory = saveQAHistory;
window.renderQAHistory = renderQAHistory;
window.sendQAQuestion = sendQAQuestion;
window.searchScripture = searchScripture;
window.addSermonChatMessage = addSermonChatMessage;
window.collectSermonContext = collectSermonContext;
window.sendSermonChatMessage = sendSermonChatMessage;
window.setLastSermonError = setLastSermonError;
window.loadStep3Codes = loadStep3Codes;
window.saveStep3Codes = saveStep3Codes;
window.createNewCode = createNewCode;
window.deleteCode = deleteCode;
window.renderCodeList = renderCodeList;
window.verifyCode = verifyCode;
window.initQAEvents = initQAEvents;
