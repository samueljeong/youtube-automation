/**
 * Brandpipe - AI 공급처 탐색기 프론트엔드
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

  // 공급처 테이블
  const suppliersBody = document.getElementById('suppliersBody');
  const supplierCount = document.getElementById('supplierCount');

  // 메타 정보
  const metaTime = document.getElementById('metaTime');
  const metaProviders = document.getElementById('metaProviders');

  // 검색 기록
  const historyList = document.getElementById('historyList');
  const refreshHistory = document.getElementById('refreshHistory');

  // 초기 로드
  loadHistory();

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

  // 검색 기록 새로고침
  refreshHistory.addEventListener('click', () => {
    loadHistory();
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

      displayResult(data);
      loadHistory(); // 기록 갱신

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
    const { product, suppliers, meta } = data;

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
    }

    // 공급처 테이블 표시
    if (suppliers && suppliers.length > 0) {
      supplierCount.textContent = suppliers.length;
      suppliersBody.innerHTML = '';

      suppliers.forEach(supplier => {
        const row = document.createElement('tr');

        // 마진 클래스
        const marginClass = supplier.estimated_margin_rate >= 0 ? 'margin-positive' : 'margin-negative';

        row.innerHTML = `
          <td>
            <div class="supplier-name">${escapeHtml(supplier.name)}</div>
            <div class="supplier-source">${escapeHtml(supplier.source)}</div>
          </td>
          <td>${formatPrice(supplier.unit_price_krw || supplier.unit_price)}</td>
          <td>${formatPrice(supplier.shipping_fee)}</td>
          <td>${supplier.moq || '-'}개</td>
          <td class="${marginClass} margin-rate">${formatPercent(supplier.estimated_margin_rate)}</td>
          <td class="${marginClass}">${formatPrice(supplier.estimated_margin_amount)}</td>
          <td>
            <a href="${escapeHtml(supplier.url)}" target="_blank" class="supplier-link">보기 →</a>
          </td>
        `;

        suppliersBody.appendChild(row);
      });

      suppliersCard.classList.add('visible');
    }

    // 메타 정보
    if (meta) {
      metaTime.textContent = `분석 시간: ${meta.analysis_time_ms}ms`;
      metaProviders.textContent = `검색 소스: ${meta.search_providers.join(', ')}`;
      metaInfo.classList.add('visible');
    }
  }

  /**
   * 검색 기록 로드
   */
  async function loadHistory() {
    try {
      const response = await fetch('/api/brandpipe/history?limit=10');
      const data = await response.json();

      if (!data.ok || !data.history || data.history.length === 0) {
        historyList.innerHTML = '<div class="history-empty">검색 기록이 없습니다</div>';
        return;
      }

      historyList.innerHTML = '';

      data.history.forEach(item => {
        const div = document.createElement('div');
        div.className = 'history-item';

        const marginText = item.margin_summary
          ? `${formatPercent(item.margin_summary.best_margin_rate)} (${item.margin_summary.supplier_count}개)`
          : '-';

        div.innerHTML = `
          <div class="history-title">${escapeHtml(item.product_title || item.input_keyword || '(제목 없음)')}</div>
          <div class="history-meta">
            <span>${formatDate(item.created_at)}</span>
            <span class="history-margin">${marginText}</span>
          </div>
        `;

        // 클릭 시 입력 필드에 채우기
        div.addEventListener('click', () => {
          if (item.input_url) {
            productUrlInput.value = item.input_url;
            keywordInput.value = '';
          } else if (item.input_keyword) {
            keywordInput.value = item.input_keyword;
            productUrlInput.value = '';
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
    initialState.style.display = 'none';
  }

  function formatPrice(price) {
    if (price === null || price === undefined) return '-';
    return new Intl.NumberFormat('ko-KR', {
      style: 'currency',
      currency: 'KRW',
      maximumFractionDigits: 0
    }).format(price);
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
});
