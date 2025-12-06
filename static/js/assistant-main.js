/**
 * Personal AI Assistant - Main Module
 * Dashboard functionality for managing events, tasks, and Mac sync
 */

const AssistantMain = (() => {
  // State
  let dashboardData = null;
  let parsedData = null;
  let selectedFile = null;
  let underAttendingData = [];
  let selectedPeople = [];

  // ===== Initialization =====
  async function init() {
    console.log('[Assistant] Initializing...');

    // Set today's date and greeting
    updateGreeting();
    setTodayDate();

    // Load dashboard data
    await loadDashboard();

    // Load news
    await loadNews();

    // Initialize attendance section
    initUploadDate();
    initStyleButtons();
    initDragDrop();

    // Check Google integrations status
    checkGcalAuth();
    checkGsheetsAuth();
    checkWebhookStatus();

    // Load video schedule from Google Sheets
    loadVideoSchedule();
  }

  function updateGreeting() {
    const hour = new Date().getHours();
    let greeting = 'Good Morning!';
    let message = "Today's schedule and news at a glance";

    if (hour >= 12 && hour < 17) {
      greeting = 'Good Afternoon!';
      message = "Check your afternoon schedule";
    } else if (hour >= 17 && hour < 21) {
      greeting = 'Good Evening!';
      message = "Review today's progress";
    } else if (hour >= 21 || hour < 5) {
      greeting = 'Good Night!';
      message = "Prepare for tomorrow";
    }

    const greetingEl = document.getElementById('greeting-text');
    const messageEl = document.getElementById('greeting-message');
    if (greetingEl) greetingEl.textContent = greeting;
    if (messageEl) messageEl.textContent = message;
  }

  function setTodayDate() {
    const today = new Date();
    const options = { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' };
    const dateEl = document.getElementById('today-date');
    if (dateEl) dateEl.textContent = today.toLocaleDateString('ko-KR', options);
  }

  // ===== News Functions =====
  async function loadNews() {
    const container = document.getElementById('news-container');
    const timeEl = document.getElementById('news-time');

    if (!container) return;

    container.innerHTML = `
      <div class="news-loading">
        <div class="spinner"></div>
        <p>Loading today's news...</p>
      </div>
    `;

    try {
      const response = await fetch('/assistant/api/news');
      const data = await response.json();

      if (data.success && data.news && data.news.length > 0) {
        renderNewsTable(data.news);

        if (timeEl && data.updated_at) {
          const updateTime = new Date(data.updated_at);
          timeEl.textContent = updateTime.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) + ' Update';
        }
      } else {
        container.innerHTML = `
          <div class="news-empty">
            <p>No news available. Click Refresh to load.</p>
          </div>
        `;
      }
    } catch (error) {
      console.error('[Assistant] News load error:', error);
      container.innerHTML = `
        <div class="news-empty">
          <p>Failed to load news. Please try again.</p>
        </div>
      `;
    }
  }

  // Store news data for script generation
  let newsData = [];
  let currentScript = '';

  function renderNewsTable(news) {
    const container = document.getElementById('news-container');
    if (!container) return;

    // Store news data for later use
    newsData = news;

    // Card-style layout (more compact)
    const html = `
      <div class="news-list">
        ${news.map((item, idx) => `
          <div class="news-item">
            <div class="news-item-left">
              <span class="news-category ${item.category === '국내' ? 'domestic' : 'international'}">
                ${item.category}
              </span>
              <span class="video-score ${item.video_potential}">${getVideoScoreIcon(item.video_potential)}</span>
            </div>
            <div class="news-item-content">
              ${item.pub_date ? `<div class="news-time">🕐 ${escapeHtml(item.pub_date)}</div>` : ''}
              <div class="news-title">
                ${item.link
                  ? `<a href="${escapeHtml(item.link)}" target="_blank" rel="noopener">${escapeHtml(item.title)}</a>`
                  : escapeHtml(item.title)
                }
              </div>
              <div class="news-summary">${escapeHtml(item.summary || '')}</div>
              ${item.interpretation ? `
                <div class="news-interpretation">💡 ${escapeHtml(item.interpretation)}</div>
              ` : ''}
            </div>
            <div class="news-item-right">
              <button class="btn-script" onclick="AssistantMain.generateScript(${idx})">
                ✍️ 대본
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;

    container.innerHTML = html;
  }

  function getVideoScoreIcon(potential) {
    switch (potential) {
      case 'high': return '🔥';
      case 'medium': return '👍';
      case 'low': return '➖';
      default: return '❓';
    }
  }

  async function refreshNews() {
    const container = document.getElementById('news-container');
    const refreshIcon = document.getElementById('refresh-icon');
    const timeEl = document.getElementById('news-time');

    if (!container) return;

    if (refreshIcon) refreshIcon.style.animation = 'spin 1s linear infinite';
    container.innerHTML = `
      <div class="news-loading">
        <div class="spinner"></div>
        <p>Refreshing news...</p>
      </div>
    `;

    try {
      const response = await fetch('/assistant/api/news/refresh', { method: 'POST' });
      const data = await response.json();

      if (data.success && data.news) {
        renderNewsTable(data.news);

        if (timeEl && data.updated_at) {
          const updateTime = new Date(data.updated_at);
          timeEl.textContent = updateTime.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) + ' Update';
        }
      } else {
        container.innerHTML = `
          <div class="news-empty">
            <p>${data.error || 'Failed to refresh news'}</p>
          </div>
        `;
      }
    } catch (error) {
      console.error('[Assistant] News refresh error:', error);
      container.innerHTML = `
        <div class="news-empty">
          <p>Network error. Please try again.</p>
        </div>
      `;
    } finally {
      if (refreshIcon) refreshIcon.style.animation = '';
    }
  }

  // ===== Script Generation Functions =====
  async function generateScript(newsIndex) {
    const news = newsData[newsIndex];
    if (!news) {
      alert('뉴스 데이터를 찾을 수 없습니다.');
      return;
    }

    // Open modal and show loading
    const modal = document.getElementById('script-modal');
    const modalBody = document.getElementById('script-modal-body');
    const copyBtn = document.getElementById('btn-copy-script');

    modal.style.display = 'flex';
    copyBtn.style.display = 'none';
    modalBody.innerHTML = `
      <div class="script-info">
        <h4>${escapeHtml(news.title)}</h4>
        <p>${escapeHtml(news.summary || '')}</p>
      </div>
      <div class="script-loading">
        <div class="spinner" style="width: 50px; height: 50px; border-width: 4px;"></div>
        <p>GPT가 10분 분량의 유튜브 대본을 생성하고 있습니다...</p>
        <p style="font-size: 0.8rem; color: var(--text-muted);">약 30초~1분 소요됩니다</p>
      </div>
    `;

    try {
      const response = await fetch('/assistant/api/news/script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: news.title,
          summary: news.summary || '',
          interpretation: news.interpretation || '',
          category: news.category
        })
      });

      const data = await response.json();

      if (data.success && data.script) {
        currentScript = data.script;

        // Format script with section highlighting
        const formattedScript = formatScript(data.script);

        modalBody.innerHTML = `
          <div class="script-info">
            <h4>${escapeHtml(news.title)}</h4>
            <p>${escapeHtml(news.summary || '')}</p>
          </div>
          <div class="script-output">${formattedScript}</div>
        `;
        copyBtn.style.display = 'inline-flex';
      } else {
        modalBody.innerHTML = `
          <div class="script-info">
            <h4>${escapeHtml(news.title)}</h4>
          </div>
          <div class="news-empty" style="color: var(--danger-color);">
            <p>대본 생성 실패: ${escapeHtml(data.error || '알 수 없는 오류')}</p>
          </div>
        `;
      }
    } catch (error) {
      console.error('[Assistant] Script generation error:', error);
      modalBody.innerHTML = `
        <div class="news-empty" style="color: var(--danger-color);">
          <p>네트워크 오류가 발생했습니다. 다시 시도해주세요.</p>
        </div>
      `;
    }
  }

  function formatScript(script) {
    // Highlight section markers like [오프닝], [배경 설명] etc.
    let formatted = escapeHtml(script);

    // Highlight section markers
    formatted = formatted.replace(/\[([^\]]+)\]/g, '<span class="scene-marker">[$1]</span>');

    // Highlight time markers like (30초), (2분) etc.
    formatted = formatted.replace(/\((\d+[분초]?[~\s]*\d*[분초]?)\)/g, '<span style="color: #a78bfa;">($1)</span>');

    return formatted;
  }

  function closeScriptModal() {
    const modal = document.getElementById('script-modal');
    modal.style.display = 'none';
    currentScript = '';
  }

  async function copyScript() {
    if (!currentScript) {
      alert('복사할 대본이 없습니다.');
      return;
    }

    try {
      await navigator.clipboard.writeText(currentScript);

      // Visual feedback
      const copyBtn = document.getElementById('btn-copy-script');
      const originalText = copyBtn.innerHTML;
      copyBtn.innerHTML = '✓ 복사됨!';
      copyBtn.style.background = 'var(--primary-color)';

      setTimeout(() => {
        copyBtn.innerHTML = originalText;
        copyBtn.style.background = '';
      }, 2000);
    } catch (err) {
      console.error('[Assistant] Copy failed:', err);
      alert('복사에 실패했습니다. 대본을 직접 선택해서 복사해주세요.');
    }
  }

  // Initialize drag and drop for file upload
  function initDragDrop() {
    const uploadZone = document.getElementById('upload-zone');
    if (!uploadZone) return;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      uploadZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
      e.preventDefault();
      e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
      uploadZone.addEventListener(eventName, () => {
        uploadZone.classList.add('dragover');
      }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      uploadZone.addEventListener(eventName, () => {
        uploadZone.classList.remove('dragover');
      }, false);
    });

    uploadZone.addEventListener('drop', (e) => {
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        const file = files[0];
        const fileName = file.name.toLowerCase();
        if (fileName.endsWith('.csv') || fileName.endsWith('.xlsx') || fileName.endsWith('.xls')) {
          selectedFile = file;
          document.getElementById('btn-upload').disabled = false;
          uploadZone.querySelector('.file-upload-text').innerHTML = `
            <strong>${escapeHtml(file.name)}</strong><br>
            <small>파일 선택됨 - 업로드 버튼을 클릭하세요</small>
          `;
        } else {
          alert('CSV 또는 XLSX 파일만 업로드 가능합니다.');
        }
      }
    }, false);
  }

  // ===== Dashboard Loading =====
  async function loadDashboard() {
    try {
      const response = await fetch('/assistant/api/dashboard');
      const data = await response.json();

      if (data.success) {
        dashboardData = data;
        renderDashboard(data);
      } else {
        console.error('[Assistant] Dashboard load error:', data.error);
        showError('Failed to load dashboard');
      }
    } catch (error) {
      console.error('[Assistant] Dashboard fetch error:', error);
      showError('Network error');
    }
  }

  // ===== Rendering =====
  function renderDashboard(data) {
    // Today's Events
    renderEvents('today-events', data.today_events);

    // Week Events
    renderEvents('week-events', data.week_events);

    // Pending Tasks
    renderTasks('pending-tasks', data.pending_tasks);

    // Pending Sync
    renderPendingSync('pending-sync', data.pending_sync);
  }

  function renderEvents(containerId, events) {
    const container = document.getElementById(containerId);
    const showDate = containerId === 'week-events';  // 이번주 섹션에서는 날짜 표시

    if (!events || events.length === 0) {
      container.innerHTML = `
        <div class="empty">
          <div class="empty-icon">📅</div>
          <div>No events scheduled</div>
        </div>
      `;
      return;
    }

    container.innerHTML = events.map(event => {
      const startTime = event.start_time ? formatTime(event.start_time) : '';
      const startDate = event.start_time ? formatDateShort(event.start_time) : '';
      const category = event.category ? `<span class="schedule-category">${escapeHtml(event.category)}</span>` : '';
      const syncBadge = getScheduleSyncBadge(event.sync_status);
      const location = event.location ? `<span class="schedule-location">📍 ${escapeHtml(event.location)}</span>` : '';
      // 이벤트 제목에서 대괄호 제거
      const title = event.title ? event.title.replace(/^\[|\]$/g, '') : '';
      // 날짜+시간 표시 (이번주 섹션) 또는 시간만 표시 (오늘 섹션)
      const timeDisplay = showDate ? `${startDate}<br>${startTime}` : startTime;
      const timeClass = showDate ? 'schedule-time date-time' : 'schedule-time';

      return `
        <div class="schedule-item">
          <div class="${timeClass}">${timeDisplay}</div>
          <div class="schedule-content">
            <div class="schedule-title" title="${escapeHtml(title)}">${escapeHtml(title)}</div>
            <div class="schedule-meta">${category}${syncBadge}${location}</div>
          </div>
        </div>
      `;
    }).join('');
  }

  function formatDateShort(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  }

  function getScheduleSyncBadge(status) {
    if (status === 'synced') {
      return '<span class="schedule-sync synced">✓ Synced</span>';
    } else if (status === 'pending_to_mac') {
      return '<span class="schedule-sync pending">⏳ Pending</span>';
    }
    return '';
  }

  function renderTasks(containerId, tasks) {
    const container = document.getElementById(containerId);

    if (!tasks || tasks.length === 0) {
      container.innerHTML = `
        <div class="empty">
          <div class="empty-icon">✅</div>
          <div>No pending tasks</div>
        </div>
      `;
      return;
    }

    container.innerHTML = tasks.map(task => {
      const dueDate = task.due_date ? formatDate(task.due_date) : '';
      const priority = task.priority || 'medium';
      const category = task.category ? `<span class="schedule-category">${escapeHtml(task.category)}</span>` : '';
      const syncBadge = getScheduleSyncBadge(task.sync_status);
      const isOverdue = task.due_date && new Date(task.due_date) < new Date() && !task.is_completed;
      const dueDateClass = isOverdue ? 'task-due overdue' : 'task-due';

      return `
        <div class="task-item" onclick="AssistantMain.completeTask(${task.id})">
          <div class="task-checkbox">
            <span style="font-size: 10px;">✓</span>
          </div>
          <div class="task-content">
            <div class="task-title">
              <span class="task-priority ${priority}"></span>
              ${escapeHtml(task.title)}
            </div>
            <div class="task-meta">
              ${dueDate ? `<span class="${dueDateClass}">📅 ${dueDate}</span>` : ''}
              ${category}${syncBadge}
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  function renderPendingSync(containerId, syncInfo) {
    const container = document.getElementById(containerId);

    if (!syncInfo || syncInfo.total === 0) {
      container.innerHTML = '<div class="empty">All synced!</div>';
      document.getElementById('btn-sync').disabled = true;
      return;
    }

    document.getElementById('btn-sync').disabled = false;
    container.innerHTML = `
      <div class="item">
        <div class="item-content">
          <div class="item-title">${syncInfo.events} events, ${syncInfo.tasks} tasks</div>
          <div class="item-meta">Waiting to sync to Mac Calendar/Reminders</div>
        </div>
      </div>
    `;
  }

  // ===== 통합 AI 분석 (GPT-5.1) =====
  async function analyzeUnified() {
    const inputBox = document.getElementById('input-box');
    const text = inputBox.value.trim();
    const statusEl = document.getElementById('analyze-status');

    if (!text) {
      alert('분석할 텍스트를 입력해주세요');
      return;
    }

    const btn = document.getElementById('btn-analyze');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="loading"></span> 분석 중...';
    btn.disabled = true;
    if (statusEl) statusEl.textContent = 'GPT-5.1이 분석 중입니다...';

    try {
      const response = await fetch('/assistant/api/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });

      const data = await response.json();

      if (data.success) {
        parsedData = data.parsed;
        showUnifiedResult(data.parsed);
        if (statusEl) statusEl.textContent = '분석 완료!';
      } else {
        alert('분석 실패: ' + data.error);
        if (statusEl) statusEl.textContent = '';
      }
    } catch (error) {
      console.error('[Assistant] Parse error:', error);
      alert('네트워크 오류');
      if (statusEl) statusEl.textContent = '';
    } finally {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  }

  function showUnifiedResult(parsed) {
    const resultDiv = document.getElementById('parsed-result');
    const eventsDiv = document.getElementById('parsed-events');
    const tasksDiv = document.getElementById('parsed-tasks');
    const peopleDiv = document.getElementById('parsed-people');
    const projectsDiv = document.getElementById('parsed-projects');

    // 일정 (Events)
    if (parsed.events && parsed.events.length > 0) {
      eventsDiv.innerHTML = `
        <div class="parsed-section">
          <h5>📅 일정 (${parsed.events.length})</h5>
          ${parsed.events.map((e, i) => `
            <div class="parsed-item">
              <div>
                <strong>${escapeHtml(e.title)}</strong>
                <span class="item-meta">${e.date || ''} ${e.time || ''}</span>
              </div>
              <span class="item-category">${e.category || ''}</span>
            </div>
          `).join('')}
        </div>
      `;
    } else {
      eventsDiv.innerHTML = '';
    }

    // 할일 (Tasks)
    if (parsed.tasks && parsed.tasks.length > 0) {
      tasksDiv.innerHTML = `
        <div class="parsed-section">
          <h5>✅ 할일 (${parsed.tasks.length})</h5>
          ${parsed.tasks.map((t, i) => `
            <div class="parsed-item">
              <div>
                <strong>${escapeHtml(t.title)}</strong>
                <span class="item-meta">${t.due_date || '기한 없음'}</span>
              </div>
              <span class="priority-badge ${t.priority || 'normal'}">${t.priority || 'normal'}</span>
            </div>
          `).join('')}
        </div>
      `;
    } else {
      tasksDiv.innerHTML = '';
    }

    // 인물 (People)
    if (parsed.people && parsed.people.length > 0) {
      peopleDiv.innerHTML = `
        <div class="parsed-section">
          <h5>👤 인물 (${parsed.people.length})</h5>
          ${parsed.people.map((p, i) => `
            <div class="parsed-item">
              <div>
                <strong>${escapeHtml(p.name)}</strong>
                ${p.role ? `<span class="role-badge">${escapeHtml(p.role)}</span>` : ''}
              </div>
              <span class="item-meta">${escapeHtml(p.notes || '')}</span>
            </div>
          `).join('')}
        </div>
      `;
    } else {
      peopleDiv.innerHTML = '';
    }

    // 프로젝트 (Projects)
    if (parsed.projects && parsed.projects.length > 0) {
      projectsDiv.innerHTML = `
        <div class="parsed-section">
          <h5>📁 프로젝트 (${parsed.projects.length})</h5>
          ${parsed.projects.map((pr, i) => `
            <div class="parsed-item">
              <div>
                <strong>${escapeHtml(pr.name)}</strong>
                ${pr.end_date ? `<span class="item-meta">~${pr.end_date}</span>` : ''}
              </div>
              <span class="project-status-badge ${pr.status || 'active'}">${pr.status || 'active'}</span>
            </div>
          `).join('')}
        </div>
      `;
    } else {
      projectsDiv.innerHTML = '';
    }

    resultDiv.classList.add('show');
  }

  async function saveUnifiedData() {
    if (!parsedData) {
      alert('저장할 데이터가 없습니다');
      return;
    }

    const btn = event.target;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="loading"></span> 저장 중...';
    btn.disabled = true;

    try {
      // save_to_db 옵션으로 한 번에 저장
      const response = await fetch('/assistant/api/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: document.getElementById('input-box').value.trim(),
          save_to_db: true
        })
      });

      const data = await response.json();

      if (data.success) {
        const counts = [];
        if (data.saved_events?.length) counts.push(`일정 ${data.saved_events.length}개`);
        if (data.saved_tasks?.length) counts.push(`할일 ${data.saved_tasks.length}개`);
        if (data.saved_people?.length) counts.push(`인물 ${data.saved_people.length}개`);
        if (data.saved_projects?.length) counts.push(`프로젝트 ${data.saved_projects.length}개`);

        showToast(`저장 완료: ${counts.join(', ')}`, 'success');

        // Clear and reload
        document.getElementById('input-box').value = '';
        document.getElementById('parsed-result').classList.remove('show');
        document.getElementById('analyze-status').textContent = '';
        parsedData = null;
        await loadDashboard();
      } else {
        alert('저장 실패: ' + data.error);
      }
    } catch (error) {
      console.error('[Assistant] Save error:', error);
      alert('네트워크 오류');
    } finally {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  }

  // 기존 함수 유지 (호환성)
  async function analyzeInput() { return analyzeUnified(); }
  async function saveParsedData() { return saveUnifiedData(); }

  // ===== Task Actions =====
  async function completeTask(taskId) {
    try {
      const response = await fetch(`/assistant/api/tasks/${taskId}/complete`, {
        method: 'POST'
      });

      const data = await response.json();
      if (data.success) {
        await loadDashboard();
      } else {
        alert('Failed to complete task: ' + data.error);
      }
    } catch (error) {
      console.error('[Assistant] Complete task error:', error);
      alert('Network error');
    }
  }

  // ===== Task Modal =====
  let selectedDueDate = null;
  let selectedCategory = '';

  function addTask() {
    // Reset and open modal
    selectedDueDate = null;
    selectedCategory = '';
    document.getElementById('task-title').value = '';
    document.getElementById('task-due-date').value = '';
    document.getElementById('task-due-date').style.display = 'none';

    // Reset button states
    document.querySelectorAll('.date-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.cat-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector('.date-btn[data-date="none"]').classList.add('active');
    document.querySelector('.cat-btn[data-cat=""]').classList.add('active');

    document.getElementById('task-modal').style.display = 'flex';
    document.getElementById('task-title').focus();
  }

  function closeTaskModal() {
    document.getElementById('task-modal').style.display = 'none';
  }

  function setDueDate(type) {
    // Update button states
    document.querySelectorAll('.date-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.date-btn[data-date="${type}"]`).classList.add('active');

    const dateInput = document.getElementById('task-due-date');
    const today = new Date();

    switch(type) {
      case 'none':
        selectedDueDate = null;
        dateInput.style.display = 'none';
        break;
      case 'today':
        selectedDueDate = today.toISOString().split('T')[0];
        dateInput.style.display = 'none';
        break;
      case 'tomorrow':
        today.setDate(today.getDate() + 1);
        selectedDueDate = today.toISOString().split('T')[0];
        dateInput.style.display = 'none';
        break;
      case 'week':
        // This Sunday
        const daysUntilSunday = 7 - today.getDay();
        today.setDate(today.getDate() + daysUntilSunday);
        selectedDueDate = today.toISOString().split('T')[0];
        dateInput.style.display = 'none';
        break;
      case 'custom':
        dateInput.style.display = 'block';
        dateInput.focus();
        break;
    }
  }

  function setCategory(cat) {
    selectedCategory = cat;
    document.querySelectorAll('.cat-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.cat-btn[data-cat="${cat}"]`).classList.add('active');
  }

  async function saveTask() {
    const title = document.getElementById('task-title').value.trim();
    if (!title) {
      alert('제목을 입력하세요.');
      return;
    }

    // Get custom date if selected
    const customDate = document.getElementById('task-due-date').value;
    const dueDate = customDate || selectedDueDate;

    try {
      const response = await fetch('/assistant/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          due_date: dueDate || null,
          priority: 'medium',
          category: selectedCategory
        })
      });

      const data = await response.json();
      if (data.success) {
        closeTaskModal();
        loadDashboard();
      } else {
        alert('태스크 추가 실패: ' + data.error);
      }
    } catch (err) {
      console.error('[Assistant] Add task error:', err);
      alert('Network error');
    }
  }

  // ===== Mac Sync =====
  async function syncToMac() {
    const btn = document.getElementById('btn-sync');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="loading"></span> Syncing...';
    btn.disabled = true;

    try {
      // Get pending items
      const response = await fetch('/assistant/api/sync/to-mac');
      const data = await response.json();

      if (data.success) {
        // Show sync data (for manual copy to Mac Shortcuts)
        const syncData = {
          events: data.events,
          tasks: data.tasks
        };

        console.log('[Assistant] Sync data for Mac:', syncData);

        // Copy to clipboard
        await navigator.clipboard.writeText(JSON.stringify(syncData, null, 2));
        alert(`Sync data copied to clipboard!\n\nEvents: ${data.events.length}\nTasks: ${data.tasks.length}\n\nPaste this in Mac Shortcuts to sync.`);
      } else {
        alert('Sync failed: ' + data.error);
      }
    } catch (error) {
      console.error('[Assistant] Sync error:', error);
      alert('Network error');
    } finally {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  }

  // ===== Google Calendar Integration =====
  let gcalAuthStatus = false;

  async function checkGcalAuth() {
    try {
      const response = await fetch('/assistant/api/gcal/auth-status');
      const data = await response.json();
      gcalAuthStatus = data.authenticated;
      updateGcalUI();
      return data.authenticated;
    } catch (error) {
      console.error('[Assistant] GCal auth check error:', error);
      return false;
    }
  }

  function updateGcalUI() {
    const authBtn = document.getElementById('btn-gcal-auth');
    const syncBtn = document.getElementById('btn-gcal-sync');
    const statusBadge = document.getElementById('gcal-status');
    const realtimeRow = document.getElementById('realtime-sync-row');

    if (gcalAuthStatus) {
      if (authBtn) authBtn.style.display = 'none';
      if (syncBtn) syncBtn.style.display = 'inline-flex';
      if (statusBadge) {
        statusBadge.textContent = '연결됨';
        statusBadge.className = 'status-badge connected';
      }
      if (realtimeRow) realtimeRow.style.display = 'flex';
    } else {
      if (authBtn) authBtn.style.display = 'inline-flex';
      if (syncBtn) syncBtn.style.display = 'none';
      if (statusBadge) {
        statusBadge.textContent = '미연결';
        statusBadge.className = 'status-badge disconnected';
      }
      if (realtimeRow) realtimeRow.style.display = 'none';
    }
  }

  async function authGcal() {
    try {
      const response = await fetch('/assistant/api/gcal/auth');
      const data = await response.json();
      if (data.auth_url) {
        // Open auth window
        window.open(data.auth_url, 'gcal_auth', 'width=500,height=600');
      } else if (data.error) {
        alert('Google Calendar 연결 오류: ' + data.error);
      } else {
        alert('Google Calendar 연결에 실패했습니다.');
      }
    } catch (error) {
      console.error('[Assistant] GCal auth error:', error);
      alert('Google Calendar 인증 오류: ' + error.message);
    }
  }

  async function syncGcal() {
    const btn = document.getElementById('btn-gcal-sync');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="loading"></span> 동기화 중...';
    btn.disabled = true;

    try {
      const response = await fetch('/assistant/api/gcal/sync', { method: 'POST' });
      const data = await response.json();

      if (data.success) {
        const msg = `Google Calendar 동기화 완료!\n\n` +
          `📤 업로드: ${data.synced_to_gcal}개\n` +
          `📥 가져오기: ${data.synced_from_gcal}개`;
        alert(msg);
        // Reload dashboard to show updated events
        await loadDashboard();
      } else {
        alert('동기화 실패: ' + data.error);
      }
    } catch (error) {
      console.error('[Assistant] GCal sync error:', error);
      alert('네트워크 오류');
    } finally {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  }

  // ===== Google Calendar Webhook (실시간 동기화) =====
  let webhookStatus = { active: false };

  async function checkWebhookStatus() {
    try {
      const response = await fetch('/assistant/api/gcal/webhook/status');
      const data = await response.json();
      webhookStatus = data;
      updateWebhookUI();
      return data;
    } catch (error) {
      console.error('[Assistant] Webhook status check error:', error);
      return { active: false };
    }
  }

  function updateWebhookUI() {
    const statusBadge = document.getElementById('realtime-status');
    const enableBtn = document.getElementById('btn-realtime-enable');
    const disableBtn = document.getElementById('btn-realtime-disable');

    if (webhookStatus.active) {
      if (statusBadge) {
        statusBadge.textContent = '활성';
        statusBadge.className = 'status-badge connected';
      }
      if (enableBtn) enableBtn.style.display = 'none';
      if (disableBtn) disableBtn.style.display = 'inline-flex';
    } else {
      if (statusBadge) {
        statusBadge.textContent = '비활성';
        statusBadge.className = 'status-badge disconnected';
      }
      if (enableBtn) enableBtn.style.display = 'inline-flex';
      if (disableBtn) disableBtn.style.display = 'none';
    }
  }

  async function enableRealtimeSync() {
    const btn = document.getElementById('btn-realtime-enable');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="loading"></span>';
    btn.disabled = true;

    try {
      const response = await fetch('/assistant/api/gcal/webhook/register', { method: 'POST' });
      const data = await response.json();

      if (data.success) {
        alert(`실시간 동기화 활성화!\n\n채널 만료: ${new Date(data.expiration).toLocaleString('ko-KR')}`);
        await checkWebhookStatus();
      } else {
        alert('활성화 실패: ' + data.error);
      }
    } catch (error) {
      console.error('[Assistant] Enable realtime error:', error);
      alert('네트워크 오류');
    } finally {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  }

  async function disableRealtimeSync() {
    if (!confirm('실시간 동기화를 비활성화하시겠습니까?')) return;

    const btn = document.getElementById('btn-realtime-disable');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="loading"></span>';
    btn.disabled = true;

    try {
      const response = await fetch('/assistant/api/gcal/webhook/stop', { method: 'POST' });
      const data = await response.json();

      if (data.success) {
        alert('실시간 동기화가 비활성화되었습니다.');
        await checkWebhookStatus();
      } else {
        alert('비활성화 실패: ' + data.error);
      }
    } catch (error) {
      console.error('[Assistant] Disable realtime error:', error);
      alert('네트워크 오류');
    } finally {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  }

  // ===== Google Sheets Integration =====
  let gsheetsAuthStatus = false;

  async function checkGsheetsAuth() {
    try {
      const response = await fetch('/assistant/api/gsheets/auth-status');
      const data = await response.json();
      gsheetsAuthStatus = data.authenticated;
      updateGsheetsUI();
      return data.authenticated;
    } catch (error) {
      console.error('[Assistant] GSheets auth check error:', error);
      return false;
    }
  }

  function updateGsheetsUI() {
    const authBtn = document.getElementById('btn-gsheets-auth');
    const exportBtns = document.getElementById('gsheets-export-btns');
    const statusBadge = document.getElementById('gsheets-status');

    if (gsheetsAuthStatus) {
      if (authBtn) authBtn.style.display = 'none';
      if (exportBtns) exportBtns.style.display = 'flex';
      if (statusBadge) {
        statusBadge.textContent = '연결됨';
        statusBadge.className = 'status-badge connected';
      }
    } else {
      if (authBtn) authBtn.style.display = 'inline-flex';
      if (exportBtns) exportBtns.style.display = 'none';
      if (statusBadge) {
        statusBadge.textContent = '미연결';
        statusBadge.className = 'status-badge disconnected';
      }
    }
  }

  async function authGsheets() {
    try {
      const response = await fetch('/assistant/api/gsheets/auth');
      const data = await response.json();
      if (data.auth_url) {
        window.open(data.auth_url, 'gsheets_auth', 'width=500,height=600');
      } else if (data.error) {
        alert('Google Sheets 연결 오류: ' + data.error);
      } else {
        alert('Google Sheets 연결에 실패했습니다.');
      }
    } catch (error) {
      console.error('[Assistant] GSheets auth error:', error);
      alert('Google Sheets 인증 오류: ' + error.message);
    }
  }

  async function exportPeopleToSheets() {
    const btn = event.target;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="loading"></span>';
    btn.disabled = true;

    try {
      const response = await fetch('/assistant/api/gsheets/export-people', { method: 'POST' });
      const data = await response.json();

      if (data.success) {
        alert(`인물 데이터 내보내기 완료!\n\n` +
          `📊 총 ${data.rows_written}개 행 저장\n` +
          `📄 스프레드시트: ${data.spreadsheet_id}`);
      } else {
        alert('내보내기 실패: ' + data.error);
      }
    } catch (error) {
      console.error('[Assistant] Export people error:', error);
      alert('네트워크 오류');
    } finally {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  }

  async function exportEventsToSheets() {
    const btn = event.target;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="loading"></span>';
    btn.disabled = true;

    try {
      const response = await fetch('/assistant/api/gsheets/export-events', { method: 'POST' });
      const data = await response.json();

      if (data.success) {
        alert(`일정 데이터 내보내기 완료!\n\n` +
          `📊 총 ${data.rows_written}개 행 저장\n` +
          `📄 스프레드시트: ${data.spreadsheet_id}`);
      } else {
        alert('내보내기 실패: ' + data.error);
      }
    } catch (error) {
      console.error('[Assistant] Export events error:', error);
      alert('네트워크 오류');
    } finally {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  }

  // Google OAuth callback handler (called from popup)
  window.handleGoogleAuthCallback = async function(service) {
    if (service === 'gcal') {
      await checkGcalAuth();
      if (gcalAuthStatus) {
        alert('Google Calendar 연결 완료!');
      }
    } else if (service === 'gsheets') {
      await checkGsheetsAuth();
      if (gsheetsAuthStatus) {
        alert('Google Sheets 연결 완료!');
        // Sheets 연결되면 영상 일정도 로드
        loadVideoSchedule();
      }
    }
  };

  // ===== Video Schedule (Google Sheets) =====
  async function loadVideoSchedule() {
    const container = document.getElementById('video-schedule');
    if (!container) return;

    try {
      const response = await fetch('/assistant/api/video-schedule');
      const data = await response.json();

      if (!data.success) {
        container.innerHTML = `<div class="empty" style="font-size: 0.8rem; color: var(--text-muted);">
          ${data.error || '데이터를 불러올 수 없습니다'}
        </div>`;
        return;
      }

      if (data.schedule.length === 0) {
        container.innerHTML = '<div class="empty">예정된 영상이 없습니다</div>';
        return;
      }

      container.innerHTML = data.schedule.map(item => {
        // 상태에 따른 스타일
        let statusClass = '';
        let statusIcon = '⏳';
        if (item.status === '완료') {
          statusClass = 'completed';
          statusIcon = '✅';
        } else if (item.status === '에러') {
          statusClass = 'error';
          statusIcon = '❌';
        } else if (item.status === '진행중') {
          statusIcon = '🔄';
        }

        // 예약 시간 포맷팅
        let timeDisplay = item.scheduled_time || '';
        if (timeDisplay) {
          try {
            const date = new Date(timeDisplay);
            if (!isNaN(date)) {
              timeDisplay = date.toLocaleString('ko-KR', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
              });
            }
          } catch (e) {}
        }

        return `
          <div class="schedule-item ${statusClass}" style="padding: 0.5rem; margin-bottom: 0.5rem; background: var(--bg-color); border-radius: 6px;">
            <span style="margin-right: 0.5rem;">${statusIcon}</span>
            <div style="flex: 1; min-width: 0;">
              <div style="font-size: 0.8rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                ${item.name || '(제목 없음)'}
              </div>
              <div style="font-size: 0.7rem; color: var(--text-muted);">
                ${timeDisplay}
              </div>
            </div>
          </div>
        `;
      }).join('');

    } catch (error) {
      console.error('[Assistant] Video schedule error:', error);
      container.innerHTML = '<div class="empty">네트워크 오류</div>';
    }
  }

  async function refreshVideoSchedule() {
    const container = document.getElementById('video-schedule');
    if (container) {
      container.innerHTML = '<div class="empty">Loading...</div>';
    }
    await loadVideoSchedule();
  }

  // ===== Section Navigation =====
  let currentSection = 'dashboard';

  function showSection(section) {
    console.log('[Assistant] Show section:', section);
    currentSection = section;

    // Hide all sections
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));

    // Show selected section
    const sectionEl = document.getElementById(`section-${section}`);
    if (sectionEl) {
      sectionEl.classList.add('active');
    }

    // Update sidebar active state
    document.querySelectorAll('.sidebar-item').forEach(item => {
      item.classList.remove('active');
      if (item.dataset.section === section) {
        item.classList.add('active');
      }
    });

    // Initialize section-specific content
    if (section === 'calendar') {
      initCalendar();
    } else if (section === 'tasks') {
      loadFullTasksList();
    } else if (section === 'attendance') {
      // Attendance section is already initialized
    } else if (section === 'people') {
      loadPeople();
    } else if (section === 'projects') {
      loadProjects();
    }
  }

  // ===== Calendar State & Functions =====
  let calendarDate = new Date();
  let calendarView = 'month';
  let selectedDate = null;
  let allEvents = [];

  async function initCalendar() {
    console.log('[Assistant] Initializing calendar');

    // Load all events
    try {
      const response = await fetch('/assistant/api/events');
      const data = await response.json();
      if (data.success) {
        allEvents = data.events || [];
      }
    } catch (err) {
      console.error('[Assistant] Failed to load events:', err);
    }

    // Render calendar
    renderCalendar();
  }

  function renderCalendar() {
    // Update title
    const year = calendarDate.getFullYear();
    const month = calendarDate.getMonth();
    document.getElementById('calendar-title').textContent =
      `${year}년 ${month + 1}월`;

    if (calendarView === 'month') {
      document.getElementById('month-view').style.display = 'block';
      document.getElementById('week-view').style.display = 'none';
      renderMonthView(year, month);
    } else {
      document.getElementById('month-view').style.display = 'none';
      document.getElementById('week-view').style.display = 'block';
      renderWeekView();
    }

    // Show today's events by default
    if (!selectedDate) {
      selectedDate = new Date();
    }
    renderSelectedDateEvents();
  }

  function renderMonthView(year, month) {
    const grid = document.getElementById('calendar-grid');

    // Keep headers, clear days
    const headers = Array.from(grid.querySelectorAll('.calendar-day-header'));
    grid.innerHTML = '';
    headers.forEach(h => grid.appendChild(h));

    // Get first day of month and total days
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startDayOfWeek = firstDay.getDay();
    const totalDays = lastDay.getDate();

    // Get previous month days to show
    const prevMonthLastDay = new Date(year, month, 0).getDate();

    // Today
    const today = new Date();
    const isCurrentMonth = today.getFullYear() === year && today.getMonth() === month;

    // Render previous month days
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      const dayNum = prevMonthLastDay - i;
      const dayEl = createCalendarDay(dayNum, true, false, false);
      grid.appendChild(dayEl);
    }

    // Render current month days
    for (let day = 1; day <= totalDays; day++) {
      const isToday = isCurrentMonth && today.getDate() === day;
      const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const isSelected = selectedDate && formatDateISO(selectedDate) === dateStr;
      const dayEvents = getEventsForDate(dateStr);
      const dayEl = createCalendarDay(day, false, isToday, isSelected, dayEvents, dateStr);
      grid.appendChild(dayEl);
    }

    // Render next month days to fill grid (6 rows = 42 cells)
    const cellsRendered = startDayOfWeek + totalDays;
    const cellsNeeded = Math.ceil(cellsRendered / 7) * 7;
    for (let day = 1; day <= cellsNeeded - cellsRendered; day++) {
      const dayEl = createCalendarDay(day, true, false, false);
      grid.appendChild(dayEl);
    }
  }

  function createCalendarDay(day, isOtherMonth, isToday, isSelected, events = [], dateStr = '') {
    const div = document.createElement('div');
    div.className = 'calendar-day';
    if (isOtherMonth) div.classList.add('other-month');
    if (isToday) div.classList.add('today');
    if (isSelected) div.classList.add('selected');

    if (dateStr) {
      div.onclick = () => selectCalendarDate(dateStr);
    }

    let html = `<div class="day-number">${day}</div>`;

    if (events && events.length > 0) {
      html += '<div class="day-events">';
      const maxShow = 2;
      events.slice(0, maxShow).forEach(e => {
        const isMac = e.source === 'mac_calendar';
        html += `<div class="day-event ${isMac ? 'mac' : ''}">${escapeHtml(e.title?.substring(0, 15) || '')}</div>`;
      });
      if (events.length > maxShow) {
        html += `<div class="day-event more">+${events.length - maxShow} more</div>`;
      }
      html += '</div>';
    }

    div.innerHTML = html;
    return div;
  }

  function getEventsForDate(dateStr) {
    return allEvents.filter(e => {
      if (!e.start_time) return false;
      const eventDate = e.start_time.split('T')[0];
      return eventDate === dateStr;
    });
  }

  function selectCalendarDate(dateStr) {
    selectedDate = new Date(dateStr);
    renderCalendar();
  }

  function renderSelectedDateEvents() {
    const dateStr = formatDateISO(selectedDate);
    const events = getEventsForDate(dateStr);

    // Update title
    const options = { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' };
    document.getElementById('selected-date-title').textContent =
      selectedDate.toLocaleDateString('ko-KR', options) + '의 일정';

    const container = document.getElementById('selected-date-events-list');

    if (events.length === 0) {
      container.innerHTML = '<div class="empty">이 날짜에 일정이 없습니다</div>';
      return;
    }

    container.innerHTML = events.map(event => {
      const startTime = event.start_time ? formatTime(event.start_time) : '';
      const category = event.category ? `<span class="item-category">${event.category}</span>` : '';
      const source = event.source === 'mac_calendar'
        ? '<span class="sync-badge sync-synced">📱 Mac</span>'
        : '';

      return `
        <div class="item event-item" onclick="AssistantMain.openEventModal(${event.id})" style="cursor: pointer;">
          <div class="item-time">${startTime}</div>
          <div class="item-content">
            <div class="item-title">${escapeHtml(event.title || '')}</div>
            <div class="item-meta">${category} ${source}</div>
          </div>
        </div>
      `;
    }).join('');
  }

  function renderWeekView() {
    const grid = document.getElementById('week-grid');
    grid.innerHTML = '';

    // Get start of week (Sunday)
    const weekStart = new Date(calendarDate);
    weekStart.setDate(weekStart.getDate() - weekStart.getDay());

    // Headers
    const today = new Date();
    grid.innerHTML = '<div class="week-day-header"></div>'; // Empty corner cell

    const dayNames = ['일', '월', '화', '수', '목', '금', '토'];
    for (let i = 0; i < 7; i++) {
      const date = new Date(weekStart);
      date.setDate(date.getDate() + i);
      const isToday = formatDateISO(date) === formatDateISO(today);

      grid.innerHTML += `
        <div class="week-day-header ${isToday ? 'today' : ''}">
          <div class="day-name">${dayNames[i]}</div>
          <div class="day-date">${date.getDate()}</div>
        </div>
      `;
    }

    // Time slots (simplified: show key hours)
    const hours = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20];

    hours.forEach(hour => {
      // Time label
      grid.innerHTML += `<div class="time-slot">${hour}:00</div>`;

      // Cells for each day
      for (let i = 0; i < 7; i++) {
        const date = new Date(weekStart);
        date.setDate(date.getDate() + i);
        const dateStr = formatDateISO(date);
        const dayEvents = getEventsForDate(dateStr).filter(e => {
          if (!e.start_time) return false;
          const eventHour = new Date(e.start_time).getHours();
          return eventHour === hour;
        });

        let cellHtml = '<div class="week-cell">';
        dayEvents.forEach(e => {
          cellHtml += `<div class="week-event">${escapeHtml(e.title?.substring(0, 10) || '')}</div>`;
        });
        cellHtml += '</div>';
        grid.innerHTML += cellHtml;
      }
    });
  }

  function calendarPrev() {
    if (calendarView === 'month') {
      calendarDate.setMonth(calendarDate.getMonth() - 1);
    } else {
      calendarDate.setDate(calendarDate.getDate() - 7);
    }
    renderCalendar();
  }

  function calendarNext() {
    if (calendarView === 'month') {
      calendarDate.setMonth(calendarDate.getMonth() + 1);
    } else {
      calendarDate.setDate(calendarDate.getDate() + 7);
    }
    renderCalendar();
  }

  function calendarToday() {
    calendarDate = new Date();
    selectedDate = new Date();
    renderCalendar();
  }

  function setCalendarView(view) {
    calendarView = view;

    // Update buttons
    document.querySelectorAll('.view-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.view === view);
    });

    renderCalendar();
  }

  function formatDateISO(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  // ===== Tasks Section Functions =====
  let allTasks = [];
  let taskFilter = 'all';

  async function loadFullTasksList() {
    console.log('[Assistant] Loading full tasks list');

    try {
      const response = await fetch('/assistant/api/tasks');
      const data = await response.json();

      if (data.success) {
        allTasks = data.tasks || [];
        updateTasksStats();
        renderFullTasksList();
      }
    } catch (err) {
      console.error('[Assistant] Failed to load tasks:', err);
    }
  }

  function updateTasksStats() {
    const today = formatDateISO(new Date());

    const total = allTasks.length;
    const completed = allTasks.filter(t => t.status === 'completed').length;
    const pending = allTasks.filter(t => t.status !== 'completed').length;
    const overdue = allTasks.filter(t => {
      if (t.status === 'completed') return false;
      if (!t.due_date) return false;
      return t.due_date < today;
    }).length;

    document.getElementById('stat-total').textContent = total;
    document.getElementById('stat-pending').textContent = pending;
    document.getElementById('stat-completed').textContent = completed;
    document.getElementById('stat-overdue').textContent = overdue;
  }

  function renderFullTasksList() {
    const container = document.getElementById('full-tasks-list');
    const today = formatDateISO(new Date());
    const weekEnd = new Date();
    weekEnd.setDate(weekEnd.getDate() + 7);
    const weekEndStr = formatDateISO(weekEnd);

    // Filter tasks
    let filteredTasks = allTasks;

    switch (taskFilter) {
      case 'pending':
        filteredTasks = allTasks.filter(t => t.status !== 'completed');
        break;
      case 'completed':
        filteredTasks = allTasks.filter(t => t.status === 'completed');
        break;
      case 'today':
        filteredTasks = allTasks.filter(t =>
          t.status !== 'completed' && t.due_date === today
        );
        break;
      case 'week':
        filteredTasks = allTasks.filter(t =>
          t.status !== 'completed' && t.due_date && t.due_date <= weekEndStr
        );
        break;
    }

    if (filteredTasks.length === 0) {
      container.innerHTML = `
        <div class="empty-tasks">
          <div class="empty-tasks-icon">✅</div>
          <p>${taskFilter === 'completed' ? '완료된 태스크가 없습니다' : '태스크가 없습니다'}</p>
        </div>
      `;
      return;
    }

    container.innerHTML = filteredTasks.map(task => {
      const isCompleted = task.status === 'completed';
      const isOverdue = !isCompleted && task.due_date && task.due_date < today;
      const isToday = task.due_date === today;

      let dueDateClass = '';
      if (isOverdue) dueDateClass = 'overdue';
      else if (isToday) dueDateClass = 'today';

      const dueDisplay = task.due_date
        ? `<span class="task-due ${dueDateClass}">📅 ${formatDate(task.due_date)}</span>`
        : '';
      const categoryDisplay = task.category
        ? `<span class="item-category">${task.category}</span>`
        : '';

      return `
        <div class="task-item ${isCompleted ? 'completed' : ''}">
          <div class="task-checkbox ${isCompleted ? 'checked' : ''}"
               onclick="AssistantMain.toggleTaskComplete(${task.id}, ${!isCompleted})">
            ${isCompleted ? '✓' : ''}
          </div>
          <div class="task-content">
            <div class="task-title">${escapeHtml(task.title)}</div>
            <div class="task-meta">
              ${dueDisplay}
              ${categoryDisplay}
            </div>
          </div>
          <div class="task-actions">
            <button class="task-action-btn delete" onclick="AssistantMain.deleteTask(${task.id})" title="삭제">
              🗑️
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  function filterTasks(filter) {
    taskFilter = filter;

    // Update filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.filter === filter);
    });

    renderFullTasksList();
  }

  async function quickAddTask() {
    const input = document.getElementById('quick-task-input');
    const title = input.value.trim();

    if (!title) {
      alert('태스크 제목을 입력하세요');
      return;
    }

    try {
      const response = await fetch('/assistant/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          priority: 'medium'
        })
      });

      const data = await response.json();
      if (data.success) {
        input.value = '';
        loadFullTasksList();
        // Also refresh dashboard if we go back
        loadDashboard();
      } else {
        alert('태스크 추가 실패: ' + data.error);
      }
    } catch (err) {
      console.error('[Assistant] Quick add task error:', err);
      alert('Network error');
    }
  }

  async function toggleTaskComplete(taskId, complete) {
    try {
      const endpoint = complete
        ? `/assistant/api/tasks/${taskId}/complete`
        : `/assistant/api/tasks/${taskId}/uncomplete`;

      const response = await fetch(endpoint, { method: 'POST' });
      const data = await response.json();

      if (data.success) {
        loadFullTasksList();
        loadDashboard();
      } else {
        alert('Failed: ' + data.error);
      }
    } catch (err) {
      console.error('[Assistant] Toggle task error:', err);
    }
  }

  async function deleteTask(taskId) {
    if (!confirm('이 태스크를 삭제하시겠습니까?')) return;

    try {
      const response = await fetch(`/assistant/api/tasks/${taskId}`, {
        method: 'DELETE'
      });
      const data = await response.json();

      if (data.success) {
        loadFullTasksList();
        loadDashboard();
      } else {
        alert('삭제 실패: ' + data.error);
      }
    } catch (err) {
      console.error('[Assistant] Delete task error:', err);
    }
  }

  // ===== Attendance Functions =====
  function showAttendanceTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`tab-${tabName}`).classList.add('active');

    // Update selected people display in messages tab
    if (tabName === 'messages') {
      updateSelectedPeopleDisplay();
    }
  }

  function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
      selectedFile = file;
      document.getElementById('btn-upload').disabled = false;

      // Update upload zone text
      const uploadZone = document.getElementById('upload-zone');
      uploadZone.querySelector('.file-upload-text').innerHTML = `
        <strong>${escapeHtml(file.name)}</strong><br>
        <small>파일 선택됨 - 업로드 버튼을 클릭하세요</small>
      `;
    }
  }

  async function uploadAttendance() {
    if (!selectedFile) {
      alert('파일을 먼저 선택해주세요.');
      return;
    }

    const uploadDate = document.getElementById('upload-date').value;
    const groupName = document.getElementById('upload-group').value;

    const formData = new FormData();
    formData.append('file', selectedFile);
    if (uploadDate) formData.append('date', uploadDate);
    if (groupName) formData.append('group_name', groupName);

    const btn = document.getElementById('btn-upload');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading"></span> 업로드 중...';

    try {
      const response = await fetch('/assistant/api/attendance/upload', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();
      const resultDiv = document.getElementById('upload-result');
      resultDiv.style.display = 'block';

      if (data.success) {
        resultDiv.innerHTML = `
          <div style="color: var(--primary-color); padding: 1rem; background: rgba(76,175,80,0.1); border-radius: 8px;">
            <strong>✓ ${data.message}</strong>
            ${data.sample ? `<br><small>샘플: ${data.sample.map(r => r.name).join(', ')}</small>` : ''}
          </div>
        `;
        // Reset
        selectedFile = null;
        document.getElementById('attendance-file').value = '';
        document.getElementById('upload-zone').querySelector('.file-upload-text').innerHTML = `
          CSV 또는 XLSX 파일을 드래그하거나 클릭하여 선택<br>
          <small>형식: name, date, status, group_name</small>
        `;
      } else {
        resultDiv.innerHTML = `
          <div style="color: var(--danger-color); padding: 1rem; background: rgba(244,67,54,0.1); border-radius: 8px;">
            <strong>✗ 오류:</strong> ${escapeHtml(data.error)}
          </div>
        `;
      }
    } catch (error) {
      console.error('[Assistant] Upload error:', error);
      alert('업로드 중 오류가 발생했습니다.');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '업로드';
    }
  }

  async function findUnderAttending() {
    const weeks = document.getElementById('absent-weeks').value;
    const group = document.getElementById('filter-group').value;

    const listDiv = document.getElementById('under-attending-list');
    listDiv.innerHTML = '<div class="empty"><span class="loading"></span> 조회 중...</div>';

    try {
      let url = `/assistant/api/attendance/under-attending?weeks=${weeks}`;
      if (group) url += `&group=${encodeURIComponent(group)}`;

      const response = await fetch(url);
      const data = await response.json();

      if (data.success) {
        underAttendingData = data.under_attending || [];

        if (underAttendingData.length === 0) {
          listDiv.innerHTML = `
            <div class="empty">
              ${data.message || '기준에 해당하는 부진자가 없습니다.'}
            </div>
          `;
          return;
        }

        listDiv.innerHTML = underAttendingData.map((person, idx) => `
          <div class="person-item">
            <input type="checkbox" id="person-${idx}" data-index="${idx}"
                   onchange="AssistantMain.togglePersonSelection(${idx})">
            <div class="person-info">
              <div class="person-name">${escapeHtml(person.name)}</div>
              <div class="person-meta">
                ${person.group_name ? `<span class="item-category">${escapeHtml(person.group_name)}</span>` : ''}
                마지막 출석: ${person.last_attended_date || '기록 없음'}
              </div>
            </div>
            <span class="absent-badge">${person.absent_weeks}주 결석</span>
          </div>
        `).join('');
      } else {
        listDiv.innerHTML = `
          <div class="empty" style="color: var(--danger-color);">
            오류: ${escapeHtml(data.error)}
          </div>
        `;
      }
    } catch (error) {
      console.error('[Assistant] Find under-attending error:', error);
      listDiv.innerHTML = '<div class="empty" style="color: var(--danger-color);">조회 중 오류가 발생했습니다.</div>';
    }
  }

  function togglePersonSelection(index) {
    const person = underAttendingData[index];
    const checkbox = document.getElementById(`person-${index}`);

    if (checkbox.checked) {
      if (!selectedPeople.find(p => p.name === person.name)) {
        selectedPeople.push(person);
      }
    } else {
      selectedPeople = selectedPeople.filter(p => p.name !== person.name);
    }

    updateSelectedPeopleDisplay();
    document.getElementById('btn-generate-msg').disabled = selectedPeople.length === 0;
  }

  function selectAllUnderAttending() {
    const checkboxes = document.querySelectorAll('#under-attending-list input[type="checkbox"]');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);

    checkboxes.forEach(cb => {
      cb.checked = !allChecked;
    });

    if (allChecked) {
      selectedPeople = [];
    } else {
      selectedPeople = [...underAttendingData];
    }

    updateSelectedPeopleDisplay();
    document.getElementById('btn-generate-msg').disabled = selectedPeople.length === 0;
  }

  function updateSelectedPeopleDisplay() {
    const div = document.getElementById('selected-people');
    if (selectedPeople.length === 0) {
      div.innerHTML = '<p style="color: var(--text-secondary);">선택된 대상자가 없습니다.</p>';
    } else {
      div.innerHTML = `
        <p><strong>선택된 대상자 (${selectedPeople.length}명):</strong></p>
        <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
          ${selectedPeople.map(p => `
            <span class="item-category">${escapeHtml(p.name)}</span>
          `).join('')}
        </div>
      `;
    }
  }

  async function generateMessages() {
    if (selectedPeople.length === 0) {
      alert('부진자 탭에서 대상자를 먼저 선택해주세요.');
      return;
    }

    // Get selected profile (youth/adult)
    const activeProfileBtn = document.querySelector('#profile-selector .style-btn.active');
    const profile = activeProfileBtn ? activeProfileBtn.dataset.profile : 'adult';

    // Get selected style
    const activeStyleBtn = document.querySelector('#style-selector .style-btn.active');
    const style = activeStyleBtn ? activeStyleBtn.dataset.style : '따뜻한';

    const btn = document.getElementById('btn-generate-msg');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading"></span> 생성 중...';

    const messageListDiv = document.getElementById('message-list');
    const profileLabel = profile === 'youth' ? '청년부 전도사' : '장년 목사';
    messageListDiv.innerHTML = `<div class="empty"><span class="loading"></span> GPT가 ${profileLabel} 톤으로 문자를 생성하고 있습니다...</div>`;

    try {
      const response = await fetch('/assistant/api/attendance/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          people: selectedPeople,
          style: style,
          profile: profile
        })
      });

      const data = await response.json();

      if (data.success) {
        const messages = data.messages || [];

        if (messages.length === 0) {
          messageListDiv.innerHTML = '<div class="empty">생성된 문자가 없습니다.</div>';
          return;
        }

        messageListDiv.innerHTML = messages.map((msg, idx) => `
          <div class="message-item">
            <div class="message-header">
              <span class="message-name">${escapeHtml(msg.name)}</span>
              <button class="copy-btn" onclick="AssistantMain.copyMessage(${idx})">복사</button>
            </div>
            <div class="message-text" id="message-text-${idx}" onclick="AssistantMain.copyMessage(${idx})">
              ${escapeHtml(msg.message)}
            </div>
          </div>
        `).join('');

        // Store messages for copy function
        window._generatedMessages = messages;
      } else {
        messageListDiv.innerHTML = `
          <div class="empty" style="color: var(--danger-color);">
            오류: ${escapeHtml(data.error)}
          </div>
        `;
      }
    } catch (error) {
      console.error('[Assistant] Generate messages error:', error);
      messageListDiv.innerHTML = '<div class="empty" style="color: var(--danger-color);">문자 생성 중 오류가 발생했습니다.</div>';
    } finally {
      btn.disabled = false;
      btn.innerHTML = '문자 생성 (GPT)';
    }
  }

  async function copyMessage(index) {
    const messages = window._generatedMessages || [];
    if (messages[index]) {
      try {
        await navigator.clipboard.writeText(messages[index].message);

        // Visual feedback
        const textDiv = document.getElementById(`message-text-${index}`);
        const originalBg = textDiv.style.background;
        textDiv.style.background = 'rgba(76, 175, 80, 0.2)';
        setTimeout(() => {
          textDiv.style.background = originalBg || '';
        }, 300);
      } catch (err) {
        console.error('[Assistant] Copy failed:', err);
        alert('복사에 실패했습니다. 텍스트를 직접 선택해주세요.');
      }
    }
  }

  // Initialize style button and profile selector click handlers
  function initStyleButtons() {
    // Profile selector (youth/adult)
    const profileSelector = document.getElementById('profile-selector');
    if (profileSelector) {
      profileSelector.querySelectorAll('.style-btn').forEach(btn => {
        btn.addEventListener('click', function() {
          profileSelector.querySelectorAll('.style-btn').forEach(b => b.classList.remove('active'));
          this.classList.add('active');
        });
      });
    }

    // Style selector (따뜻한/격려/공식적인)
    const styleSelector = document.getElementById('style-selector');
    if (styleSelector) {
      styleSelector.querySelectorAll('.style-btn').forEach(btn => {
        btn.addEventListener('click', function() {
          styleSelector.querySelectorAll('.style-btn').forEach(b => b.classList.remove('active'));
          this.classList.add('active');
        });
      });
    }
  }

  // Set default upload date
  function initUploadDate() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('upload-date').value = today;
  }

  // ===== Utility Functions =====
  function formatTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
  }

  function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
  }

  function getSyncBadge(status) {
    if (status === 'synced') {
      return '<span class="sync-badge sync-synced">✓ Synced</span>';
    } else if (status === 'pending_to_mac') {
      return '<span class="sync-badge sync-pending">⏳ Pending</span>';
    }
    return '';
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function formatKoreanDate(dateStr) {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      const year = d.getFullYear();
      const month = d.getMonth() + 1;
      const day = d.getDate();
      const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
      const weekday = weekdays[d.getDay()];
      return `${year}년 ${month}월 ${day}일 (${weekday})`;
    } catch (e) {
      return dateStr;
    }
  }

  function showError(message) {
    console.error('[Assistant] Error:', message);
    // Show error in all containers
    ['today-events', 'week-events', 'pending-tasks', 'pending-sync'].forEach(id => {
      const container = document.getElementById(id);
      if (container) {
        container.innerHTML = `<div class="empty" style="color: #f44336;">Error: ${message}</div>`;
      }
    });
  }

  function showToast(message, type = 'info') {
    // 기존 토스트 제거
    const existing = document.querySelector('.toast-notification');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.style.cssText = `
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      padding: 12px 24px;
      border-radius: 8px;
      color: white;
      font-weight: 500;
      z-index: 10000;
      animation: slideUp 0.3s ease;
      max-width: 90%;
      text-align: center;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
    `;
    toast.textContent = message;
    document.body.appendChild(toast);

    // 3초 후 자동 제거
    setTimeout(() => {
      toast.style.animation = 'fadeOut 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // ===== People Management =====
  let peopleList = [];
  let currentPersonId = null;
  let quickInputType = 'people'; // 'people' or 'project'

  async function loadPeople() {
    const search = document.getElementById('people-search')?.value || '';
    const category = document.getElementById('people-category-filter')?.value || '';

    try {
      const res = await fetch(`/assistant/api/people?search=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}`);
      const data = await res.json();

      if (data.success) {
        peopleList = data.people;
        renderPeopleList();
      }
    } catch (err) {
      console.error('Failed to load people:', err);
    }
  }

  function renderPeopleList() {
    const container = document.getElementById('people-list');
    if (!container) return;

    if (peopleList.length === 0) {
      container.innerHTML = '<div class="empty">No people found</div>';
      return;
    }

    container.innerHTML = peopleList.map(person => `
      <div class="person-card ${currentPersonId === person.id ? 'selected' : ''}" onclick="AssistantMain.selectPerson(${person.id})">
        <div class="person-avatar">👤</div>
        <div class="person-info-brief">
          <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
            <span class="person-name">${escapeHtml(person.name)}</span>
            ${person.category ? `<span class="person-category-badge">${escapeHtml(person.category)}</span>` : ''}
            ${person.birthday ? `<span style="font-size: 0.75rem; color: var(--text-secondary);">🎂 ${person.birthday}</span>` : ''}
          </div>
          ${person.notes ? `<div class="person-last-note">${escapeHtml(person.notes.substring(0, 50))}${person.notes.length > 50 ? '...' : ''}</div>` : ''}
        </div>
      </div>
    `).join('');
  }

  async function selectPerson(personId) {
    currentPersonId = personId;
    renderPeopleList();

    try {
      const res = await fetch(`/assistant/api/people/${personId}`);
      const data = await res.json();

      if (data.success) {
        const person = data.person;
        document.getElementById('person-detail-name').textContent = person.name;

        const infoHtml = `
          ${person.category ? `<div><strong>Category:</strong> ${escapeHtml(person.category)}</div>` : ''}
          ${person.phone ? `<div><strong>Phone:</strong> ${escapeHtml(person.phone)}</div>` : ''}
          ${person.email ? `<div><strong>Email:</strong> ${escapeHtml(person.email)}</div>` : ''}
          ${person.address ? `<div><strong>Address:</strong> ${escapeHtml(person.address)}</div>` : ''}
          ${person.birthday ? `<div><strong>Birthday:</strong> 🎂 ${person.birthday}</div>` : ''}
          ${person.notes ? `<div><strong>Notes:</strong> ${escapeHtml(person.notes)}</div>` : ''}
        `;
        document.getElementById('person-info').innerHTML = infoHtml;

        // Render notes
        const notesContainer = document.getElementById('person-notes-list');
        if (person.notes_list && person.notes_list.length > 0) {
          notesContainer.innerHTML = person.notes_list.map(note => `
            <div class="note-item">
              <div class="note-header">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                  <span class="note-date">${formatKoreanDate(note.note_date)}</span>
                  ${note.category ? `<span class="note-category-badge">${escapeHtml(note.category)}</span>` : ''}
                </div>
                <button class="note-delete" onclick="AssistantMain.deletePersonNote(${note.id}); event.stopPropagation();">×</button>
              </div>
              <div class="note-content">${escapeHtml(note.content)}</div>
            </div>
          `).join('');
        } else {
          notesContainer.innerHTML = '<div class="empty">No notes yet</div>';
        }

        document.getElementById('person-detail-panel').style.display = 'block';
      }
    } catch (err) {
      console.error('Failed to load person:', err);
    }
  }

  function addPerson() {
    document.getElementById('person-modal-title').textContent = 'Add Person';
    document.getElementById('person-id').value = '';
    document.getElementById('person-name').value = '';
    document.getElementById('person-category').value = '';
    document.getElementById('person-phone').value = '';
    document.getElementById('person-email').value = '';
    document.getElementById('person-address').value = '';
    document.getElementById('person-birthday').value = '';
    document.getElementById('person-notes').value = '';
    document.getElementById('person-modal').style.display = 'flex';
  }

  function editPerson() {
    if (!currentPersonId) return;
    const person = peopleList.find(p => p.id === currentPersonId);
    if (!person) return;

    document.getElementById('person-modal-title').textContent = 'Edit Person';
    document.getElementById('person-id').value = person.id;
    document.getElementById('person-name').value = person.name || '';
    document.getElementById('person-category').value = person.category || '';
    document.getElementById('person-phone').value = person.phone || '';
    document.getElementById('person-email').value = person.email || '';
    document.getElementById('person-address').value = person.address || '';
    document.getElementById('person-birthday').value = person.birthday || '';
    document.getElementById('person-notes').value = person.notes || '';
    document.getElementById('person-modal').style.display = 'flex';
  }

  function closePersonModal() {
    document.getElementById('person-modal').style.display = 'none';
  }

  // 중복 확인 모달 관련
  let pendingDuplicateData = null;
  let pendingDuplicateType = null;

  function showDuplicateModal(message, duplicates, parsedData, type) {
    pendingDuplicateData = parsedData;
    pendingDuplicateType = type;

    document.getElementById('duplicate-message').textContent = message;

    const listEl = document.getElementById('duplicate-list');
    listEl.innerHTML = duplicates.map(item => {
      const info = type === 'people'
        ? `${item.category || ''} ${item.phone || ''} ${item.birthday ? '🎂 ' + item.birthday : ''}`
        : `${item.status || ''} ${item.start_date ? '시작: ' + item.start_date : ''} ${item.end_date ? '~ ' + item.end_date : ''}`;
      return `
        <div class="duplicate-item" style="padding: 0.75rem; border: 1px solid var(--border-color); border-radius: 6px; cursor: pointer; transition: background 0.2s;"
             onclick="AssistantMain.selectDuplicate(${item.id})"
             onmouseover="this.style.background='var(--primary-light)'"
             onmouseout="this.style.background=''">
          <strong>${item.name}</strong>
          <div style="font-size: 0.85rem; color: var(--text-secondary);">${info}</div>
        </div>
      `;
    }).join('');

    document.getElementById('duplicate-modal').style.display = 'flex';
  }

  function closeDuplicateModal() {
    document.getElementById('duplicate-modal').style.display = 'none';
    pendingDuplicateData = null;
    pendingDuplicateType = null;
  }

  async function selectDuplicate(existingId) {
    // 기존 항목에 노트만 추가
    if (!pendingDuplicateData) return;

    const endpoint = pendingDuplicateType === 'people'
      ? '/assistant/api/quick-add-people'
      : '/assistant/api/quick-add-project';

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...pendingDuplicateData,
          use_existing_id: existingId
        })
      });

      const result = await res.json();
      if (result.success) {
        closeDuplicateModal();
        showToast(result.message, 'success');
        if (pendingDuplicateType === 'people') {
          loadPeople();
        } else {
          loadProjects();
        }
        loadDashboard();
      } else {
        alert(result.error || 'Failed to add');
      }
    } catch (err) {
      console.error('Failed to add to existing:', err);
    }
  }

  async function forceCreate() {
    // 강제로 새로 만들기
    if (!pendingDuplicateData) return;

    const endpoint = pendingDuplicateType === 'people'
      ? '/assistant/api/quick-add-people'
      : '/assistant/api/quick-add-project';

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...pendingDuplicateData,
          force: true
        })
      });

      const result = await res.json();
      if (result.success) {
        closeDuplicateModal();
        showToast(result.message, 'success');
        if (pendingDuplicateType === 'people') {
          loadPeople();
        } else {
          loadProjects();
        }
        loadDashboard();
      } else {
        alert(result.error || 'Failed to create');
      }
    } catch (err) {
      console.error('Failed to force create:', err);
    }
  }

  async function savePerson() {
    const id = document.getElementById('person-id').value;
    const data = {
      name: document.getElementById('person-name').value.trim(),
      category: document.getElementById('person-category').value,
      phone: document.getElementById('person-phone').value.trim(),
      email: document.getElementById('person-email').value.trim(),
      address: document.getElementById('person-address').value.trim(),
      birthday: document.getElementById('person-birthday').value || null,
      notes: document.getElementById('person-notes').value.trim()
    };

    if (!data.name) {
      alert('Name is required');
      return;
    }

    try {
      const url = id ? `/assistant/api/people/${id}` : '/assistant/api/people';
      const method = id ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });

      const result = await res.json();
      if (result.success) {
        closePersonModal();
        loadPeople();
        if (result.birthday_event_created) {
          showToast('생일 이벤트가 캘린더에 추가되었습니다', 'success');
          loadDashboard();
        }
        if (id) selectPerson(parseInt(id));
      } else if (result.error === 'duplicate_found') {
        // 중복 발견 - 모달 표시
        closePersonModal();
        showDuplicateModal(result.message, result.duplicates, data, 'people');
      } else {
        alert(result.error || 'Failed to save person');
      }
    } catch (err) {
      console.error('Failed to save person:', err);
      alert('Failed to save person');
    }
  }

  async function deletePerson() {
    if (!currentPersonId) return;
    if (!confirm('Are you sure you want to delete this person?')) return;

    try {
      const res = await fetch(`/assistant/api/people/${currentPersonId}`, { method: 'DELETE' });
      const result = await res.json();

      if (result.success) {
        currentPersonId = null;
        document.getElementById('person-detail-panel').style.display = 'none';
        loadPeople();
      } else {
        alert(result.error || 'Failed to delete person');
      }
    } catch (err) {
      console.error('Failed to delete person:', err);
    }
  }

  function addPersonNote() {
    if (!currentPersonId) return;
    document.getElementById('person-note-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('person-note-content').value = '';
    document.getElementById('person-note-category').value = '';
    document.getElementById('person-note-modal').style.display = 'flex';
  }

  function closePersonNoteModal() {
    document.getElementById('person-note-modal').style.display = 'none';
  }

  async function savePersonNote() {
    const data = {
      note_date: document.getElementById('person-note-date').value,
      content: document.getElementById('person-note-content').value.trim(),
      category: document.getElementById('person-note-category').value
    };

    if (!data.content) {
      alert('Note content is required');
      return;
    }

    try {
      const res = await fetch(`/assistant/api/people/${currentPersonId}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });

      const result = await res.json();
      if (result.success) {
        closePersonNoteModal();
        selectPerson(currentPersonId);
      } else {
        alert(result.error || 'Failed to save note');
      }
    } catch (err) {
      console.error('Failed to save note:', err);
    }
  }

  async function deletePersonNote(noteId) {
    if (!confirm('Delete this note?')) return;

    try {
      const res = await fetch(`/assistant/api/people/notes/${noteId}`, { method: 'DELETE' });
      const result = await res.json();

      if (result.success) {
        selectPerson(currentPersonId);
      }
    } catch (err) {
      console.error('Failed to delete note:', err);
    }
  }

  function searchPeople() {
    loadPeople();
  }

  function filterPeopleByCategory() {
    loadPeople();
  }

  // ===== Projects Management =====
  let projectsList = [];
  let currentProjectId = null;
  let projectStatusFilter = 'all';

  async function loadProjects() {
    const search = document.getElementById('projects-search')?.value || '';
    const status = projectStatusFilter === 'all' ? '' : projectStatusFilter;

    try {
      const res = await fetch(`/assistant/api/projects?search=${encodeURIComponent(search)}&status=${encodeURIComponent(status)}`);
      const data = await res.json();

      if (data.success) {
        projectsList = data.projects;
        renderProjectsList();
      }
    } catch (err) {
      console.error('Failed to load projects:', err);
    }
  }

  function renderProjectsList() {
    const container = document.getElementById('projects-list');
    if (!container) return;

    if (projectsList.length === 0) {
      container.innerHTML = '<div class="empty">No projects found</div>';
      return;
    }

    container.innerHTML = projectsList.map(project => `
      <div class="project-card ${currentProjectId === project.id ? 'selected' : ''}" onclick="AssistantMain.selectProject(${project.id})">
        <div class="project-icon">📁</div>
        <div class="project-info-brief">
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span class="project-name">${escapeHtml(project.name)}</span>
            <span class="project-status-badge ${project.status}">${project.status}</span>
          </div>
          ${project.description ? `<div class="project-last-note">${escapeHtml(project.description.substring(0, 50))}${project.description.length > 50 ? '...' : ''}</div>` : ''}
        </div>
      </div>
    `).join('');
  }

  async function selectProject(projectId) {
    currentProjectId = projectId;
    renderProjectsList();

    try {
      const res = await fetch(`/assistant/api/projects/${projectId}`);
      const data = await res.json();

      if (data.success) {
        const project = data.project;
        document.getElementById('project-detail-name').textContent = project.name;

        const infoHtml = `
          <div><strong>상태:</strong> <span class="project-status-badge ${project.status}">${project.status}</span></div>
          ${project.description ? `<div><strong>설명:</strong> ${escapeHtml(project.description)}</div>` : ''}
          ${project.priority ? `<div><strong>우선순위:</strong> ${project.priority}</div>` : ''}
          ${project.start_date ? `<div><strong>시작:</strong> ${formatKoreanDate(project.start_date)}</div>` : ''}
          ${project.end_date ? `<div><strong>종료:</strong> ${formatKoreanDate(project.end_date)}</div>` : ''}
        `;
        document.getElementById('project-info').innerHTML = infoHtml;

        // Render notes
        const notesContainer = document.getElementById('project-notes-list');
        if (project.notes_list && project.notes_list.length > 0) {
          notesContainer.innerHTML = project.notes_list.map(note => `
            <div class="note-item">
              <div class="note-header">
                <span class="note-date">${formatKoreanDate(note.note_date)}</span>
                <button class="note-delete" onclick="AssistantMain.deleteProjectNote(${note.id}); event.stopPropagation();">×</button>
              </div>
              <div class="note-content">${escapeHtml(note.content)}</div>
            </div>
          `).join('');
        } else {
          notesContainer.innerHTML = '<div class="empty">No notes yet</div>';
        }

        document.getElementById('project-detail-panel').style.display = 'block';
      }
    } catch (err) {
      console.error('Failed to load project:', err);
    }
  }

  function addProject() {
    document.getElementById('project-modal-title').textContent = 'Add Project';
    document.getElementById('project-id').value = '';
    document.getElementById('project-name').value = '';
    document.getElementById('project-description').value = '';
    document.getElementById('project-status').value = 'active';
    document.getElementById('project-priority').value = 'medium';
    document.getElementById('project-start-date').value = '';
    document.getElementById('project-end-date').value = '';
    document.getElementById('project-modal').style.display = 'flex';
  }

  function editProject() {
    if (!currentProjectId) return;
    const project = projectsList.find(p => p.id === currentProjectId);
    if (!project) return;

    document.getElementById('project-modal-title').textContent = 'Edit Project';
    document.getElementById('project-id').value = project.id;
    document.getElementById('project-name').value = project.name || '';
    document.getElementById('project-description').value = project.description || '';
    document.getElementById('project-status').value = project.status || 'active';
    document.getElementById('project-priority').value = project.priority || 'medium';
    document.getElementById('project-start-date').value = project.start_date || '';
    document.getElementById('project-end-date').value = project.end_date || '';
    document.getElementById('project-modal').style.display = 'flex';
  }

  function closeProjectModal() {
    document.getElementById('project-modal').style.display = 'none';
  }

  async function saveProject() {
    const id = document.getElementById('project-id').value;
    const data = {
      name: document.getElementById('project-name').value.trim(),
      description: document.getElementById('project-description').value.trim(),
      status: document.getElementById('project-status').value,
      priority: document.getElementById('project-priority').value,
      start_date: document.getElementById('project-start-date').value || null,
      end_date: document.getElementById('project-end-date').value || null
    };

    if (!data.name) {
      alert('Project name is required');
      return;
    }

    try {
      const url = id ? `/assistant/api/projects/${id}` : '/assistant/api/projects';
      const method = id ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });

      const result = await res.json();
      if (result.success) {
        closeProjectModal();
        loadProjects();
        if (id) selectProject(parseInt(id));
      } else {
        alert(result.error || 'Failed to save project');
      }
    } catch (err) {
      console.error('Failed to save project:', err);
      alert('Failed to save project');
    }
  }

  async function deleteProject() {
    if (!currentProjectId) return;
    if (!confirm('Are you sure you want to delete this project?')) return;

    try {
      const res = await fetch(`/assistant/api/projects/${currentProjectId}`, { method: 'DELETE' });
      const result = await res.json();

      if (result.success) {
        currentProjectId = null;
        document.getElementById('project-detail-panel').style.display = 'none';
        loadProjects();
      } else {
        alert(result.error || 'Failed to delete project');
      }
    } catch (err) {
      console.error('Failed to delete project:', err);
    }
  }

  function addProjectNote() {
    if (!currentProjectId) return;
    document.getElementById('project-note-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('project-note-content').value = '';
    document.getElementById('project-note-modal').style.display = 'flex';
  }

  function closeProjectNoteModal() {
    document.getElementById('project-note-modal').style.display = 'none';
  }

  async function saveProjectNote() {
    const data = {
      note_date: document.getElementById('project-note-date').value,
      content: document.getElementById('project-note-content').value.trim()
    };

    if (!data.content) {
      alert('Note content is required');
      return;
    }

    try {
      const res = await fetch(`/assistant/api/projects/${currentProjectId}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });

      const result = await res.json();
      if (result.success) {
        closeProjectNoteModal();
        selectProject(currentProjectId);
      } else {
        alert(result.error || 'Failed to save note');
      }
    } catch (err) {
      console.error('Failed to save note:', err);
    }
  }

  async function deleteProjectNote(noteId) {
    if (!confirm('Delete this note?')) return;

    try {
      const res = await fetch(`/assistant/api/projects/notes/${noteId}`, { method: 'DELETE' });
      const result = await res.json();

      if (result.success) {
        selectProject(currentProjectId);
      }
    } catch (err) {
      console.error('Failed to delete note:', err);
    }
  }

  function searchProjects() {
    loadProjects();
  }

  function filterProjectsByStatus(status) {
    projectStatusFilter = status;
    // Update button active state
    document.querySelectorAll('#section-projects .filter-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.status === status);
    });
    loadProjects();
  }

  // ===== Quick Input for People/Projects =====
  function setQuickInputType(type) {
    quickInputType = type;
    // Update button styles
    document.querySelectorAll('.input-type-toggle .toggle-btn').forEach(btn => {
      if (btn.dataset.type === type) {
        btn.style.background = 'var(--primary-light)';
        btn.style.color = 'var(--primary-dark)';
      } else {
        btn.style.background = 'white';
        btn.style.color = 'var(--text-secondary)';
      }
    });

    // Update placeholder
    const textarea = document.getElementById('input-box-people');
    if (textarea) {
      if (type === 'people') {
        textarea.placeholder = '예: 홍길동 집사 12월 10일 담낭암 수술 예정...';
      } else {
        textarea.placeholder = '예: 교회 리모델링 프로젝트 1차 설계 검토 완료...';
      }
    }
  }

  let parsedPeopleData = null;

  async function analyzeInputPeople() {
    const inputText = document.getElementById('input-box-people').value.trim();
    if (!inputText) {
      alert('Please enter some text');
      return;
    }

    const btn = document.getElementById('btn-analyze-people');
    const originalText = btn.textContent;
    btn.textContent = '분석 중...';
    btn.disabled = true;

    try {
      // Step 1: AI 분석
      const analyzeRes = await fetch('/assistant/api/analyze-input-people', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: inputText, type: quickInputType })
      });

      const analyzeData = await analyzeRes.json();

      if (!analyzeData.success) {
        alert(analyzeData.error || 'Failed to analyze input');
        return;
      }

      const parsed = analyzeData.parsed;
      btn.textContent = '저장 중...';

      // Step 2: 바로 저장 (force=true로 중복 확인 건너뛰기)
      const saveUrl = quickInputType === 'people'
        ? '/assistant/api/quick-add-people'
        : '/assistant/api/quick-add-project';

      const saveRes = await fetch(saveUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...parsed, force: true })
      });

      const saveData = await saveRes.json();

      if (saveData.success) {
        // 성공 - 입력창 비우고 결과 표시
        document.getElementById('input-box-people').value = '';
        document.getElementById('parsed-result-people').style.display = 'none';

        // 결과 메시지 표시
        const summary = quickInputType === 'people'
          ? `✓ ${parsed.name} 등록 완료${parsed.note_content ? ` (${parsed.note_date})` : ''}`
          : `✓ ${parsed.name} 프로젝트 등록 완료`;
        showToast(saveData.message || summary, 'success');

        // 리스트 새로고침
        if (quickInputType === 'people') {
          loadPeople();
        } else {
          loadProjects();
        }

        // 이벤트가 생성됐으면 대시보드도 새로고침
        if (saveData.birthday_event_created || saveData.note_event_created ||
            (saveData.events_created && saveData.events_created.length > 0)) {
          loadDashboard();
        }
      } else {
        alert(saveData.error || 'Failed to save');
      }
    } catch (err) {
      console.error('Failed to analyze/save:', err);
      alert('오류가 발생했습니다: ' + err.message);
    } finally {
      btn.textContent = originalText;
      btn.disabled = false;
    }
  }

  async function saveParsedPeople() {
    if (!parsedPeopleData) return;

    try {
      const url = quickInputType === 'people'
        ? '/assistant/api/quick-add-people'
        : '/assistant/api/quick-add-project';

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(parsedPeopleData)
      });

      const result = await res.json();

      if (result.success) {
        showToast(result.message, 'success');
        document.getElementById('input-box-people').value = '';
        document.getElementById('parsed-result-people').style.display = 'none';
        parsedPeopleData = null;

        // Refresh the list if on that section
        if (quickInputType === 'people') {
          loadPeople();
        } else {
          loadProjects();
        }
        // 이벤트가 생성됐으면 대시보드도 새로고침
        if (result.birthday_event_created || result.note_event_created || (result.events_created && result.events_created.length > 0)) {
          loadDashboard();
        }
      } else if (result.error === 'duplicate_found') {
        // 중복 발견 - 모달 표시
        document.getElementById('parsed-result-people').style.display = 'none';
        showDuplicateModal(result.message, result.duplicates, result.parsed_data || parsedPeopleData, quickInputType);
      } else {
        alert(result.error || 'Failed to save');
      }
    } catch (err) {
      console.error('Failed to save:', err);
      alert('Failed to save');
    }
  }

  // ===== Event Modal Functions =====
  async function openEventModal(eventId) {
    try {
      const response = await fetch(`/assistant/api/events/${eventId}`);
      const data = await response.json();

      if (!data.success) {
        showToast(data.error || '이벤트를 불러올 수 없습니다', 'error');
        return;
      }

      const event = data.event;

      // Populate modal fields
      document.getElementById('event-id').value = event.id;
      document.getElementById('event-title').value = event.title || '';
      document.getElementById('event-category').value = event.category || '';

      // Format datetime for input
      if (event.start_time) {
        const startDt = new Date(event.start_time);
        document.getElementById('event-start').value = formatDateTimeLocal(startDt);
      } else {
        document.getElementById('event-start').value = '';
      }

      if (event.end_time) {
        const endDt = new Date(event.end_time);
        document.getElementById('event-end').value = formatDateTimeLocal(endDt);
      } else {
        document.getElementById('event-end').value = '';
      }

      // Show modal
      document.getElementById('event-modal').style.display = 'flex';
    } catch (err) {
      console.error('[Assistant] Open event modal error:', err);
      showToast('이벤트를 불러오는 중 오류가 발생했습니다', 'error');
    }
  }

  function closeEventModal() {
    document.getElementById('event-modal').style.display = 'none';
  }

  function formatDateTimeLocal(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  }

  async function saveEvent() {
    const eventId = document.getElementById('event-id').value;
    const title = document.getElementById('event-title').value.trim();
    const startTime = document.getElementById('event-start').value;
    const endTime = document.getElementById('event-end').value;
    const category = document.getElementById('event-category').value.trim();

    if (!title) {
      showToast('제목을 입력해주세요', 'error');
      return;
    }

    try {
      const response = await fetch(`/assistant/api/events/${eventId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          start_time: startTime || null,
          end_time: endTime || null,
          category: category || null
        })
      });

      const data = await response.json();

      if (data.success) {
        showToast('일정이 수정되었습니다', 'success');
        closeEventModal();
        loadDashboard();
      } else {
        showToast(data.error || '저장 실패', 'error');
      }
    } catch (err) {
      console.error('[Assistant] Save event error:', err);
      showToast('저장 중 오류가 발생했습니다', 'error');
    }
  }

  async function deleteEvent() {
    const eventId = document.getElementById('event-id').value;

    if (!confirm('이 일정을 삭제하시겠습니까?')) {
      return;
    }

    try {
      const response = await fetch(`/assistant/api/events/${eventId}`, {
        method: 'DELETE'
      });

      const data = await response.json();

      if (data.success) {
        showToast('일정이 삭제되었습니다', 'success');
        closeEventModal();
        loadDashboard();
      } else {
        showToast(data.error || '삭제 실패', 'error');
      }
    } catch (err) {
      console.error('[Assistant] Delete event error:', err);
      showToast('삭제 중 오류가 발생했습니다', 'error');
    }
  }

  // ===== Initialize on DOM Ready =====
  document.addEventListener('DOMContentLoaded', init);

  // ===== Public API =====
  return {
    loadDashboard,
    analyzeInput,
    saveParsedData,
    analyzeUnified,
    saveUnifiedData,
    completeTask,
    addTask,
    closeTaskModal,
    setDueDate,
    setCategory,
    saveTask,
    syncToMac,
    // Google Calendar functions
    checkGcalAuth,
    authGcal,
    syncGcal,
    // Google Calendar Webhook (realtime sync)
    checkWebhookStatus,
    enableRealtimeSync,
    disableRealtimeSync,
    // Google Sheets functions
    checkGsheetsAuth,
    authGsheets,
    exportPeopleToSheets,
    exportEventsToSheets,
    // Video Schedule (from Sheets)
    refreshVideoSchedule,
    showSection,
    // News functions
    refreshNews,
    generateScript,
    closeScriptModal,
    copyScript,
    // Calendar functions
    calendarPrev,
    calendarNext,
    calendarToday,
    setCalendarView,
    // Event modal functions
    openEventModal,
    closeEventModal,
    saveEvent,
    deleteEvent,
    // Tasks section functions
    filterTasks,
    quickAddTask,
    toggleTaskComplete,
    deleteTask,
    // Attendance functions
    showAttendanceTab,
    handleFileSelect,
    uploadAttendance,
    findUnderAttending,
    togglePersonSelection,
    selectAllUnderAttending,
    generateMessages,
    copyMessage,
    // People functions
    loadPeople,
    selectPerson,
    addPerson,
    editPerson,
    closePersonModal,
    savePerson,
    deletePerson,
    addPersonNote,
    closePersonNoteModal,
    savePersonNote,
    deletePersonNote,
    searchPeople,
    filterPeopleByCategory,
    // Projects functions
    loadProjects,
    selectProject,
    addProject,
    editProject,
    closeProjectModal,
    saveProject,
    deleteProject,
    addProjectNote,
    closeProjectNoteModal,
    saveProjectNote,
    deleteProjectNote,
    searchProjects,
    filterProjectsByStatus,
    // Quick Input People/Projects
    setQuickInputType,
    analyzeInputPeople,
    saveParsedPeople,
    // Duplicate modal functions
    showDuplicateModal,
    closeDuplicateModal,
    selectDuplicate,
    forceCreate
  };
})();
