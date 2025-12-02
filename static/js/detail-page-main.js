/**
 * 상세페이지 제작 페이지
 * - 키워드 입력 → AI 카피 생성
 * - 섹션별 이미지 생성
 */

window.DetailPageApp = {
  // 상태
  generatedCopy: null,
  generatedImages: [],

  init() {
    console.log('[DetailPage] 초기화');
    this.bindEvents();
  },

  bindEvents() {
    // 생성 버튼
    document.getElementById('btn-generate')?.addEventListener('click', () => this.generate());

    // 전체 복사
    document.getElementById('btn-copy-all')?.addEventListener('click', () => this.copyAllText());

    // 이미지 재생성
    document.getElementById('btn-regenerate-images')?.addEventListener('click', () => this.regenerateImages());

    // 전체 다운로드
    document.getElementById('btn-download-all')?.addEventListener('click', () => this.downloadAll());
  },

  // 선택된 섹션 가져오기
  getSelectedSections() {
    const checkboxes = document.querySelectorAll('.checkbox-group input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
  },

  // 상세페이지 생성
  async generate() {
    const productName = document.getElementById('product-name')?.value?.trim();
    const category = document.getElementById('product-category')?.value;
    const targetAudience = document.getElementById('target-audience')?.value;
    const features = document.getElementById('product-features')?.value?.trim();
    const pricePoint = document.getElementById('price-point')?.value?.trim();
    const pageStyle = document.getElementById('page-style')?.value;
    const sections = this.getSelectedSections();

    if (!productName) {
      this.showStatus('상품명을 입력해주세요.', 'error');
      return;
    }

    if (sections.length === 0) {
      this.showStatus('최소 1개 이상의 섹션을 선택해주세요.', 'error');
      return;
    }

    // UI 상태 변경
    const btn = document.getElementById('btn-generate');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span> 생성 중...';

    document.getElementById('step3-section').classList.remove('hidden');
    document.getElementById('generate-loading').classList.remove('hidden');
    document.getElementById('result-container').classList.add('hidden');

    try {
      // 1. 카피 생성
      this.updateLoadingText('상세페이지 카피를 작성하는 중...');

      const copyResponse = await fetch('/api/detail-page/generate-copy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          productName,
          category,
          targetAudience,
          features,
          pricePoint,
          pageStyle,
          sections
        })
      });

      const copyData = await copyResponse.json();

      if (!copyData.ok) {
        throw new Error(copyData.error || '카피 생성 실패');
      }

      this.generatedCopy = copyData.copy;
      this.displayCopy(copyData.copy);

      // 2. 이미지 생성
      this.updateLoadingText('이미지를 생성하는 중... (시간이 걸릴 수 있습니다)');

      const imageResponse = await fetch('/api/detail-page/generate-images', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          productName,
          category,
          pageStyle,
          sections,
          copy: copyData.copy
        })
      });

      const imageData = await imageResponse.json();

      if (!imageData.ok) {
        throw new Error(imageData.error || '이미지 생성 실패');
      }

      this.generatedImages = imageData.images;
      this.displayImages(imageData.images);

      // 완료
      document.getElementById('generate-loading').classList.add('hidden');
      document.getElementById('result-container').classList.remove('hidden');
      this.showStatus('상세페이지가 생성되었습니다!', 'success');

    } catch (error) {
      console.error('[DetailPage] 생성 오류:', error);
      this.showStatus(error.message, 'error');
      document.getElementById('generate-loading').classList.add('hidden');
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  },

  // 로딩 텍스트 업데이트
  updateLoadingText(text) {
    const el = document.getElementById('loading-text');
    if (el) el.textContent = text;
  },

  // 카피 표시
  displayCopy(copy) {
    const container = document.getElementById('copy-sections');
    if (!container) return;

    const sectionNames = {
      hero: '히어로 배너',
      problem: '문제 제기',
      solution: '해결책',
      features: '주요 특징',
      usage: '사용 방법',
      review: '후기/리뷰',
      spec: '제품 스펙',
      cta: 'CTA'
    };

    container.innerHTML = '';

    for (const [key, content] of Object.entries(copy)) {
      if (!content) continue;

      const item = document.createElement('div');
      item.className = 'copy-section-item';
      item.innerHTML = `
        <div class="copy-section-title">${sectionNames[key] || key}</div>
        <div class="copy-section-content">${content}</div>
      `;
      container.appendChild(item);
    }
  },

  // 이미지 표시
  displayImages(images) {
    const container = document.getElementById('image-grid');
    if (!container) return;

    const sectionNames = {
      hero: '히어로 배너',
      problem: '문제 제기',
      solution: '해결책',
      features: '주요 특징',
      usage: '사용 방법',
      review: '후기',
      spec: '스펙',
      cta: 'CTA'
    };

    container.innerHTML = '';

    images.forEach((img, idx) => {
      const item = document.createElement('div');
      item.className = 'image-item';
      item.innerHTML = `
        <img src="${img.url}" alt="${img.section}">
        <div class="image-item-overlay">
          <span class="image-item-title">${sectionNames[img.section] || img.section}</span>
          <button class="image-item-download" onclick="DetailPageApp.downloadImage('${img.url}', '${img.section}')">📥</button>
        </div>
      `;
      container.appendChild(item);
    });
  },

  // 전체 텍스트 복사
  copyAllText() {
    if (!this.generatedCopy) {
      this.showStatus('복사할 내용이 없습니다.', 'error');
      return;
    }

    const sectionNames = {
      hero: '[ 히어로 배너 ]',
      problem: '[ 문제 제기 ]',
      solution: '[ 해결책 ]',
      features: '[ 주요 특징 ]',
      usage: '[ 사용 방법 ]',
      review: '[ 후기/리뷰 ]',
      spec: '[ 제품 스펙 ]',
      cta: '[ CTA ]'
    };

    let text = '';
    for (const [key, content] of Object.entries(this.generatedCopy)) {
      if (!content) continue;
      text += `${sectionNames[key] || key}\n${content}\n\n`;
    }

    navigator.clipboard.writeText(text.trim()).then(() => {
      this.showStatus('전체 카피가 복사되었습니다!', 'success');
    }).catch(() => {
      this.showStatus('복사 실패', 'error');
    });
  },

  // 이미지 재생성
  async regenerateImages() {
    if (!this.generatedCopy) {
      this.showStatus('먼저 상세페이지를 생성해주세요.', 'error');
      return;
    }

    const btn = document.getElementById('btn-regenerate-images');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span> 재생성 중...';

    try {
      const productName = document.getElementById('product-name')?.value?.trim();
      const category = document.getElementById('product-category')?.value;
      const pageStyle = document.getElementById('page-style')?.value;
      const sections = this.getSelectedSections();

      const response = await fetch('/api/detail-page/generate-images', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          productName,
          category,
          pageStyle,
          sections,
          copy: this.generatedCopy
        })
      });

      const data = await response.json();

      if (!data.ok) {
        throw new Error(data.error || '이미지 재생성 실패');
      }

      this.generatedImages = data.images;
      this.displayImages(data.images);
      this.showStatus('이미지가 재생성되었습니다!', 'success');

    } catch (error) {
      console.error('[DetailPage] 이미지 재생성 오류:', error);
      this.showStatus(error.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  },

  // 개별 이미지 다운로드
  downloadImage(url, section) {
    const a = document.createElement('a');
    a.href = url;
    a.download = `detail_${section}_${Date.now()}.png`;
    a.click();
  },

  // 전체 다운로드
  async downloadAll() {
    if (!this.generatedImages || this.generatedImages.length === 0) {
      this.showStatus('다운로드할 이미지가 없습니다.', 'error');
      return;
    }

    const btn = document.getElementById('btn-download-all');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span> 다운로드 준비 중...';

    try {
      const response = await fetch('/api/detail-page/download-zip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          images: this.generatedImages,
          copy: this.generatedCopy
        })
      });

      if (!response.ok) {
        throw new Error('다운로드 실패');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `detail_page_${Date.now()}.zip`;
      a.click();
      window.URL.revokeObjectURL(url);

      this.showStatus('다운로드 완료!', 'success');

    } catch (error) {
      console.error('[DetailPage] 다운로드 오류:', error);
      this.showStatus(error.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  },

  // 상태 메시지 표시
  showStatus(message, type = 'info') {
    const statusBar = document.getElementById('status-bar');
    const statusMessage = statusBar?.querySelector('.status-message');
    const statusIcon = statusBar?.querySelector('.status-icon');

    if (!statusBar) return;

    const icons = {
      success: '✅',
      error: '❌',
      info: 'ℹ️'
    };

    if (statusIcon) statusIcon.textContent = icons[type] || icons.info;
    if (statusMessage) statusMessage.textContent = message;
    statusBar.className = `status-bar ${type}`;
    statusBar.classList.remove('hidden');

    setTimeout(() => {
      statusBar.classList.add('hidden');
    }, 4000);
  }
};

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
  DetailPageApp.init();
});
