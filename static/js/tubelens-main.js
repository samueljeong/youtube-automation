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
  searchType: 'video',
  sortType: 'viewCount',
  selectedChannelIndex: -1,
  channelList: [],
  currentVideoId: null,
  currentComments: [],
  currentDescription: '',
  filters: {
    ciiGreat: false,
    ciiGood: false,
    ciiSoso: false
  },

  // 초기화
  init() {
    this.loadApiKeys();
    this.updateApiKeysList();
    this.updateStatus();
    console.log('[TubeLens] Initialized');
  },

  // ===== API 키 관리 =====
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

    if (!key.startsWith('AIza') || key.length !== 39) {
      alert('올바른 YouTube API 키 형식이 아닙니다.\n(AIza로 시작하는 39자리 키)');
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
    this.updateStatus(`API 키 ${index + 1} 활성화됨`);
  },

  updateApiKeysList() {
    const container = document.getElementById('api-keys-list');
    if (!container) return;

    if (this.apiKeys.length === 0) {
      container.innerHTML = '<div class="empty-list">등록된 API 키가 없습니다</div>';
      return;
    }

    container.innerHTML = this.apiKeys.map((key, index) => {
      const isActive = index === this.currentApiKeyIndex;
      const maskedKey = key.substring(0, 8) + '••••••••' + key.substring(key.length - 4);
      return `
        <div class="api-key-item ${isActive ? 'active' : ''}">
          <span class="api-key-text">${maskedKey}</span>
          <div class="api-key-actions">
            ${!isActive ? `<button class="btn-sm success" onclick="TubeLens.setActiveApiKey(${index})">사용</button>` : '<span style="color:#48bb78;font-size:0.8rem;">✓ 활성</span>'}
            <button class="btn-sm danger" onclick="TubeLens.removeApiKey(${index})">삭제</button>
          </div>
        </div>
      `;
    }).join('');
  },

  // ===== 모달 관리 =====
  openSettings() {
    document.getElementById('settings-modal').classList.add('show');
  },

  closeSettings() {
    document.getElementById('settings-modal').classList.remove('show');
  },

  openVideoModal(videoId, title) {
    this.currentVideoId = videoId;
    document.getElementById('video-modal-title').textContent = title;
    document.getElementById('video-iframe').src = `https://www.youtube.com/embed/${videoId}?autoplay=1`;
    document.getElementById('video-modal').classList.add('show');
  },

  closeVideoModal() {
    document.getElementById('video-iframe').src = '';
    document.getElementById('video-modal').classList.remove('show');
  },

  openYouTube() {
    if (this.currentVideoId) {
      window.open(`https://www.youtube.com/watch?v=${this.currentVideoId}`, '_blank');
    }
  },

  openChannelModal(channels) {
    this.channelList = channels;
    this.selectedChannelIndex = -1;

    const container = document.getElementById('channel-list');
    container.innerHTML = channels.map((ch, i) => `
      <div class="channel-item" data-index="${i}" onclick="TubeLens.selectChannelItem(${i})">
        <img class="channel-thumb" src="${ch.thumbnailUrl || ''}" alt="" onerror="this.style.display='none'">
        <div class="channel-info">
          <h4>${ch.channelTitle}${ch.isExactMatch ? ' <span style="color:#48bb78">(일치)</span>' : ''}</h4>
          <p>구독자 ${this.formatNumber(ch.subscriberCount)}명 · 영상 ${this.formatNumber(ch.videoCount)}개</p>
        </div>
      </div>
    `).join('');

    document.getElementById('channel-modal').classList.add('show');
  },

  selectChannelItem(index) {
    document.querySelectorAll('.channel-item').forEach(el => el.classList.remove('selected'));
    document.querySelector(`.channel-item[data-index="${index}"]`).classList.add('selected');
    this.selectedChannelIndex = index;
  },

  closeChannelModal() {
    document.getElementById('channel-modal').classList.remove('show');
  },

  async selectChannel() {
    if (this.selectedChannelIndex < 0) {
      alert('채널을 선택해주세요.');
      return;
    }

    const channel = this.channelList[this.selectedChannelIndex];
    this.closeChannelModal();
    await this.loadChannelVideos(channel);
  },

  openCommentsModal() {
    document.getElementById('comments-modal').classList.add('show');
  },

  closeCommentsModal() {
    document.getElementById('comments-modal').classList.remove('show');
  },

  openDescriptionModal() {
    document.getElementById('description-modal').classList.add('show');
  },

  closeDescriptionModal() {
    document.getElementById('description-modal').classList.remove('show');
  },

  // ===== 검색 설정 =====
  setSearchType(type) {
    this.searchType = type;
    document.getElementById('btn-video').classList.toggle('active', type === 'video');
    document.getElementById('btn-channel').classList.toggle('active', type === 'channel');
  },

  setSort(type) {
    this.sortType = type;
    document.getElementById('btn-sort-view').classList.toggle('active', type === 'viewCount');
    document.getElementById('btn-sort-date').classList.toggle('active', type === 'date');
  },

  toggleCii(grade) {
    const key = 'cii' + grade.charAt(0).toUpperCase() + grade.slice(1);
    this.filters[key] = !this.filters[key];
    document.getElementById(`cii-${grade}`).classList.toggle('active');
  },

  // ===== 상태 업데이트 =====
  updateStatus(message) {
    const el = document.getElementById('status-bar');
    if (!el) return;

    if (message) {
      el.textContent = message;
    } else if (this.apiKeys.length === 0) {
      el.textContent = '준비 완료 - API 키를 설정하고 검색을 시작하세요';
    } else {
      el.textContent = `준비 완료 - API 키 ${this.currentApiKeyIndex + 1}/${this.apiKeys.length} 활성`;
    }
  },

  showLoading(show) {
    const loading = document.getElementById('loading');
    const tableWrapper = document.getElementById('table-wrapper');
    const emptyState = document.querySelector('.empty-state');

    if (loading) loading.style.display = show ? 'flex' : 'none';
    if (tableWrapper) tableWrapper.style.display = show ? 'none' : (this.currentResults.length > 0 ? 'block' : 'none');
    if (emptyState) emptyState.style.display = show || this.currentResults.length > 0 ? 'none' : 'flex';
  },

  // ===== API 호출 =====
  getApiKey() {
    if (this.apiKeys.length === 0) return null;
    return this.apiKeys[this.currentApiKeyIndex];
  },

  async youtubeApi(endpoint, params = {}) {
    const apiKey = this.getApiKey();
    if (!apiKey) throw new Error('API 키가 없습니다');

    const url = new URL(`https://www.googleapis.com/youtube/v3/${endpoint}`);
    url.searchParams.set('key', apiKey);
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        url.searchParams.set(k, v);
      }
    });

    const res = await fetch(url);
    const data = await res.json();

    if (data.error) {
      // API 키 할당량 초과시 다음 키로 전환
      if (data.error.code === 403 && this.apiKeys.length > 1) {
        this.currentApiKeyIndex = (this.currentApiKeyIndex + 1) % this.apiKeys.length;
        this.saveApiKeys();
        this.updateStatus(`API 할당량 초과 - 키 ${this.currentApiKeyIndex + 1}로 전환`);
        return this.youtubeApi(endpoint, params);
      }
      throw new Error(data.error.message);
    }

    return data;
  },

  // ===== 검색 기능 =====
  async search() {
    const keyword = document.getElementById('search-keyword').value.trim();

    if (!keyword) {
      alert('검색어를 입력해주세요.');
      return;
    }

    if (this.apiKeys.length === 0) {
      alert('먼저 API 키를 설정해주세요.');
      this.openSettings();
      return;
    }

    this.showLoading(true);
    this.updateStatus('검색 중...');

    try {
      if (this.searchType === 'channel') {
        await this.searchChannels(keyword);
      } else {
        await this.searchVideos(keyword);
      }
    } catch (error) {
      console.error('[TubeLens] Search error:', error);
      alert('검색 중 오류가 발생했습니다: ' + error.message);
      this.showLoading(false);
      this.updateStatus('검색 실패: ' + error.message);
    }
  },

  async searchVideos(keyword) {
    const maxResults = parseInt(document.getElementById('max-results').value) || 50;
    const timePeriod = document.getElementById('time-period').value;
    const regionCode = document.getElementById('region').value;
    const videoType = document.getElementById('video-type').value;

    // 기간 계산
    let publishedAfter = '';
    if (timePeriod) {
      const now = new Date();
      const periods = {
        hour: 1 / 24,
        day: 1,
        week: 7,
        month: 30,
        year: 365
      };
      if (periods[timePeriod]) {
        now.setDate(now.getDate() - periods[timePeriod]);
        publishedAfter = now.toISOString();
      }
    }

    // 영상 타입별 duration 필터
    let videoDuration = '';
    if (videoType === 'shorts') videoDuration = 'short';
    else if (videoType === 'long_4_20') videoDuration = 'medium';
    else if (videoType === 'long_20') videoDuration = 'long';

    // 검색 실행
    const searchResult = await this.youtubeApi('search', {
      part: 'snippet',
      q: keyword,
      type: 'video',
      maxResults: Math.min(maxResults, 50),
      order: this.sortType,
      regionCode: regionCode,
      publishedAfter: publishedAfter,
      videoDuration: videoDuration
    });

    if (!searchResult.items || searchResult.items.length === 0) {
      this.originalResults = [];
      this.currentResults = [];
      this.displayResults([]);
      this.updateStatus('검색 결과가 없습니다');
      return;
    }

    // 영상 상세 정보 가져오기
    const videoIds = searchResult.items.map(item => item.id.videoId).join(',');
    const videoDetails = await this.youtubeApi('videos', {
      part: 'snippet,statistics,contentDetails',
      id: videoIds
    });

    // 채널 정보 가져오기
    const channelIds = [...new Set(videoDetails.items.map(v => v.snippet.channelId))].join(',');
    const channelDetails = await this.youtubeApi('channels', {
      part: 'statistics',
      id: channelIds
    });

    const channelMap = {};
    channelDetails.items.forEach(ch => {
      channelMap[ch.id] = parseInt(ch.statistics.subscriberCount) || 0;
    });

    // 결과 가공
    this.originalResults = videoDetails.items.map((video, index) => {
      const subscriberCount = channelMap[video.snippet.channelId] || 0;
      const viewCount = parseInt(video.statistics.viewCount) || 0;
      const likeCount = parseInt(video.statistics.likeCount) || 0;
      const commentCount = parseInt(video.statistics.commentCount) || 0;

      // CII 계산
      const { contributionValue, performanceValue, cii } = this.calculateCII(viewCount, subscriberCount);

      return {
        index: index + 1,
        videoId: video.id,
        title: video.snippet.title,
        channelId: video.snippet.channelId,
        channelTitle: video.snippet.channelTitle,
        thumbnail: video.snippet.thumbnails.medium?.url || video.snippet.thumbnails.default?.url,
        publishedAt: this.formatDate(video.snippet.publishedAt),
        duration: this.formatDuration(video.contentDetails.duration),
        viewCount,
        likeCount,
        commentCount,
        subscriberCount,
        contributionValue,
        performanceValue,
        cii,
        description: video.snippet.description
      };
    });

    this.currentResults = [...this.originalResults];
    this.displayResults(this.currentResults);
    this.updateStatus(`${this.currentResults.length}개 영상 검색됨`);
  },

  async searchChannels(keyword) {
    const regionCode = document.getElementById('region').value;

    const result = await this.youtubeApi('search', {
      part: 'snippet',
      q: keyword,
      type: 'channel',
      maxResults: 10,
      regionCode: regionCode
    });

    if (!result.items || result.items.length === 0) {
      alert('검색된 채널이 없습니다.');
      this.showLoading(false);
      this.updateStatus('채널 검색 결과 없음');
      return;
    }

    const channelIds = result.items.map(item => item.id.channelId).join(',');
    const channelDetails = await this.youtubeApi('channels', {
      part: 'snippet,statistics,contentDetails',
      id: channelIds
    });

    const channels = channelDetails.items.map(ch => ({
      channelId: ch.id,
      channelTitle: ch.snippet.title,
      thumbnailUrl: ch.snippet.thumbnails.default?.url,
      subscriberCount: parseInt(ch.statistics.subscriberCount) || 0,
      videoCount: parseInt(ch.statistics.videoCount) || 0,
      uploadPlaylist: ch.contentDetails?.relatedPlaylists?.uploads,
      isExactMatch: ch.snippet.title.toLowerCase() === keyword.toLowerCase()
    }));

    this.showLoading(false);
    this.openChannelModal(channels);
    this.updateStatus(`${channels.length}개 채널 검색됨`);
  },

  async loadChannelVideos(channel) {
    this.showLoading(true);
    this.updateStatus(`채널 영상 로딩 중: ${channel.channelTitle}`);

    try {
      const maxResults = parseInt(document.getElementById('max-results').value) || 50;
      const videoTypeFilter = document.getElementById('channel-video-type').value;

      // 채널의 업로드 플레이리스트에서 영상 가져오기
      const playlistResult = await this.youtubeApi('playlistItems', {
        part: 'snippet',
        playlistId: channel.uploadPlaylist,
        maxResults: Math.min(maxResults, 50)
      });

      if (!playlistResult.items || playlistResult.items.length === 0) {
        this.originalResults = [];
        this.currentResults = [];
        this.displayResults([]);
        this.updateStatus('채널에 영상이 없습니다');
        return;
      }

      const videoIds = playlistResult.items.map(item => item.snippet.resourceId.videoId).join(',');
      const videoDetails = await this.youtubeApi('videos', {
        part: 'snippet,statistics,contentDetails',
        id: videoIds
      });

      // 결과 가공
      this.originalResults = videoDetails.items.map((video, index) => {
        const viewCount = parseInt(video.statistics.viewCount) || 0;
        const likeCount = parseInt(video.statistics.likeCount) || 0;
        const commentCount = parseInt(video.statistics.commentCount) || 0;

        const { contributionValue, performanceValue, cii } = this.calculateCII(viewCount, channel.subscriberCount);

        return {
          index: index + 1,
          videoId: video.id,
          title: video.snippet.title,
          channelId: channel.channelId,
          channelTitle: channel.channelTitle,
          thumbnail: video.snippet.thumbnails.medium?.url || video.snippet.thumbnails.default?.url,
          publishedAt: this.formatDate(video.snippet.publishedAt),
          duration: this.formatDuration(video.contentDetails.duration),
          viewCount,
          likeCount,
          commentCount,
          subscriberCount: channel.subscriberCount,
          contributionValue,
          performanceValue,
          cii,
          description: video.snippet.description
        };
      });

      // 영상 타입 필터링
      if (videoTypeFilter === 'shorts') {
        this.originalResults = this.originalResults.filter(v => this.isShorts(v.duration));
      } else if (videoTypeFilter === 'long') {
        this.originalResults = this.originalResults.filter(v => !this.isShorts(v.duration));
      }

      // 인덱스 재정렬
      this.originalResults.forEach((v, i) => v.index = i + 1);

      this.currentResults = [...this.originalResults];
      this.displayResults(this.currentResults);
      this.updateStatus(`${channel.channelTitle} - ${this.currentResults.length}개 영상`);

    } catch (error) {
      console.error('[TubeLens] Load channel videos error:', error);
      alert('채널 영상을 불러오는 중 오류가 발생했습니다: ' + error.message);
      this.showLoading(false);
    }
  },

  isShorts(duration) {
    // 1분 이하면 쇼츠로 판단
    const match = duration.match(/(\d+):(\d+)/);
    if (match) {
      const minutes = parseInt(match[1]);
      const seconds = parseInt(match[2]);
      return minutes === 0 && seconds <= 60;
    }
    return false;
  },

  // ===== CII 계산 =====
  calculateCII(viewCount, subscriberCount) {
    if (!subscriberCount || subscriberCount === 0) {
      return { contributionValue: 0, performanceValue: 0, cii: 'N/A' };
    }

    // 채널 기여도: (조회수 / 구독자수) * 100
    const contributionValue = (viewCount / subscriberCount) * 100;

    // 성과도 배율: 조회수 / 구독자수
    const performanceValue = viewCount / subscriberCount;

    // CII 등급
    let cii = 'Bad';
    if (performanceValue >= 3) cii = 'Great!!';
    else if (performanceValue >= 1.5) cii = 'Good';
    else if (performanceValue >= 0.5) cii = 'Soso';
    else if (performanceValue >= 0.2) cii = 'Not bad';

    return { contributionValue, performanceValue, cii };
  },

  // ===== 필터 =====
  applyFilters() {
    if (this.originalResults.length === 0) {
      alert('먼저 검색을 실행해주세요.');
      return;
    }

    const minViews = parseInt(document.getElementById('min-views').value) || 0;
    const maxSubs = parseInt(document.getElementById('subscriber-range').value) || Infinity;
    const { ciiGreat, ciiGood, ciiSoso } = this.filters;
    const hasCiiFilter = ciiGreat || ciiGood || ciiSoso;

    this.currentResults = this.originalResults.filter(item => {
      // 조회수 필터
      if (minViews > 0 && item.viewCount < minViews) return false;

      // 구독자 필터
      if (maxSubs < Infinity && item.subscriberCount > maxSubs) return false;

      // CII 필터
      if (hasCiiFilter) {
        if (ciiGreat && item.cii === 'Great!!') return true;
        if (ciiGood && item.cii === 'Good') return true;
        if (ciiSoso && item.cii === 'Soso') return true;
        return false;
      }

      return true;
    });

    // 인덱스 재정렬
    this.currentResults.forEach((v, i) => v.index = i + 1);

    this.displayResults(this.currentResults);
    this.updateStatus(`필터 적용됨 - ${this.currentResults.length}개 영상`);
  },

  clearFilters() {
    this.filters = { ciiGreat: false, ciiGood: false, ciiSoso: false };
    document.querySelectorAll('.cii-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById('min-views').value = '';
    document.getElementById('subscriber-range').value = '';

    if (this.originalResults.length > 0) {
      this.currentResults = [...this.originalResults];
      this.currentResults.forEach((v, i) => v.index = i + 1);
      this.displayResults(this.currentResults);
      this.updateStatus('필터 초기화됨');
    }
  },

  // ===== 결과 표시 =====
  displayResults(results) {
    const tbody = document.getElementById('results-tbody');
    const countEl = document.getElementById('results-count');
    const tableWrapper = document.getElementById('table-wrapper');
    const emptyState = document.querySelector('.empty-state');

    if (!results || results.length === 0) {
      if (tbody) tbody.innerHTML = '';
      if (countEl) countEl.textContent = '0개 영상';
      if (tableWrapper) tableWrapper.style.display = 'none';
      if (emptyState) emptyState.style.display = 'flex';
      this.showLoading(false);
      return;
    }

    if (countEl) countEl.textContent = `${results.length}개 영상`;
    if (tableWrapper) tableWrapper.style.display = 'block';
    if (emptyState) emptyState.style.display = 'none';

    if (tbody) {
      tbody.innerHTML = results.map(item => this.createResultRow(item)).join('');
    }

    this.showLoading(false);
  },

  createResultRow(item) {
    // CII 뱃지 클래스
    const ciiClasses = {
      'Great!!': 'cii-great',
      'Good': 'cii-good',
      'Soso': 'cii-soso',
      'Not bad': 'cii-notbad',
      'Bad': 'cii-bad',
      'N/A': 'cii-bad'
    };
    const ciiClass = ciiClasses[item.cii] || 'cii-bad';

    // 기여도 게이지
    const contribPercent = Math.min(100, item.contributionValue);
    const contribColor = contribPercent >= 100 ? 'green' : contribPercent >= 50 ? 'blue' : contribPercent >= 20 ? 'yellow' : 'red';

    return `
      <tr>
        <td>${item.index}</td>
        <td>
          <img class="thumbnail" src="${item.thumbnail}" alt=""
               onclick="TubeLens.openVideoModal('${item.videoId}', '${this.escapeHtml(item.title)}')"
               onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22140%22 height=%2279%22><rect fill=%22%23e1e5eb%22 width=%22140%22 height=%2279%22/><text x=%2270%22 y=%2245%22 text-anchor=%22middle%22 fill=%22%23999%22 font-size=%2212%22>No Image</text></svg>'">
        </td>
        <td class="channel-name" onclick="TubeLens.searchChannelById('${item.channelId}')">${item.channelTitle}</td>
        <td class="video-title">${item.title}</td>
        <td>${item.publishedAt}</td>
        <td>${this.formatNumber(item.viewCount)}</td>
        <td>${this.formatNumber(item.subscriberCount)}</td>
        <td>
          <div class="gauge"><div class="gauge-fill ${contribColor}" style="width:${contribPercent}%"></div></div>
          <div class="gauge-value">${contribPercent.toFixed(0)}%</div>
        </td>
        <td>${item.performanceValue.toFixed(2)}x</td>
        <td><span class="cii-badge ${ciiClass}">${item.cii}</span></td>
        <td>${item.duration}</td>
        <td>${this.formatNumber(item.likeCount)}</td>
        <td style="cursor:pointer;color:#3182ce" onclick="TubeLens.loadComments('${item.videoId}', '${this.escapeHtml(item.title)}')">${this.formatNumber(item.commentCount)}</td>
      </tr>
    `;
  },

  // ===== 댓글 =====
  async loadComments(videoId, title) {
    try {
      this.updateStatus('댓글 로딩 중...');

      const result = await this.youtubeApi('commentThreads', {
        part: 'snippet',
        videoId: videoId,
        order: 'relevance',
        maxResults: 20
      });

      if (!result.items || result.items.length === 0) {
        this.currentComments = [];
        document.getElementById('comments-list').innerHTML = '<div class="empty-list">댓글이 없습니다</div>';
      } else {
        this.currentComments = result.items.map(item => ({
          author: item.snippet.topLevelComment.snippet.authorDisplayName,
          authorImage: item.snippet.topLevelComment.snippet.authorProfileImageUrl,
          text: item.snippet.topLevelComment.snippet.textDisplay,
          likeCount: item.snippet.topLevelComment.snippet.likeCount,
          publishedAt: item.snippet.topLevelComment.snippet.publishedAt
        }));

        document.getElementById('comments-list').innerHTML = this.currentComments.map(c => `
          <div class="comment-item">
            <img class="comment-avatar" src="${c.authorImage}" alt="" onerror="this.style.display='none'">
            <div>
              <div class="comment-author">${c.author}</div>
              <div class="comment-text">${c.text}</div>
              <div class="comment-meta">👍 ${c.likeCount} · ${this.formatDate(c.publishedAt)}</div>
            </div>
          </div>
        `).join('');
      }

      this.openCommentsModal();
      this.updateStatus(`${this.currentComments.length}개 댓글 로드됨`);

    } catch (error) {
      console.error('[TubeLens] Load comments error:', error);
      alert('댓글을 불러오는 중 오류가 발생했습니다: ' + error.message);
    }
  },

  copyComments() {
    if (!this.currentComments || this.currentComments.length === 0) {
      alert('복사할 댓글이 없습니다.');
      return;
    }

    const text = this.currentComments.map((c, i) => `${i + 1}. [${c.author}] ${c.text.replace(/<[^>]*>/g, '')}`).join('\n\n');

    navigator.clipboard.writeText(text).then(() => {
      alert('댓글이 클립보드에 복사되었습니다.');
    }).catch(() => {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      alert('댓글이 클립보드에 복사되었습니다.');
    });
  },

  // ===== 설명 =====
  showDescription(videoId) {
    const video = this.currentResults.find(v => v.videoId === videoId);
    if (video) {
      this.currentDescription = video.description;
      document.getElementById('description-content').textContent = video.description || '설명이 없습니다.';
      this.openDescriptionModal();
    }
  },

  copyDescription() {
    if (!this.currentDescription) {
      alert('복사할 설명이 없습니다.');
      return;
    }

    navigator.clipboard.writeText(this.currentDescription).then(() => {
      alert('설명이 클립보드에 복사되었습니다.');
    }).catch(() => {
      const textarea = document.createElement('textarea');
      textarea.value = this.currentDescription;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      alert('설명이 클립보드에 복사되었습니다.');
    });
  },

  // ===== 채널 검색 =====
  async searchChannelById(channelId) {
    try {
      const result = await this.youtubeApi('channels', {
        part: 'snippet,statistics,contentDetails',
        id: channelId
      });

      if (result.items && result.items.length > 0) {
        const ch = result.items[0];
        this.openChannelModal([{
          channelId: ch.id,
          channelTitle: ch.snippet.title,
          thumbnailUrl: ch.snippet.thumbnails.default?.url,
          subscriberCount: parseInt(ch.statistics.subscriberCount) || 0,
          videoCount: parseInt(ch.statistics.videoCount) || 0,
          uploadPlaylist: ch.contentDetails?.relatedPlaylists?.uploads
        }]);
      }
    } catch (error) {
      console.error('[TubeLens] Search channel error:', error);
    }
  },

  // ===== 유틸리티 =====
  formatNumber(num) {
    if (!num) return '0';
    num = parseInt(num);
    if (num >= 100000000) return (num / 100000000).toFixed(1) + '억';
    if (num >= 10000) return (num / 10000).toFixed(1) + '만';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toLocaleString();
  },

  formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
  },

  formatDuration(isoDuration) {
    if (!isoDuration) return '0:00';
    const match = isoDuration.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
    if (!match) return '0:00';

    const hours = parseInt(match[1]) || 0;
    const minutes = parseInt(match[2]) || 0;
    const seconds = parseInt(match[3]) || 0;

    if (hours > 0) {
      return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }
    return `${minutes}:${String(seconds).padStart(2, '0')}`;
  },

  escapeHtml(text) {
    if (!text) return '';
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
};

// 모달 외부 클릭 시 닫기
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal') && e.target.classList.contains('show')) {
    e.target.classList.remove('show');
    if (e.target.id === 'video-modal') {
      document.getElementById('video-iframe').src = '';
    }
  }
});

// 초기화
document.addEventListener('DOMContentLoaded', () => {
  TubeLens.init();
});
