/**
 * Brandpipe - AI 공급처 탐색기 프론트엔드 v3.0
 * Track 3: 워치리스트 + 즐겨찾기 + 메모
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM 요소
  const analyzeForm = document.getElementById('analyzeForm');
  const analyzeBtn = document.getElementById('analyzeBtn');
  const productUrlInput = document.getElementById('productUrl');
  const keywordInput = document.getElementById('keyword');
  const includeOverseasCheckbox = document.getElementById('includeOverseas');

  // 결과 영역
  const errorMessage = document.getElementById('errorMessage');
  const loadingState = document.getElementById('loadingState');
  const productCard = document.getElementById('productCard');
  const suppliersCard = document.getElementById('suppliersCard');
  const initialState = document.getElementById('initialState');
  const metaInfo = document.getElementById('metaInfo');

  // 상품 정보
  const productImage = document.getElementById('productImage');
  const productTitle = document.getElementById('productTitle');
  const productMeta = document.getElementById('productMeta');
  const productPrice = document.getElementById('productPrice');
  const productLink = document.getElementById('productLink');
  const addToWatchlistBtn = document.getElementById('addToWatchlistBtn');

  // 공급처 테이블
  const suppliersBody = document.getElementById('suppliersBody');
  const supplierCount = document.getElementById('supplierCount');

  // 메타 정보
  const metaTime = document.getElementById('metaTime');
  const metaProviders = document.getElementById('metaProviders');

  // 검색 기록
  const historyList = document.getElementById('historyList');
  const refreshHistory = document.getElementById('refreshHistory');
  const historyTabs = document.querySelectorAll('.history-tab');

  // 워치리스트
  const watchlistList = document.getElementById('watchlistList');
  const watchlistCount = document.getElementById('watchlistCount');

  // 판매가 시뮬레이터
  const priceSimulator = document.getElementById('priceSimulator');
  const customPriceInput = document.getElementById('customPrice');
  const resetPriceBtn = document.getElementById('resetPrice');

  // 필터 배너
  const filterBanner = document.getElementById('filterBanner');
  const filterRate = document.getElementById('filterRate');
  const filterAmount = document.getElementById('filterAmount');
  const filteredCount = document.getElementById('filteredCount');
  const totalCount = document.getElementById('totalCount');

  // 테스트 URL 버튼
  const testUrlBtns = document.querySelectorAll('.test-url-btn[data-type]');

  // 상태 저장
  let currentData = null;
  let originalPlatformPrice = 0;
  let currentHistoryFilter = 'all';

  // 초기 로드
  loadHistory();
  loadWatchlist();

  // 폼 제출 핸들러
  analyzeForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const productUrl = productUrlInput.value.trim();
    const keyword = keywordInput.value.trim();

    if (!productUrl && !keyword) {
      showError('상품 URL 또는 키워드 중 하나는 입력해야 합니다.');
      return;
    }

    await analyzeProduct(productUrl, keyword);
  });

  // 테스트 URL 버튼 핸들러
  testUrlBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
      const type = btn.dataset.type;
      const value = btn.dataset.value;

      if (type === 'keyword') {
        keywordInput.value = value;
        productUrlInput.value = '';
      } else if (type === 'url') {
        productUrlInput.value = value;
        keywordInput.value = '';
      }

      // 바로 분석 실행
      await analyzeProduct(productUrlInput.value.trim(), keywordInput.value.trim());
    });
  });

  // 검색 기록 새로고침
  refreshHistory.addEventListener('click', () => {
    loadHistory(currentHistoryFilter === 'favorites');
  });

  // 히스토리 탭 핸들러
  historyTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      historyTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentHistoryFilter = tab.dataset.filter;
      loadHistory(currentHistoryFilter === 'favorites');
    });
  });

  // 워치리스트 추가 버튼
  addToWatchlistBtn.addEventListener('click', async () => {
    if (!currentData || !currentData.product) {
      alert('먼저 상품을 분석해 주세요.');
      return;
    }

    await addToWatchlist();
  });

  // 판매가 시뮬레이터: 가격 변경 시 재계산
  customPriceInput.addEventListener('input', () => {
    if (currentData && currentData.suppliers) {
      const customPrice = parseInt(customPriceInput.value) || 0;
      recalcMarginForCustomPrice(customPrice);
    }
  });

  // 초기화 버튼
  resetPriceBtn.addEventListener('click', () => {
    customPriceInput.value = originalPlatformPrice;
    if (currentData) {
      recalcMarginForCustomPrice(originalPlatformPrice);
    }
  });

  /**
   * 상품 분석 API 호출
   */
  async function analyzeProduct(productUrl, keyword) {
    hideAll();
    showLoading(true);

    try {
      const response = await fetch('/api/brandpipe/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          product_url: productUrl || null,
          keyword: keyword || null,
          include_overseas: includeOverseasCheckbox.checked
        })
      });

      const data = await response.json();

      showLoading(false);

      if (!data.ok) {
        showError(data.error || '분석 중 오류가 발생했습니다.');
        return;
      }

      // 상태 저장
      currentData = data;
      originalPlatformPrice = data.product?.price || 0;

      displayResult(data);
      loadHistory(currentHistoryFilter === 'favorites');

    } catch (err) {
      console.error('분석 오류:', err);
      showLoading(false);
      showError('서버 연결에 실패했습니다. 잠시 후 다시 시도해 주세요.');
    }
  }

  /**
   * 결과 표시
   */
  function displayResult(data) {
    const { product, suppliers, filters, meta } = data;

    // 상품 정보 표시
    if (product) {
      productTitle.textContent = product.title || '(제목 없음)';

      // 메타 정보
      const metaTags = [];
      if (product.brand) metaTags.push(`브랜드: ${product.brand}`);
      if (product.platform) metaTags.push(`플랫폼: ${product.platform}`);
      if (product.category) metaTags.push(`카테고리: ${product.category}`);
      productMeta.innerHTML = metaTags.map(tag => `<span>${tag}</span>`).join('');

      // 가격
      if (product.price) {
        productPrice.textContent = formatPrice(product.price);
      } else {
        productPrice.textContent = '가격 정보 없음';
      }

      // 이미지
      if (product.image_url) {
        productImage.src = product.image_url;
        productImage.style.display = 'block';
      } else {
        productImage.src = '';
        productImage.style.display = 'none';
      }

      // 링크
      if (product.platform_url) {
        productLink.href = product.platform_url;
        productLink.style.display = 'inline-block';
      } else {
        productLink.style.display = 'none';
      }

      productCard.classList.add('visible');

      // 판매가 시뮬레이터 초기화
      if (product.price) {
        customPriceInput.value = product.price;
        priceSimulator.classList.add('visible');
      }
    }

    // 필터 정보 표시
    if (filters) {
      filterRate.textContent = Math.round(filters.min_margin_rate * 100);
      filterAmount.textContent = formatNumber(filters.min_margin_amount);
      filteredCount.textContent = filters.filtered_count;
      totalCount.textContent = filters.total_count;
      filterBanner.classList.add('visible');
    }

    // 공급처 테이블 표시
    renderSuppliersTable(suppliers);

    // 메타 정보
    if (meta) {
      metaTime.textContent = `분석 시간: ${meta.analysis_time_ms}ms`;
      metaProviders.textContent = `검색 소스: ${meta.search_providers.join(', ')}`;
      metaInfo.classList.add('visible');
    }
  }

  /**
   * 공급처 테이블 렌더링
   */
  function renderSuppliersTable(suppliers, customPrice = null) {
    if (!suppliers || suppliers.length === 0) {
      suppliersCard.classList.remove('visible');
      return;
    }

    supplierCount.textContent = suppliers.length;
    suppliersBody.innerHTML = '';

    suppliers.forEach(supplier => {
      const row = document.createElement('tr');

      // 마진 계산 (커스텀 가격 사용 시)
      let marginRate = supplier.estimated_margin_rate;
      let marginAmount = supplier.estimated_margin_amount;

      if (customPrice !== null && customPrice > 0) {
        const totalCost = (supplier.unit_price_krw || supplier.unit_price) +
                         (supplier.shipping_fee || 0) +
                         (customPrice * 0.13);
        marginAmount = Math.round(customPrice - totalCost);
        marginRate = marginAmount / customPrice;
      }

      // 마진 클래스
      const marginClass = marginRate >= 0 ? 'margin-positive' : 'margin-negative';

      // 유사도 배지
      const simScore = supplier.similarity_score || 0;
      let simClass = 'similarity-low';
      let simLabel = '낮음';
      if (simScore >= 0.7) {
        simClass = 'similarity-high';
        simLabel = '높음';
      } else if (simScore >= 0.4) {
        simClass = 'similarity-medium';
        simLabel = '보통';
      }

      // 출처 배지
      const sourceLabel = getSourceLabel(supplier.source);
      const sourceBadgeClass = getSourceBadgeClass(supplier.source);

      row.innerHTML = `
        <td>
          <div class="supplier-name">${escapeHtml(supplier.name)}</div>
        </td>
        <td>
          <span class="source-badge ${sourceBadgeClass}">${sourceLabel}</span>
        </td>
        <td>
          <span class="similarity-badge ${simClass}">${simLabel} ${Math.round(simScore * 100)}%</span>
        </td>
        <td>${formatPrice(supplier.unit_price_krw || supplier.unit_price)}</td>
        <td>${formatPrice(supplier.shipping_fee)}</td>
        <td>${supplier.moq || '-'}개</td>
        <td class="${marginClass} margin-rate">${formatPercent(marginRate)}</td>
        <td class="${marginClass}">${formatPrice(marginAmount)}</td>
        <td>
          <a href="${escapeHtml(supplier.url)}" target="_blank" class="supplier-link">보기 →</a>
        </td>
      `;

      // 유사도 낮으면 행 스타일 변경
      if (simScore < 0.4) {
        row.style.opacity = '0.6';
      }

      suppliersBody.appendChild(row);
    });

    suppliersCard.classList.add('visible');
  }

  /**
   * 커스텀 가격으로 마진 재계산
   */
  function recalcMarginForCustomPrice(customPrice) {
    if (!currentData || !currentData.suppliers) return;

    // 테이블 다시 렌더링
    renderSuppliersTable(currentData.suppliers, customPrice);

    // 필터 카운트 업데이트
    if (currentData.filters) {
      let passCount = 0;
      currentData.suppliers.forEach(s => {
        const totalCost = (s.unit_price_krw || s.unit_price) +
                         (s.shipping_fee || 0) +
                         (customPrice * 0.13);
        const marginAmount = customPrice - totalCost;
        const marginRate = marginAmount / customPrice;

        if (marginRate >= currentData.filters.min_margin_rate &&
            marginAmount >= currentData.filters.min_margin_amount) {
          passCount++;
        }
      });
      filteredCount.textContent = passCount;
    }
  }

  /**
   * 검색 기록 로드
   */
  async function loadHistory(favoritesOnly = false) {
    try {
      const url = favoritesOnly
        ? '/api/brandpipe/history?limit=20&favorites_only=true'
        : '/api/brandpipe/history?limit=20';

      const response = await fetch(url);
      const data = await response.json();

      if (!data.ok || !data.history || data.history.length === 0) {
        historyList.innerHTML = `<div class="history-empty">${favoritesOnly ? '즐겨찾기가 없습니다' : '검색 기록이 없습니다'}</div>`;
        return;
      }

      historyList.innerHTML = '';

      data.history.forEach(item => {
        const div = document.createElement('div');
        div.className = 'history-item' + (item.is_favorite ? ' favorite' : '');
        div.dataset.id = item.id;

        // 최고 마진 표시
        let marginText = '-';
        if (item.margin_summary) {
          const rate = formatPercent(item.margin_summary.best_margin_rate);
          const amount = formatPrice(item.margin_summary.best_margin_amount);
          marginText = `${rate} / ${amount}`;
        }

        div.innerHTML = `
          <div class="history-title">${escapeHtml(item.product_title || item.input_keyword || '(제목 없음)')}</div>
          <div class="history-meta">
            <span>${formatDate(item.created_at)}</span>
            <span class="history-margin">${marginText}</span>
          </div>
          ${item.note ? `<div class="history-note">📝 ${escapeHtml(item.note)}</div>` : ''}
          <div class="history-actions">
            <button class="history-action-btn ${item.is_favorite ? 'active' : ''}" data-action="favorite" title="즐겨찾기">
              ${item.is_favorite ? '⭐' : '☆'}
            </button>
            <button class="history-action-btn" data-action="note" title="메모">📝</button>
          </div>
        `;

        // 클릭 시 입력 필드에 채우기 (액션 버튼 제외)
        div.addEventListener('click', (e) => {
          if (e.target.closest('.history-action-btn')) return;

          if (item.input_url) {
            productUrlInput.value = item.input_url;
            keywordInput.value = '';
          } else if (item.input_keyword) {
            keywordInput.value = item.input_keyword;
            productUrlInput.value = '';
          }
        });

        // 즐겨찾기 버튼
        const favBtn = div.querySelector('[data-action="favorite"]');
        favBtn.addEventListener('click', async (e) => {
          e.stopPropagation();
          await toggleFavorite(item.id, !item.is_favorite);
          loadHistory(currentHistoryFilter === 'favorites');
        });

        // 메모 버튼
        const noteBtn = div.querySelector('[data-action="note"]');
        noteBtn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const newNote = prompt('메모를 입력하세요:', item.note || '');
          if (newNote !== null) {
            await updateNote(item.id, newNote);
            loadHistory(currentHistoryFilter === 'favorites');
          }
        });

        historyList.appendChild(div);
      });

    } catch (err) {
      console.error('히스토리 로드 오류:', err);
      historyList.innerHTML = '<div class="history-empty">기록을 불러올 수 없습니다</div>';
    }
  }

  /**
   * 즐겨찾기 토글
   */
  async function toggleFavorite(searchId, isFavorite) {
    try {
      await fetch('/api/brandpipe/search/favorite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ search_id: searchId, is_favorite: isFavorite })
      });
    } catch (err) {
      console.error('즐겨찾기 토글 오류:', err);
    }
  }

  /**
   * 메모 업데이트
   */
  async function updateNote(searchId, note) {
    try {
      await fetch('/api/brandpipe/search/note', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ search_id: searchId, note: note })
      });
    } catch (err) {
      console.error('메모 업데이트 오류:', err);
    }
  }

  /**
   * 워치리스트 로드
   */
  async function loadWatchlist() {
    try {
      const response = await fetch('/api/brandpipe/watchlist?limit=20');
      const data = await response.json();

      if (!data.ok || !data.items || data.items.length === 0) {
        watchlistList.innerHTML = '<div class="watchlist-empty">관심 상품이 없습니다</div>';
        watchlistCount.textContent = '0';
        return;
      }

      watchlistCount.textContent = data.items.length;
      watchlistList.innerHTML = '';

      data.items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'watchlist-item';

        // 마진 정보
        let marginInfo = '';
        if (item.last_best_margin_rate !== null) {
          marginInfo = `최고 마진: ${formatPercent(item.last_best_margin_rate)}`;
        }

        div.innerHTML = `
          <div class="watchlist-info">
            <div class="watchlist-title">${escapeHtml(item.product_title)}</div>
            <div class="watchlist-meta">
              <span>${item.platform || '키워드'}</span>
              ${marginInfo ? `<span>${marginInfo}</span>` : ''}
              ${item.last_checked_at ? `<span>확인: ${formatDate(item.last_checked_at)}</span>` : ''}
            </div>
          </div>
          <div class="watchlist-actions">
            <button class="watchlist-btn" data-action="analyze" title="재분석">🔄</button>
            <button class="watchlist-btn danger" data-action="remove" title="삭제">🗑️</button>
          </div>
        `;

        // 재분석 버튼
        const analyzeBtn = div.querySelector('[data-action="analyze"]');
        analyzeBtn.addEventListener('click', async () => {
          await reanalyzeWatchlistItem(item.id);
        });

        // 삭제 버튼
        const removeBtn = div.querySelector('[data-action="remove"]');
        removeBtn.addEventListener('click', async () => {
          if (confirm('워치리스트에서 삭제하시겠습니까?')) {
            await removeFromWatchlist(item.id);
            loadWatchlist();
          }
        });

        watchlistList.appendChild(div);
      });

    } catch (err) {
      console.error('워치리스트 로드 오류:', err);
      watchlistList.innerHTML = '<div class="watchlist-empty">불러올 수 없습니다</div>';
    }
  }

  /**
   * 워치리스트에 추가
   */
  async function addToWatchlist() {
    if (!currentData || !currentData.product) return;

    const product = currentData.product;

    try {
      const response = await fetch('/api/brandpipe/watchlist/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          search_id: currentData.search_id || null,
          product_title: product.title || '',
          product_url: product.platform_url || '',
          platform: product.platform || '',
          target_margin_rate: 0.2,
          target_margin_amount: 5000
        })
      });

      const data = await response.json();
      if (data.ok) {
        alert('워치리스트에 추가되었습니다!');
        loadWatchlist();
      } else {
        alert('추가 실패: ' + (data.error || '알 수 없는 오류'));
      }
    } catch (err) {
      console.error('워치리스트 추가 오류:', err);
      alert('서버 오류가 발생했습니다.');
    }
  }

  /**
   * 워치리스트에서 삭제
   */
  async function removeFromWatchlist(id) {
    try {
      await fetch('/api/brandpipe/watchlist/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: id })
      });
    } catch (err) {
      console.error('워치리스트 삭제 오류:', err);
    }
  }

  /**
   * 워치리스트 항목 재분석
   */
  async function reanalyzeWatchlistItem(id) {
    try {
      showLoading(true);

      const response = await fetch('/api/brandpipe/watchlist/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: id })
      });

      const data = await response.json();
      showLoading(false);

      if (!data.ok) {
        showError(data.error || '재분석 중 오류가 발생했습니다.');
        return;
      }

      // 결과 표시
      currentData = data;
      originalPlatformPrice = data.product?.price || 0;
      displayResult(data);
      loadWatchlist();

    } catch (err) {
      console.error('워치리스트 재분석 오류:', err);
      showLoading(false);
      showError('서버 연결에 실패했습니다.');
    }
  }

  /**
   * 유틸리티 함수들
   */

  function showLoading(show) {
    if (show) {
      loadingState.classList.add('visible');
      analyzeBtn.classList.add('loading');
      analyzeBtn.disabled = true;
    } else {
      loadingState.classList.remove('visible');
      analyzeBtn.classList.remove('loading');
      analyzeBtn.disabled = false;
    }
  }

  function showError(message) {
    errorMessage.textContent = message;
    errorMessage.classList.add('visible');
  }

  function hideAll() {
    errorMessage.classList.remove('visible');
    loadingState.classList.remove('visible');
    productCard.classList.remove('visible');
    suppliersCard.classList.remove('visible');
    metaInfo.classList.remove('visible');
    priceSimulator.classList.remove('visible');
    filterBanner.classList.remove('visible');
    if (initialState) initialState.style.display = 'none';
  }

  function formatPrice(price) {
    if (price === null || price === undefined) return '-';
    return new Intl.NumberFormat('ko-KR', {
      style: 'currency',
      currency: 'KRW',
      maximumFractionDigits: 0
    }).format(price);
  }

  function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    return new Intl.NumberFormat('ko-KR').format(num);
  }

  function formatPercent(rate) {
    if (rate === null || rate === undefined) return '-';
    return (rate * 100).toFixed(1) + '%';
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMin = Math.floor(diffMs / 60000);
    const diffHour = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);

    if (diffMin < 1) return '방금 전';
    if (diffMin < 60) return `${diffMin}분 전`;
    if (diffHour < 24) return `${diffHour}시간 전`;
    if (diffDay < 7) return `${diffDay}일 전`;

    return date.toLocaleDateString('ko-KR', {
      month: 'short',
      day: 'numeric'
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /**
   * 출처 코드를 한글 라벨로 변환
   */
  function getSourceLabel(source) {
    const labels = {
      'domeggook': '도매꾹',
      'domeme': '도매매',
      'naver_shopping': '네이버 쇼핑',
      'alibaba': '알리바바',
      'mock': '테스트'
    };
    return labels[source] || source || '기타';
  }

  /**
   * 출처에 따른 배지 클래스 반환
   */
  function getSourceBadgeClass(source) {
    const classes = {
      'domeggook': 'source-domeggook',
      'domeme': 'source-domeme',
      'naver_shopping': 'source-naver',
      'alibaba': 'source-alibaba',
      'mock': 'source-default'
    };
    return classes[source] || 'source-default';
  }
});
