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
    filters: {
      ciiGreat: false,
      ciiGood: false,
      ciiSoso: false
    },

    // 초기화
    init: function() {
      this.loadApiKeys();
      this.updateApiKeysList();
      this.updateStatus();
      console.log('[TubeLens] Initialized with', this.apiKeys.length, 'API keys');
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

      var html = '<tr>';
      html += '<td>' + item.index + '</td>';
      html += '<td><img class="thumbnail" src="' + item.thumbnail + '" alt="" onclick="TubeLens.openVideoModal(\'' + item.videoId + '\', \'' + escapedTitle.replace(/'/g, "\\'") + '\')" onerror="this.src=\'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22140%22 height=%2279%22><rect fill=%22%23e1e5eb%22 width=%22140%22 height=%2279%22/><text x=%2270%22 y=%2245%22 text-anchor=%22middle%22 fill=%22%23999%22 font-size=%2212%22>No Image</text></svg>\'"></td>';
      html += '<td class="channel-name" onclick="TubeLens.searchChannelById(\'' + item.channelId + '\')">' + item.channelTitle + '</td>';
      html += '<td class="video-title">' + item.title + '</td>';
      html += '<td>' + item.publishedAt + '</td>';
      html += '<td>' + this.formatNumber(item.subscriberCount) + '</td>';
      html += '<td>' + this.formatNumber(item.viewCount) + '</td>';
      html += '<td><div class="gauge"><div class="gauge-fill ' + contribColor + '" style="width:' + contribPercent + '%"></div></div><div class="gauge-value">' + contribPercent.toFixed(0) + '%</div></td>';
      html += '<td>' + item.performanceValue.toFixed(2) + 'x</td>';
      html += '<td><span class="cii-badge ' + ciiClass + '">' + item.cii + '</span></td>';
      html += '<td>' + item.duration + '</td>';
      html += '<td>' + this.formatNumber(item.likeCount) + '</td>';
      html += '<td style="cursor:pointer;color:#3182ce" onclick="TubeLens.loadComments(\'' + item.videoId + '\', \'' + escapedTitle.replace(/'/g, "\\'") + '\')">' + this.formatNumber(item.commentCount) + '</td>';
      html += '<td>' + engagementRate.toFixed(2) + '%</td>';
      html += '<td>' + this.formatNumber(item.videoCount || 0) + '</td>';
      html += '<td style="cursor:pointer;color:#3182ce" onclick="TubeLens.showDescription(\'' + item.videoId + '\')">보기</td>';
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
