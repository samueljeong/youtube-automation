/**
 * 쿠팡파트너스 쇼츠 제작 페이지
 * - 쿠팡 URL 입력 → 상품 정보 추출
 * - AI 대본 자동 생성
 * - TTS + 이미지 슬라이드쇼 → 쇼츠 영상 생성
 */

window.ShortsApp = {
  // 상태
  productData: null,
  ttsAudioUrl: null,
  videoUrl: null,

  init() {
    console.log('[Shorts] 초기화');
    this.bindEvents();
    this.updateCharCounts();
  },

  bindEvents() {
    // 상품 정보 가져오기
    document.getElementById('btn-fetch-product')?.addEventListener('click', () => this.fetchProduct());

    // AI 대본 생성
    document.getElementById('btn-generate-script')?.addEventListener('click', () => this.generateScript());

    // TTS 생성
    document.getElementById('btn-generate-tts')?.addEventListener('click', () => this.generateTTS());

    // 영상 생성
    document.getElementById('btn-generate-video')?.addEventListener('click', () => this.generateVideo());

    // 다운로드
    document.getElementById('btn-download')?.addEventListener('click', () => this.downloadVideo());

    // 대본 복사
    document.getElementById('btn-copy-script')?.addEventListener('click', () => this.copyScript());

    // URL 입력 엔터키
    document.getElementById('coupang-url')?.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') this.fetchProduct();
    });

    // 글자수 카운트
    ['script-hook', 'script-content', 'script-cta'].forEach(id => {
      document.getElementById(id)?.addEventListener('input', () => this.updateCharCounts());
    });
  },

  // 쿠팡 상품 정보 가져오기
  async fetchProduct() {
    const urlInput = document.getElementById('coupang-url');
    const url = urlInput?.value?.trim();

    if (!url) {
      this.showStatus('쿠팡 상품 URL을 입력해주세요.', 'error');
      return;
    }

    if (!url.includes('coupang.com')) {
      this.showStatus('올바른 쿠팡 URL이 아닙니다.', 'error');
      return;
    }

    this.showLoading('fetch-loading', true);
    this.showStatus('상품 정보를 가져오는 중...', 'info');

    try {
      const response = await fetch('/api/shorts/fetch-coupang', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });

      const data = await response.json();

      if (!data.ok) {
        throw new Error(data.error || '상품 정보를 가져올 수 없습니다.');
      }

      this.productData = data.product;
      this.displayProduct(data.product);
      this.enableStep2();
      this.showStatus('상품 정보를 가져왔습니다!', 'success');

    } catch (error) {
      console.error('[Shorts] 상품 정보 오류:', error);
      this.showStatus(error.message, 'error');
    } finally {
      this.showLoading('fetch-loading', false);
    }
  },

  // 상품 정보 표시
  displayProduct(product) {
    const productInfo = document.getElementById('product-info');
    const imagesDiv = document.getElementById('product-images');
    const nameEl = document.getElementById('product-name');
    const priceEl = document.getElementById('product-price');
    const ratingEl = document.getElementById('product-rating');
    const reviewsEl = document.getElementById('product-reviews');

    // 이미지 표시
    imagesDiv.innerHTML = '';
    (product.images || []).slice(0, 6).forEach((imgUrl, idx) => {
      const img = document.createElement('img');
      img.src = imgUrl;
      img.alt = `상품 이미지 ${idx + 1}`;
      img.className = idx === 0 ? 'selected' : '';
      img.onclick = () => {
        imagesDiv.querySelectorAll('img').forEach(i => i.classList.remove('selected'));
        img.classList.add('selected');
      };
      imagesDiv.appendChild(img);
    });

    // 상품 정보 표시
    nameEl.textContent = product.name || '상품명 없음';
    priceEl.textContent = product.price || '가격 정보 없음';
    ratingEl.textContent = `★ ${product.rating || '0.0'}`;
    reviewsEl.textContent = `(리뷰 ${product.reviewCount || 0}개)`;

    productInfo.classList.remove('hidden');
  },

  // Step 2 활성화
  enableStep2() {
    document.getElementById('btn-generate-script').disabled = false;
    document.getElementById('btn-generate-tts').disabled = false;
  },

  // AI 대본 자동 생성
  async generateScript() {
    if (!this.productData) {
      this.showStatus('먼저 상품 정보를 가져와주세요.', 'error');
      return;
    }

    const btn = document.getElementById('btn-generate-script');
    const originalText = btn.innerHTML;
    btn.disabled = true;

    // Hook 스타일 옵션 가져오기
    const hookStyle = document.getElementById('hook-style')?.value || 'random';
    const category = document.getElementById('product-category')?.value || 'auto';
    const lengthPreset = document.getElementById('length-preset')?.value || 'medium';
    const generateVariations = document.getElementById('generate-variations')?.checked || false;

    btn.innerHTML = generateVariations
      ? '<span class="btn-icon">⏳</span> 3개 대본 생성 중...'
      : '<span class="btn-icon">⏳</span> 생성 중...';

    try {
      const response = await fetch('/api/shorts/generate-script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          productName: this.productData.name,
          price: this.productData.price,
          rating: this.productData.rating,
          reviewCount: this.productData.reviewCount,
          hookStyle: hookStyle,
          category: category,
          lengthPreset: lengthPreset,
          variations: generateVariations
        })
      });

      const data = await response.json();

      if (!data.ok) {
        throw new Error(data.error || '대본 생성 실패');
      }

      // 3개 대본 변형 모드
      if (generateVariations && data.scripts) {
        this.displayScriptVariations(data.scripts);
        this.showStatus(`${data.count}개 대본이 생성되었습니다! 선택해주세요.`, 'success');
      } else {
        // 단일 대본 모드
        document.getElementById('script-variations')?.classList.add('hidden');
        this.applyScript(data.script);
        this.showStatus('대본이 생성되었습니다!', 'success');
      }

    } catch (error) {
      console.error('[Shorts] 대본 생성 오류:', error);
      this.showStatus(error.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  },

  // 대본을 에디터에 적용
  applyScript(script) {
    document.getElementById('script-hook').value = script.hook || '';

    // content가 있으면 사용, 없으면 pain + solution + features 조합
    let content = script.content || '';
    if (!content) {
      const parts = [];
      if (script.pain) parts.push(script.pain);
      if (script.solution) parts.push(script.solution);
      if (script.features && Array.isArray(script.features)) {
        const features = script.features;
        if (features[0]) parts.push(`첫째, ${features[0]}.`);
        if (features[1]) parts.push(`둘째, ${features[1]}.`);
        if (features[2]) parts.push(`셋째, ${features[2]}.`);
      }
      content = parts.join('\n');
    }
    document.getElementById('script-content').value = content;
    document.getElementById('script-cta').value = script.cta || '';
    this.updateCharCounts();

    // 쿠팡파트너스 고지 문구
    if (script.disclosure) {
      console.log('[Shorts] 고지 문구:', script.disclosure);
    }
  },

  // 3개 대본 변형 표시
  displayScriptVariations(scripts) {
    const container = document.getElementById('script-variations');
    const grid = document.getElementById('variations-grid');

    // 스타일 라벨
    const styleLabels = {
      'price_shock': '💰 가격 자극',
      'pain_trigger': '🧊 문제 공감',
      'shock_surprise': '⚡ 반전/충격',
      'urgency': '⏰ 긴급',
      'random': '🎲 랜덤'
    };

    // 카드 생성
    grid.innerHTML = scripts.map((script, index) => {
      const styleLabel = styleLabels[script.style] || `버전 ${index + 1}`;
      const preview = script.pain || script.content?.slice(0, 60) || '';

      return `
        <div class="variation-card" data-index="${index}">
          <span class="variation-badge">${styleLabel}</span>
          <div class="variation-hook">"${script.hook}"</div>
          <div class="variation-preview">${preview}...</div>
        </div>
      `;
    }).join('');

    // 클릭 이벤트 바인딩
    grid.querySelectorAll('.variation-card').forEach(card => {
      card.addEventListener('click', () => {
        const index = parseInt(card.dataset.index);
        this.selectVariation(scripts, index);

        // 선택 상태 표시
        grid.querySelectorAll('.variation-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
      });
    });

    // 표시
    container.classList.remove('hidden');

    // 저장
    this.currentVariations = scripts;
  },

  // 변형 선택
  selectVariation(scripts, index) {
    const script = scripts[index];
    this.applyScript(script);
    this.showStatus(`버전 ${index + 1} 대본이 적용되었습니다.`, 'success');
  },

  // TTS 음성 생성
  async generateTTS() {
    const hook = document.getElementById('script-hook')?.value?.trim() || '';
    const content = document.getElementById('script-content')?.value?.trim() || '';
    const cta = document.getElementById('script-cta')?.value?.trim() || '';

    const fullScript = `${hook} ${content} ${cta}`.trim();

    if (!fullScript) {
      this.showStatus('대본을 입력해주세요.', 'error');
      return;
    }

    const voice = document.getElementById('voice-select')?.value || 'ko-KR-Neural2-C';
    const speed = parseFloat(document.getElementById('speech-rate')?.value) || 1.2;

    const btn = document.getElementById('btn-generate-tts');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span> 생성 중...';

    try {
      const response = await fetch('/api/shorts/generate-tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: fullScript,
          voice: voice,
          speed: speed
        })
      });

      const data = await response.json();

      if (!data.ok) {
        throw new Error(data.error || 'TTS 생성 실패');
      }

      this.ttsAudioUrl = data.audioUrl;
      document.getElementById('btn-generate-video').disabled = false;
      this.showStatus('음성이 생성되었습니다!', 'success');

    } catch (error) {
      console.error('[Shorts] TTS 오류:', error);
      this.showStatus(error.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  },

  // 쇼츠 영상 생성
  async generateVideo() {
    if (!this.productData || !this.ttsAudioUrl) {
      this.showStatus('상품 정보와 TTS 음성이 필요합니다.', 'error');
      return;
    }

    const effect = document.getElementById('transition-effect')?.value || 'kenburns';
    const imageDuration = parseInt(document.getElementById('image-duration')?.value) || 4;

    const btn = document.getElementById('btn-generate-video');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span> 생성 중...';

    const progressSection = document.getElementById('progress-section');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');

    progressSection.classList.remove('hidden');
    progressFill.style.width = '10%';
    progressText.textContent = '영상 생성 시작...';

    try {
      const response = await fetch('/api/shorts/generate-video', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          images: this.productData.images?.slice(0, 6) || [],
          audioUrl: this.ttsAudioUrl,
          effect: effect,
          imageDuration: imageDuration
        })
      });

      progressFill.style.width = '50%';
      progressText.textContent = '영상 렌더링 중...';

      const data = await response.json();

      if (!data.ok) {
        throw new Error(data.error || '영상 생성 실패');
      }

      progressFill.style.width = '100%';
      progressText.textContent = '완료!';

      this.videoUrl = data.videoUrl;
      this.displayResult(data.videoUrl);
      this.showStatus('쇼츠 영상이 생성되었습니다!', 'success');

    } catch (error) {
      console.error('[Shorts] 영상 생성 오류:', error);
      this.showStatus(error.message, 'error');
      progressText.textContent = '오류 발생';
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  },

  // 결과 표시
  displayResult(videoUrl) {
    const resultSection = document.getElementById('result-section');
    const video = document.getElementById('result-video');

    video.src = videoUrl;
    resultSection.classList.remove('hidden');
  },

  // 다운로드
  downloadVideo() {
    if (!this.videoUrl) {
      this.showStatus('다운로드할 영상이 없습니다.', 'error');
      return;
    }

    const a = document.createElement('a');
    a.href = this.videoUrl;
    a.download = `coupang_shorts_${Date.now()}.mp4`;
    a.click();
  },

  // 대본 복사
  copyScript() {
    const hook = document.getElementById('script-hook')?.value || '';
    const content = document.getElementById('script-content')?.value || '';
    const cta = document.getElementById('script-cta')?.value || '';

    const fullScript = `[훅]\n${hook}\n\n[상품소개]\n${content}\n\n[CTA]\n${cta}`;

    navigator.clipboard.writeText(fullScript).then(() => {
      this.showStatus('대본이 클립보드에 복사되었습니다!', 'success');
    }).catch(() => {
      this.showStatus('복사 실패', 'error');
    });
  },

  // 글자수 업데이트
  updateCharCounts() {
    const hook = document.getElementById('script-hook')?.value || '';
    const content = document.getElementById('script-content')?.value || '';
    const cta = document.getElementById('script-cta')?.value || '';

    document.getElementById('hook-count').textContent = hook.length;
    document.getElementById('content-count').textContent = content.length;
    document.getElementById('cta-count').textContent = cta.length;
    document.getElementById('total-count').textContent = hook.length + content.length + cta.length;
  },

  // 로딩 표시
  showLoading(elementId, show) {
    const el = document.getElementById(elementId);
    if (el) {
      el.classList.toggle('hidden', !show);
    }
  },

  // 상태 메시지 표시
  showStatus(message, type = 'info') {
    const statusBar = document.getElementById('status-bar');
    const statusMessage = statusBar.querySelector('.status-message');
    const statusIcon = statusBar.querySelector('.status-icon');

    const icons = {
      success: '✅',
      error: '❌',
      info: 'ℹ️'
    };

    statusIcon.textContent = icons[type] || icons.info;
    statusMessage.textContent = message;
    statusBar.className = `status-bar ${type}`;
    statusBar.classList.remove('hidden');

    setTimeout(() => {
      statusBar.classList.add('hidden');
    }, 4000);
  }
};

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
  ShortsApp.init();
});
