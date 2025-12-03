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

    // Set today's date
    const today = new Date();
    const options = { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' };
    document.getElementById('today-date').textContent = today.toLocaleDateString('ko-KR', options);

    // Load dashboard data
    await loadDashboard();

    // Initialize attendance section
    initUploadDate();
    initStyleButtons();
    initDragDrop();
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
  function showSection(section) {
    console.log('[Assistant] Show section:', section);
    // TODO: Implement section navigation
    alert('Section navigation coming soon: ' + section);
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
