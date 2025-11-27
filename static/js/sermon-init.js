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

// ===== 저장된 설교 관리 =====
function renderSavedList() {
  const saved = JSON.parse(localStorage.getItem('sermon-saved') || '[]');
  const list = document.getElementById('saved-list');

  if (!list) return;

  if (saved.length === 0) {
    list.innerHTML = '<p style="color: #999; font-size: .8rem; text-align: center; padding: .5rem;">저장된 자료가 없습니다.</p>';
    return;
  }

  list.innerHTML = saved.map((item, idx) => {
    const catLabel = getCategoryLabel(item.category);
    const display = item.seriesName
      ? `${item.date} - ${catLabel} - ${item.seriesName}`
      : `${item.date} - ${catLabel} - ${item.styleName}`;

    return `
      <div class="storage-item">
        <span style="font-size: .85rem;">${display}</span>
        <div>
          <button onclick="loadSaved(${idx})" style="margin-right: .3rem;">불러오기</button>
          <button onclick="deleteSaved(${idx})">삭제</button>
        </div>
      </div>
    `;
  }).join('');
}

window.loadSaved = function(idx) {
  const saved = JSON.parse(localStorage.getItem('sermon-saved') || '[]');
  const item = saved[idx];

  document.getElementById('sermon-date').value = item.date || '';
  document.getElementById('sermon-category').value = item.category || 'general';
  document.getElementById('sermon-ref').value = item.ref || '';
  document.getElementById('sermon-text').value = item.text || '';
  document.getElementById('series-name').value = item.seriesName || '';
  document.getElementById('manual-title').value = item.manualTitle || '';
  const specialNotesEl = document.getElementById('special-notes');
  if (specialNotesEl) specialNotesEl.value = item.specialNotes || '';

  window.currentCategory = item.category || 'general';
  window.currentStyleId = item.styleId || '';
  window.stepResults = item.results || {};
  window.titleOptions = item.titleOptions || [];
  window.selectedTitle = item.selectedTitle || '';

  // 제목이 있으면 표시
  if (window.titleOptions.length >= 3) {
    displayTitleOptions(window.titleOptions);
    // 저장된 선택 복원
    if (window.selectedTitle) {
      const titleIdx = window.titleOptions.indexOf(window.selectedTitle);
      if (titleIdx >= 0) {
        const radio = document.querySelector(`input[name="selectedTitle"][value="${titleIdx}"]`);
        if (radio) radio.checked = true;
      }
    }
  }

  renderCategories();
  renderStyles();
  renderProcessingSteps();
  renderResultBoxes();
  renderGuideTabs();
  updateAnalysisUI();

  document.querySelectorAll('textarea').forEach(autoResize);
};

window.deleteSaved = function(idx) {
  if (!confirm('삭제하시겠습니까?')) return;
  const saved = JSON.parse(localStorage.getItem('sermon-saved') || '[]');
  saved.splice(idx, 1);
  localStorage.setItem('sermon-saved', JSON.stringify(saved));
  renderSavedList();
};

window.renderSavedList = renderSavedList;

document.addEventListener('DOMContentLoaded', async () => {
  console.log('🚀 Sermon 앱 초기화 시작...');
  console.log('[Init] 초기 currentCategory:', window.currentCategory);
  console.log('[Init] 초기 currentStyleId:', window.currentStyleId);

  // ===== 날짜 초기화 =====
  const dateInput = document.getElementById('sermon-date');
  if (dateInput) {
    dateInput.value = new Date().toISOString().split('T')[0];
  }

  // ===== Firebase 데이터 로드 =====
  console.log('[Init] Firebase 데이터 로드 시작');
  showStatus('☁️ 클라우드 동기화 중...');
  await loadFromFirebase();
  hideStatus();
  console.log('[Init] Firebase 로드 완료');
  console.log('[Init] loadFromFirebase 후 currentCategory:', window.currentCategory);
  console.log('[Init] loadFromFirebase 후 currentStyleId:', window.currentStyleId);

  // ===== 스타일 자동 선택 (중요: UI 렌더링 전에 실행) =====
  console.log('[Init] ensureStyleSelected 호출');
  ensureStyleSelected();
  console.log('[Init] ensureStyleSelected 후 currentStyleId:', window.currentStyleId);

  // ===== UI 렌더링 =====
  console.log('[Init] UI 렌더링 시작');
  renderCategories();
  console.log('[Init] renderCategories 후 currentCategory:', window.currentCategory);
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
  console.log('[Init] renderStyles 호출 전 currentStyleId:', window.currentStyleId);
  renderStyles();
  console.log('[Init] renderStyles 후 currentStyleId:', window.currentStyleId);
  renderProcessingSteps();
  bindAdminStyleSelect();
  console.log('[Init] updateAnalysisUI 호출');
  updateAnalysisUI();

  // 설교 준비 시작 버튼
  const btnStartAnalysis = document.getElementById('btn-start-analysis');
  console.log('[Init] btn-start-analysis 찾음:', !!btnStartAnalysis);
  if (btnStartAnalysis) {
    btnStartAnalysis.addEventListener('click', startAutoAnalysis);
    console.log('[Init] startAutoAnalysis 이벤트 리스너 등록 완료');
  } else {
    console.error('[Init] btn-start-analysis 버튼을 찾을 수 없습니다!');
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

  // ===== 저장 버튼 =====
  const btnSave = document.getElementById('btn-save');
  if (btnSave) {
    btnSave.addEventListener('click', () => {
      const saved = JSON.parse(localStorage.getItem('sermon-saved') || '[]');
      const style = getCurrentStyle();

      saved.push({
        date: document.getElementById('sermon-date')?.value || '',
        category: window.currentCategory,
        styleId: window.currentStyleId,
        styleName: style ? style.name : '',
        seriesName: document.getElementById('series-name')?.value || '',
        ref: document.getElementById('sermon-ref')?.value || '',
        manualTitle: document.getElementById('manual-title')?.value || '',
        selectedTitle: window.selectedTitle,
        text: document.getElementById('sermon-text')?.value || '',
        specialNotes: document.getElementById('special-notes')?.value || '',
        results: window.stepResults,
        titleOptions: window.titleOptions,
        savedAt: new Date().toISOString()
      });

      localStorage.setItem('sermon-saved', JSON.stringify(saved));
      renderSavedList();
      alert('✅ 저장되었습니다!');
    });
  }

  // ===== 관리자 패널 토글 =====
  const toggleGuidesBtn = document.getElementById('toggle-guides');
  if (toggleGuidesBtn) {
    toggleGuidesBtn.addEventListener('click', () => {
      if (!window.guideUnlocked) {
        const modal = document.getElementById('modal-password');
        if (modal) modal.classList.add('show');
        const input = document.getElementById('password-input');
        if (input) {
          input.value = '';
          input.focus();
        }
      } else {
        const adminModal = document.getElementById('modal-admin-panel');
        if (adminModal) adminModal.classList.add('show');

        const steps = getCurrentSteps();
        if (steps.length > 0) {
          window.currentGuideStep = steps[0].id;
          renderGuideTabs();
          loadGuide(window.currentCategory, window.currentGuideStep);
        }
      }
    });
  }

  // 관리자 패널 닫기
  const btnCloseAdminPanel = document.getElementById('btn-close-admin-panel');
  if (btnCloseAdminPanel) {
    btnCloseAdminPanel.addEventListener('click', () => {
      const modal = document.getElementById('modal-admin-panel');
      if (modal) modal.classList.remove('show');
    });
  }

  // 패스워드 제출
  const btnSubmitPassword = document.getElementById('btn-submit-password');
  if (btnSubmitPassword) {
    btnSubmitPassword.addEventListener('click', () => {
      const input = document.getElementById('password-input');
      if (input && input.value === window.GUIDE_PASSWORD) {
        window.guideUnlocked = true;
        const modal = document.getElementById('modal-password');
        if (modal) modal.classList.remove('show');

        const adminModal = document.getElementById('modal-admin-panel');
        if (adminModal) adminModal.classList.add('show');

        const steps = getCurrentSteps();
        if (steps.length > 0) {
          window.currentGuideStep = steps[0].id;
          renderGuideTabs();
          loadGuide(window.currentCategory, window.currentGuideStep);
        }
      } else {
        alert('❌ 패스워드가 틀렸습니다.');
        if (input) input.value = '';
      }
    });
  }

  // 패스워드 모달 닫기
  const btnCancelPassword = document.getElementById('btn-cancel-password');
  if (btnCancelPassword) {
    btnCancelPassword.addEventListener('click', () => {
      const modal = document.getElementById('modal-password');
      if (modal) modal.classList.remove('show');
    });
  }

  // ===== 카테고리 관리 =====
  const btnManageCategories = document.getElementById('btn-manage-categories');
  if (btnManageCategories) {
    btnManageCategories.addEventListener('click', () => {
      if (window.manageUnlocked) {
        renderCategoryManageList();
        const modal = document.getElementById('modal-categories');
        if (modal) modal.classList.add('show');
      } else {
        window.pendingManageAction = 'categories';
        const modal = document.getElementById('modal-manage-password');
        if (modal) modal.classList.add('show');
        const input = document.getElementById('manage-password-input');
        if (input) {
          input.value = '';
          setTimeout(() => input.focus(), 100);
        }
      }
    });
  }

  // 카테고리 모달 닫기
  const btnCloseCategories = document.getElementById('btn-close-categories');
  if (btnCloseCategories) {
    btnCloseCategories.addEventListener('click', () => {
      const modal = document.getElementById('modal-categories');
      if (modal) modal.classList.remove('show');
    });
  }

  // 카테고리 추가
  const btnAddCategory = document.getElementById('btn-add-category');
  if (btnAddCategory) {
    btnAddCategory.addEventListener('click', async () => {
      const input = document.getElementById('new-cat-label');
      if (!input) return;

      const label = input.value.trim();
      if (!label) {
        alert('표시 이름을 입력하세요.');
        return;
      }

      if (window.config.categories.find(c => c.label === label)) {
        alert('이미 존재하는 카테고리 이름입니다.');
        return;
      }

      const value = generateCategoryId();
      window.config.categories.push({value, label});
      window.config.categorySettings[value] = { masterGuide: "", styles: [] };

      await saveConfig();
      renderCategories();
      renderCategoryManageList();
      input.value = '';
    });
  }

  // ===== 스타일 관리 =====
  const btnManageStyles = document.getElementById('btn-manage-styles');
  if (btnManageStyles) {
    btnManageStyles.addEventListener('click', () => {
      if (window.manageUnlocked) {
        const categoryLabel = document.getElementById('modal-styles-category');
        if (categoryLabel) {
          categoryLabel.textContent = getCategoryLabel(window.currentCategory);
        }
        renderStylesManageList();
        const modal = document.getElementById('modal-styles');
        if (modal) modal.classList.add('show');
      } else {
        window.pendingManageAction = 'styles';
        const modal = document.getElementById('modal-manage-password');
        if (modal) modal.classList.add('show');
        const input = document.getElementById('manage-password-input');
        if (input) {
          input.value = '';
          setTimeout(() => input.focus(), 100);
        }
      }
    });
  }

  // 스타일 모달 닫기
  const btnCloseStyles = document.getElementById('btn-close-styles');
  if (btnCloseStyles) {
    btnCloseStyles.addEventListener('click', () => {
      const modal = document.getElementById('modal-styles');
      if (modal) modal.classList.remove('show');
    });
  }

  // 스타일 추가
  const btnAddStyle = document.getElementById('btn-add-style');
  if (btnAddStyle) {
    btnAddStyle.addEventListener('click', addStyle);
  }

  // ===== 관리 패스워드 =====
  const btnSubmitManagePassword = document.getElementById('btn-submit-manage-password');
  if (btnSubmitManagePassword) {
    btnSubmitManagePassword.addEventListener('click', () => {
      const input = document.getElementById('manage-password-input');
      if (input && input.value === window.MANAGE_PASSWORD) {
        window.manageUnlocked = true;
        const modal = document.getElementById('modal-manage-password');
        if (modal) modal.classList.remove('show');

        // 대기 중인 액션 실행
        if (window.pendingManageAction === 'categories') {
          renderCategoryManageList();
          const catModal = document.getElementById('modal-categories');
          if (catModal) catModal.classList.add('show');
        } else if (window.pendingManageAction === 'styles') {
          const categoryLabel = document.getElementById('modal-styles-category');
          if (categoryLabel) {
            categoryLabel.textContent = getCategoryLabel(window.currentCategory);
          }
          renderStylesManageList();
          const styleModal = document.getElementById('modal-styles');
          if (styleModal) styleModal.classList.add('show');
        }
        window.pendingManageAction = null;
      } else {
        alert('❌ 패스워드가 틀렸습니다.');
        if (input) input.value = '';
      }
    });
  }

  // 관리 패스워드 모달 닫기
  const btnCancelManagePassword = document.getElementById('btn-cancel-manage-password');
  if (btnCancelManagePassword) {
    btnCancelManagePassword.addEventListener('click', () => {
      const modal = document.getElementById('modal-manage-password');
      if (modal) modal.classList.remove('show');
      window.pendingManageAction = null;
    });
  }

  // ===== 가이드 저장 버튼 =====
  const btnSaveGuide = document.getElementById('btn-save-guide');
  if (btnSaveGuide) {
    btnSaveGuide.addEventListener('click', saveGuide);
  }

  // 총괄 지침 저장 버튼
  const btnSaveMasterGuide = document.getElementById('btn-save-master-guide');
  if (btnSaveMasterGuide) {
    btnSaveMasterGuide.addEventListener('click', saveMasterGuide);
  }

  // ===== GPT PRO 버튼 =====
  const btnGptPro = document.getElementById('btn-gpt-pro');
  if (btnGptPro) {
    btnGptPro.addEventListener('click', executeGptPro);
  }

  // GPT PRO 결과 복사
  const btnCopyGptPro = document.getElementById('btn-copy-gpt-pro');
  if (btnCopyGptPro) {
    btnCopyGptPro.addEventListener('click', () => {
      const result = document.getElementById('gpt-pro-result');
      if (result && result.value) {
        navigator.clipboard.writeText(result.value).then(() => {
          btnCopyGptPro.textContent = '복사됨!';
          setTimeout(() => { btnCopyGptPro.textContent = '📋 설교문 전체 복사'; }, 1500);
        });
      }
    });
  }

  // ===== 전체 복사 버튼 =====
  const btnCopyAll = document.getElementById('btn-copy-all');
  if (btnCopyAll) {
    btnCopyAll.addEventListener('click', () => {
      if (typeof copyAllResults === 'function') {
        copyAllResults();
      }
    });
  }

  // ===== 첫 방문 가이드 모달 =====
  const btnCloseGuide = document.getElementById('btn-close-guide');
  if (btnCloseGuide) {
    btnCloseGuide.addEventListener('click', () => {
      const modal = document.getElementById('modal-guide');
      if (modal) modal.classList.remove('show');
    });
  }

  const btnHideGuideWeek = document.getElementById('btn-hide-guide-week');
  if (btnHideGuideWeek) {
    btnHideGuideWeek.addEventListener('click', () => {
      localStorage.setItem('sermon-guide-hide-until', (Date.now() + 7 * 24 * 60 * 60 * 1000).toString());
      const modal = document.getElementById('modal-guide');
      if (modal) modal.classList.remove('show');
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
