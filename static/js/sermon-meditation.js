/**
 * sermon-meditation.js
 * 묵상메시지 생성 기능
 *
 * 주요 함수:
 * - initMeditationDate() - 날짜 초기화
 * - updateMeditationDayFromInputs() - 요일 업데이트
 * - saveMeditationTemplate(), loadMeditationTemplate() - 템플릿 관리
 * - createMeditation() - 묵상메시지 생성
 * - copyMeditation() - 결과 복사
 *
 * 이 파일은 sermon.html의 묵상메시지 관련 코드를 모듈화한 것입니다.
 */

// 요일 배열 (한국어)
const koreanDays = ['일', '월', '화', '수', '목', '금', '토'];

// 월/일에서 요일 업데이트
function updateMeditationDayFromInputs() {
  const monthInput = document.getElementById('meditation-month');
  const dayNumInput = document.getElementById('meditation-day-num');
  const daySpan = document.getElementById('meditation-day');

  if (monthInput && dayNumInput && daySpan) {
    const month = parseInt(monthInput.value, 10);
    const day = parseInt(dayNumInput.value, 10);
    if (month >= 1 && month <= 12 && day >= 1 && day <= 31) {
      const now = new Date();
      const date = new Date(now.getFullYear(), month - 1, day);
      const dayIndex = date.getDay();
      daySpan.textContent = `(${koreanDays[dayIndex]})`;
    }
  }
}

// 묵상메시지 날짜 초기화 (서울 시간)
function initMeditationDate() {
  const monthInput = document.getElementById('meditation-month');
  const dayNumInput = document.getElementById('meditation-day-num');

  if (monthInput && dayNumInput) {
    // 서울 시간대로 현재 날짜 계산
    const now = new Date();
    const seoulOffset = 9 * 60; // UTC+9
    const localOffset = now.getTimezoneOffset();
    const seoulTime = new Date(now.getTime() + (seoulOffset + localOffset) * 60 * 1000);

    monthInput.value = seoulTime.getMonth() + 1;
    dayNumInput.value = seoulTime.getDate();

    updateMeditationDayFromInputs();
  }

  // 템플릿 로드
  loadMeditationTemplate();
}

// 템플릿 저장/로드 (localStorage)
function saveMeditationTemplate() {
  const templateInput = document.getElementById('meditation-template');
  if (templateInput) {
    localStorage.setItem('meditation_template', templateInput.value);
  }
}

function loadMeditationTemplate() {
  const templateInput = document.getElementById('meditation-template');
  if (templateInput) {
    const saved = localStorage.getItem('meditation_template');
    if (saved) {
      templateInput.value = saved;
      autoResizeTextarea(templateInput);
    }
  }
}

function resetMeditationTemplate() {
  const templateInput = document.getElementById('meditation-template');
  if (templateInput) {
    templateInput.value = '';
    localStorage.removeItem('meditation_template');
  }
}

// 묵상메시지 생성
async function createMeditation() {
  const monthInput = document.getElementById('meditation-month');
  const dayNumInput = document.getElementById('meditation-day-num');
  const daySpan = document.getElementById('meditation-day');
  const ref = document.getElementById('meditation-ref')?.value.trim();
  const verse = document.getElementById('meditation-verse')?.value.trim();
  const sender = document.getElementById('meditation-sender')?.value.trim();
  const template = document.getElementById('meditation-template')?.value.trim();

  if (!ref) {
    alert('성경본문을 입력해주세요.');
    return;
  }
  if (!verse) {
    alert('본문말씀을 입력해주세요.');
    return;
  }

  // 날짜 포맷팅 (예: 7월 16일 (수))
  let dateStr = '';
  if (monthInput && dayNumInput && monthInput.value && dayNumInput.value) {
    const dayText = daySpan ? daySpan.textContent : '';
    dateStr = `${monthInput.value}월 ${dayNumInput.value}일 ${dayText}`;
  }

  showStatus('🙏 묵상메시지 생성 중...');
  showGptLoading();

  try {
    const response = await fetch('/api/sermon/meditation', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        reference: ref,
        verse: verse,
        dateStr: dateStr,
        sender: sender,
        template: template
      })
    });

    const data = await response.json();

    if (data.ok) {
      const resultTextarea = document.getElementById('meditation-result');
      if (resultTextarea) {
        // 최종 메시지 조합
        let finalMessage = '';

        // 날짜 + 오늘의 말씀
        if (dateStr) {
          finalMessage += `${dateStr} 오늘의 말씀\n\n`;
        }

        // 성경구절
        finalMessage += `${ref}\n`;

        // 본문말씀
        finalMessage += `${verse}\n\n`;

        // 묵상메시지 (GPT 생성 결과)
        finalMessage += data.result;

        // 보내는 사람
        if (sender) {
          finalMessage += `\n\n- ${sender} -`;
        }

        resultTextarea.value = finalMessage;
        autoResizeTextarea(resultTextarea);
      }
      showStatus('✅ 묵상메시지 생성 완료!');
    } else {
      alert(`오류: ${data.error}`);
      showStatus('❌ 실패');
    }
  } catch (err) {
    alert(`네트워크 오류: ${err.message}`);
    showStatus('❌ 오류');
  } finally {
    hideGptLoading();
    setTimeout(hideStatus, 2000);
  }
}

// 묵상메시지 복사
function copyMeditation() {
  const resultTextarea = document.getElementById('meditation-result');
  if (resultTextarea && resultTextarea.value) {
    navigator.clipboard.writeText(resultTextarea.value).then(() => {
      showStatus('📋 복사되었습니다!');
      setTimeout(hideStatus, 2000);
    }).catch(() => {
      // fallback
      resultTextarea.select();
      document.execCommand('copy');
      showStatus('📋 복사되었습니다!');
      setTimeout(hideStatus, 2000);
    });
  }
}

// ===== 이벤트 리스너 초기화 =====
function initMeditationEvents() {
  // 월/일 입력 변경 이벤트
  const meditationMonth = document.getElementById('meditation-month');
  const meditationDayNum = document.getElementById('meditation-day-num');

  if (meditationMonth) {
    meditationMonth.addEventListener('change', updateMeditationDayFromInputs);
    meditationMonth.addEventListener('input', updateMeditationDayFromInputs);
  }
  if (meditationDayNum) {
    meditationDayNum.addEventListener('change', updateMeditationDayFromInputs);
    meditationDayNum.addEventListener('input', updateMeditationDayFromInputs);
  }

  // 템플릿 textarea 이벤트
  const meditationTemplate = document.getElementById('meditation-template');
  if (meditationTemplate) {
    meditationTemplate.addEventListener('input', () => {
      saveMeditationTemplate();
      autoResizeTextarea(meditationTemplate);
    });
  }

  // 템플릿 초기화 버튼
  const btnResetTemplate = document.getElementById('btn-reset-template');
  if (btnResetTemplate) {
    btnResetTemplate.addEventListener('click', () => {
      if (confirm('템플릿을 초기화하시겠습니까?')) {
        resetMeditationTemplate();
      }
    });
  }

  // 메시지 제작 버튼
  const btnCreateMeditation = document.getElementById('btn-create-meditation');
  if (btnCreateMeditation) {
    btnCreateMeditation.addEventListener('click', createMeditation);
  }

  // 복사 버튼
  const btnCopyMeditation = document.getElementById('btn-copy-meditation');
  if (btnCopyMeditation) {
    btnCopyMeditation.addEventListener('click', copyMeditation);
  }
}

// 전역 노출
window.koreanDays = koreanDays;
window.updateMeditationDayFromInputs = updateMeditationDayFromInputs;
window.initMeditationDate = initMeditationDate;
window.saveMeditationTemplate = saveMeditationTemplate;
window.loadMeditationTemplate = loadMeditationTemplate;
window.resetMeditationTemplate = resetMeditationTemplate;
window.createMeditation = createMeditation;
window.copyMeditation = copyMeditation;
window.initMeditationEvents = initMeditationEvents;
