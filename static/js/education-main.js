/**
 * education-main.js
 * 교육 설계 도우미 프론트엔드 로직
 */

// 장비 목록
let equipmentList = ['피아노', '프로젝터'];

// 생성 결과 저장
let generatedResult = null;

// ===== 초기화 =====
document.addEventListener('DOMContentLoaded', () => {
  // 프로그램 타입 변경 시 custom 입력 필드 토글
  document.getElementById('edu-program-type').addEventListener('change', (e) => {
    const customRow = document.getElementById('custom-type-row');
    customRow.style.display = e.target.value === 'custom' ? 'block' : 'none';
  });

  // 장비 입력 엔터키 처리
  document.getElementById('equipment-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addEquipment();
    }
  });

  // 탭 클릭 이벤트
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const tabName = tab.dataset.tab;
      switchTab(tabName);
    });
  });

  // 초기 장비 렌더링
  renderEquipmentTags();
});

// ===== 부목표 관리 =====
function addSubGoal() {
  const list = document.getElementById('sub-goals-list');
  const count = list.children.length + 1;
  const item = document.createElement('div');
  item.className = 'sub-goal-item';
  item.innerHTML = `
    <input type="text" placeholder="부목표 ${count}">
    <button type="button" class="btn-remove-goal" onclick="removeSubGoal(this)">×</button>
  `;
  list.appendChild(item);
}

function removeSubGoal(btn) {
  const list = document.getElementById('sub-goals-list');
  if (list.children.length > 1) {
    btn.parentElement.remove();
  }
}

// ===== 장비 관리 =====
function addEquipment() {
  const input = document.getElementById('equipment-input');
  const value = input.value.trim();
  if (value && !equipmentList.includes(value)) {
    equipmentList.push(value);
    renderEquipmentTags();
  }
  input.value = '';
}

function removeEquipment(item) {
  equipmentList = equipmentList.filter(e => e !== item);
  renderEquipmentTags();
}

function renderEquipmentTags() {
  const container = document.getElementById('equipment-tags');
  container.innerHTML = equipmentList.map(item => `
    <span class="equipment-tag">
      ${item}
      <span class="remove" onclick="removeEquipment('${item}')">×</span>
    </span>
  `).join('');
}

// ===== 폼 데이터 수집 =====
function collectFormData() {
  // 부목표 수집
  const subGoals = [];
  document.querySelectorAll('#sub-goals-list input').forEach(input => {
    const val = input.value.trim();
    if (val) subGoals.push(val);
  });

  return {
    program_basic: {
      title: document.getElementById('edu-title').value.trim(),
      program_type: document.getElementById('edu-program-type').value,
      program_type_label: document.getElementById('edu-program-type').value === 'custom'
        ? document.getElementById('edu-program-type-label').value.trim() || null
        : null,
      target_group: document.getElementById('edu-target-group').value.trim(),
      participants_count: parseInt(document.getElementById('edu-participants').value) || null,
      age_range: document.getElementById('edu-age-range').value.trim() || null,
      ministry_context: document.getElementById('edu-ministry-context').value.trim() || null
    },
    schedule: {
      total_sessions: parseInt(document.getElementById('edu-total-sessions').value) || 4,
      total_weeks: parseInt(document.getElementById('edu-total-weeks').value) || null,
      session_duration_min: parseInt(document.getElementById('edu-session-duration').value) || 90,
      session_frequency: document.getElementById('edu-frequency').value,
      start_hint: document.getElementById('edu-start-hint').value.trim() || null
    },
    goals: {
      main_goal: document.getElementById('edu-main-goal').value.trim(),
      sub_goals: subGoals
    },
    current_status: {
      participants_level: document.getElementById('edu-level').value,
      strengths: document.getElementById('edu-strengths').value.trim() || null,
      problems: document.getElementById('edu-problems').value.trim() || null,
      special_context: document.getElementById('edu-special-context').value.trim() || null
    },
    constraints: {
      available_time_slot: document.getElementById('edu-time-slot').value.trim() || null,
      available_space: document.getElementById('edu-space').value.trim() || null,
      available_equipment: equipmentList,
      budget_level: document.getElementById('edu-budget').value,
      other_limitations: document.getElementById('edu-other-limitations').value.trim() || null
    },
    output_preferences: {
      need_curriculum_outline: document.getElementById('opt-curriculum').checked,
      need_detailed_session_plans: document.getElementById('opt-detailed').checked,
      need_announcement_text: document.getElementById('opt-announcement').checked,
      need_homework_idea: document.getElementById('opt-homework').checked,
      need_evaluation_items: document.getElementById('opt-evaluation').checked,
      tone: document.getElementById('edu-tone').value,
      detail_level: document.getElementById('edu-detail-level').value
    },
    extra_notes: document.getElementById('edu-extra-notes').value.trim() || null
  };
}

// ===== 유효성 검사 =====
function validateForm() {
  const title = document.getElementById('edu-title').value.trim();
  const targetGroup = document.getElementById('edu-target-group').value.trim();
  const totalSessions = document.getElementById('edu-total-sessions').value;
  const sessionDuration = document.getElementById('edu-session-duration').value;
  const mainGoal = document.getElementById('edu-main-goal').value.trim();

  if (!title) {
    alert('교육명을 입력해주세요.');
    document.getElementById('edu-title').focus();
    return false;
  }
  if (!targetGroup) {
    alert('대상 그룹을 입력해주세요.');
    document.getElementById('edu-target-group').focus();
    return false;
  }
  if (!totalSessions || totalSessions < 1) {
    alert('전체 회차를 입력해주세요.');
    document.getElementById('edu-total-sessions').focus();
    return false;
  }
  if (!sessionDuration || sessionDuration < 30) {
    alert('회당 시간을 30분 이상 입력해주세요.');
    document.getElementById('edu-session-duration').focus();
    return false;
  }
  if (!mainGoal) {
    alert('핵심 목표를 입력해주세요.');
    document.getElementById('edu-main-goal').focus();
    return false;
  }

  return true;
}

// ===== API 호출 =====
async function generateCurriculum() {
  if (!validateForm()) return;

  const formData = collectFormData();
  const btn = document.getElementById('btn-generate');
  const loading = document.getElementById('loading-overlay');

  btn.disabled = true;
  loading.classList.add('show');

  try {
    const res = await fetch('/api/education/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });

    const data = await res.json();

    if (data.status === 'ok') {
      generatedResult = {
        input: formData,
        output: data.result,
        usage: data.usage
      };
      renderResult(data.result);
      document.getElementById('result-section').classList.add('show');
      document.getElementById('result-section').scrollIntoView({ behavior: 'smooth' });
    } else {
      alert('오류: ' + (data.message || '알 수 없는 오류'));
    }
  } catch (err) {
    console.error(err);
    alert('네트워크 오류가 발생했습니다.');
  } finally {
    btn.disabled = false;
    loading.classList.remove('show');
  }
}

// ===== 결과 렌더링 =====
function renderResult(result) {
  renderSummary(result.program_summary);
  renderCurriculum(result.curriculum_outline);
  renderSessions(result.sessions_detail);
  renderAnnouncements(result.announcements);
  renderEvaluation(result.evaluation);
}

function renderSummary(summary) {
  if (!summary) {
    document.getElementById('summary-content').innerHTML = '<p>개요 정보가 없습니다.</p>';
    return;
  }

  const outcomes = summary.key_outcomes?.map(o => `<li>${o}</li>`).join('') || '';

  document.getElementById('summary-content').innerHTML = `
    <div class="result-card">
      <h3>${summary.title || '제목 없음'}</h3>
      <p><strong>대상:</strong> ${summary.target_overview || '-'}</p>
      <p><strong>기간:</strong> ${summary.duration_overview || '-'}</p>
      <p><strong>목적:</strong> ${summary.purpose_statement || '-'}</p>
      ${outcomes ? `<p><strong>기대 성과:</strong></p><ul>${outcomes}</ul>` : ''}
    </div>
  `;
}

function renderCurriculum(curriculum) {
  const container = document.getElementById('curriculum-content');

  if (!curriculum || !curriculum.sessions || curriculum.sessions.length === 0) {
    container.innerHTML = '<p>커리큘럼 개요가 없습니다.</p>';
    return;
  }

  container.innerHTML = curriculum.sessions.map(s => `
    <div class="result-card">
      <h3>${s.session_number}회차: ${s.title}</h3>
      <p><strong>핵심 주제:</strong> ${s.core_theme || '-'}</p>
      <p><strong>목표:</strong> ${s.main_objective || '-'}</p>
      ${s.keywords?.length ? `<p><strong>키워드:</strong> ${s.keywords.join(', ')}</p>` : ''}
    </div>
  `).join('');
}

function renderSessions(sessions) {
  const container = document.getElementById('sessions-content');

  if (!sessions || sessions.length === 0) {
    container.innerHTML = '<p>회차별 상세 교안이 없습니다.</p>';
    return;
  }

  container.innerHTML = sessions.map(s => {
    const timePlan = s.time_plan?.map(t =>
      `<span class="time-segment">${t.segment} <span class="minutes">${t.minutes}분</span></span>`
    ).join('') || '';

    const contents = s.key_contents?.map(c => `<li>${c}</li>`).join('') || '';
    const activities = s.activities?.map(a => `<li>${a}</li>`).join('') || '';
    const materials = s.materials?.join(', ') || '-';

    return `
      <div class="session-card">
        <div class="session-header">
          <span class="session-number">${s.session_number}회차</span>
          <span class="session-title">${s.title}</span>
        </div>
        <div class="session-body">
          <p><strong>목표:</strong> ${s.objective || '-'}</p>

          ${timePlan ? `<div class="label">시간 배분</div><div class="time-plan">${timePlan}</div>` : ''}

          ${contents ? `<div class="label">핵심 내용</div><ul>${contents}</ul>` : ''}

          ${activities ? `<div class="label">활동/나눔</div><ul>${activities}</ul>` : ''}

          <div class="label">준비물</div>
          <p>${materials}</p>

          ${s.homework ? `<div class="label">숙제/적용</div><p>${s.homework}</p>` : ''}

          ${s.notes_for_leader ? `<div class="label">리더 메모</div><p style="color: #667eea; font-style: italic;">${s.notes_for_leader}</p>` : ''}
        </div>
      </div>
    `;
  }).join('');
}

function renderAnnouncements(announcements) {
  const container = document.getElementById('announcements-content');

  if (!announcements || (!announcements.kakao_short && !announcements.bulletin)) {
    container.innerHTML = '<p>공지문이 없습니다.</p>';
    return;
  }

  let html = '';

  if (announcements.kakao_short) {
    html += `
      <div class="announcement-box">
        <h4>카카오톡 공지용</h4>
        <pre>${announcements.kakao_short}</pre>
        <button class="btn-copy" onclick="copyText(\`${escapeForJs(announcements.kakao_short)}\`)">복사</button>
      </div>
    `;
  }

  if (announcements.bulletin) {
    html += `
      <div class="announcement-box">
        <h4>주보/알림용</h4>
        <pre>${announcements.bulletin}</pre>
        <button class="btn-copy" onclick="copyText(\`${escapeForJs(announcements.bulletin)}\`)">복사</button>
      </div>
    `;
  }

  container.innerHTML = html;
}

function renderEvaluation(evaluation) {
  const container = document.getElementById('evaluation-content');

  if (!evaluation || !evaluation.feedback_questions || evaluation.feedback_questions.length === 0) {
    container.innerHTML = '<p>평가 문항이 없습니다.</p>';
    return;
  }

  const questions = evaluation.feedback_questions.map((q, i) => `<li>${q}</li>`).join('');

  container.innerHTML = `
    <div class="result-card">
      <h3>피드백 질문</h3>
      <ol>${questions}</ol>
    </div>
  `;
}

// ===== 탭 전환 =====
function switchTab(tabName) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

  document.querySelector(`.tab[data-tab="${tabName}"]`).classList.add('active');
  document.getElementById(`tab-${tabName}`).classList.add('active');
}

// ===== 유틸리티 =====
function escapeForJs(str) {
  return str.replace(/`/g, '\\`').replace(/\$/g, '\\$');
}

function copyText(text) {
  navigator.clipboard.writeText(text).then(() => {
    alert('복사되었습니다!');
  });
}

function copyAllResult() {
  if (!generatedResult) {
    alert('생성된 결과가 없습니다.');
    return;
  }

  const text = JSON.stringify(generatedResult.output, null, 2);
  navigator.clipboard.writeText(text).then(() => {
    alert('전체 결과가 복사되었습니다!');
  });
}

async function saveResult() {
  if (!generatedResult) {
    alert('저장할 결과가 없습니다.');
    return;
  }

  try {
    const res = await fetch('/api/education/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...generatedResult.input,
        result: generatedResult.output
      })
    });

    const data = await res.json();

    if (data.status === 'ok') {
      alert('저장되었습니다!\n파일명: ' + data.filename);
    } else {
      alert('저장 실패: ' + data.message);
    }
  } catch (err) {
    console.error(err);
    alert('저장 중 오류가 발생했습니다.');
  }
}

function resetForm() {
  if (!confirm('입력 내용을 모두 초기화하시겠습니까?')) return;

  // 입력 필드 초기화
  document.querySelectorAll('input[type="text"], input[type="number"], textarea').forEach(el => {
    el.value = '';
  });

  // select 초기화
  document.getElementById('edu-program-type').value = 'choir_training';
  document.getElementById('edu-frequency').value = 'weekly';
  document.getElementById('edu-level').value = 'mixed';
  document.getElementById('edu-budget').value = 'mid';
  document.getElementById('edu-tone').value = '장년';
  document.getElementById('edu-detail-level').value = 'normal';

  // 체크박스 초기화
  document.getElementById('opt-curriculum').checked = true;
  document.getElementById('opt-detailed').checked = true;
  document.getElementById('opt-announcement').checked = true;
  document.getElementById('opt-homework').checked = true;
  document.getElementById('opt-evaluation').checked = false;

  // 부목표 초기화
  const subGoalsList = document.getElementById('sub-goals-list');
  subGoalsList.innerHTML = `
    <div class="sub-goal-item">
      <input type="text" placeholder="부목표 1">
      <button type="button" class="btn-remove-goal" onclick="removeSubGoal(this)">×</button>
    </div>
  `;

  // 장비 초기화
  equipmentList = ['피아노', '프로젝터'];
  renderEquipmentTags();

  // custom type row 숨기기
  document.getElementById('custom-type-row').style.display = 'none';

  // 결과 섹션 숨기기
  document.getElementById('result-section').classList.remove('show');

  generatedResult = null;
}
