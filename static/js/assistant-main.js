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
      container.innerHTML = '<div class="empty">No events</div>';
      return;
    }

    container.innerHTML = events.map(event => {
      const startTime = event.start_time ? formatTime(event.start_time) : '';
      const startDate = event.start_time ? formatDate(event.start_time) : '';
      const category = event.category ? `<span class="item-category">${event.category}</span>` : '';
      const syncBadge = getSyncBadge(event.sync_status);
      // 이벤트 제목에서 대괄호 제거
      const title = event.title ? event.title.replace(/^\[|\]$/g, '') : '';
      // 날짜+시간 표시 (이번주 섹션) 또는 시간만 표시 (오늘 섹션)
      const timeDisplay = showDate ? `${startDate} ${startTime}` : startTime;

      return `
        <div class="item">
          <div class="item-time">${timeDisplay}</div>
          <div class="item-content">
            <div class="item-title">${escapeHtml(title)}</div>
            <div class="item-meta">${category} ${syncBadge}</div>
          </div>
        </div>
      `;
    }).join('');
  }

  function renderTasks(containerId, tasks) {
    const container = document.getElementById(containerId);

    if (!tasks || tasks.length === 0) {
      container.innerHTML = '<div class="empty">No pending tasks</div>';
      return;
    }

    container.innerHTML = tasks.map(task => {
      const dueDate = task.due_date ? formatDate(task.due_date) : 'No due date';
      const priorityClass = `priority-${task.priority || 'medium'}`;
      const category = task.category ? `<span class="item-category">${task.category}</span>` : '';
      const syncBadge = getSyncBadge(task.sync_status);

      return `
        <div class="item">
          <div class="item-content">
            <div class="item-title">
              <span class="${priorityClass}">●</span>
              ${escapeHtml(task.title)}
            </div>
            <div class="item-meta">
              <span>${dueDate}</span>
              ${category} ${syncBadge}
            </div>
          </div>
          <button class="btn btn-small btn-secondary" onclick="AssistantMain.completeTask(${task.id})">
            ✓
          </button>
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

  // ===== Input Analyzer =====
  async function analyzeInput() {
    const inputBox = document.getElementById('input-box');
    const text = inputBox.value.trim();

    if (!text) {
      alert('Please enter some text to analyze');
      return;
    }

    const btn = document.getElementById('btn-analyze');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="loading"></span> Analyzing...';
    btn.disabled = true;

    try {
      const response = await fetch('/assistant/api/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });

      const data = await response.json();

      if (data.success) {
        parsedData = data.parsed;
        showParsedResult(data.parsed);
      } else {
        alert('Analysis failed: ' + data.error);
      }
    } catch (error) {
      console.error('[Assistant] Parse error:', error);
      alert('Network error');
    } finally {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  }

  function showParsedResult(parsed) {
    const resultDiv = document.getElementById('parsed-result');
    const eventsDiv = document.getElementById('parsed-events');
    const tasksDiv = document.getElementById('parsed-tasks');

    // Render parsed events
    if (parsed.events && parsed.events.length > 0) {
      eventsDiv.innerHTML = `
        <h5>Events (${parsed.events.length})</h5>
        ${parsed.events.map((e, i) => `
          <div class="parsed-item">
            <div>
              <strong>${escapeHtml(e.title)}</strong>
              <span class="item-meta">${e.date} ${e.time || ''}</span>
            </div>
            <span class="item-category">${e.category || ''}</span>
          </div>
        `).join('')}
      `;
    } else {
      eventsDiv.innerHTML = '';
    }

    // Render parsed tasks
    if (parsed.tasks && parsed.tasks.length > 0) {
      tasksDiv.innerHTML = `
        <h5 style="margin-top: 1rem;">Tasks (${parsed.tasks.length})</h5>
        ${parsed.tasks.map((t, i) => `
          <div class="parsed-item">
            <div>
              <strong>${escapeHtml(t.title)}</strong>
              <span class="item-meta">${t.due_date || 'No due date'}</span>
            </div>
            <span class="priority-${t.priority || 'medium'}">${t.priority || 'medium'}</span>
          </div>
        `).join('')}
      `;
    } else {
      tasksDiv.innerHTML = '';
    }

    resultDiv.classList.add('show');
  }

  async function saveParsedData() {
    if (!parsedData) {
      alert('No parsed data to save');
      return;
    }

    try {
      let savedEvents = 0;
      let savedTasks = 0;

      // Save events
      for (const event of (parsedData.events || [])) {
        const response = await fetch('/assistant/api/events', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: event.title,
            start_time: `${event.date}T${event.time || '00:00'}:00`,
            end_time: event.end_time ? `${event.date}T${event.end_time}:00` : null,
            category: event.category
          })
        });
        if ((await response.json()).success) savedEvents++;
      }

      // Save tasks
      for (const task of (parsedData.tasks || [])) {
        const response = await fetch('/assistant/api/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: task.title,
            due_date: task.due_date,
            priority: task.priority,
            category: task.category
          })
        });
        if ((await response.json()).success) savedTasks++;
      }

      alert(`Saved ${savedEvents} events and ${savedTasks} tasks`);

      // Clear and reload
      document.getElementById('input-box').value = '';
      document.getElementById('parsed-result').classList.remove('show');
      parsedData = null;
      await loadDashboard();

    } catch (error) {
      console.error('[Assistant] Save error:', error);
      alert('Failed to save data');
    }
  }

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
        <div class="item">
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

  // ===== Initialize on DOM Ready =====
  document.addEventListener('DOMContentLoaded', init);

  // ===== Public API =====
  return {
    loadDashboard,
    analyzeInput,
    saveParsedData,
    completeTask,
    addTask,
    closeTaskModal,
    setDueDate,
    setCategory,
    saveTask,
    syncToMac,
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
    copyMessage
  };
})();
