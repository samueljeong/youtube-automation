/**
 * TubeLens - YouTube Analytics Tool
 * 메인 JavaScript 모듈
 */

const TubeLens = {
  // 상태 변수
  apiKeys: [],
  currentApiKeyIndex: 0,
  currentResults: [],
  originalResults: [],
  searchMode: 'video', // 'video' or 'channel'
  sortMode: 'views',   // 'views' or 'date'
  selectedChannel: null,
  currentVideoId: null,
  filters: {
    ciiGreat: false,
    ciiGood: false,
    ciiSoso: false,
    viewCount: '',
    subscriberCount: ''
  },

  // 초기화
  init() {
    this.loadApiKeys();
    this.updateApiKeysList();
    this.updateStatus();
    console.log('TubeLens initialized');
  },

  // API 키 관리
  loadApiKeys() {
    const saved = localStorage.getItem('tubelens_api_keys');
    if (saved) {
      this.apiKeys = JSON.parse(saved);
      this.currentApiKeyIndex = parseInt(localStorage.getItem('tubelens_api_index') || '0');
    }
  },

  saveApiKeys() {
    localStorage.setItem('tubelens_api_keys', JSON.stringify(this.apiKeys));
    localStorage.setItem('tubelens_api_index', this.currentApiKeyIndex.toString());
  },

  addApiKey() {
    const input = document.getElementById('new-api-key');
    const key = input.value.trim();

    if (!key) {
      alert('API 키를 입력해주세요.');
      return;
    }

    // YouTube API 키 형식 검증
    if (!key.startsWith('AIza') || key.length !== 39) {
      alert('올바른 YouTube API 키 형식이 아닙니다.');
      return;
    }

    if (this.apiKeys.includes(key)) {
      alert('이미 등록된 API 키입니다.');
      return;
    }

    this.apiKeys.push(key);
    this.saveApiKeys();
    this.updateApiKeysList();
    input.value = '';
    this.updateStatus('API 키가 추가되었습니다.');
  },

  removeApiKey(index) {
    if (confirm('이 API 키를 삭제하시겠습니까?')) {
      this.apiKeys.splice(index, 1);
      if (this.currentApiKeyIndex >= this.apiKeys.length) {
        this.currentApiKeyIndex = Math.max(0, this.apiKeys.length - 1);
      }
      this.saveApiKeys();
      this.updateApiKeysList();
    }
  },

  setActiveApiKey(index) {
    this.currentApiKeyIndex = index;
    this.saveApiKeys();
    this.updateApiKeysList();
  },

  updateApiKeysList() {
    const container = document.getElementById('api-keys-list');
    if (!container) return;

    if (this.apiKeys.length === 0) {
      container.innerHTML = '<div class="empty-keys">등록된 API 키가 없습니다</div>';
      return;
    }

    container.innerHTML = this.apiKeys.map((key, index) => {
      const isActive = index === this.currentApiKeyIndex;
      const maskedKey = key.substring(0, 8) + '...' + key.substring(key.length - 4);
      return `
        <div class="api-key-item ${isActive ? 'active' : ''}">
          <span class="api-key-text">${maskedKey}</span>
          <div class="api-key-actions">
            ${!isActive ? `<button class="btn-use" onclick="TubeLens.setActiveApiKey(${index})">사용</button>` : ''}
            <button class="btn-remove" onclick="TubeLens.removeApiKey(${index})">삭제</button>
          </div>
        </div>
      `;
    }).join('');
  },

  // 설정 모달
  openSettings() {
    document.getElementById('settings-modal').style.display = 'flex';
  },

  closeSettings() {
    document.getElementById('settings-modal').style.display = 'none';
  },

  // 검색 모드 설정
  setSearchMode(mode) {
    this.searchMode = mode;
    document.getElementById('btn-video-search').classList.toggle('active', mode === 'video');
    document.getElementById('btn-channel-search').classList.toggle('active', mode === 'channel');
  },

  // 정렬 모드 설정
  setSort(mode) {
    this.sortMode = mode;
    document.getElementById('btn-sort-views').classList.toggle('active', mode === 'views');
    document.getElementById('btn-sort-date').classList.toggle('active', mode === 'date');
  },

  // 상태 업데이트
  updateStatus(message) {
    const statusEl = document.getElementById('status-text');
    if (message) {
      statusEl.textContent = message;
    } else {
      if (this.apiKeys.length === 0) {
        statusEl.textContent = '준비됨 - API 키를 설정해주세요';
      } else {
        statusEl.textContent = `준비됨 - API 키 ${this.currentApiKeyIndex + 1}/${this.apiKeys.length} 활성`;
      }
    }
  },

  // 로딩 표시
  showLoading(show) {
    document.getElementById('loading-indicator').style.display = show ? 'flex' : 'none';
    document.getElementById('empty-results').style.display = 'none';
    document.querySelector('.table-wrapper').style.display = show ? 'none' : 'block';
  },

  // API 호출
  async callApi(endpoint, data) {
    const response = await fetch(`/api/tubelens/${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...data,
        apiKeys: this.apiKeys,
        currentApiKeyIndex: this.currentApiKeyIndex
      })
    });

    const result = await response.json();

    if (!result.success) {
      throw new Error(result.message || 'API 요청 실패');
    }

    return result;
  },

  // 영상 검색
  async startSearch() {
    if (this.apiKeys.length === 0) {
      alert('먼저 API 키를 설정해주세요.');
      this.openSettings();
      return;
    }

    const keyword = document.getElementById('search-keyword').value.trim();

    this.showLoading(true);
    this.updateStatus('검색 중...');

    try {
      if (this.searchMode === 'channel') {
        // 채널 검색
        if (!keyword) {
          alert('채널명을 입력해주세요.');
          this.showLoading(false);
          return;
        }

        const result = await this.callApi('channel-search', {
          channelName: keyword,
          regionCode: document.getElementById('region-code').value
        });

        if (result.data && result.data.length > 0) {
          this.showChannelModal(result.data);
        } else {
          alert('검색된 채널이 없습니다.');
        }
        this.showLoading(false);
        this.updateStatus(result.message);

      } else {
        // 영상 검색
        const result = await this.callApi('search', {
          keyword: keyword,
          maxResults: parseInt(document.getElementById('max-results').value),
          timeFrame: document.getElementById('time-frame').value,
          regionCode: document.getElementById('region-code').value,
          videoType: document.getElementById('video-type').value,
          isViewsSort: this.sortMode === 'views'
        });

        this.originalResults = result.data;
        this.currentResults = [...this.originalResults];
        this.displayResults(this.currentResults);
        this.updateStatus(result.message);
      }

    } catch (error) {
      console.error('검색 오류:', error);
      alert('검색 중 오류가 발생했습니다: ' + error.message);
      this.showLoading(false);
      this.updateStatus('검색 실패');
    }
  },

  // URL 분석
  async analyzeUrl() {
    if (this.apiKeys.length === 0) {
      alert('먼저 API 키를 설정해주세요.');
      this.openSettings();
      return;
    }

    const url = document.getElementById('youtube-url').value.trim();
    if (!url) {
      alert('YouTube URL을 입력해주세요.');
      return;
    }

    this.showLoading(true);
    this.updateStatus('URL 분석 중...');

    try {
      const result = await this.callApi('analyze', { url });

      if (result.type === 'channel') {
        // 채널인 경우
        this.showChannelModal([result.data[0]]);
        this.showLoading(false);
      } else {
        // 영상인 경우 - 기존 결과에 추가
        if (this.originalResults.length === 0) {
          this.originalResults = result.data;
        } else {
          const newResults = result.data.map((item, i) => ({
            ...item,
            index: this.originalResults.length + i + 1
          }));
          this.originalResults = this.originalResults.concat(newResults);
        }

        // 전체 인덱스 재조정
        this.originalResults = this.originalResults.map((item, i) => ({
          ...item,
          index: i + 1
        }));

        this.currentResults = [...this.originalResults];
        this.displayResults(this.currentResults);

        // URL 입력창 초기화
        document.getElementById('youtube-url').value = '';
      }

      this.updateStatus(result.message + ` (총 ${this.originalResults.length}개)`);

    } catch (error) {
      console.error('분석 오류:', error);
      alert('분석 중 오류가 발생했습니다: ' + error.message);
      this.showLoading(false);
      this.updateStatus('분석 실패');
    }
  },

  // 채널 모달 표시
  showChannelModal(channels) {
    const container = document.getElementById('channel-list');
    container.innerHTML = channels.map((ch, index) => `
      <div class="channel-item" data-index="${index}" onclick="TubeLens.selectChannel(${index})">
        <img class="channel-thumbnail" src="${ch.thumbnailUrl}" alt="${ch.channelTitle}" onerror="this.style.display='none'">
        <div class="channel-info">
          <div class="channel-title">${ch.channelTitle} ${ch.isExactMatch ? '(정확일치)' : ''}</div>
          <div class="channel-stats">
            구독자: ${this.formatNumber(ch.subscriberCount)}명 · 영상: ${this.formatNumber(ch.videoCount)}개
          </div>
        </div>
      </div>
    `).join('');

    this.channelList = channels;
    this.selectedChannel = null;
    document.getElementById('channel-modal').style.display = 'flex';
  },

  selectChannel(index) {
    // 이전 선택 해제
    document.querySelectorAll('.channel-item').forEach(el => el.classList.remove('selected'));

    // 새 선택
    document.querySelector(`.channel-item[data-index="${index}"]`).classList.add('selected');
    this.selectedChannel = this.channelList[index];
  },

  async collectChannelVideos() {
    if (!this.selectedChannel) {
      alert('채널을 선택해주세요.');
      return;
    }

    this.closeChannelModal();
    this.showLoading(true);
    this.updateStatus(`채널 영상 수집 중... (${this.selectedChannel.channelTitle})`);

    try {
      const result = await this.callApi('channel-videos', {
        channelId: this.selectedChannel.channelId,
        uploadPlaylist: this.selectedChannel.uploadPlaylist,
        maxResults: parseInt(document.getElementById('max-results').value),
        videoType: document.getElementById('channel-video-type').value
      });

      this.originalResults = result.data;
      this.currentResults = [...this.originalResults];
      this.displayResults(this.currentResults);
      this.updateStatus(result.message);

    } catch (error) {
      console.error('채널 영상 수집 오류:', error);
      alert('채널 영상을 수집하는 중 오류가 발생했습니다: ' + error.message);
      this.showLoading(false);
      this.updateStatus('채널 영상 수집 실패');
    }
  },

  closeChannelModal() {
    document.getElementById('channel-modal').style.display = 'none';
  },

  // 결과 표시
  displayResults(results) {
    const tbody = document.getElementById('results-body');
    const countEl = document.getElementById('result-count');

    if (!results || results.length === 0) {
      tbody.innerHTML = '';
      document.getElementById('empty-results').style.display = 'flex';
      document.querySelector('.table-wrapper').style.display = 'none';
      countEl.textContent = '(0개)';
      this.showLoading(false);
      return;
    }

    document.getElementById('empty-results').style.display = 'none';
    document.querySelector('.table-wrapper').style.display = 'block';
    countEl.textContent = `(${results.length}개)`;

    tbody.innerHTML = results.map(item => this.createResultRow(item)).join('');
    this.showLoading(false);
  },

  createResultRow(item) {
    // CII 뱃지 클래스
    let ciiClass = 'cii-bad';
    if (item.cii === 'Great!!') ciiClass = 'cii-great';
    else if (item.cii === 'Good') ciiClass = 'cii-good';
    else if (item.cii === 'Soso') ciiClass = 'cii-soso';
    else if (item.cii === 'Not bad') ciiClass = 'cii-notbad';

    // 게이지 바 생성
    const contributionGauge = this.createGaugeBar(item.contributionValue);
    const engagementGauge = this.createGaugeBar(item.engagementRate * 10); // 참여율은 스케일 조정

    return `
      <tr>
        <td>${item.index}</td>
        <td>
          <img class="thumbnail" src="${item.thumbnail}" alt="썸네일"
               onclick="TubeLens.showVideoModal('${item.videoId}', '${this.escapeHtml(item.title)}')"
               onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22120%22 height=%2268%22><rect fill=%22%23eee%22 width=%22120%22 height=%2268%22/></svg>'">
        </td>
        <td class="channel-name" onclick="TubeLens.searchChannelById('${item.channelId}')">${item.channelTitle}</td>
        <td class="video-title" title="${this.escapeHtml(item.title)}">${item.title}</td>
        <td>${item.publishedAt}</td>
        <td>${this.formatNumber(item.subscriberCount)}</td>
        <td>${this.formatNumber(item.viewCount)}</td>
        <td>${contributionGauge}</td>
        <td>${item.performanceValue.toFixed(1)}배</td>
        <td><span class="cii-badge ${ciiClass}">${item.cii}</span></td>
        <td>${item.duration}</td>
        <td>${this.formatNumber(item.likeCount)}</td>
        <td style="cursor: pointer; color: #007bff;" onclick="TubeLens.showComments('${item.videoId}', '${this.escapeHtml(item.title)}')">${this.formatNumber(item.commentCount)}</td>
        <td>${engagementGauge}</td>
      </tr>
    `;
  },

  createGaugeBar(value) {
    if (!value || value <= 0) {
      return `
        <div class="gauge-container">
          <div class="gauge-bar gauge-red" style="width: 1%;"></div>
          <div class="gauge-text">0%</div>
        </div>
      `;
    }

    let colorClass = 'gauge-red';
    if (value >= 80) colorClass = 'gauge-green';
    else if (value >= 50) colorClass = 'gauge-blue';
    else if (value >= 20) colorClass = 'gauge-yellow';

    const barWidth = Math.min(100, Math.max(5, value));
    const displayText = value < 1 ? value.toFixed(1) + '%' : Math.round(value) + '%';

    return `
      <div class="gauge-container">
        <div class="gauge-bar ${colorClass}" style="width: ${barWidth}%;"></div>
        <div class="gauge-text">${displayText}</div>
      </div>
    `;
  },

  // 필터
  toggleCiiFilter(grade) {
    const key = 'cii' + grade.charAt(0).toUpperCase() + grade.slice(1);
    this.filters[key] = !this.filters[key];
    document.getElementById(`cii-${grade}`).classList.toggle('active');
  },

  async applyFilters() {
    if (this.originalResults.length === 0) {
      alert('먼저 검색을 실행해주세요.');
      return;
    }

    this.filters.viewCount = document.getElementById('view-count-filter').value;
    this.filters.subscriberCount = document.getElementById('subscriber-filter').value;

    try {
      const result = await this.callApi('filter', {
        results: this.originalResults,
        filters: this.filters
      });

      this.currentResults = result.data;
      this.displayResults(this.currentResults);
      this.updateStatus(result.message);

    } catch (error) {
      console.error('필터 오류:', error);
      alert('필터 적용 중 오류가 발생했습니다.');
    }
  },

  clearFilters() {
    this.filters = {
      ciiGreat: false,
      ciiGood: false,
      ciiSoso: false,
      viewCount: '',
      subscriberCount: ''
    };

    document.querySelectorAll('.cii-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById('view-count-filter').value = '';
    document.getElementById('subscriber-filter').value = '';

    if (this.originalResults.length > 0) {
      this.currentResults = [...this.originalResults];
      this.displayResults(this.currentResults);
      this.updateStatus('필터 해제됨');
    }
  },

  clearResults() {
    this.originalResults = [];
    this.currentResults = [];
    document.getElementById('results-body').innerHTML = '';
    document.getElementById('search-keyword').value = '';
    document.getElementById('youtube-url').value = '';
    document.getElementById('empty-results').style.display = 'flex';
    document.querySelector('.table-wrapper').style.display = 'none';
    document.getElementById('result-count').textContent = '(0개)';
    this.updateStatus('결과 초기화됨');
  },

  // 영상 모달
  showVideoModal(videoId, title) {
    this.currentVideoId = videoId;
    document.getElementById('video-modal-title').textContent = title;
    document.getElementById('video-iframe').src = `https://www.youtube.com/embed/${videoId}`;
    document.getElementById('video-modal').style.display = 'flex';
  },

  closeVideoModal() {
    document.getElementById('video-iframe').src = '';
    document.getElementById('video-modal').style.display = 'none';
  },

  openYouTube() {
    if (this.currentVideoId) {
      window.open(`https://www.youtube.com/watch?v=${this.currentVideoId}`, '_blank');
    }
  },

  // 댓글 모달
  async showComments(videoId, title) {
    if (this.apiKeys.length === 0) {
      alert('API 키가 필요합니다.');
      return;
    }

    try {
      const result = await this.callApi('comments', { videoId });

      const container = document.getElementById('comments-list');
      if (result.data && result.data.length > 0) {
        container.innerHTML = result.data.map(comment => `
          <div class="comment-item">
            <img class="comment-avatar" src="${comment.authorImage}" onerror="this.style.display='none'">
            <div class="comment-content">
              <div class="comment-author">${comment.author}</div>
              <div class="comment-text">${comment.text}</div>
              <div class="comment-meta">👍 ${comment.likeCount} · ${new Date(comment.publishedAt).toLocaleDateString()}</div>
            </div>
          </div>
        `).join('');
      } else {
        container.innerHTML = '<div class="empty-keys">댓글이 없습니다</div>';
      }

      this.currentComments = result.data;
      document.getElementById('comments-modal').style.display = 'flex';

    } catch (error) {
      console.error('댓글 가져오기 오류:', error);
      alert('댓글을 가져오는 중 오류가 발생했습니다: ' + error.message);
    }
  },

  closeCommentsModal() {
    document.getElementById('comments-modal').style.display = 'none';
  },

  copyComments() {
    if (!this.currentComments || this.currentComments.length === 0) {
      alert('복사할 댓글이 없습니다.');
      return;
    }

    const text = this.currentComments.map((c, i) => `${i + 1}. ${c.text}`).join('\n\n');

    navigator.clipboard.writeText(text).then(() => {
      alert('댓글이 클립보드에 복사되었습니다.');
    }).catch(() => {
      // 대체 방법
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      alert('댓글이 클립보드에 복사되었습니다.');
    });
  },

  // 채널 ID로 검색
  async searchChannelById(channelId) {
    if (this.apiKeys.length === 0) {
      alert('API 키가 필요합니다.');
      return;
    }

    try {
      const result = await this.callApi('analyze', {
        url: `https://www.youtube.com/channel/${channelId}`
      });

      if (result.data && result.data.length > 0) {
        this.showChannelModal([result.data[0]]);
      }
    } catch (error) {
      console.error('채널 정보 가져오기 오류:', error);
    }
  },

  // 유틸리티
  formatNumber(num) {
    if (!num) return '0';
    if (num >= 100000000) return (num / 100000000).toFixed(1) + '억';
    if (num >= 10000) return (num / 10000).toFixed(1) + '만';
    if (num >= 1000) return (num / 1000).toFixed(1) + '천';
    return num.toLocaleString();
  },

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/'/g, '&apos;').replace(/"/g, '&quot;');
  }
};

// 모달 외부 클릭 시 닫기
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal')) {
    e.target.style.display = 'none';
    // 비디오 모달인 경우 iframe 정리
    if (e.target.id === 'video-modal') {
      document.getElementById('video-iframe').src = '';
    }
  }
});

// 채널 모달에 선택 버튼 이벤트 추가
document.addEventListener('DOMContentLoaded', () => {
  TubeLens.init();

  // 채널 선택 버튼 추가
  const channelModal = document.getElementById('channel-modal');
  if (channelModal) {
    const modalBody = channelModal.querySelector('.modal-body');
    const footer = document.createElement('div');
    footer.className = 'modal-footer';
    footer.innerHTML = `
      <button class="btn btn-search" onclick="TubeLens.collectChannelVideos()">영상 수집</button>
      <button class="btn btn-close" onclick="TubeLens.closeChannelModal()">취소</button>
    `;
    modalBody.parentNode.insertBefore(footer, modalBody.nextSibling);
  }
});
