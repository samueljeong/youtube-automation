/**
 * TubeLens - YouTube Analytics Tool
 * 메인 JavaScript 모듈
 */

(function() {
  'use strict';

  var TubeLens = {
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
    currentTab: 'search',
    trendingCategory: '',
    risingCategory: '',
    filters: {
      ciiGreat: false,
      ciiGood: false,
      ciiSoso: false
    },

    // 초기화
    init: function() {
      this.loadApiKeys();
      this.loadServerConfig();  // 서버 API 키 자동 로드
      this.updateApiKeysList();
      this.updateStatus();
      this.initCategoryPills();
      this.initExcludePills();
      console.log('[TubeLens] Initialized with', this.apiKeys.length, 'API keys');
    },

    // 서버 설정 로드 (API 키)
    loadServerConfig: function() {
      var self = this;
      fetch('/api/tubelens/config')
        .then(function(res) { return res.json(); })
        .then(function(data) {
          if (data.success && data.data.hasYouTubeKey) {
            self.serverHasApiKey = true;
            self.serverMaskedKey = data.data.maskedKey;
            console.log('[TubeLens] 서버에 YouTube API 키가 설정되어 있습니다.');
            self.updateStatus('서버 API 키 사용 가능 - 검색 준비 완료');
          }
        })
        .catch(function(err) {
          console.log('[TubeLens] 서버 설정 로드 실패:', err);
        });
    },

    // 제외 카테고리 필 초기화
    initExcludePills: function() {
      var excluded = this.getExcludedCategories();
      var pills = document.querySelectorAll('.exclude-pill');
      pills.forEach(function(pill) {
        var catId = pill.getAttribute('data-category');
        if (excluded.indexOf(catId) !== -1) {
          pill.classList.add('excluded');
        }
      });
    },

    // 카테고리 필 초기화
    initCategoryPills: function() {
      var self = this;

      // 트렌딩 카테고리
      var trendingPills = document.querySelectorAll('#trending-categories .category-pill');
      trendingPills.forEach(function(pill) {
        pill.addEventListener('click', function() {
          trendingPills.forEach(function(p) { p.classList.remove('active'); });
          this.classList.add('active');
          self.trendingCategory = this.getAttribute('data-category') || '';
        });
      });

      // 급상승 카테고리
      var risingPills = document.querySelectorAll('#rising-categories .category-pill');
      risingPills.forEach(function(pill) {
        pill.addEventListener('click', function() {
          risingPills.forEach(function(p) { p.classList.remove('active'); });
          this.classList.add('active');
          self.risingCategory = this.getAttribute('data-category') || '';
        });
      });
    },

    // 탭 전환
    switchTab: function(tabName) {
      this.currentTab = tabName;

      // 탭 버튼 업데이트
      var tabs = document.querySelectorAll('.main-tab');
      tabs.forEach(function(tab) {
        tab.classList.remove('active');
      });
      document.getElementById('tab-' + tabName).classList.add('active');

      // 패널 업데이트
      var panels = document.querySelectorAll('.tab-panel');
      panels.forEach(function(panel) {
        panel.classList.remove('active');
      });
      document.getElementById('panel-' + tabName).classList.add('active');

      // 상태 업데이트
      if (tabName === 'search') {
        this.updateStatus('키워드 또는 채널을 검색하세요');
      } else if (tabName === 'trending') {
        this.updateStatus('지금 뜨는 인기 영상을 확인하세요');
      } else if (tabName === 'rising') {
        this.updateStatus('구독자 대비 고성과 영상을 발굴하세요');
      } else if (tabName === 'analyzer') {
        this.updateStatus('키워드와 필터를 설정하고 분석을 시작하세요');
      }

      // Empty state 메시지 업데이트
      this.updateEmptyState(tabName);
    },

    // Empty state 메시지 업데이트
    updateEmptyState: function(tabName) {
      var emptyState = document.querySelector('.empty-state');
      if (!emptyState) return;

      var h4 = emptyState.querySelector('h4');
      var p = emptyState.querySelector('p');
      if (!h4 || !p) return;

      if (tabName === 'search') {
        h4.textContent = '검색어를 입력해주세요';
        p.textContent = 'YouTube 영상을 검색하고 분석해보세요';
      } else if (tabName === 'trending') {
        h4.textContent = '인기 영상 보기를 클릭하세요';
        p.textContent = '지금 뜨고 있는 인기 영상을 확인해보세요';
      } else if (tabName === 'rising') {
        h4.textContent = '급상승 영상 발굴을 클릭하세요';
        p.textContent = '구독자 대비 고성과 영상을 발굴해보세요';
      } else if (tabName === 'analyzer') {
        h4.textContent = '콘텐츠 분석을 시작하세요';
        p.textContent = '키워드로 터진 영상을 찾고 제목/설명/댓글을 분석하세요';
      }
    },

    // ===== 트렌딩 영상 =====
    loadTrending: function() {
      var self = this;

      if (this.apiKeys.length === 0) {
        alert('먼저 API 키를 설정해주세요.');
        this.openSettings();
        return;
      }

      var regionCode = document.getElementById('trending-region').value;
      var videoType = document.getElementById('trending-video-type').value;

      this.showLoading(true);
      this.updateStatus('인기 영상 로딩 중...');

      fetch('/api/tubelens/trending', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          regionCode: regionCode,
          categoryId: this.trendingCategory,
          maxResults: 50,
          apiKeys: this.apiKeys,
          currentApiKeyIndex: this.currentApiKeyIndex
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          // 제외 카테고리 필터링
          var results = self.filterExcludedCategories(data.data);
          // 영상 타입 필터링
          results = self.filterByVideoType(results, videoType);
          self.originalResults = results;
          self.currentResults = results.slice();
          self.displayResults(self.currentResults);
          self.updateStatus('🔥 인기 영상 ' + self.currentResults.length + '개 로드됨');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Trending error:', error);
        alert('인기 영상 로드 실패: ' + error.message);
        self.showLoading(false);
        self.updateStatus('로드 실패: ' + error.message);
      });
    },

    // ===== 급상승 발굴 =====
    loadRising: function() {
      var self = this;

      if (this.apiKeys.length === 0) {
        alert('먼저 API 키를 설정해주세요.');
        this.openSettings();
        return;
      }

      var regionCode = document.getElementById('rising-region').value;
      var maxSubscribers = document.getElementById('rising-max-subs').value;
      var timeFrame = document.getElementById('rising-time').value;
      var videoType = document.getElementById('rising-video-type').value;

      this.showLoading(true);
      this.updateStatus('급상승 영상 발굴 중... (시간이 좀 걸릴 수 있습니다)');

      fetch('/api/tubelens/rising', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          regionCode: regionCode,
          maxSubscribers: parseInt(maxSubscribers),
          timeFrame: timeFrame,
          categoryId: this.risingCategory,
          videoType: videoType,
          apiKeys: this.apiKeys,
          currentApiKeyIndex: this.currentApiKeyIndex
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          // 제외 카테고리 필터링
          var results = self.filterExcludedCategories(data.data);
          // 영상 타입 필터링 (API에서도 하지만 추가 보정)
          results = self.filterByVideoType(results, videoType);
          self.originalResults = results;
          self.currentResults = results.slice();
          self.displayResults(self.currentResults);
          self.updateStatus('🚀 급상승 영상 ' + self.currentResults.length + '개 발굴됨');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Rising error:', error);
        alert('급상승 영상 발굴 실패: ' + error.message);
        self.showLoading(false);
        self.updateStatus('발굴 실패: ' + error.message);
      });
    },

    // 영상 타입 필터링 (쇼츠/롱폼)
    filterByVideoType: function(videos, videoType) {
      if (!videoType || videoType === 'all') return videos;

      var filtered = videos.filter(function(v) {
        var duration = v.durationSeconds || 0;
        if (videoType === 'shorts') {
          return duration <= 60;
        } else if (videoType === 'long') {
          return duration > 60;
        }
        return true;
      });

      // 인덱스 재할당
      filtered.forEach(function(v, i) {
        v.index = i + 1;
      });

      return filtered;
    },

    // 제외 카테고리 필터링
    filterExcludedCategories: function(videos) {
      var excluded = this.getExcludedCategories();
      if (excluded.length === 0) return videos;

      var filtered = videos.filter(function(v) {
        var categoryId = v.categoryId ? v.categoryId.toString() : '';
        return excluded.indexOf(categoryId) === -1;
      });

      // 인덱스 재할당
      filtered.forEach(function(v, i) {
        v.index = i + 1;
      });

      return filtered;
    },

    getExcludedCategories: function() {
      var saved = localStorage.getItem('tubelens_excluded_categories');
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch (e) {
          return [];
        }
      }
      return [];
    },

    setExcludedCategories: function(categories) {
      localStorage.setItem('tubelens_excluded_categories', JSON.stringify(categories));
    },

    toggleExcludeCategory: function(categoryId) {
      var excluded = this.getExcludedCategories();
      var index = excluded.indexOf(categoryId);
      if (index === -1) {
        excluded.push(categoryId);
      } else {
        excluded.splice(index, 1);
      }
      this.setExcludedCategories(excluded);

      // UI 업데이트
      var pills = document.querySelectorAll('.exclude-pill[data-category="' + categoryId + '"]');
      pills.forEach(function(pill) {
        pill.classList.toggle('excluded');
      });
    },

    // ===== API 키 관리 =====
    loadApiKeys: function() {
      var saved = localStorage.getItem('tubelens_api_keys');
      if (saved) {
        try {
          this.apiKeys = JSON.parse(saved);
          this.currentApiKeyIndex = parseInt(localStorage.getItem('tubelens_api_index') || '0');
        } catch (e) {
          console.error('[TubeLens] Failed to load API keys:', e);
          this.apiKeys = [];
        }
      }
    },

    saveApiKeys: function() {
      localStorage.setItem('tubelens_api_keys', JSON.stringify(this.apiKeys));
      localStorage.setItem('tubelens_api_index', this.currentApiKeyIndex.toString());
    },

    addApiKey: function() {
      var input = document.getElementById('new-api-key');
      var key = input.value.trim();

      if (!key) {
        alert('API 키를 입력해주세요.');
        return;
      }

      if (!key.startsWith('AIza') || key.length !== 39) {
        alert('올바른 YouTube API 키 형식이 아닙니다.\n(AIza로 시작하는 39자리 키)');
        return;
      }

      if (this.apiKeys.indexOf(key) !== -1) {
        alert('이미 등록된 API 키입니다.');
        return;
      }

      this.apiKeys.push(key);
      this.saveApiKeys();
      this.updateApiKeysList();
      input.value = '';
      this.updateStatus('API 키가 추가되었습니다.');
    },

    removeApiKey: function(index) {
      if (confirm('이 API 키를 삭제하시겠습니까?')) {
        this.apiKeys.splice(index, 1);
        if (this.currentApiKeyIndex >= this.apiKeys.length) {
          this.currentApiKeyIndex = Math.max(0, this.apiKeys.length - 1);
        }
        this.saveApiKeys();
        this.updateApiKeysList();
      }
    },

    setActiveApiKey: function(index) {
      this.currentApiKeyIndex = index;
      this.saveApiKeys();
      this.updateApiKeysList();
      this.updateStatus('API 키 ' + (index + 1) + ' 활성화됨');
    },

    updateApiKeysList: function() {
      var container = document.getElementById('api-keys-list');
      if (!container) return;

      var self = this;

      if (this.apiKeys.length === 0) {
        container.innerHTML = '<div class="empty-list">등록된 API 키가 없습니다</div>';
        return;
      }

      var html = '';
      for (var i = 0; i < this.apiKeys.length; i++) {
        var key = this.apiKeys[i];
        var isActive = i === this.currentApiKeyIndex;
        var maskedKey = key.substring(0, 8) + '••••••••' + key.substring(key.length - 4);

        html += '<div class="api-key-item ' + (isActive ? 'active' : '') + '">';
        html += '<span class="api-key-text">' + maskedKey + '</span>';
        html += '<div class="api-key-actions">';
        if (!isActive) {
          html += '<button class="btn-sm success" onclick="TubeLens.setActiveApiKey(' + i + ')">사용</button>';
        } else {
          html += '<span style="color:#48bb78;font-size:0.8rem;">✓ 활성</span>';
        }
        html += '<button class="btn-sm danger" onclick="TubeLens.removeApiKey(' + i + ')">삭제</button>';
        html += '</div></div>';
      }
      container.innerHTML = html;
    },

    // ===== 모달 관리 =====
    openSettings: function() {
      document.getElementById('settings-modal').classList.add('show');
    },

    closeSettings: function() {
      document.getElementById('settings-modal').classList.remove('show');
    },

    openVideoModal: function(videoId, title) {
      this.currentVideoId = videoId;
      document.getElementById('video-modal-title').textContent = title;
      document.getElementById('video-iframe').src = 'https://www.youtube.com/embed/' + videoId + '?autoplay=1';
      document.getElementById('video-modal').classList.add('show');
    },

    closeVideoModal: function() {
      document.getElementById('video-iframe').src = '';
      document.getElementById('video-modal').classList.remove('show');
    },

    openYouTube: function() {
      if (this.currentVideoId) {
        window.open('https://www.youtube.com/watch?v=' + this.currentVideoId, '_blank');
      }
    },

    openChannelModal: function(channels) {
      this.channelList = channels;
      this.selectedChannelIndex = -1;

      var html = '';
      for (var i = 0; i < channels.length; i++) {
        var ch = channels[i];
        html += '<div class="channel-item" data-index="' + i + '" onclick="TubeLens.selectChannelItem(' + i + ')">';
        html += '<img class="channel-thumb" src="' + (ch.thumbnailUrl || '') + '" alt="" onerror="this.style.display=\'none\'">';
        html += '<div class="channel-info">';
        html += '<h4>' + ch.channelTitle + (ch.isExactMatch ? ' <span style="color:#48bb78">(일치)</span>' : '') + '</h4>';
        html += '<p>구독자 ' + this.formatNumber(ch.subscriberCount) + '명 · 영상 ' + this.formatNumber(ch.videoCount) + '개</p>';
        html += '</div></div>';
      }

      document.getElementById('channel-list').innerHTML = html;
      document.getElementById('channel-modal').classList.add('show');
    },

    selectChannelItem: function(index) {
      var items = document.querySelectorAll('.channel-item');
      for (var i = 0; i < items.length; i++) {
        items[i].classList.remove('selected');
      }
      document.querySelector('.channel-item[data-index="' + index + '"]').classList.add('selected');
      this.selectedChannelIndex = index;
    },

    closeChannelModal: function() {
      document.getElementById('channel-modal').classList.remove('show');
    },

    selectChannel: function() {
      if (this.selectedChannelIndex < 0) {
        alert('채널을 선택해주세요.');
        return;
      }

      var channel = this.channelList[this.selectedChannelIndex];
      this.closeChannelModal();
      this.loadChannelVideos(channel);
    },

    openCommentsModal: function() {
      document.getElementById('comments-modal').classList.add('show');
    },

    closeCommentsModal: function() {
      document.getElementById('comments-modal').classList.remove('show');
    },

    openDescriptionModal: function() {
      document.getElementById('description-modal').classList.add('show');
    },

    closeDescriptionModal: function() {
      document.getElementById('description-modal').classList.remove('show');
    },

    // ===== 검색 설정 =====
    setSearchType: function(type) {
      this.searchType = type;
      document.getElementById('btn-video').classList.toggle('active', type === 'video');
      document.getElementById('btn-channel').classList.toggle('active', type === 'channel');
    },

    setSort: function(type) {
      this.sortType = type;
      document.getElementById('btn-sort-view').classList.toggle('active', type === 'viewCount');
      document.getElementById('btn-sort-date').classList.toggle('active', type === 'date');
    },

    toggleCii: function(grade) {
      var key = 'cii' + grade.charAt(0).toUpperCase() + grade.slice(1);
      this.filters[key] = !this.filters[key];
      document.getElementById('cii-' + grade).classList.toggle('active');
    },

    // ===== 상태 업데이트 =====
    updateStatus: function(message) {
      var el = document.getElementById('status-bar');
      if (!el) return;

      if (message) {
        el.textContent = message;
      } else if (this.apiKeys.length === 0) {
        el.textContent = '준비 완료 - API 키를 설정하고 검색을 시작하세요';
      } else {
        el.textContent = '준비 완료 - API 키 ' + (this.currentApiKeyIndex + 1) + '/' + this.apiKeys.length + ' 활성';
      }
    },

    showLoading: function(show) {
      var loading = document.getElementById('loading');
      var tableWrapper = document.getElementById('table-wrapper');
      var emptyState = document.querySelector('.empty-state');

      if (loading) loading.style.display = show ? 'flex' : 'none';
      if (tableWrapper) tableWrapper.style.display = show ? 'none' : (this.currentResults.length > 0 ? 'block' : 'none');
      if (emptyState) emptyState.style.display = show || this.currentResults.length > 0 ? 'none' : 'flex';
    },

    // ===== API 호출 =====
    getApiKey: function() {
      if (this.apiKeys.length === 0) return null;
      return this.apiKeys[this.currentApiKeyIndex];
    },

    youtubeApi: function(endpoint, params) {
      var self = this;
      var apiKey = this.getApiKey();
      if (!apiKey) return Promise.reject(new Error('API 키가 없습니다'));

      params = params || {};
      var url = new URL('https://www.googleapis.com/youtube/v3/' + endpoint);
      url.searchParams.set('key', apiKey);

      Object.keys(params).forEach(function(k) {
        var v = params[k];
        if (v !== undefined && v !== null && v !== '') {
          url.searchParams.set(k, v);
        }
      });

      return fetch(url).then(function(res) {
        return res.json();
      }).then(function(data) {
        if (data.error) {
          // API 키 할당량 초과시 다음 키로 전환
          if (data.error.code === 403 && self.apiKeys.length > 1) {
            self.currentApiKeyIndex = (self.currentApiKeyIndex + 1) % self.apiKeys.length;
            self.saveApiKeys();
            self.updateStatus('API 할당량 초과 - 키 ' + (self.currentApiKeyIndex + 1) + '로 전환');
            return self.youtubeApi(endpoint, params);
          }
          throw new Error(data.error.message);
        }
        return data;
      });
    },

    // ===== 검색 기능 =====
    search: function() {
      var self = this;
      var keyword = document.getElementById('search-keyword').value.trim();

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

      if (this.searchType === 'channel') {
        this.searchChannels(keyword).catch(function(error) {
          console.error('[TubeLens] Search error:', error);
          alert('검색 중 오류가 발생했습니다: ' + error.message);
          self.showLoading(false);
          self.updateStatus('검색 실패: ' + error.message);
        });
      } else {
        this.searchVideos(keyword).catch(function(error) {
          console.error('[TubeLens] Search error:', error);
          alert('검색 중 오류가 발생했습니다: ' + error.message);
          self.showLoading(false);
          self.updateStatus('검색 실패: ' + error.message);
        });
      }
    },

    searchVideos: function(keyword) {
      var self = this;
      var maxResults = parseInt(document.getElementById('max-results').value) || 50;
      var timePeriod = document.getElementById('time-period').value;
      var regionCode = document.getElementById('region').value;
      var videoType = document.getElementById('video-type').value;

      // 기간 계산
      var publishedAfter = '';
      if (timePeriod) {
        var now = new Date();
        var periods = {
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
      var videoDuration = '';
      if (videoType === 'shorts') videoDuration = 'short';
      else if (videoType === 'long_4_20') videoDuration = 'medium';
      else if (videoType === 'long_20') videoDuration = 'long';

      // 검색 실행
      return this.youtubeApi('search', {
        part: 'snippet',
        q: keyword,
        type: 'video',
        maxResults: Math.min(maxResults, 50),
        order: this.sortType,
        regionCode: regionCode,
        publishedAfter: publishedAfter,
        videoDuration: videoDuration
      }).then(function(searchResult) {
        if (!searchResult.items || searchResult.items.length === 0) {
          self.originalResults = [];
          self.currentResults = [];
          self.displayResults([]);
          self.updateStatus('검색 결과가 없습니다');
          return;
        }

        // 영상 상세 정보 가져오기
        var videoIds = searchResult.items.map(function(item) {
          return item.id.videoId;
        }).join(',');

        return self.youtubeApi('videos', {
          part: 'snippet,statistics,contentDetails',
          id: videoIds
        }).then(function(videoDetails) {
          // 채널 정보 가져오기 (구독자 수 + 총 영상 수)
          var channelIdSet = {};
          videoDetails.items.forEach(function(v) {
            channelIdSet[v.snippet.channelId] = true;
          });
          var channelIds = Object.keys(channelIdSet).join(',');

          return self.youtubeApi('channels', {
            part: 'statistics',
            id: channelIds
          }).then(function(channelDetails) {
            var channelMap = {};
            channelDetails.items.forEach(function(ch) {
              channelMap[ch.id] = {
                subscriberCount: parseInt(ch.statistics.subscriberCount) || 0,
                videoCount: parseInt(ch.statistics.videoCount) || 0
              };
            });

            // 결과 가공
            self.originalResults = videoDetails.items.map(function(video, index) {
              var channelInfo = channelMap[video.snippet.channelId] || { subscriberCount: 0, videoCount: 0 };
              var viewCount = parseInt(video.statistics.viewCount) || 0;
              var likeCount = parseInt(video.statistics.likeCount) || 0;
              var commentCount = parseInt(video.statistics.commentCount) || 0;

              // CII 계산
              var ciiData = self.calculateCII(viewCount, channelInfo.subscriberCount);

              return {
                index: index + 1,
                videoId: video.id,
                title: video.snippet.title,
                channelId: video.snippet.channelId,
                channelTitle: video.snippet.channelTitle,
                thumbnail: (video.snippet.thumbnails.medium && video.snippet.thumbnails.medium.url) ||
                           (video.snippet.thumbnails.default && video.snippet.thumbnails.default.url) || '',
                publishedAt: self.formatDate(video.snippet.publishedAt),
                duration: self.formatDuration(video.contentDetails.duration),
                viewCount: viewCount,
                likeCount: likeCount,
                commentCount: commentCount,
                subscriberCount: channelInfo.subscriberCount,
                videoCount: channelInfo.videoCount,
                contributionValue: ciiData.contributionValue,
                performanceValue: ciiData.performanceValue,
                cii: ciiData.cii,
                description: video.snippet.description
              };
            });

            self.currentResults = self.originalResults.slice();
            self.displayResults(self.currentResults);
            self.updateStatus(self.currentResults.length + '개 영상 검색됨');
          });
        });
      });
    },

    // ===== URL 분석 =====
    analyzeUrl: function() {
      var self = this;
      var url = document.getElementById('youtube-url').value.trim();

      if (!url) {
        alert('YouTube URL을 입력해주세요.');
        return;
      }

      if (this.apiKeys.length === 0) {
        alert('먼저 API 키를 설정해주세요.');
        this.openSettings();
        return;
      }

      // URL에서 비디오 ID 또는 채널 ID 추출
      var videoId = null;
      var channelId = null;

      // 비디오 URL 패턴
      var videoPatterns = [
        /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/)([a-zA-Z0-9_-]{11})/,
        /youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})/
      ];

      for (var i = 0; i < videoPatterns.length; i++) {
        var match = url.match(videoPatterns[i]);
        if (match) {
          videoId = match[1];
          break;
        }
      }

      // 채널 URL 패턴
      var channelPatterns = [
        /youtube\.com\/channel\/([a-zA-Z0-9_-]+)/,
        /youtube\.com\/@([a-zA-Z0-9_-]+)/,
        /youtube\.com\/c\/([a-zA-Z0-9_-]+)/,
        /youtube\.com\/user\/([a-zA-Z0-9_-]+)/
      ];

      for (var j = 0; j < channelPatterns.length; j++) {
        var match2 = url.match(channelPatterns[j]);
        if (match2) {
          channelId = match2[1];
          break;
        }
      }

      if (!videoId && !channelId) {
        alert('올바른 YouTube URL이 아닙니다.');
        return;
      }

      this.showLoading(true);
      this.updateStatus('URL 분석 중...');

      var promise;
      if (videoId) {
        promise = this.analyzeVideo(videoId);
      } else {
        promise = this.analyzeChannel(channelId);
      }

      promise.then(function() {
        document.getElementById('youtube-url').value = '';
      }).catch(function(error) {
        console.error('[TubeLens] URL analysis error:', error);
        alert('URL 분석 중 오류가 발생했습니다: ' + error.message);
        self.showLoading(false);
      });
    },

    analyzeVideo: function(videoId) {
      var self = this;

      return this.youtubeApi('videos', {
        part: 'snippet,statistics,contentDetails',
        id: videoId
      }).then(function(videoDetails) {
        if (!videoDetails.items || videoDetails.items.length === 0) {
          throw new Error('영상을 찾을 수 없습니다.');
        }

        var video = videoDetails.items[0];

        return self.youtubeApi('channels', {
          part: 'statistics',
          id: video.snippet.channelId
        }).then(function(channelDetails) {
          var channelInfo = channelDetails.items[0] ? {
            subscriberCount: parseInt(channelDetails.items[0].statistics.subscriberCount) || 0,
            videoCount: parseInt(channelDetails.items[0].statistics.videoCount) || 0
          } : { subscriberCount: 0, videoCount: 0 };

          var viewCount = parseInt(video.statistics.viewCount) || 0;
          var likeCount = parseInt(video.statistics.likeCount) || 0;
          var commentCount = parseInt(video.statistics.commentCount) || 0;

          var ciiData = self.calculateCII(viewCount, channelInfo.subscriberCount);

          var newItem = {
            index: self.originalResults.length + 1,
            videoId: video.id,
            title: video.snippet.title,
            channelId: video.snippet.channelId,
            channelTitle: video.snippet.channelTitle,
            thumbnail: (video.snippet.thumbnails.medium && video.snippet.thumbnails.medium.url) ||
                       (video.snippet.thumbnails.default && video.snippet.thumbnails.default.url) || '',
            publishedAt: self.formatDate(video.snippet.publishedAt),
            duration: self.formatDuration(video.contentDetails.duration),
            viewCount: viewCount,
            likeCount: likeCount,
            commentCount: commentCount,
            subscriberCount: channelInfo.subscriberCount,
            videoCount: channelInfo.videoCount,
            contributionValue: ciiData.contributionValue,
            performanceValue: ciiData.performanceValue,
            cii: ciiData.cii,
            description: video.snippet.description
          };

          self.originalResults.push(newItem);
          self.currentResults = self.originalResults.slice();
          self.displayResults(self.currentResults);
          self.updateStatus('영상 추가됨 - 총 ' + self.currentResults.length + '개');
        });
      });
    },

    analyzeChannel: function(channelIdOrHandle) {
      var self = this;
      var channelId = channelIdOrHandle;

      var promise;
      if (!channelIdOrHandle.startsWith('UC')) {
        promise = this.youtubeApi('search', {
          part: 'snippet',
          q: channelIdOrHandle,
          type: 'channel',
          maxResults: 1
        }).then(function(searchResult) {
          if (searchResult.items && searchResult.items.length > 0) {
            channelId = searchResult.items[0].id.channelId;
          } else {
            throw new Error('채널을 찾을 수 없습니다.');
          }
          return channelId;
        });
      } else {
        promise = Promise.resolve(channelId);
      }

      return promise.then(function(cid) {
        return self.youtubeApi('channels', {
          part: 'snippet,statistics,contentDetails',
          id: cid
        });
      }).then(function(channelDetails) {
        if (!channelDetails.items || channelDetails.items.length === 0) {
          throw new Error('채널을 찾을 수 없습니다.');
        }

        var ch = channelDetails.items[0];
        self.showLoading(false);
        self.openChannelModal([{
          channelId: ch.id,
          channelTitle: ch.snippet.title,
          thumbnailUrl: ch.snippet.thumbnails.default ? ch.snippet.thumbnails.default.url : '',
          subscriberCount: parseInt(ch.statistics.subscriberCount) || 0,
          videoCount: parseInt(ch.statistics.videoCount) || 0,
          uploadPlaylist: ch.contentDetails && ch.contentDetails.relatedPlaylists ? ch.contentDetails.relatedPlaylists.uploads : ''
        }]);
        self.updateStatus('채널 분석 완료');
      });
    },

    searchChannels: function(keyword) {
      var self = this;
      var regionCode = document.getElementById('region').value;

      return this.youtubeApi('search', {
        part: 'snippet',
        q: keyword,
        type: 'channel',
        maxResults: 10,
        regionCode: regionCode
      }).then(function(result) {
        if (!result.items || result.items.length === 0) {
          alert('검색된 채널이 없습니다.');
          self.showLoading(false);
          self.updateStatus('채널 검색 결과 없음');
          return;
        }

        var channelIds = result.items.map(function(item) {
          return item.id.channelId;
        }).join(',');

        return self.youtubeApi('channels', {
          part: 'snippet,statistics,contentDetails',
          id: channelIds
        }).then(function(channelDetails) {
          var channels = channelDetails.items.map(function(ch) {
            return {
              channelId: ch.id,
              channelTitle: ch.snippet.title,
              thumbnailUrl: ch.snippet.thumbnails.default ? ch.snippet.thumbnails.default.url : '',
              subscriberCount: parseInt(ch.statistics.subscriberCount) || 0,
              videoCount: parseInt(ch.statistics.videoCount) || 0,
              uploadPlaylist: ch.contentDetails && ch.contentDetails.relatedPlaylists ? ch.contentDetails.relatedPlaylists.uploads : '',
              isExactMatch: ch.snippet.title.toLowerCase() === keyword.toLowerCase()
            };
          });

          self.showLoading(false);
          self.openChannelModal(channels);
          self.updateStatus(channels.length + '개 채널 검색됨');
        });
      });
    },

    loadChannelVideos: function(channel) {
      var self = this;
      this.showLoading(true);
      this.updateStatus('채널 영상 로딩 중: ' + channel.channelTitle);

      var maxResults = parseInt(document.getElementById('max-results').value) || 50;
      var videoTypeFilter = document.getElementById('channel-video-type').value;

      return this.youtubeApi('playlistItems', {
        part: 'snippet',
        playlistId: channel.uploadPlaylist,
        maxResults: Math.min(maxResults, 50)
      }).then(function(playlistResult) {
        if (!playlistResult.items || playlistResult.items.length === 0) {
          self.originalResults = [];
          self.currentResults = [];
          self.displayResults([]);
          self.updateStatus('채널에 영상이 없습니다');
          return;
        }

        var videoIds = playlistResult.items.map(function(item) {
          return item.snippet.resourceId.videoId;
        }).join(',');

        return self.youtubeApi('videos', {
          part: 'snippet,statistics,contentDetails',
          id: videoIds
        }).then(function(videoDetails) {
          self.originalResults = videoDetails.items.map(function(video, index) {
            var viewCount = parseInt(video.statistics.viewCount) || 0;
            var likeCount = parseInt(video.statistics.likeCount) || 0;
            var commentCount = parseInt(video.statistics.commentCount) || 0;

            var ciiData = self.calculateCII(viewCount, channel.subscriberCount);

            return {
              index: index + 1,
              videoId: video.id,
              title: video.snippet.title,
              channelId: channel.channelId,
              channelTitle: channel.channelTitle,
              thumbnail: (video.snippet.thumbnails.medium && video.snippet.thumbnails.medium.url) ||
                         (video.snippet.thumbnails.default && video.snippet.thumbnails.default.url) || '',
              publishedAt: self.formatDate(video.snippet.publishedAt),
              duration: self.formatDuration(video.contentDetails.duration),
              viewCount: viewCount,
              likeCount: likeCount,
              commentCount: commentCount,
              subscriberCount: channel.subscriberCount,
              videoCount: channel.videoCount,
              contributionValue: ciiData.contributionValue,
              performanceValue: ciiData.performanceValue,
              cii: ciiData.cii,
              description: video.snippet.description
            };
          });

          // 영상 타입 필터링
          if (videoTypeFilter === 'shorts') {
            self.originalResults = self.originalResults.filter(function(v) {
              return self.isShorts(v.duration);
            });
          } else if (videoTypeFilter === 'long') {
            self.originalResults = self.originalResults.filter(function(v) {
              return !self.isShorts(v.duration);
            });
          }

          // 인덱스 재정렬
          self.originalResults.forEach(function(v, i) {
            v.index = i + 1;
          });

          self.currentResults = self.originalResults.slice();
          self.displayResults(self.currentResults);
          self.updateStatus(channel.channelTitle + ' - ' + self.currentResults.length + '개 영상');
        });
      }).catch(function(error) {
        console.error('[TubeLens] Load channel videos error:', error);
        alert('채널 영상을 불러오는 중 오류가 발생했습니다: ' + error.message);
        self.showLoading(false);
      });
    },

    isShorts: function(duration) {
      var match = duration.match(/(\d+):(\d+)/);
      if (match) {
        var minutes = parseInt(match[1]);
        var seconds = parseInt(match[2]);
        return minutes === 0 && seconds <= 60;
      }
      return false;
    },

    // ===== CII 계산 =====
    calculateCII: function(viewCount, subscriberCount) {
      if (!subscriberCount || subscriberCount === 0) {
        return { contributionValue: 0, performanceValue: 0, cii: 'N/A' };
      }

      var contributionValue = (viewCount / subscriberCount) * 100;
      var performanceValue = viewCount / subscriberCount;

      var cii = 'Bad';
      if (performanceValue >= 3) cii = 'Great!!';
      else if (performanceValue >= 1.5) cii = 'Good';
      else if (performanceValue >= 0.5) cii = 'Soso';
      else if (performanceValue >= 0.2) cii = 'Not bad';

      return { contributionValue: contributionValue, performanceValue: performanceValue, cii: cii };
    },

    // ===== 필터 =====
    applyFilters: function() {
      if (this.originalResults.length === 0) {
        alert('먼저 검색을 실행해주세요.');
        return;
      }

      var self = this;
      var minViews = parseInt(document.getElementById('min-views').value) || 0;
      var maxSubs = parseInt(document.getElementById('subscriber-range').value) || Infinity;
      var ciiGreat = this.filters.ciiGreat;
      var ciiGood = this.filters.ciiGood;
      var ciiSoso = this.filters.ciiSoso;
      var hasCiiFilter = ciiGreat || ciiGood || ciiSoso;

      this.currentResults = this.originalResults.filter(function(item) {
        if (minViews > 0 && item.viewCount < minViews) return false;
        if (maxSubs < Infinity && item.subscriberCount > maxSubs) return false;

        if (hasCiiFilter) {
          if (ciiGreat && item.cii === 'Great!!') return true;
          if (ciiGood && item.cii === 'Good') return true;
          if (ciiSoso && item.cii === 'Soso') return true;
          return false;
        }

        return true;
      });

      this.currentResults.forEach(function(v, i) {
        v.index = i + 1;
      });

      this.displayResults(this.currentResults);
      this.updateStatus('필터 적용됨 - ' + this.currentResults.length + '개 영상');
    },

    clearFilters: function() {
      this.filters = { ciiGreat: false, ciiGood: false, ciiSoso: false };
      var ciiBtns = document.querySelectorAll('.cii-btn');
      for (var i = 0; i < ciiBtns.length; i++) {
        ciiBtns[i].classList.remove('active');
      }
      document.getElementById('min-views').value = '';
      document.getElementById('subscriber-range').value = '';

      if (this.originalResults.length > 0) {
        this.currentResults = this.originalResults.slice();
        var self = this;
        this.currentResults.forEach(function(v, i) {
          v.index = i + 1;
        });
        this.displayResults(this.currentResults);
        this.updateStatus('필터 초기화됨');
      }
    },

    // ===== 결과 표시 =====
    displayResults: function(results) {
      var tbody = document.getElementById('results-tbody');
      var countEl = document.getElementById('results-count');
      var tableWrapper = document.getElementById('table-wrapper');
      var emptyState = document.querySelector('.empty-state');

      if (!results || results.length === 0) {
        if (tbody) tbody.innerHTML = '';
        if (countEl) countEl.textContent = '0개 영상';
        if (tableWrapper) tableWrapper.style.display = 'none';
        if (emptyState) emptyState.style.display = 'flex';
        this.showLoading(false);
        return;
      }

      if (countEl) countEl.textContent = results.length + '개 영상';
      if (tableWrapper) tableWrapper.style.display = 'block';
      if (emptyState) emptyState.style.display = 'none';

      if (tbody) {
        var self = this;
        var html = '';
        for (var i = 0; i < results.length; i++) {
          html += this.createResultRow(results[i]);
        }
        tbody.innerHTML = html;
      }

      this.showLoading(false);
    },

    createResultRow: function(item) {
      var ciiClasses = {
        'Great!!': 'cii-great',
        'Good': 'cii-good',
        'Soso': 'cii-soso',
        'Not bad': 'cii-notbad',
        'Bad': 'cii-bad',
        'N/A': 'cii-bad'
      };
      var ciiClass = ciiClasses[item.cii] || 'cii-bad';

      var contribPercent = Math.min(100, item.contributionValue);
      var contribColor = contribPercent >= 100 ? 'green' : contribPercent >= 50 ? 'blue' : contribPercent >= 20 ? 'yellow' : 'red';

      var engagementRate = item.viewCount > 0 ? ((item.likeCount + item.commentCount) / item.viewCount * 100) : 0;

      var escapedTitle = this.escapeHtml(item.title);

      // 급상승 점수 관련 (있는 경우)
      var risingBadge = '';
      if (item.risingScore !== undefined) {
        var risingClass = item.risingScore >= 70 ? 'rising-hot' : item.risingScore >= 50 ? 'rising-up' : 'rising-normal';
        risingBadge = '<span class="rising-badge ' + risingClass + '">' + (item.risingGrade || '') + '</span>';
      }

      var html = '<tr>';
      html += '<td>' + item.index + '</td>';
      html += '<td><img class="thumbnail" src="' + item.thumbnail + '" alt="" onclick="TubeLens.openVideoModal(\'' + item.videoId + '\', \'' + escapedTitle.replace(/'/g, "\\'") + '\')" onerror="this.src=\'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22140%22 height=%2279%22><rect fill=%22%23e1e5eb%22 width=%22140%22 height=%2279%22/><text x=%2270%22 y=%2245%22 text-anchor=%22middle%22 fill=%22%23999%22 font-size=%2212%22>No Image</text></svg>\'"></td>';
      html += '<td class="channel-name" onclick="TubeLens.searchChannelById(\'' + item.channelId + '\')">' + item.channelTitle + '</td>';
      html += '<td class="video-title">' + item.title + '</td>';
      html += '<td>' + item.publishedAt + '</td>';
      html += '<td>' + this.formatNumber(item.subscriberCount) + '</td>';
      html += '<td>' + this.formatNumber(item.viewCount) + '</td>';

      // 100배 떡상 배지 (신의 간택)
      var viral100xBadge = '';
      if (item.performanceValue >= 100) {
        viral100xBadge = '<span class="viral-100x-badge">' + Math.floor(item.performanceValue) + '배 떡상</span>';
      } else if (item.performanceValue >= 50) {
        viral100xBadge = '<span class="viral-100x-badge" style="background:linear-gradient(135deg,#ed8936,#dd6b20);animation:none">' + Math.floor(item.performanceValue) + '배</span>';
      }

      // 급상승 점수 또는 기존 기여도 표시
      if (item.risingScore !== undefined) {
        html += '<td>' + risingBadge + '<br><small>' + (item.risingScore || 0) + '점</small></td>';
        html += '<td>' + viral100xBadge + '<br><small>' + this.formatNumber(item.viewsPerHour || 0) + '/h</small><br><small>' + this.formatNumber(item.viewsPerDay || 0) + '/d</small></td>';
      } else {
        html += '<td><div class="gauge"><div class="gauge-fill ' + contribColor + '" style="width:' + contribPercent + '%"></div></div><div class="gauge-value">' + contribPercent.toFixed(0) + '%</div></td>';
        html += '<td>' + viral100xBadge + (viral100xBadge ? '<br>' : '') + '<span>' + item.performanceValue.toFixed(2) + 'x</span></td>';
      }

      html += '<td><span class="cii-badge ' + ciiClass + '">' + item.cii + '</span></td>';
      html += '<td>' + item.duration + '</td>';
      html += '<td>' + this.formatNumber(item.likeCount) + '</td>';
      html += '<td style="cursor:pointer;color:#3182ce" onclick="TubeLens.loadComments(\'' + item.videoId + '\', \'' + escapedTitle.replace(/'/g, "\\'") + '\')">' + this.formatNumber(item.commentCount) + '</td>';
      html += '<td>' + engagementRate.toFixed(2) + '%</td>';
      html += '<td>' + this.formatNumber(item.videoCount || 0) + '</td>';
      html += '<td style="cursor:pointer;color:#3182ce" onclick="TubeLens.showDescription(\'' + item.videoId + '\')">보기</td>';
      html += '<td class="action-buttons" style="white-space:nowrap;">';
      html += '<button class="btn-ai-plan" onclick="TubeLens.generateAIPlan(\'' + item.videoId + '\')" title="AI 기획 생성">🎯 AI기획</button>';
      html += '<button class="btn-action bookmark" onclick="TubeLens.addBookmark(\'' + item.videoId + '\')" title="북마크">⭐</button>';
      html += '<button class="btn-action" onclick="TubeLens.analyzeVideoScore(\'' + item.videoId + '\')" title="종합 분석 (SEO+바이럴)" style="background:#667eea;color:#fff;font-size:0.75rem;">📊</button>';
      html += '<button class="btn-action ab" onclick="TubeLens.suggestTitles(\'' + item.videoId + '\')" title="제목 A/B 제안">AB</button>';
      html += '<button class="btn-action sentiment" onclick="TubeLens.analyzeSentiment(\'' + item.videoId + '\')" title="댓글 감성 분석">💬</button>';
      html += '<button class="btn-action compare" onclick="TubeLens.addToCompare(\'' + item.channelId + '\', \'' + item.channelTitle.replace(/'/g, "\\'") + '\')" title="채널 비교에 추가">⚖️</button>';
      html += '<button class="btn-action" onclick="TubeLens.addToWatchlist(\'' + item.channelId + '\', \'' + item.channelTitle.replace(/'/g, "\\'") + '\')" title="워치리스트에 추가" style="background:#f56565;color:#fff;">👁️</button>';
      html += '</td>';
      html += '</tr>';

      return html;
    },

    // ===== 댓글 =====
    loadComments: function(videoId, title) {
      var self = this;
      this.updateStatus('댓글 로딩 중...');

      this.youtubeApi('commentThreads', {
        part: 'snippet',
        videoId: videoId,
        order: 'relevance',
        maxResults: 20
      }).then(function(result) {
        if (!result.items || result.items.length === 0) {
          self.currentComments = [];
          document.getElementById('comments-list').innerHTML = '<div class="empty-list">댓글이 없습니다</div>';
        } else {
          self.currentComments = result.items.map(function(item) {
            return {
              author: item.snippet.topLevelComment.snippet.authorDisplayName,
              authorImage: item.snippet.topLevelComment.snippet.authorProfileImageUrl,
              text: item.snippet.topLevelComment.snippet.textDisplay,
              likeCount: item.snippet.topLevelComment.snippet.likeCount,
              publishedAt: item.snippet.topLevelComment.snippet.publishedAt
            };
          });

          var html = '';
          for (var i = 0; i < self.currentComments.length; i++) {
            var c = self.currentComments[i];
            html += '<div class="comment-item">';
            html += '<img class="comment-avatar" src="' + c.authorImage + '" alt="" onerror="this.style.display=\'none\'">';
            html += '<div>';
            html += '<div class="comment-author">' + c.author + '</div>';
            html += '<div class="comment-text">' + c.text + '</div>';
            html += '<div class="comment-meta">👍 ' + c.likeCount + ' · ' + self.formatDate(c.publishedAt) + '</div>';
            html += '</div></div>';
          }
          document.getElementById('comments-list').innerHTML = html;
        }

        self.openCommentsModal();
        self.updateStatus(self.currentComments.length + '개 댓글 로드됨');
      }).catch(function(error) {
        console.error('[TubeLens] Load comments error:', error);
        alert('댓글을 불러오는 중 오류가 발생했습니다: ' + error.message);
      });
    },

    copyComments: function() {
      if (!this.currentComments || this.currentComments.length === 0) {
        alert('복사할 댓글이 없습니다.');
        return;
      }

      var text = '';
      for (var i = 0; i < this.currentComments.length; i++) {
        var c = this.currentComments[i];
        text += (i + 1) + '. [' + c.author + '] ' + c.text.replace(/<[^>]*>/g, '') + '\n\n';
      }

      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function() {
          alert('댓글이 클립보드에 복사되었습니다.');
        }).catch(function() {
          fallbackCopy(text);
        });
      } else {
        fallbackCopy(text);
      }

      function fallbackCopy(t) {
        var textarea = document.createElement('textarea');
        textarea.value = t;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        alert('댓글이 클립보드에 복사되었습니다.');
      }
    },

    // ===== 설명 =====
    showDescription: function(videoId) {
      var video = null;
      for (var i = 0; i < this.currentResults.length; i++) {
        if (this.currentResults[i].videoId === videoId) {
          video = this.currentResults[i];
          break;
        }
      }
      if (video) {
        this.currentDescription = video.description;
        document.getElementById('description-content').textContent = video.description || '설명이 없습니다.';
        this.openDescriptionModal();
      }
    },

    copyDescription: function() {
      if (!this.currentDescription) {
        alert('복사할 설명이 없습니다.');
        return;
      }

      var text = this.currentDescription;

      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function() {
          alert('설명이 클립보드에 복사되었습니다.');
        }).catch(function() {
          fallbackCopy(text);
        });
      } else {
        fallbackCopy(text);
      }

      function fallbackCopy(t) {
        var textarea = document.createElement('textarea');
        textarea.value = t;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        alert('설명이 클립보드에 복사되었습니다.');
      }
    },

    // ===== 채널 검색 =====
    searchChannelById: function(channelId) {
      var self = this;

      this.youtubeApi('channels', {
        part: 'snippet,statistics,contentDetails',
        id: channelId
      }).then(function(result) {
        if (result.items && result.items.length > 0) {
          var ch = result.items[0];
          self.openChannelModal([{
            channelId: ch.id,
            channelTitle: ch.snippet.title,
            thumbnailUrl: ch.snippet.thumbnails.default ? ch.snippet.thumbnails.default.url : '',
            subscriberCount: parseInt(ch.statistics.subscriberCount) || 0,
            videoCount: parseInt(ch.statistics.videoCount) || 0,
            uploadPlaylist: ch.contentDetails && ch.contentDetails.relatedPlaylists ? ch.contentDetails.relatedPlaylists.uploads : ''
          }]);
        }
      }).catch(function(error) {
        console.error('[TubeLens] Search channel error:', error);
      });
    },

    // ===== 유틸리티 =====
    formatNumber: function(num) {
      if (!num) return '0';
      num = parseInt(num);
      if (num >= 100000000) return (num / 100000000).toFixed(1) + '억';
      if (num >= 10000) return (num / 10000).toFixed(1) + '만';
      if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
      return num.toLocaleString();
    },

    formatDate: function(dateStr) {
      if (!dateStr) return '';
      var date = new Date(dateStr);
      var y = date.getFullYear();
      var m = ('0' + (date.getMonth() + 1)).slice(-2);
      var d = ('0' + date.getDate()).slice(-2);
      return y + '.' + m + '.' + d;
    },

    formatDuration: function(isoDuration) {
      if (!isoDuration) return '0:00';
      var match = isoDuration.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
      if (!match) return '0:00';

      var hours = parseInt(match[1]) || 0;
      var minutes = parseInt(match[2]) || 0;
      var seconds = parseInt(match[3]) || 0;

      if (hours > 0) {
        return hours + ':' + ('0' + minutes).slice(-2) + ':' + ('0' + seconds).slice(-2);
      }
      return minutes + ':' + ('0' + seconds).slice(-2);
    },

    escapeHtml: function(text) {
      if (!text) return '';
      return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    },

    // ===== AI 분석 기능 =====

    // 제목 패턴 분석
    analyzeTitles: function() {
      var self = this;

      if (this.currentResults.length === 0) {
        alert('먼저 영상을 검색하거나 급상승 발굴을 실행해주세요.');
        return;
      }

      var titles = this.currentResults.slice(0, 20).map(function(v) {
        return {
          title: v.title,
          viewCount: v.viewCount,
          subscriberCount: v.subscriberCount
        };
      });

      this.updateStatus('🤖 AI가 제목 패턴을 분석 중...');

      fetch('/api/tubelens/analyze-titles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ titles: titles })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.showAnalysisModal('제목 패턴 분석', data.data);
          self.updateStatus('✅ 제목 패턴 분석 완료');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Title analysis error:', error);
        alert('제목 분석 실패: ' + error.message);
        self.updateStatus('분석 실패: ' + error.message);
      });
    },

    // 썸네일 패턴 분석
    analyzeThumbnails: function() {
      var self = this;

      if (this.currentResults.length === 0) {
        alert('먼저 영상을 검색하거나 급상승 발굴을 실행해주세요.');
        return;
      }

      var videos = this.currentResults.slice(0, 10).map(function(v) {
        return {
          title: v.title,
          thumbnail: v.thumbnail,
          viewCount: v.viewCount
        };
      });

      this.updateStatus('🤖 AI가 썸네일 패턴을 분석 중...');

      fetch('/api/tubelens/analyze-thumbnails', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ videos: videos })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.showAnalysisModal('썸네일 패턴 분석', data.data);
          self.updateStatus('✅ 썸네일 패턴 분석 완료');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Thumbnail analysis error:', error);
        alert('썸네일 분석 실패: ' + error.message);
        self.updateStatus('분석 실패: ' + error.message);
      });
    },

    // 콘텐츠 아이디어 생성
    generateIdeas: function(style) {
      var self = this;
      style = style || 'story';

      if (this.currentResults.length === 0) {
        alert('먼저 영상을 검색하거나 급상승 발굴을 실행해주세요.');
        return;
      }

      var videos = this.currentResults.slice(0, 10).map(function(v) {
        return {
          title: v.title,
          description: v.description || ''
        };
      });

      this.updateStatus('🤖 AI가 콘텐츠 아이디어를 생성 중...');

      fetch('/api/tubelens/generate-ideas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videos: videos,
          contentStyle: style
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.showIdeasModal('콘텐츠 아이디어', data.data);
          self.updateStatus('✅ 콘텐츠 아이디어 생성 완료');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Ideas generation error:', error);
        alert('아이디어 생성 실패: ' + error.message);
        self.updateStatus('생성 실패: ' + error.message);
      });
    },

    // 분석 결과 모달 표시
    showAnalysisModal: function(title, data) {
      var html = '<div class="analysis-content">';

      if (data.summary) {
        html += '<div class="analysis-summary"><strong>📊 요약:</strong> ' + data.summary + '</div>';
      }

      if (data.common_patterns && data.common_patterns.length) {
        html += '<div class="analysis-section"><h4>🔍 공통 패턴</h4><ul>';
        data.common_patterns.forEach(function(p) { html += '<li>' + p + '</li>'; });
        html += '</ul></div>';
      }

      if (data.click_triggers && data.click_triggers.length) {
        html += '<div class="analysis-section"><h4>🎯 클릭 유발 요소</h4><ul>';
        data.click_triggers.forEach(function(p) { html += '<li>' + p + '</li>'; });
        html += '</ul></div>';
      }

      if (data.emotional_hooks && data.emotional_hooks.length) {
        html += '<div class="analysis-section"><h4>💡 감정 자극 표현</h4><ul>';
        data.emotional_hooks.forEach(function(p) { html += '<li>' + p + '</li>'; });
        html += '</ul></div>';
      }

      if (data.title_suggestions && data.title_suggestions.length) {
        html += '<div class="analysis-section"><h4>✨ 추천 제목 템플릿</h4>';
        data.title_suggestions.forEach(function(s) {
          html += '<div class="title-suggestion"><strong>' + s.template + '</strong><br><small>예시: ' + s.example + '</small></div>';
        });
        html += '</div>';
      }

      if (data.recommended_keywords && data.recommended_keywords.length) {
        html += '<div class="analysis-section"><h4>🏷️ 추천 키워드</h4><div class="keyword-tags">';
        data.recommended_keywords.forEach(function(k) { html += '<span class="keyword-tag">' + k + '</span>'; });
        html += '</div></div>';
      }

      // 썸네일 분석용
      if (data.common_elements && data.common_elements.length) {
        html += '<div class="analysis-section"><h4>🖼️ 공통 요소</h4><ul>';
        data.common_elements.forEach(function(p) { html += '<li>' + p + '</li>'; });
        html += '</ul></div>';
      }

      if (data.color_patterns && data.color_patterns.length) {
        html += '<div class="analysis-section"><h4>🎨 색상 패턴</h4><ul>';
        data.color_patterns.forEach(function(p) { html += '<li>' + p + '</li>'; });
        html += '</ul></div>';
      }

      if (data.recommendations && data.recommendations.length) {
        html += '<div class="analysis-section"><h4>💡 추천 사항</h4>';
        data.recommendations.forEach(function(r) {
          html += '<div class="recommendation-item"><strong>' + r.tip + '</strong><br><small>' + r.reason + '</small></div>';
        });
        html += '</div>';
      }

      html += '</div>';

      document.getElementById('analysis-modal-title').textContent = title;
      document.getElementById('analysis-modal-content').innerHTML = html;
      document.getElementById('analysis-modal').classList.add('show');
    },

    // 아이디어 모달 표시
    showIdeasModal: function(title, data) {
      var html = '<div class="ideas-content">';

      if (data.trend_analysis) {
        html += '<div class="trend-analysis"><strong>📈 트렌드 분석:</strong> ' + data.trend_analysis + '</div>';
      }

      if (data.ideas && data.ideas.length) {
        html += '<div class="ideas-list">';
        data.ideas.forEach(function(idea, idx) {
          html += '<div class="idea-card">';
          html += '<div class="idea-header"><span class="idea-number">' + (idx + 1) + '</span>';
          html += '<span class="viral-badge viral-' + (idea.viral_potential || '중').toLowerCase() + '">' + (idea.viral_potential || '중') + '</span></div>';
          html += '<h4 class="idea-title">' + idea.title + '</h4>';
          html += '<div class="idea-hook"><strong>🎬 훅:</strong> ' + idea.hook + '</div>';
          html += '<div class="idea-outline"><strong>📝 개요:</strong> ' + idea.outline + '</div>';
          html += '<div class="idea-emotion"><strong>🎭 타겟 감정:</strong> ' + idea.target_emotion + '</div>';
          html += '</div>';
        });
        html += '</div>';
      }

      if (data.keywords && data.keywords.length) {
        html += '<div class="ideas-keywords"><h4>🏷️ 추천 키워드</h4><div class="keyword-tags">';
        data.keywords.forEach(function(k) { html += '<span class="keyword-tag">' + k + '</span>'; });
        html += '</div></div>';
      }

      if (data.avoid && data.avoid.length) {
        html += '<div class="ideas-avoid"><h4>⚠️ 피해야 할 요소</h4><ul>';
        data.avoid.forEach(function(a) { html += '<li>' + a + '</li>'; });
        html += '</ul></div>';
      }

      html += '</div>';

      document.getElementById('analysis-modal-title').textContent = title;
      document.getElementById('analysis-modal-content').innerHTML = html;
      document.getElementById('analysis-modal').classList.add('show');
    },

    closeAnalysisModal: function() {
      document.getElementById('analysis-modal').classList.remove('show');
    },

    // ===== 북마크/관심목록 기능 =====

    bookmarks: [],

    loadBookmarks: function() {
      var saved = localStorage.getItem('tubelens_bookmarks');
      if (saved) {
        try {
          this.bookmarks = JSON.parse(saved);
        } catch (e) {
          this.bookmarks = [];
        }
      }
    },

    saveBookmarks: function() {
      localStorage.setItem('tubelens_bookmarks', JSON.stringify(this.bookmarks));
    },

    addBookmark: function(videoId) {
      var video = null;
      for (var i = 0; i < this.currentResults.length; i++) {
        if (this.currentResults[i].videoId === videoId) {
          video = this.currentResults[i];
          break;
        }
      }

      if (!video) {
        alert('영상을 찾을 수 없습니다.');
        return;
      }

      // 이미 북마크된 경우
      var exists = this.bookmarks.some(function(b) { return b.videoId === videoId; });
      if (exists) {
        alert('이미 북마크에 추가된 영상입니다.');
        return;
      }

      this.bookmarks.push({
        videoId: video.videoId,
        title: video.title,
        thumbnail: video.thumbnail,
        channelTitle: video.channelTitle,
        viewCount: video.viewCount,
        publishedAt: video.publishedAt,
        savedAt: new Date().toISOString()
      });

      this.saveBookmarks();
      this.updateStatus('북마크에 추가되었습니다.');
      alert('북마크에 추가되었습니다!');
    },

    removeBookmark: function(videoId) {
      this.bookmarks = this.bookmarks.filter(function(b) { return b.videoId !== videoId; });
      this.saveBookmarks();
      this.showBookmarks();
      this.updateStatus('북마크에서 제거되었습니다.');
    },

    showBookmarks: function() {
      this.loadBookmarks();

      var html = '<div class="bookmarks-content">';

      if (this.bookmarks.length === 0) {
        html += '<div class="empty-list" style="padding:40px;text-align:center;color:#999;">저장된 북마크가 없습니다.</div>';
      } else {
        html += '<div class="bookmarks-list">';
        var self = this;
        this.bookmarks.forEach(function(b, idx) {
          html += '<div class="bookmark-item" style="display:flex;gap:12px;padding:12px;border-bottom:1px solid #eee;align-items:center;">';
          html += '<img src="' + b.thumbnail + '" style="width:100px;height:56px;border-radius:6px;object-fit:cover;" onerror="this.style.display=\'none\'">';
          html += '<div style="flex:1;">';
          html += '<div style="font-weight:600;margin-bottom:4px;">' + b.title + '</div>';
          html += '<div style="font-size:0.85rem;color:#666;">' + b.channelTitle + ' · ' + self.formatNumber(b.viewCount) + '회</div>';
          html += '</div>';
          html += '<div style="display:flex;gap:8px;">';
          html += '<button class="btn-sm success" onclick="TubeLens.openVideoModal(\'' + b.videoId + '\', \'' + self.escapeHtml(b.title).replace(/'/g, "\\'") + '\')">보기</button>';
          html += '<button class="btn-sm danger" onclick="TubeLens.removeBookmark(\'' + b.videoId + '\')">삭제</button>';
          html += '</div></div>';
        });
        html += '</div>';
      }

      html += '</div>';

      document.getElementById('analysis-modal-title').textContent = '북마크 (' + this.bookmarks.length + '개)';
      document.getElementById('analysis-modal-content').innerHTML = html;
      document.getElementById('analysis-modal').classList.add('show');
    },

    // ===== 경쟁 채널 비교 =====

    compareChannels: [],

    addToCompare: function(channelId, channelTitle) {
      if (this.compareChannels.length >= 5) {
        alert('최대 5개 채널까지 비교할 수 있습니다.');
        return;
      }

      var exists = this.compareChannels.some(function(c) { return c.id === channelId; });
      if (exists) {
        alert('이미 비교 목록에 있는 채널입니다.');
        return;
      }

      this.compareChannels.push({ id: channelId, title: channelTitle });
      this.updateStatus('비교 목록에 추가됨: ' + channelTitle + ' (' + this.compareChannels.length + '/5)');
      alert(channelTitle + '이(가) 비교 목록에 추가되었습니다.');
    },

    showCompareChannels: function() {
      var self = this;

      if (this.compareChannels.length < 2) {
        alert('비교할 채널을 2개 이상 추가해주세요.\n채널명 옆 비교 버튼을 클릭하세요.');
        return;
      }

      this.updateStatus('채널 비교 분석 중...');

      var channelIds = this.compareChannels.map(function(c) { return c.id; });

      fetch('/api/tubelens/compare-channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channelIds: channelIds,
          apiKeys: this.apiKeys,
          currentApiKeyIndex: this.currentApiKeyIndex
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.showCompareModal(data.data);
          self.updateStatus('채널 비교 분석 완료');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Compare error:', error);
        alert('채널 비교 실패: ' + error.message);
        self.updateStatus('비교 실패: ' + error.message);
      });
    },

    showCompareModal: function(channels) {
      var self = this;
      var html = '<div class="compare-content">';

      // 비교 테이블
      html += '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:0.9rem;">';
      html += '<thead><tr style="background:#f8f9fa;"><th style="padding:12px;text-align:left;">채널</th>';
      channels.forEach(function(ch) {
        html += '<th style="padding:12px;text-align:center;"><img src="' + ch.thumbnail + '" style="width:40px;height:40px;border-radius:50%;"><br>' + ch.channelTitle + '</th>';
      });
      html += '</tr></thead><tbody>';

      var metrics = [
        { label: '구독자 수', key: 'subscriberCount', format: 'number' },
        { label: '총 조회수', key: 'viewCount', format: 'number' },
        { label: '영상 수', key: 'videoCount', format: 'number' },
        { label: '영상당 평균 조회수', key: 'avgViewsPerVideo', format: 'number' },
        { label: '최근 10개 평균 조회수', key: 'recentAvgViews', format: 'number' },
        { label: '최근 10개 평균 좋아요', key: 'recentAvgLikes', format: 'number' },
        { label: '참여율', key: 'engagementRate', format: 'percent' },
        { label: '개설일', key: 'publishedAt', format: 'date' }
      ];

      metrics.forEach(function(m) {
        html += '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px;font-weight:500;">' + m.label + '</td>';
        channels.forEach(function(ch) {
          var val = ch[m.key];
          var formatted = val;
          if (m.format === 'number') formatted = self.formatNumber(val);
          else if (m.format === 'percent') formatted = val + '%';
          html += '<td style="padding:10px;text-align:center;">' + formatted + '</td>';
        });
        html += '</tr>';
      });

      html += '</tbody></table></div>';

      // 비교 목록 초기화 버튼
      html += '<div style="margin-top:20px;text-align:center;">';
      html += '<button class="btn btn-secondary" onclick="TubeLens.clearCompareChannels()">비교 목록 초기화</button>';
      html += '</div>';

      html += '</div>';

      document.getElementById('analysis-modal-title').textContent = '경쟁 채널 비교 (' + channels.length + '개)';
      document.getElementById('analysis-modal-content').innerHTML = html;
      document.getElementById('analysis-modal').classList.add('show');
    },

    clearCompareChannels: function() {
      this.compareChannels = [];
      this.closeAnalysisModal();
      this.updateStatus('비교 목록이 초기화되었습니다.');
    },

    // ===== 키워드 트렌드 =====

    analyzeKeywordTrend: function() {
      var self = this;
      var keyword = prompt('트렌드를 분석할 키워드를 입력하세요:');

      if (!keyword) return;

      this.updateStatus('키워드 트렌드 분석 중: ' + keyword);

      fetch('/api/tubelens/keyword-trend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keyword: keyword,
          apiKeys: this.apiKeys,
          currentApiKeyIndex: this.currentApiKeyIndex
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.showTrendModal(data.data);
          self.updateStatus('키워드 트렌드 분석 완료');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Trend error:', error);
        alert('트렌드 분석 실패: ' + error.message);
        self.updateStatus('분석 실패: ' + error.message);
      });
    },

    showTrendModal: function(data) {
      var self = this;
      var html = '<div class="trend-content">';

      // 트렌드 방향
      var trendIcon = data.trendDirection === '상승' ? '📈' : '📉';
      var trendColor = data.trendDirection === '상승' ? '#48bb78' : '#f56565';

      html += '<div style="background:linear-gradient(135deg,#e0e7ff,#c7d2fe);padding:20px;border-radius:12px;margin-bottom:20px;text-align:center;">';
      html += '<h3 style="font-size:1.5rem;margin-bottom:8px;">' + trendIcon + ' ' + data.keyword + '</h3>';
      html += '<div style="font-size:1.1rem;color:' + trendColor + ';font-weight:600;">' + data.trendDirection + ' 추세 (' + data.trendStrength + ')</div>';
      html += '</div>';

      // 기간별 데이터
      html += '<div style="margin-bottom:20px;"><h4 style="margin-bottom:12px;">기간별 분석</h4>';
      html += '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">';

      data.trendData.forEach(function(t) {
        html += '<div style="background:#f8f9fa;padding:16px;border-radius:10px;text-align:center;">';
        html += '<div style="font-size:0.85rem;color:#666;margin-bottom:8px;">최근 ' + t.period + '</div>';
        html += '<div style="font-size:1.3rem;font-weight:700;color:#333;">' + t.videoCount + '개</div>';
        html += '<div style="font-size:0.8rem;color:#888;">평균 ' + self.formatNumber(t.avgViews) + '회</div>';
        html += '<div style="font-size:0.75rem;color:#aaa;">' + t.videosPerDay + '개/일</div>';
        html += '</div>';
      });

      html += '</div></div>';

      // 추천
      html += '<div style="background:#f0fdf4;padding:16px;border-radius:10px;border-left:4px solid #48bb78;">';
      html += '<strong>💡 분석 결과:</strong><br>' + data.recommendation;
      html += '</div>';

      html += '</div>';

      document.getElementById('analysis-modal-title').textContent = '키워드 트렌드';
      document.getElementById('analysis-modal-content').innerHTML = html;
      document.getElementById('analysis-modal').classList.add('show');
    },

    // ===== 제목 A/B 테스트 제안 =====

    suggestTitles: function(videoId) {
      var self = this;
      var video = null;

      for (var i = 0; i < this.currentResults.length; i++) {
        if (this.currentResults[i].videoId === videoId) {
          video = this.currentResults[i];
          break;
        }
      }

      if (!video) {
        alert('영상을 찾을 수 없습니다.');
        return;
      }

      this.updateStatus('AI가 대안 제목을 생성 중...');

      fetch('/api/tubelens/suggest-titles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: video.title,
          description: video.description || ''
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.showTitleSuggestionsModal(video.title, data.data);
          self.updateStatus('대안 제목 생성 완료');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Title suggest error:', error);
        alert('제목 제안 실패: ' + error.message);
        self.updateStatus('제안 실패: ' + error.message);
      });
    },

    showTitleSuggestionsModal: function(originalTitle, data) {
      var html = '<div class="title-suggestions-content">';

      // 원본 제목
      html += '<div style="background:#f8f9fa;padding:16px;border-radius:10px;margin-bottom:20px;">';
      html += '<div style="font-size:0.85rem;color:#666;margin-bottom:6px;">원본 제목</div>';
      html += '<div style="font-size:1.1rem;font-weight:600;">' + originalTitle + '</div>';
      html += '</div>';

      // 분석
      if (data.analysis) {
        html += '<div style="background:#fff3cd;padding:12px 16px;border-radius:8px;margin-bottom:20px;font-size:0.9rem;">';
        html += '<strong>📊 분석:</strong> ' + data.analysis;
        html += '</div>';
      }

      // 대안 제목들
      html += '<h4 style="margin-bottom:12px;">✨ 대안 제목 (A/B 테스트용)</h4>';
      html += '<div style="display:grid;gap:12px;">';

      if (data.suggestions) {
        data.suggestions.forEach(function(s, idx) {
          html += '<div style="background:#fff;border:1px solid #e1e5eb;padding:16px;border-radius:10px;">';
          html += '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">';
          html += '<span style="background:#667eea;color:#fff;padding:4px 10px;border-radius:12px;font-size:0.75rem;">' + s.type + '</span>';
          html += '<button class="btn-sm success" onclick="navigator.clipboard.writeText(\'' + s.title.replace(/'/g, "\\'") + '\');alert(\'복사되었습니다!\');">복사</button>';
          html += '</div>';
          html += '<div style="font-size:1.05rem;font-weight:600;margin-bottom:8px;">' + s.title + '</div>';
          html += '<div style="font-size:0.85rem;color:#666;">' + s.reason + '</div>';
          html += '</div>';
        });
      }

      html += '</div></div>';

      document.getElementById('analysis-modal-title').textContent = '제목 A/B 제안';
      document.getElementById('analysis-modal-content').innerHTML = html;
      document.getElementById('analysis-modal').classList.add('show');
    },

    // ===== 댓글 감성 분석 =====

    analyzeSentiment: function(videoId) {
      var self = this;

      this.updateStatus('AI가 댓글 감성을 분석 중...');

      fetch('/api/tubelens/analyze-sentiment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videoId: videoId,
          apiKeys: this.apiKeys,
          currentApiKeyIndex: this.currentApiKeyIndex
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.showSentimentModal(data.data);
          self.updateStatus('댓글 감성 분석 완료');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Sentiment error:', error);
        alert('감성 분석 실패: ' + error.message);
        self.updateStatus('분석 실패: ' + error.message);
      });
    },

    showSentimentModal: function(data) {
      var html = '<div class="sentiment-content">';

      // 감성 비율 차트
      var sentiment = data.sentiment || { positive: 0, neutral: 0, negative: 0 };
      html += '<div style="margin-bottom:24px;">';
      html += '<h4 style="margin-bottom:12px;">감성 분포 (' + (data.totalComments || 0) + '개 댓글)</h4>';
      html += '<div style="display:flex;height:24px;border-radius:12px;overflow:hidden;background:#e1e5eb;">';
      html += '<div style="width:' + sentiment.positive + '%;background:#48bb78;" title="긍정 ' + sentiment.positive + '%"></div>';
      html += '<div style="width:' + sentiment.neutral + '%;background:#ed8936;" title="중립 ' + sentiment.neutral + '%"></div>';
      html += '<div style="width:' + sentiment.negative + '%;background:#f56565;" title="부정 ' + sentiment.negative + '%"></div>';
      html += '</div>';
      html += '<div style="display:flex;justify-content:space-between;margin-top:8px;font-size:0.85rem;">';
      html += '<span style="color:#48bb78;">😊 긍정 ' + sentiment.positive + '%</span>';
      html += '<span style="color:#ed8936;">😐 중립 ' + sentiment.neutral + '%</span>';
      html += '<span style="color:#f56565;">😞 부정 ' + sentiment.negative + '%</span>';
      html += '</div></div>';

      // 요약
      if (data.summary) {
        html += '<div style="background:linear-gradient(135deg,#e0e7ff,#c7d2fe);padding:16px;border-radius:12px;margin-bottom:20px;">';
        html += '<strong>📊 요약:</strong> ' + data.summary;
        html += '</div>';
      }

      // 긍정적인 점
      if (data.positive_points && data.positive_points.length) {
        html += '<div style="margin-bottom:16px;"><h4 style="margin-bottom:8px;">👍 시청자들이 좋아하는 점</h4><ul style="list-style:none;padding:0;">';
        data.positive_points.forEach(function(p) {
          html += '<li style="padding:8px 12px;background:#f0fdf4;border-radius:6px;margin-bottom:6px;font-size:0.9rem;">' + p + '</li>';
        });
        html += '</ul></div>';
      }

      // 부정적인 점
      if (data.negative_points && data.negative_points.length) {
        html += '<div style="margin-bottom:16px;"><h4 style="margin-bottom:8px;">👎 아쉬운 점</h4><ul style="list-style:none;padding:0;">';
        data.negative_points.forEach(function(p) {
          html += '<li style="padding:8px 12px;background:#fef2f2;border-radius:6px;margin-bottom:6px;font-size:0.9rem;">' + p + '</li>';
        });
        html += '</ul></div>';
      }

      // 키워드
      if (data.keywords && data.keywords.length) {
        html += '<div style="margin-bottom:16px;"><h4 style="margin-bottom:8px;">🏷️ 자주 언급된 키워드</h4>';
        html += '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
        data.keywords.forEach(function(k) {
          html += '<span style="background:#667eea;color:#fff;padding:6px 14px;border-radius:20px;font-size:0.85rem;">' + k + '</span>';
        });
        html += '</div></div>';
      }

      // 개선 제안
      if (data.suggestions && data.suggestions.length) {
        html += '<div><h4 style="margin-bottom:8px;">💡 개선 제안</h4><ul style="list-style:none;padding:0;">';
        data.suggestions.forEach(function(s) {
          html += '<li style="padding:10px 14px;background:#f0fdf4;border-left:4px solid #48bb78;border-radius:6px;margin-bottom:8px;font-size:0.9rem;">' + s + '</li>';
        });
        html += '</ul></div>';
      }

      html += '</div>';

      document.getElementById('analysis-modal-title').textContent = '댓글 감성 분석';
      document.getElementById('analysis-modal-content').innerHTML = html;
      document.getElementById('analysis-modal').classList.add('show');
    },

    // ===== 태그 분석 =====

    analyzeTags: function() {
      var self = this;

      if (this.currentResults.length === 0) {
        alert('먼저 영상을 검색하세요.');
        return;
      }

      var videoIds = this.currentResults.slice(0, 20).map(function(v) { return v.videoId; });

      this.updateStatus('태그 패턴 분석 중...');

      fetch('/api/tubelens/analyze-tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videoIds: videoIds,
          apiKeys: this.apiKeys,
          currentApiKeyIndex: this.currentApiKeyIndex
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.showTagsModal(data.data);
          self.updateStatus('태그 분석 완료');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Tags error:', error);
        alert('태그 분석 실패: ' + error.message);
        self.updateStatus('분석 실패: ' + error.message);
      });
    },

    showTagsModal: function(data) {
      var html = '<div class="tags-content">';

      // 통계 요약
      html += '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px;">';
      html += '<div style="background:#f8f9fa;padding:16px;border-radius:10px;text-align:center;">';
      html += '<div style="font-size:1.5rem;font-weight:700;color:#667eea;">' + data.totalTagsAnalyzed + '</div>';
      html += '<div style="font-size:0.85rem;color:#666;">분석된 태그</div></div>';
      html += '<div style="background:#f8f9fa;padding:16px;border-radius:10px;text-align:center;">';
      html += '<div style="font-size:1.5rem;font-weight:700;color:#48bb78;">' + data.avgTagsPerVideo + '</div>';
      html += '<div style="font-size:0.85rem;color:#666;">영상당 평균 태그</div></div>';
      html += '<div style="background:#f8f9fa;padding:16px;border-radius:10px;text-align:center;">';
      html += '<div style="font-size:1.5rem;font-weight:700;color:#ed8936;">' + data.totalHashtagsAnalyzed + '</div>';
      html += '<div style="font-size:0.85rem;color:#666;">해시태그</div></div>';
      html += '</div>';

      // 인기 태그
      if (data.topTags && data.topTags.length) {
        html += '<div style="margin-bottom:20px;"><h4 style="margin-bottom:12px;">🏷️ 인기 태그 TOP 10</h4>';
        html += '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
        data.topTags.slice(0, 10).forEach(function(t, idx) {
          var bg = idx < 3 ? '#667eea' : '#a0aec0';
          html += '<span style="background:' + bg + ';color:#fff;padding:8px 14px;border-radius:20px;font-size:0.9rem;cursor:pointer;" onclick="navigator.clipboard.writeText(\'' + t.tag + '\');alert(\'복사됨: ' + t.tag + '\');">' + t.tag + ' <small>(' + t.count + ')</small></span>';
        });
        html += '</div></div>';
      }

      // 인기 해시태그
      if (data.topHashtags && data.topHashtags.length) {
        html += '<div style="margin-bottom:20px;"><h4 style="margin-bottom:12px;"># 인기 해시태그</h4>';
        html += '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
        data.topHashtags.forEach(function(h) {
          html += '<span style="background:#f093fb;color:#fff;padding:8px 14px;border-radius:20px;font-size:0.9rem;cursor:pointer;" onclick="navigator.clipboard.writeText(\'#' + h.hashtag + '\');alert(\'복사됨: #' + h.hashtag + '\');">#' + h.hashtag + ' <small>(' + h.count + ')</small></span>';
        });
        html += '</div></div>';
      }

      // 추천
      if (data.recommendations && data.recommendations.length) {
        html += '<div style="background:#f0fdf4;padding:16px;border-radius:10px;border-left:4px solid #48bb78;"><h4 style="margin-bottom:8px;">💡 추천</h4><ul style="margin:0;padding-left:20px;">';
        data.recommendations.forEach(function(r) {
          html += '<li style="margin-bottom:6px;">' + r + '</li>';
        });
        html += '</ul></div>';
      }

      html += '</div>';

      document.getElementById('analysis-modal-title').textContent = '태그 분석';
      document.getElementById('analysis-modal-content').innerHTML = html;
      document.getElementById('analysis-modal').classList.add('show');
    },

    // ===== 통합 분석 기능 =====

    // 영상 종합 점수 분석 (SEO + 바이럴)
    analyzeVideoScore: function(videoId) {
      var self = this;

      this.updateStatus('영상 종합 분석 중...');

      fetch('/api/tubelens/video-score', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videoId: videoId,
          apiKeys: this.apiKeys,
          currentApiKeyIndex: this.currentApiKeyIndex
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.showVideoScoreModal(data.data);
          self.updateStatus('영상 종합 분석 완료');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Video score error:', error);
        alert('영상 분석 실패: ' + error.message);
        self.updateStatus('분석 실패: ' + error.message);
      });
    },

    showVideoScoreModal: function(data) {
      var self = this;
      var html = '<div class="video-score-content">';

      // 영상 정보
      html += '<div style="display:flex;gap:16px;margin-bottom:20px;align-items:center;">';
      html += '<img src="' + data.thumbnail + '" style="width:160px;border-radius:8px;">';
      html += '<div>';
      html += '<h3 style="margin:0 0 8px 0;font-size:1.1rem;">' + data.title + '</h3>';
      html += '<div style="font-size:2rem;font-weight:700;color:#667eea;">' + data.totalScore + '<span style="font-size:1rem;color:#666;">/100</span></div>';
      html += '<div style="font-size:1.1rem;margin-top:4px;">' + data.totalGrade + '</div>';
      html += '</div></div>';

      // 점수 바
      html += '<div style="background:#e1e5eb;border-radius:10px;height:20px;overflow:hidden;margin-bottom:24px;">';
      var scoreColor = data.totalScore >= 70 ? '#48bb78' : data.totalScore >= 50 ? '#667eea' : data.totalScore >= 30 ? '#ed8936' : '#f56565';
      html += '<div style="width:' + data.totalScore + '%;height:100%;background:' + scoreColor + ';"></div>';
      html += '</div>';

      // SEO 점수
      html += '<div style="background:#f8f9fa;padding:16px;border-radius:12px;margin-bottom:16px;">';
      html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">';
      html += '<h4 style="margin:0;">🔍 SEO 점수</h4>';
      html += '<span style="font-size:1.5rem;font-weight:700;color:#667eea;">' + data.seo.score + ' <small style="font-size:0.9rem;">(' + data.seo.grade + ')</small></span>';
      html += '</div>';
      html += '<ul style="list-style:none;padding:0;margin:0;">';
      data.seo.details.forEach(function(d) {
        html += '<li style="padding:6px 0;border-bottom:1px solid #eee;font-size:0.9rem;">' + d + '</li>';
      });
      html += '</ul></div>';

      // 바이럴 점수
      html += '<div style="background:#f8f9fa;padding:16px;border-radius:12px;">';
      html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">';
      html += '<h4 style="margin:0;">🚀 바이럴 점수</h4>';
      html += '<span style="font-size:1.5rem;font-weight:700;color:#f56565;">' + data.viral.viralScore + '</span>';
      html += '</div>';
      html += '<div style="margin-bottom:12px;color:#666;">' + data.viral.viralGrade + '</div>';
      html += '<table style="width:100%;font-size:0.85rem;">';
      data.viral.viralFactors.forEach(function(f) {
        html += '<tr><td style="padding:6px 0;">' + f[0] + '</td><td style="text-align:center;">' + f[1] + '</td><td style="text-align:right;font-weight:600;">' + (typeof f[2] === 'number' ? self.formatNumber(Math.round(f[2])) : f[2]) + '</td></tr>';
      });
      html += '</table></div>';

      html += '</div>';

      document.getElementById('analysis-modal-title').textContent = '영상 종합 분석';
      document.getElementById('analysis-modal-content').innerHTML = html;
      document.getElementById('analysis-modal').classList.add('show');
    },

    // 채널 업로드 패턴 분석
    analyzeUploadPattern: function(channelId) {
      var self = this;

      if (!channelId) {
        // 현재 결과에서 첫 번째 채널 ID 사용
        if (this.currentResults.length > 0) {
          channelId = this.currentResults[0].channelId;
        } else {
          channelId = prompt('채널 ID를 입력하세요:');
          if (!channelId) return;
        }
      }

      this.updateStatus('채널 업로드 패턴 분석 중...');

      fetch('/api/tubelens/upload-pattern', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channelId: channelId,
          apiKeys: this.apiKeys,
          currentApiKeyIndex: this.currentApiKeyIndex
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.showUploadPatternModal(data.data);
          self.updateStatus('업로드 패턴 분석 완료');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Upload pattern error:', error);
        alert('패턴 분석 실패: ' + error.message);
        self.updateStatus('분석 실패: ' + error.message);
      });
    },

    showUploadPatternModal: function(data) {
      var self = this;
      var html = '<div class="upload-pattern-content">';

      // 채널 정보
      html += '<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:16px;border-radius:12px;margin-bottom:20px;text-align:center;">';
      html += '<h3 style="margin:0 0 8px 0;">' + data.channelTitle + '</h3>';
      html += '<div style="font-size:0.9rem;opacity:0.9;">최근 ' + data.analyzedVideos + '개 영상 분석</div>';
      html += '</div>';

      // 요일별 패턴
      html += '<div style="margin-bottom:20px;">';
      html += '<h4 style="margin-bottom:12px;">📅 요일별 성과</h4>';
      html += '<div style="display:flex;gap:8px;justify-content:space-between;">';
      var maxDayAvg = Math.max.apply(null, data.dayPattern.data.map(function(d) { return d.avgViews; })) || 1;
      data.dayPattern.data.forEach(function(d) {
        var height = Math.max(10, (d.avgViews / maxDayAvg) * 100);
        var isBest = d.day === data.dayPattern.bestDay;
        html += '<div style="flex:1;text-align:center;">';
        html += '<div style="height:100px;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;">';
        html += '<div style="width:100%;background:' + (isBest ? '#48bb78' : '#667eea') + ';height:' + height + '%;border-radius:4px 4px 0 0;"></div>';
        html += '</div>';
        html += '<div style="font-size:0.85rem;margin-top:4px;font-weight:' + (isBest ? '700' : '400') + ';">' + d.day + '</div>';
        html += '<div style="font-size:0.7rem;color:#666;">' + self.formatNumber(d.avgViews) + '</div>';
        html += '</div>';
      });
      html += '</div>';
      html += '<div style="background:#f0fdf4;padding:10px 14px;border-radius:8px;font-size:0.9rem;border-left:4px solid #48bb78;">' + data.dayPattern.recommendation + '</div>';
      html += '</div>';

      // 시간대별 패턴
      html += '<div style="margin-bottom:20px;">';
      html += '<h4 style="margin-bottom:12px;">⏰ 시간대별 성과</h4>';
      html += '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;">';
      var maxTimeAvg = Math.max.apply(null, data.timePattern.data.map(function(t) { return t.avgViews; })) || 1;
      data.timePattern.data.forEach(function(t) {
        var isBest = t.period === data.timePattern.bestTime;
        var width = Math.max(10, (t.avgViews / maxTimeAvg) * 100);
        html += '<div style="background:#f8f9fa;padding:12px;border-radius:8px;' + (isBest ? 'border:2px solid #48bb78;' : '') + '">';
        html += '<div style="font-size:0.85rem;margin-bottom:6px;">' + t.period + '</div>';
        html += '<div style="background:#e1e5eb;height:12px;border-radius:6px;overflow:hidden;">';
        html += '<div style="width:' + width + '%;height:100%;background:' + (isBest ? '#48bb78' : '#667eea') + ';"></div>';
        html += '</div>';
        html += '<div style="font-size:0.8rem;color:#666;margin-top:4px;">평균 ' + self.formatNumber(t.avgViews) + '회</div>';
        html += '</div>';
      });
      html += '</div>';
      html += '<div style="background:#f0fdf4;padding:10px 14px;border-radius:8px;font-size:0.9rem;border-left:4px solid #48bb78;">' + data.timePattern.recommendation + '</div>';
      html += '</div>';

      // 영상 길이 & 제목 길이
      html += '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px;">';

      // 영상 길이
      html += '<div style="background:#f8f9fa;padding:16px;border-radius:12px;">';
      html += '<h4 style="margin:0 0 12px 0;font-size:0.95rem;">🎬 영상 길이별 성과</h4>';
      for (var key in data.durationPattern.data) {
        var d = data.durationPattern.data[key];
        var isBest = d.label === data.durationPattern.bestDuration;
        html += '<div style="margin-bottom:8px;"><span style="font-size:0.85rem;' + (isBest ? 'font-weight:700;color:#48bb78;' : '') + '">' + d.label + '</span>';
        html += '<span style="float:right;font-size:0.85rem;">' + self.formatNumber(d.avgViews) + '회</span></div>';
      }
      html += '</div>';

      // 제목 길이
      html += '<div style="background:#f8f9fa;padding:16px;border-radius:12px;">';
      html += '<h4 style="margin:0 0 12px 0;font-size:0.95rem;">📝 제목 길이별 성과</h4>';
      for (var key2 in data.titleLengthPattern.data) {
        var t2 = data.titleLengthPattern.data[key2];
        var isBest2 = t2.label === data.titleLengthPattern.bestTitleLength;
        html += '<div style="margin-bottom:8px;"><span style="font-size:0.85rem;' + (isBest2 ? 'font-weight:700;color:#48bb78;' : '') + '">' + t2.label + '</span>';
        html += '<span style="float:right;font-size:0.85rem;">' + self.formatNumber(t2.avgViews) + '회</span></div>';
      }
      html += '</div>';

      html += '</div>';

      html += '</div>';

      document.getElementById('analysis-modal-title').textContent = '업로드 패턴 분석';
      document.getElementById('analysis-modal-content').innerHTML = html;
      document.getElementById('analysis-modal').classList.add('show');
    },

    // 유사 채널 찾기
    findSimilarChannels: function(channelId) {
      var self = this;

      if (!channelId) {
        if (this.currentResults.length > 0) {
          channelId = this.currentResults[0].channelId;
        } else {
          channelId = prompt('채널 ID를 입력하세요:');
          if (!channelId) return;
        }
      }

      this.updateStatus('유사 채널 검색 중...');

      fetch('/api/tubelens/similar-channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channelId: channelId,
          apiKeys: this.apiKeys,
          currentApiKeyIndex: this.currentApiKeyIndex
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.showSimilarChannelsModal(data.data);
          self.updateStatus('유사 채널 검색 완료');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Similar channels error:', error);
        alert('유사 채널 검색 실패: ' + error.message);
        self.updateStatus('검색 실패: ' + error.message);
      });
    },

    showSimilarChannelsModal: function(data) {
      var self = this;
      var html = '<div class="similar-channels-content">';

      // 기준 채널
      html += '<div style="background:#f8f9fa;padding:16px;border-radius:12px;margin-bottom:20px;">';
      html += '<div style="font-size:0.85rem;color:#666;margin-bottom:6px;">기준 채널</div>';
      html += '<div style="font-size:1.1rem;font-weight:600;">' + data.baseChannel.channelTitle + '</div>';
      html += '<div style="font-size:0.9rem;color:#666;">구독자 ' + self.formatNumber(data.baseChannel.subscriberCount) + '명</div>';
      html += '</div>';

      // 유사 채널 목록
      html += '<h4 style="margin-bottom:12px;">🔍 유사 채널 (' + data.similarChannels.length + '개)</h4>';
      html += '<div style="display:grid;gap:12px;">';

      data.similarChannels.forEach(function(ch, idx) {
        html += '<div style="display:flex;gap:12px;padding:12px;background:#fff;border:1px solid #e1e5eb;border-radius:10px;align-items:center;">';
        html += '<div style="font-size:1.2rem;font-weight:700;color:#667eea;width:24px;">' + (idx + 1) + '</div>';
        html += '<img src="' + ch.thumbnail + '" style="width:48px;height:48px;border-radius:50%;" onerror="this.style.display=\'none\'">';
        html += '<div style="flex:1;">';
        html += '<div style="font-weight:600;margin-bottom:4px;">' + ch.channelTitle + '</div>';
        html += '<div style="font-size:0.85rem;color:#666;">구독자 ' + self.formatNumber(ch.subscriberCount) + '명 · 영상 ' + self.formatNumber(ch.videoCount) + '개</div>';
        html += '</div>';
        html += '<div style="text-align:right;">';
        html += '<div style="background:#667eea;color:#fff;padding:4px 10px;border-radius:12px;font-size:0.8rem;">유사도 ' + ch.similarity + '%</div>';
        html += '<div style="font-size:0.75rem;color:#666;margin-top:4px;">' + ch.sizeRatio + '</div>';
        html += '</div>';
        html += '<button class="btn-sm success" onclick="TubeLens.addToCompare(\'' + ch.channelId + '\', \'' + ch.channelTitle.replace(/'/g, "\\'") + '\')">비교</button>';
        html += '</div>';
      });

      html += '</div></div>';

      document.getElementById('analysis-modal-title').textContent = '유사 채널';
      document.getElementById('analysis-modal-content').innerHTML = html;
      document.getElementById('analysis-modal').classList.add('show');
    },

    // 설명란 템플릿 생성
    generateDescription: function(videoId) {
      var self = this;
      var title = '';

      if (videoId) {
        var video = this.currentResults.find(function(v) { return v.videoId === videoId; });
        if (video) title = video.title;
      }

      if (!title) {
        title = prompt('영상 제목을 입력하세요:');
        if (!title) return;
      }

      var category = prompt('콘텐츠 스타일을 선택하세요 (general/news/story/education):', 'general') || 'general';

      this.updateStatus('설명란 템플릿 생성 중...');

      fetch('/api/tubelens/generate-description', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title,
          category: category,
          includeSections: ['timestamps', 'hashtags', 'cta']
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.showDescriptionTemplateModal(title, data.data);
          self.updateStatus('설명란 템플릿 생성 완료');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Description template error:', error);
        alert('설명란 생성 실패: ' + error.message);
        self.updateStatus('생성 실패: ' + error.message);
      });
    },

    showDescriptionTemplateModal: function(title, data) {
      var html = '<div class="description-template-content">';

      // 영상 제목
      html += '<div style="background:#f8f9fa;padding:12px 16px;border-radius:8px;margin-bottom:16px;">';
      html += '<div style="font-size:0.85rem;color:#666;margin-bottom:4px;">영상 제목</div>';
      html += '<div style="font-weight:600;">' + title + '</div>';
      html += '</div>';

      // 훅 라인
      if (data.hookLine) {
        html += '<div style="background:linear-gradient(135deg,#f093fb,#f5576c);color:#fff;padding:16px;border-radius:10px;margin-bottom:16px;">';
        html += '<div style="font-size:0.85rem;opacity:0.9;margin-bottom:6px;">🎣 검색 결과에 노출되는 첫 줄</div>';
        html += '<div style="font-size:1.1rem;font-weight:600;">' + data.hookLine + '</div>';
        html += '</div>';
      }

      // 설명란 템플릿
      html += '<div style="margin-bottom:16px;">';
      html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">';
      html += '<h4 style="margin:0;">📝 설명란 템플릿</h4>';
      html += '<button class="btn-sm success" onclick="navigator.clipboard.writeText(document.getElementById(\'desc-template\').innerText);alert(\'복사되었습니다!\');">전체 복사</button>';
      html += '</div>';
      html += '<div id="desc-template" style="background:#f8f9fa;padding:16px;border-radius:10px;font-size:0.9rem;white-space:pre-wrap;max-height:300px;overflow-y:auto;border:1px solid #e1e5eb;">' + (data.description || '').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</div>';
      html += '</div>';

      // 작성 팁
      if (data.tips && data.tips.length) {
        html += '<div style="background:#f0fdf4;padding:16px;border-radius:10px;border-left:4px solid #48bb78;">';
        html += '<h4 style="margin:0 0 10px 0;">💡 작성 팁</h4>';
        html += '<ul style="margin:0;padding-left:20px;">';
        data.tips.forEach(function(tip) {
          html += '<li style="margin-bottom:6px;font-size:0.9rem;">' + tip + '</li>';
        });
        html += '</ul></div>';
      }

      html += '</div>';

      document.getElementById('analysis-modal-title').textContent = '설명란 템플릿';
      document.getElementById('analysis-modal-content').innerHTML = html;
      document.getElementById('analysis-modal').classList.add('show');
    },

    // ===== 경쟁채널 워치리스트 =====

    watchlist: [],

    loadWatchlist: function() {
      var saved = localStorage.getItem('tubelens_watchlist');
      if (saved) {
        try {
          this.watchlist = JSON.parse(saved);
        } catch (e) {
          this.watchlist = [];
        }
      }
    },

    saveWatchlist: function() {
      localStorage.setItem('tubelens_watchlist', JSON.stringify(this.watchlist));
    },

    addToWatchlist: function(channelId, channelTitle) {
      this.loadWatchlist();

      var exists = this.watchlist.some(function(w) { return w.channelId === channelId; });
      if (exists) {
        alert('이미 워치리스트에 있는 채널입니다.');
        return;
      }

      this.watchlist.push({
        channelId: channelId,
        channelTitle: channelTitle,
        addedAt: new Date().toISOString(),
        lastChecked: null,
        lastVideoCount: 0
      });

      this.saveWatchlist();
      this.updateStatus('워치리스트에 추가됨: ' + channelTitle);
      alert(channelTitle + '이(가) 워치리스트에 추가되었습니다.');
    },

    removeFromWatchlist: function(channelId) {
      this.watchlist = this.watchlist.filter(function(w) { return w.channelId !== channelId; });
      this.saveWatchlist();
      this.showWatchlist();
    },

    showWatchlist: function() {
      var self = this;
      this.loadWatchlist();

      var html = '<div class="watchlist-content">';

      if (this.watchlist.length === 0) {
        html += '<div style="padding:40px;text-align:center;color:#999;">';
        html += '<div style="font-size:3rem;margin-bottom:12px;">👀</div>';
        html += '<div>워치리스트가 비어있습니다.</div>';
        html += '<div style="font-size:0.85rem;margin-top:8px;">채널 비교 버튼 옆 👁️ 버튼으로 추가하세요.</div>';
        html += '</div>';
      } else {
        html += '<div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;">';
        html += '<span style="font-size:0.9rem;color:#666;">' + this.watchlist.length + '개 채널 추적 중</span>';
        html += '<button class="btn-sm" onclick="TubeLens.checkWatchlistUpdates()">새 영상 확인</button>';
        html += '</div>';

        html += '<div style="display:grid;gap:12px;">';
        this.watchlist.forEach(function(w) {
          html += '<div style="display:flex;gap:12px;padding:12px;background:#fff;border:1px solid #e1e5eb;border-radius:10px;align-items:center;">';
          html += '<div style="flex:1;">';
          html += '<div style="font-weight:600;margin-bottom:4px;">' + w.channelTitle + '</div>';
          html += '<div style="font-size:0.8rem;color:#666;">추가: ' + self.formatDate(w.addedAt) + '</div>';
          html += '</div>';
          html += '<div style="display:flex;gap:8px;">';
          html += '<button class="btn-sm" onclick="TubeLens.analyzeUploadPattern(\'' + w.channelId + '\')">분석</button>';
          html += '<button class="btn-sm success" onclick="TubeLens.searchChannelById(\'' + w.channelId + '\')">영상</button>';
          html += '<button class="btn-sm danger" onclick="TubeLens.removeFromWatchlist(\'' + w.channelId + '\')">삭제</button>';
          html += '</div></div>';
        });
        html += '</div>';
      }

      html += '</div>';

      document.getElementById('analysis-modal-title').textContent = '경쟁채널 워치리스트';
      document.getElementById('analysis-modal-content').innerHTML = html;
      document.getElementById('analysis-modal').classList.add('show');
    },

    checkWatchlistUpdates: function() {
      alert('워치리스트 새 영상 확인 기능은 준비 중입니다.\n현재는 채널별 "영상" 버튼으로 확인해주세요.');
    },

    // 결과 테이블에 워치리스트 버튼 추가를 위한 헬퍼
    addActionButtonsToRow: function(item) {
      var html = '<td class="action-buttons" style="white-space:nowrap;">';
      html += '<button class="btn-action bookmark" onclick="TubeLens.addBookmark(\'' + item.videoId + '\')" title="북마크">⭐</button>';
      html += '<button class="btn-action" onclick="TubeLens.analyzeVideoScore(\'' + item.videoId + '\')" title="종합 분석" style="background:#667eea;color:#fff;">📊</button>';
      html += '<button class="btn-action ab" onclick="TubeLens.suggestTitles(\'' + item.videoId + '\')" title="제목 A/B 제안">AB</button>';
      html += '<button class="btn-action sentiment" onclick="TubeLens.analyzeSentiment(\'' + item.videoId + '\')" title="댓글 감성 분석">💬</button>';
      html += '<button class="btn-action compare" onclick="TubeLens.addToCompare(\'' + item.channelId + '\', \'' + item.channelTitle.replace(/'/g, "\\'") + '\')" title="채널 비교에 추가">⚖️</button>';
      html += '<button class="btn-action" onclick="TubeLens.addToWatchlist(\'' + item.channelId + '\', \'' + item.channelTitle.replace(/'/g, "\\'") + '\')" title="워치리스트에 추가" style="background:#f56565;color:#fff;">👁️</button>';
      html += '</td>';
      return html;
    },

    // ===== 콘텐츠 분석기 =====
    analyzerResults: [],

    setAnalyzerPreset: function(keyword, region, language) {
      document.getElementById('analyzer-keyword').value = keyword;
      document.getElementById('analyzer-region').value = region;
      document.getElementById('analyzer-language').value = language;
      this.updateStatus('프리셋 적용됨: ' + keyword);
    },

    runAnalyzer: function() {
      var self = this;
      var keyword = document.getElementById('analyzer-keyword').value.trim();

      if (!keyword) {
        alert('검색 키워드를 입력해주세요.');
        document.getElementById('analyzer-keyword').focus();
        return;
      }

      if (this.apiKeys.length === 0 && !this.serverHasApiKey) {
        alert('먼저 API 키를 설정해주세요.');
        this.openSettings();
        return;
      }

      var regionCode = document.getElementById('analyzer-region').value;
      var language = document.getElementById('analyzer-language').value;
      var timeFrame = document.getElementById('analyzer-time').value;
      var duration = document.getElementById('analyzer-duration').value;
      var minViews = parseInt(document.getElementById('analyzer-min-views').value) || 10000;
      var maxResults = parseInt(document.getElementById('analyzer-max-results').value) || 25;

      this.showLoading(true);
      this.updateStatus('콘텐츠 분석 중... "' + keyword + '"');

      fetch('/api/tubelens/analyzer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keyword: keyword,
          regionCode: regionCode,
          relevanceLanguage: language,
          timeFrame: timeFrame,
          duration: duration,
          minViews: minViews,
          maxResults: maxResults,
          apiKeys: this.apiKeys,
          currentApiKeyIndex: this.currentApiKeyIndex
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.analyzerResults = data.data;
          self.originalResults = data.data;
          self.currentResults = data.data.slice();
          self.displayAnalyzerCards(data.data);
          self.updateStatus('콘텐츠 분석 완료: ' + data.data.length + '개 영상 발견');
        } else {
          throw new Error(data.message);
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] Analyzer error:', error);
        alert('콘텐츠 분석 실패: ' + error.message);
        self.showLoading(false);
        self.updateStatus('분석 실패: ' + error.message);
      });
    },

    displayAnalyzerCards: function(videos) {
      var self = this;
      var tbody = document.getElementById('results-tbody');
      var tableWrapper = document.getElementById('table-wrapper');
      var resultsBody = document.getElementById('results-body');

      this.showLoading(false);

      if (!videos || videos.length === 0) {
        tableWrapper.style.display = 'none';
        document.querySelector('.empty-state').style.display = 'flex';
        document.getElementById('results-count').textContent = '0개 영상';
        return;
      }

      document.querySelector('.empty-state').style.display = 'none';
      document.getElementById('results-count').textContent = videos.length + '개 영상';

      // 카드 뷰로 표시
      var html = '<div class="analyzer-results">';

      videos.forEach(function(v, idx) {
        var descPreview = (v.description || '').substring(0, 100).replace(/</g, '&lt;').replace(/>/g, '&gt;');
        if ((v.description || '').length > 100) descPreview += '...';

        var topCommentText = v.topComment ? v.topComment.substring(0, 80) : '댓글 로딩 필요';
        if (v.topComment && v.topComment.length > 80) topCommentText += '...';

        html += '<div class="analyzer-card">';
        html += '<div class="analyzer-card-thumb" onclick="TubeLens.openVideoModal(\'' + v.videoId + '\', \'' + self.escapeHtml(v.title) + '\')">';
        html += '<img src="' + (v.thumbnail || '') + '" alt="" onerror="this.src=\'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 9%22><rect fill=%22%23ddd%22 width=%2216%22 height=%229%22/></svg>\'">';
        html += '<span class="analyzer-card-rank">' + (idx + 1) + '</span>';
        html += '<span class="analyzer-card-duration">' + (v.duration || '0:00') + '</span>';
        html += '</div>';

        html += '<div class="analyzer-card-body">';
        html += '<div class="analyzer-card-title" title="' + self.escapeHtml(v.title) + '">' + self.escapeHtml(v.title) + '</div>';
        html += '<div class="analyzer-card-channel" onclick="TubeLens.loadChannelVideos({channelId:\'' + v.channelId + '\',channelTitle:\'' + self.escapeHtml(v.channelTitle) + '\'})">' + self.escapeHtml(v.channelTitle) + '</div>';

        html += '<div class="analyzer-card-stats">';
        html += '<span>👁 ' + self.formatNumber(v.viewCount) + '</span>';
        html += '<span>👍 ' + self.formatNumber(v.likeCount) + '</span>';
        html += '<span>💬 ' + self.formatNumber(v.commentCount) + '</span>';
        html += '<span>📅 ' + (v.publishedAt || '') + '</span>';
        html += '</div>';

        if (descPreview) {
          html += '<div class="analyzer-card-desc">' + descPreview + '</div>';
        }

        html += '<div class="analyzer-card-comments" data-video-id="' + v.videoId + '">';
        html += '<div class="analyzer-card-comments-title">인기 댓글</div>';
        html += '<div class="analyzer-card-comment">' + (v.topComment ? self.escapeHtml(topCommentText) : '<span style="color:#999">클릭하여 로드</span>') + '</div>';
        html += '</div>';

        html += '<div class="analyzer-card-actions">';
        html += '<button class="analyzer-card-btn play" onclick="TubeLens.openVideoModal(\'' + v.videoId + '\', \'' + self.escapeHtml(v.title) + '\')">재생</button>';
        html += '<button class="analyzer-card-btn comments" onclick="TubeLens.loadComments(\'' + v.videoId + '\', \'' + self.escapeHtml(v.title) + '\')">댓글</button>';
        html += '<button class="analyzer-card-btn desc" onclick="TubeLens.showDescription(\'' + v.videoId + '\')">전체설명</button>';
        html += '<button class="analyzer-card-btn copy" onclick="TubeLens.copyVideoInfo(\'' + v.videoId + '\')">복사</button>';
        html += '</div>';

        html += '</div>';
        html += '</div>';
      });

      html += '</div>';

      // 테이블 대신 카드 뷰 표시
      tableWrapper.style.display = 'none';

      // 기존 카드 뷰 제거 후 새로 추가
      var existingCards = resultsBody.querySelector('.analyzer-results');
      if (existingCards) {
        existingCards.remove();
      }
      resultsBody.insertAdjacentHTML('beforeend', html);

      // 댓글 자동 로드 (각 카드에 대해)
      this.loadTopCommentsForCards(videos);
    },

    loadTopCommentsForCards: function(videos) {
      var self = this;
      videos.forEach(function(v) {
        if (v.topComment) return; // 이미 로드된 경우 스킵

        self.fetchTopComment(v.videoId).then(function(comment) {
          var cardComments = document.querySelector('.analyzer-card-comments[data-video-id="' + v.videoId + '"] .analyzer-card-comment');
          if (cardComments && comment) {
            var text = comment.substring(0, 80);
            if (comment.length > 80) text += '...';
            cardComments.textContent = text;
            v.topComment = comment;
          }
        });
      });
    },

    fetchTopComment: function(videoId) {
      var self = this;
      return fetch('/api/tubelens/comments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videoId: videoId,
          maxResults: 1,
          apiKeys: this.apiKeys,
          currentApiKeyIndex: this.currentApiKeyIndex
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success && data.data && data.data.length > 0) {
          return data.data[0].text;
        }
        return null;
      })
      .catch(function(err) {
        console.log('[TubeLens] Failed to fetch comment for', videoId);
        return null;
      });
    },

    showDescription: function(videoId) {
      var video = this.currentResults.find(function(v) { return v.videoId === videoId; });
      if (video) {
        this.currentDescription = video.description || '설명이 없습니다.';
        document.getElementById('description-content').textContent = this.currentDescription;
        this.openDescriptionModal();
      }
    },

    copyVideoInfo: function(videoId) {
      var video = this.currentResults.find(function(v) { return v.videoId === videoId; });
      if (!video) return;

      var text = '제목: ' + video.title + '\n';
      text += '채널: ' + video.channelTitle + '\n';
      text += 'URL: https://www.youtube.com/watch?v=' + videoId + '\n';
      text += '조회수: ' + this.formatNumber(video.viewCount) + '\n';
      text += '좋아요: ' + this.formatNumber(video.likeCount) + '\n';
      text += '게시일: ' + video.publishedAt + '\n';
      text += '\n설명:\n' + (video.description || '없음');

      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function() {
          alert('영상 정보가 클립보드에 복사되었습니다.');
        });
      } else {
        var textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        alert('영상 정보가 클립보드에 복사되었습니다.');
      }
    },

    exportAnalyzerResults: function() {
      if (!this.currentResults || this.currentResults.length === 0) {
        alert('내보낼 결과가 없습니다. 먼저 분석을 실행해주세요.');
        return;
      }

      var csv = 'No,제목,채널명,조회수,좋아요,댓글수,게시일,영상길이,URL,설명\n';
      var self = this;

      this.currentResults.forEach(function(v, idx) {
        var row = [
          idx + 1,
          '"' + (v.title || '').replace(/"/g, '""') + '"',
          '"' + (v.channelTitle || '').replace(/"/g, '""') + '"',
          v.viewCount || 0,
          v.likeCount || 0,
          v.commentCount || 0,
          v.publishedAt || '',
          v.duration || '',
          'https://www.youtube.com/watch?v=' + v.videoId,
          '"' + (v.description || '').replace(/"/g, '""').replace(/\n/g, ' ') + '"'
        ];
        csv += row.join(',') + '\n';
      });

      // BOM 추가 (한글 Excel 호환)
      var blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = 'tubelens_analyzer_' + new Date().toISOString().slice(0,10) + '.csv';
      a.click();
      URL.revokeObjectURL(url);

      this.updateStatus('CSV 파일 다운로드 완료');
    },

    escapeHtml: function(text) {
      if (!text) return '';
      return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    },

    // ===== AI 기획 생성 =====
    currentAIPlanVideo: null,
    currentAIPlanPrompt: '',

    generateAIPlan: function(videoId) {
      var self = this;
      var video = this.currentResults.find(function(v) { return v.videoId === videoId; });

      if (!video) {
        alert('영상 정보를 찾을 수 없습니다.');
        return;
      }

      this.currentAIPlanVideo = video;
      this.updateStatus('AI 기획 생성 중...');

      // 모달 표시 (로딩 상태)
      var modalTitle = document.getElementById('analysis-modal-title');
      var modalContent = document.getElementById('analysis-modal-content');

      modalTitle.textContent = '🎯 AI 콘텐츠 기획';

      // 로딩 UI
      var loadingHtml = '<div class="ai-plan-content">';
      loadingHtml += '<div class="ai-plan-video-info">';
      loadingHtml += '<img src="' + (video.thumbnail || '') + '" alt="">';
      loadingHtml += '<div class="ai-plan-video-stats">';
      loadingHtml += '<h4>' + this.escapeHtml(video.title) + '</h4>';
      loadingHtml += '<p>채널: ' + this.escapeHtml(video.channelTitle) + '</p>';
      loadingHtml += '<p>조회수: ' + this.formatNumber(video.viewCount) + ' · 구독자: ' + this.formatNumber(video.subscriberCount) + '</p>';
      loadingHtml += '<p><strong style="color:#ff0000">성과도: ' + (video.performanceValue || 0).toFixed(2) + '배</strong></p>';
      loadingHtml += '</div></div>';
      loadingHtml += '<div style="text-align:center;padding:40px">';
      loadingHtml += '<div class="loading-spinner"></div>';
      loadingHtml += '<p>AI가 떡상 영상의 DNA를 분석 중...</p>';
      loadingHtml += '</div></div>';

      modalContent.innerHTML = loadingHtml;
      document.getElementById('analysis-modal').classList.add('show');

      // API 호출
      fetch('/api/tubelens/generate-ai-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videoId: video.videoId,
          title: video.title,
          description: video.description,
          channelTitle: video.channelTitle,
          viewCount: video.viewCount,
          subscriberCount: video.subscriberCount,
          likeCount: video.likeCount,
          commentCount: video.commentCount,
          performanceValue: video.performanceValue,
          duration: video.duration,
          publishedAt: video.publishedAt
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.success) {
          self.currentAIPlanPrompt = data.data.prompt;
          self.displayAIPlanResult(video, data.data);
          self.updateStatus('AI 기획 생성 완료');
        } else {
          throw new Error(data.message || 'AI 기획 생성 실패');
        }
      })
      .catch(function(error) {
        console.error('[TubeLens] AI Plan error:', error);
        // 에러 시 기본 템플릿 제공
        self.displayAIPlanFallback(video);
        self.updateStatus('AI 기획 생성 실패 - 기본 템플릿 제공');
      });
    },

    displayAIPlanResult: function(video, planData) {
      var modalContent = document.getElementById('analysis-modal-content');

      var html = '<div class="ai-plan-content">';

      // 영상 정보
      html += '<div class="ai-plan-video-info">';
      html += '<img src="' + (video.thumbnail || '') + '" alt="">';
      html += '<div class="ai-plan-video-stats">';
      html += '<h4>' + this.escapeHtml(video.title) + '</h4>';
      html += '<p>채널: ' + this.escapeHtml(video.channelTitle) + '</p>';
      html += '<p>조회수: ' + this.formatNumber(video.viewCount) + ' · 구독자: ' + this.formatNumber(video.subscriberCount) + '</p>';
      html += '<p><strong style="color:#ff0000">🔥 성과도: ' + (video.performanceValue || 0).toFixed(2) + '배</strong></p>';
      html += '</div></div>';

      // 성공 요인 분석
      if (planData.successFactors) {
        html += '<div class="ai-plan-section">';
        html += '<h4>📊 이 영상이 터진 이유</h4>';
        html += '<ul>';
        planData.successFactors.forEach(function(factor) {
          html += '<li>' + factor + '</li>';
        });
        html += '</ul></div>';
      }

      // 추천 제목
      if (planData.suggestedTitles) {
        html += '<div class="ai-plan-section">';
        html += '<h4>🏷️ 비슷한 스타일 제목 제안</h4>';
        html += '<ul>';
        planData.suggestedTitles.forEach(function(title) {
          html += '<li>' + title + '</li>';
        });
        html += '</ul></div>';
      }

      // 썸네일 제안
      if (planData.thumbnailIdeas) {
        html += '<div class="ai-plan-section">';
        html += '<h4>🖼️ 썸네일 문구 제안</h4>';
        html += '<ul>';
        planData.thumbnailIdeas.forEach(function(idea) {
          html += '<li>' + idea + '</li>';
        });
        html += '</ul></div>';
      }

      // 초반 30초 후킹
      if (planData.hookScript) {
        html += '<div class="ai-plan-section">';
        html += '<h4>🎬 초반 30초 후킹 스크립트</h4>';
        html += '<p style="background:#fff;padding:12px;border-radius:8px;white-space:pre-wrap;">' + planData.hookScript + '</p>';
        html += '</div>';
      }

      // 콘텐츠 기획 아이디어
      if (planData.contentIdeas) {
        html += '<div class="ai-plan-section">';
        html += '<h4>💡 관련 콘텐츠 아이디어</h4>';
        html += '<ul>';
        planData.contentIdeas.forEach(function(idea) {
          html += '<li>' + idea + '</li>';
        });
        html += '</ul></div>';
      }

      // 복사 버튼
      html += '<button class="copy-prompt-btn" onclick="TubeLens.copyAIPlanPrompt()">';
      html += '<span>📋</span> Gemini에 붙여넣기용 프롬프트 복사';
      html += '</button>';

      html += '</div>';

      modalContent.innerHTML = html;
    },

    displayAIPlanFallback: function(video) {
      var self = this;
      var modalContent = document.getElementById('analysis-modal-content');

      // 기본 분석 생성
      var performanceText = '';
      if (video.performanceValue >= 100) {
        performanceText = '🔥 신의 간택! 구독자 대비 조회수가 무려 ' + Math.floor(video.performanceValue) + '배입니다!';
      } else if (video.performanceValue >= 50) {
        performanceText = '🚀 고성과 영상! 구독자 대비 조회수가 ' + Math.floor(video.performanceValue) + '배입니다.';
      } else if (video.performanceValue >= 10) {
        performanceText = '👍 평균 이상의 성과! 구독자 대비 조회수가 ' + Math.floor(video.performanceValue) + '배입니다.';
      } else {
        performanceText = '📊 구독자 대비 조회수가 ' + video.performanceValue.toFixed(2) + '배입니다.';
      }

      var prompt = this.generateAIPlanPrompt(video);
      this.currentAIPlanPrompt = prompt;

      var html = '<div class="ai-plan-content">';

      // 영상 정보
      html += '<div class="ai-plan-video-info">';
      html += '<img src="' + (video.thumbnail || '') + '" alt="">';
      html += '<div class="ai-plan-video-stats">';
      html += '<h4>' + this.escapeHtml(video.title) + '</h4>';
      html += '<p>채널: ' + this.escapeHtml(video.channelTitle) + '</p>';
      html += '<p>조회수: ' + this.formatNumber(video.viewCount) + ' · 구독자: ' + this.formatNumber(video.subscriberCount) + '</p>';
      html += '<p><strong style="color:#ff0000">' + performanceText + '</strong></p>';
      html += '</div></div>';

      html += '<div class="ai-plan-section">';
      html += '<h4>🎯 AI 분석 프롬프트</h4>';
      html += '<p>아래 버튼을 클릭하여 프롬프트를 복사한 후 Gemini 또는 ChatGPT에 붙여넣으세요.</p>';
      html += '<p style="background:#fff;padding:12px;border-radius:8px;font-size:0.85rem;max-height:200px;overflow-y:auto;white-space:pre-wrap;">' + this.escapeHtml(prompt.substring(0, 500)) + '...</p>';
      html += '</div>';

      // 복사 버튼
      html += '<button class="copy-prompt-btn" onclick="TubeLens.copyAIPlanPrompt()">';
      html += '<span>📋</span> Gemini에 붙여넣기용 프롬프트 복사';
      html += '</button>';

      html += '</div>';

      modalContent.innerHTML = html;
    },

    generateAIPlanPrompt: function(video) {
      var prompt = '다음은 YouTube에서 구독자 대비 ' + (video.performanceValue || 0).toFixed(0) + '배의 조회수를 기록한 떡상 영상입니다.\n\n';
      prompt += '=== 영상 정보 ===\n';
      prompt += '제목: ' + video.title + '\n';
      prompt += '채널: ' + video.channelTitle + '\n';
      prompt += '조회수: ' + this.formatNumber(video.viewCount) + '\n';
      prompt += '구독자 수: ' + this.formatNumber(video.subscriberCount) + '\n';
      prompt += '성과도 배율: ' + (video.performanceValue || 0).toFixed(2) + '배\n';
      prompt += '좋아요: ' + this.formatNumber(video.likeCount) + '\n';
      prompt += '댓글 수: ' + this.formatNumber(video.commentCount) + '\n';
      prompt += '영상 길이: ' + video.duration + '\n';
      prompt += 'URL: https://www.youtube.com/watch?v=' + video.videoId + '\n\n';

      if (video.description) {
        prompt += '=== 영상 설명 ===\n';
        prompt += video.description.substring(0, 500) + '\n\n';
      }

      prompt += '=== 분석 요청 ===\n';
      prompt += '이 영상이 터진 이유를 분석하고, 다음을 제공해주세요:\n\n';
      prompt += '1. 이 영상이 터진 3가지 핵심 요인\n';
      prompt += '2. 비슷한 스타일의 제목 3개 제안\n';
      prompt += '3. 클릭을 유도하는 썸네일 문구 2개\n';
      prompt += '4. 초반 30초 후킹을 위한 멘트 예시\n';
      prompt += '5. 이 영상을 참고한 관련 콘텐츠 아이디어 3개\n';

      return prompt;
    },

    copyAIPlanPrompt: function() {
      if (!this.currentAIPlanPrompt) {
        alert('복사할 프롬프트가 없습니다.');
        return;
      }

      if (navigator.clipboard) {
        navigator.clipboard.writeText(this.currentAIPlanPrompt).then(function() {
          alert('✅ 프롬프트가 클립보드에 복사되었습니다!\n\nGemini 또는 ChatGPT에 붙여넣어 분석을 받아보세요.');
        });
      } else {
        var textarea = document.createElement('textarea');
        textarea.value = this.currentAIPlanPrompt;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        alert('✅ 프롬프트가 클립보드에 복사되었습니다!\n\nGemini 또는 ChatGPT에 붙여넣어 분석을 받아보세요.');
      }
    }
  };

  // window에 TubeLens 객체 할당
  window.TubeLens = TubeLens;

  // 모달 외부 클릭 시 닫기
  document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal') && e.target.classList.contains('show')) {
      e.target.classList.remove('show');
      if (e.target.id === 'video-modal') {
        document.getElementById('video-iframe').src = '';
      }
    }
  });

  // 초기화
  document.addEventListener('DOMContentLoaded', function() {
    TubeLens.init();
  });

})();
