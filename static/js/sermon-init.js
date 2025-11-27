/**
 * sermon-init.js
 * 앱 초기화 - 모든 모듈 로드 후 마지막에 실행
 *
 * 로드 순서:
 * 1. Firebase SDK (CDN)
 * 2. sermon-utils.js
 * 3. sermon-firebase.js
 * 4. sermon-main.js
 * 5. sermon-render.js
 * 6. sermon-step.js
 * 7. sermon-gpt-pro.js
 * 8. sermon-admin.js
 * 9. sermon-qa.js
 * 10. sermon-meditation.js
 * 11. sermon-design.js
 * 12. sermon-init.js (이 파일)
 */

document.addEventListener('DOMContentLoaded', async () => {
  console.log('🚀 Sermon 앱 초기화 시작...');

  // ===== 날짜 초기화 =====
  const dateInput = document.getElementById('sermon-date');
  if (dateInput) {
    dateInput.value = new Date().toISOString().split('T')[0];
  }

  // ===== Firebase 데이터 로드 =====
  showStatus('☁️ 클라우드 동기화 중...');
  await loadFromFirebase();
  hideStatus();

  // ===== UI 렌더링 =====
  renderCategories();
  loadMasterGuide(window.currentCategory);
  loadModelSettings();
  loadStep3Codes();

  // ===== 이벤트 리스너 등록 =====

  // 코드 생성 버튼
  const btnCreateCode = document.getElementById('btn-create-code');
  if (btnCreateCode) {
    btnCreateCode.addEventListener('click', createNewCode);
  }

  // 본문 추천
  const btnSearchScripture = document.getElementById('btn-search-scripture');
  if (btnSearchScripture) {
    btnSearchScripture.addEventListener('click', searchScripture);
  }
  const scriptureSearchInput = document.getElementById('scripture-search');
  if (scriptureSearchInput) {
    scriptureSearchInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') searchScripture();
    });
  }

  // UI 렌더링 계속
  renderStyles();
  renderProcessingSteps();
  bindAdminStyleSelect();
  updateAnalysisUI();

  // 설교 준비 시작 버튼
  const btnStartAnalysis = document.getElementById('btn-start-analysis');
  if (btnStartAnalysis) {
    btnStartAnalysis.addEventListener('click', startAutoAnalysis);
  }

  // 성경 본문 입력 시 UI 업데이트
  const sermonRefInput = document.getElementById('sermon-ref');
  if (sermonRefInput) {
    sermonRefInput.addEventListener('input', () => {
      updateAnalysisUI();
    });
  }

  // ===== 모델 선택 이벤트 =====
  const step1Select = document.getElementById('model-step1');
  const step2Select = document.getElementById('model-step2');
  const gptProSelect = document.getElementById('model-gpt-pro');

  if (step1Select) {
    step1Select.addEventListener('change', async () => {
      await saveModelSettings();
      showStatus('✅ 모델 설정 저장됨');
      setTimeout(hideStatus, 1500);
    });
  }
  if (step2Select) {
    step2Select.addEventListener('change', async () => {
      await saveModelSettings();
      showStatus('✅ 모델 설정 저장됨');
      setTimeout(hideStatus, 1500);
    });
  }
  if (gptProSelect) {
    gptProSelect.addEventListener('change', async () => {
      await saveModelSettings();
      showStatus('✅ 모델 설정 저장됨');
      setTimeout(hideStatus, 1500);
    });
  }

  // Step3 토큰 설정
  const step3MaxTokensInput = document.getElementById('step3-max-tokens');
  if (step3MaxTokensInput) {
    step3MaxTokensInput.addEventListener('change', async () => {
      await saveModelSettings();
      showStatus('✅ 토큰 설정 저장됨');
      setTimeout(hideStatus, 1500);
    });
  }

  // ===== 상태 초기화 (새로고침 시) =====
  window.stepResults = {};
  window.titleOptions = [];
  window.selectedTitle = '';

  // AUTO_SAVE_KEY 데이터 삭제 및 타임스탬프 설정
  localStorage.removeItem(AUTO_SAVE_KEY);
  const futureTimestamp = (Date.now() + 365 * 24 * 60 * 60 * 1000).toString();
  localStorage.setItem(`${AUTO_SAVE_KEY}_timestamp`, futureTimestamp);

  // Q&A 히스토리 초기화
  sessionStorage.removeItem(QA_STORAGE_KEY);

  // GPT PRO 결과 초기화
  const gptProContainer = document.getElementById('gpt-pro-result-container');
  if (gptProContainer) gptProContainer.style.display = 'none';
  const gptProResult = document.getElementById('gpt-pro-result');
  if (gptProResult) gptProResult.value = '';

  // 제목 선택 박스 숨기기
  const titleBox = document.getElementById('title-selection-box');
  if (titleBox) titleBox.style.display = 'none';

  // ===== 추가 UI 렌더링 =====
  renderResultBoxes();
  renderGuideTabs();
  renderSavedList();

  // ===== 첫 방문자 가이드 =====
  const guideHideUntil = localStorage.getItem('sermon-guide-hide-until');
  const now = Date.now();
  if (!guideHideUntil || now > parseInt(guideHideUntil)) {
    const modal = document.getElementById('modal-guide');
    if (modal) {
      modal.classList.add('show');
    }
  }

  // ===== 실시간 동기화 =====
  console.log('🔄 실시간 동기화 활성화');
  setupRealtimeSync();

  // ===== Q&A 초기화 =====
  renderQAHistory();

  const btnSendQA = document.getElementById('btn-send-qa');
  if (btnSendQA) {
    btnSendQA.addEventListener('click', sendQAQuestion);
  }

  const qaInput = document.getElementById('qa-input');
  if (qaInput) {
    qaInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendQAQuestion();
      }
    });
  }

  // ===== Textarea 자동 리사이즈 =====
  document.querySelectorAll('textarea').forEach(autoResize);

  // ===== 묵상메시지 초기화 =====
  if (typeof initMeditationDate === 'function') {
    initMeditationDate();
  }
  if (typeof initMeditationEvents === 'function') {
    initMeditationEvents();
  }

  // ===== 디자인 도우미 초기화 =====
  if (typeof initDesignEvents === 'function') {
    initDesignEvents();
  }

  // ===== 챗봇 이벤트 =====
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

  console.log('✅ Sermon 앱 초기화 완료!');
});

// 전역 노출
window.initSermonApp = function() {
  console.log('Sermon 앱이 이미 초기화되었습니다.');
};
