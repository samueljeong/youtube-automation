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

// ===== 성경구절 변환 함수 =====
/**
 * 성경구절을 다양한 형식으로 변환
 * @param {string} ref - 원본 성경구절 (예: "민수기 8:14", "민4:13", "창세기 1:1-3")
 * @returns {object} - { original, 장절, 축약 }
 */
function convertScriptureRef(ref) {
  if (!ref) return { original: '', 장절: '', 축약: '' };

  // 성경 책 이름 매핑 (전체 -> 축약)
  const bookAbbrev = {
    '창세기': '창', '출애굽기': '출', '레위기': '레', '민수기': '민', '신명기': '신',
    '여호수아': '수', '사사기': '삿', '룻기': '룻', '사무엘상': '삼상', '사무엘하': '삼하',
    '열왕기상': '왕상', '열왕기하': '왕하', '역대상': '대상', '역대하': '대하',
    '에스라': '스', '느헤미야': '느', '에스더': '에', '욥기': '욥', '시편': '시',
    '잠언': '잠', '전도서': '전', '아가': '아', '이사야': '사', '예레미야': '렘',
    '예레미야애가': '애', '에스겔': '겔', '다니엘': '단', '호세아': '호', '요엘': '욜',
    '아모스': '암', '오바댜': '옵', '요나': '욘', '미가': '미', '나훔': '나',
    '하박국': '합', '스바냐': '습', '학개': '학', '스가랴': '슥', '말라기': '말',
    '마태복음': '마', '마가복음': '막', '누가복음': '눅', '요한복음': '요',
    '사도행전': '행', '로마서': '롬', '고린도전서': '고전', '고린도후서': '고후',
    '갈라디아서': '갈', '에베소서': '엡', '빌립보서': '빌', '골로새서': '골',
    '데살로니가전서': '살전', '데살로니가후서': '살후', '디모데전서': '딤전', '디모데후서': '딤후',
    '디도서': '딛', '빌레몬서': '몬', '히브리서': '히', '야고보서': '약',
    '베드로전서': '벧전', '베드로후서': '벧후', '요한일서': '요일', '요한이서': '요이',
    '요한삼서': '요삼', '유다서': '유', '요한계시록': '계'
  };

  // 축약 -> 전체 역매핑
  const bookFull = {};
  for (const [full, abbr] of Object.entries(bookAbbrev)) {
    bookFull[abbr] = full;
  }

  // 성경구절 파싱 정규식: "책이름 장:절" 또는 "책이름장:절"
  // 예: "민수기 8:14", "민4:13", "창세기 1:1-3"
  const regex = /^([가-힣]+)\s*(\d+)[:\s장]?\s*(\d+(?:-\d+)?)\s*절?$/;
  const match = ref.trim().match(regex);

  if (!match) {
    // 파싱 실패시 원본 그대로 반환
    return { original: ref, 장절: ref, 축약: ref };
  }

  const bookName = match[1];
  const chapter = match[2];
  const verses = match[3];

  // 책 이름이 축약형인지 전체형인지 확인
  let fullName = bookFull[bookName] || bookName;
  let abbrevName = bookAbbrev[bookName] || bookAbbrev[fullName] || bookName;

  return {
    original: ref,
    장절: `${fullName} ${chapter}장 ${verses}절`,
    축약: `${abbrevName}${chapter}:${verses}`
  };
}

// ===== 템플릿 placeholder 치환 =====
/**
 * 템플릿의 placeholder를 실제 값으로 치환
 * @param {string} template - 템플릿 문자열
 * @param {object} values - 치환할 값들
 * @returns {string} - 치환된 문자열
 */
function replacePlaceholders(template, values) {
  let result = template;

  // placeholder 치환
  const replacements = {
    '{{날짜}}': values.날짜 || '',
    '{{성경구절}}': values.성경구절 || '',
    '{{성경구절_장절}}': values.성경구절_장절 || '',
    '{{성경구절_축약}}': values.성경구절_축약 || '',
    '{{본문말씀}}': values.본문말씀 || '',
    '{{묵상}}': values.묵상 || '',
    '{{제목}}': values.제목 || '',
    '{{인용구}}': values.인용구 || '',
    '{{보내는사람}}': values.보내는사람 || ''
  };

  for (const [placeholder, value] of Object.entries(replacements)) {
    result = result.split(placeholder).join(value);
  }

  return result;
}

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
        let finalMessage = '';

        if (data.mode === 'placeholder') {
          // placeholder 모드: 템플릿의 placeholder를 실제 값으로 치환
          const refConverted = convertScriptureRef(ref);

          const values = {
            날짜: dateStr,
            성경구절: ref,
            성경구절_장절: refConverted.장절,
            성경구절_축약: refConverted.축약,
            본문말씀: verse,
            묵상: data.묵상 || data.result,
            제목: data.제목 || '',
            인용구: data.인용구 || '',
            보내는사람: sender ? `- ${sender} -` : ''
          };

          finalMessage = replacePlaceholders(template, values);
        } else if (data.mode === 'legacy' && template) {
          // legacy 모드 (placeholder 없는 템플릿): GPT가 전체 메시지 생성
          finalMessage = data.result;
        } else {
          // default 모드 (템플릿 없음): 기본 형식으로 조합
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
window.convertScriptureRef = convertScriptureRef;
window.replacePlaceholders = replacePlaceholders;
window.updateMeditationDayFromInputs = updateMeditationDayFromInputs;
window.initMeditationDate = initMeditationDate;
window.saveMeditationTemplate = saveMeditationTemplate;
window.loadMeditationTemplate = loadMeditationTemplate;
window.resetMeditationTemplate = resetMeditationTemplate;
window.createMeditation = createMeditation;
window.copyMeditation = copyMeditation;
window.initMeditationEvents = initMeditationEvents;
