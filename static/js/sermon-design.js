/**
 * sermon-design.js
 * 디자인 도우미 기능 (배너/현수막 생성)
 *
 * 주요 함수:
 * - initDesignHelper() - 디자인 도우미 초기화
 * - generateBanner() - 배너 이미지 생성
 * - generateBannerPrompt() - AI 프롬프트 생성
 * - loadReferenceImages(), addReferenceImage() - 참조 이미지 관리
 * - crawlImages(), bulkAddCrawledImages() - 웹사이트 크롤링
 *
 * 이 파일은 sermon.html의 디자인 도우미 관련 코드를 모듈화한 것입니다.
 */

// ===== 디자인 도우미 초기화 =====
function initDesignHelper() {
  // 모델 선택 라디오 버튼 스타일 업데이트
  const modelRadios = document.querySelectorAll('input[name="banner-model"]');
  modelRadios.forEach(radio => {
    radio.addEventListener('change', updateModelSelection);
  });
  updateModelSelection();

  // 크기 프리셋 버튼 이벤트
  const presetButtons = document.querySelectorAll('.size-preset');
  presetButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      // 모든 버튼 비활성화 스타일
      presetButtons.forEach(b => {
        b.style.background = '#f8f9fa';
        b.style.border = '1px solid #ddd';
        b.style.color = '#333';
        b.classList.remove('active');
      });
      // 클릭된 버튼 활성화 스타일
      btn.style.background = '#667eea';
      btn.style.border = '1px solid #667eea';
      btn.style.color = 'white';
      btn.classList.add('active');

      // 크기 입력 필드 업데이트
      const width = btn.dataset.width;
      const height = btn.dataset.height;
      document.getElementById('banner-width').value = width;
      document.getElementById('banner-height').value = height;
      updateSizePreview();
    });
  });

  // 크기 입력 필드 변경 이벤트
  const widthInput = document.getElementById('banner-width');
  const heightInput = document.getElementById('banner-height');
  if (widthInput) widthInput.addEventListener('input', updateSizePreview);
  if (heightInput) heightInput.addEventListener('input', updateSizePreview);

  updateSizePreview();
}

// 모델 선택 스타일 업데이트
function updateModelSelection() {
  const dalleLabel = document.getElementById('model-dalle3-label');
  const fluxLabel = document.getElementById('model-flux-label');
  const dalleRadio = document.querySelector('input[name="banner-model"][value="dalle3"]');
  const fluxRadio = document.querySelector('input[name="banner-model"][value="flux_pro"]');

  if (dalleLabel && fluxLabel) {
    dalleLabel.style.border = dalleRadio.checked ? '2px solid #667eea' : '2px solid transparent';
    dalleLabel.style.background = dalleRadio.checked ? '#f0f4ff' : '#f8f9fa';
    fluxLabel.style.border = fluxRadio.checked ? '2px solid #667eea' : '2px solid transparent';
    fluxLabel.style.background = fluxRadio.checked ? '#f0f4ff' : '#f8f9fa';
  }
}

// 크기 미리보기 업데이트
function updateSizePreview() {
  const width = parseInt(document.getElementById('banner-width').value) || 100;
  const height = parseInt(document.getElementById('banner-height').value) || 100;
  const preview = document.getElementById('banner-size-preview');

  if (preview) {
    const ratio = (width / height).toFixed(2);
    let type = '정사각형';
    if (width > height * 1.2) type = '가로형';
    else if (height > width * 1.2) type = '세로형';
    preview.textContent = `비율: ${ratio}:1 (${type})`;
  }
}

// cm를 AI 이미지 비율로 변환
function cmToAspectRatio(widthCm, heightCm) {
  const ratio = widthCm / heightCm;

  // DALL-E 3 지원 크기로 매핑
  if (ratio >= 1.5) {
    return { layout: 'horizontal', dalle_size: '1792x1024', flux_aspect: '16:9' };
  } else if (ratio <= 0.67) {
    return { layout: 'vertical', dalle_size: '1024x1792', flux_aspect: '9:16' };
  } else {
    return { layout: 'square', dalle_size: '1024x1024', flux_aspect: '1:1' };
  }
}

// 고급 옵션 토글
function toggleAdvancedOptions() {
  const options = document.getElementById('advanced-options');
  const arrow = document.getElementById('advanced-options-arrow');
  if (options && arrow) {
    const isHidden = options.style.display === 'none';
    options.style.display = isHidden ? 'block' : 'none';
    arrow.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
  }
}

// AI로 프롬프트 생성
async function generateBannerPrompt() {
  const template = document.getElementById('banner-template').value;
  const eventName = document.getElementById('banner-event-name').value;
  const theme = document.getElementById('banner-theme').value;
  const customPromptTextarea = document.getElementById('banner-custom-prompt');

  customPromptTextarea.value = '프롬프트 생성 중...';

  try {
    const response = await fetch('/api/banner/generate-prompt', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        template: template,
        event_name: eventName,
        theme: theme
      })
    });

    const data = await response.json();
    if (data.ok) {
      customPromptTextarea.value = data.prompt;
    } else {
      customPromptTextarea.value = '';
      alert('프롬프트 생성 실패: ' + data.error);
    }
  } catch (err) {
    customPromptTextarea.value = '';
    alert('네트워크 오류: ' + err.message);
  }
}

// 현수막 이미지 생성
async function generateBanner() {
  const model = document.querySelector('input[name="banner-model"]:checked').value;
  const template = document.getElementById('banner-template').value;

  // cm 기반 크기에서 레이아웃 결정
  const widthCm = parseInt(document.getElementById('banner-width').value) || 500;
  const heightCm = parseInt(document.getElementById('banner-height').value) || 90;
  const sizeConfig = cmToAspectRatio(widthCm, heightCm);
  const layout = sizeConfig.layout;

  const eventName = document.getElementById('banner-event-name').value;
  const churchName = document.getElementById('banner-church-name').value;
  const schedule = document.getElementById('banner-schedule').value;
  const speaker = document.getElementById('banner-speaker').value;
  const theme = document.getElementById('banner-theme').value;
  const customPrompt = document.getElementById('banner-custom-prompt').value;
  const addText = document.getElementById('banner-add-text').checked;
  const fontId = document.getElementById('banner-font').value;

  // UI 업데이트
  const btnGenerate = document.getElementById('btn-generate-banner');
  const loadingDiv = document.getElementById('banner-loading');
  const placeholder = document.getElementById('banner-placeholder');
  const resultDiv = document.getElementById('banner-result');

  btnGenerate.disabled = true;
  btnGenerate.innerHTML = '⏳ 생성 중...';
  loadingDiv.style.display = 'block';
  placeholder.style.display = 'none';
  resultDiv.style.display = 'none';

  try {
    // 텍스트 오버레이 포함 API 사용
    const response = await fetch('/api/banner/generate-with-text', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        model: model,
        template: template,
        layout: layout,
        width_cm: widthCm,
        height_cm: heightCm,
        event_name: eventName,
        church_name: churchName,
        schedule: schedule,
        speaker: speaker,
        theme: theme,
        custom_prompt: customPrompt,
        add_text: addText,
        font_id: fontId
      })
    });

    const data = await response.json();

    if (data.ok) {
      // 결과 표시
      const bannerImage = document.getElementById('banner-image');
      const downloadLink = document.getElementById('banner-download-link');

      bannerImage.src = data.image_url;

      // Base64 이미지인 경우 다운로드 링크 처리
      if (data.image_url.startsWith('data:')) {
        downloadLink.href = data.image_url;
      } else {
        downloadLink.href = data.image_url;
      }

      // 정보 업데이트
      document.getElementById('banner-info-model').textContent = data.model;
      document.getElementById('banner-info-template').textContent = data.template;
      // 크기를 cm로 표시
      const layoutNames = { horizontal: '가로형', vertical: '세로형', square: '정사각형' };
      const layoutName = layoutNames[layout] || layout;
      document.getElementById('banner-info-layout').textContent = `${widthCm} x ${heightCm} cm (${layoutName})`;
      document.getElementById('banner-info-text').textContent = data.text_added ? '추가됨' : '없음';
      document.getElementById('banner-info-font').textContent = data.font || '-';

      resultDiv.style.display = 'block';
    } else {
      alert('이미지 생성 실패: ' + data.error);
      placeholder.style.display = 'block';
    }
  } catch (err) {
    alert('네트워크 오류: ' + err.message);
    placeholder.style.display = 'block';
  } finally {
    btnGenerate.disabled = false;
    btnGenerate.innerHTML = '🎨 배경 이미지 생성';
    loadingDiv.style.display = 'none';
  }
}

// 다시 생성
function regenerateBanner() {
  generateBanner();
}

// ===== 참조 이미지 관리 =====

// 참조 이미지 미리보기
function previewReferenceImage() {
  const url = document.getElementById('ref-image-url').value.trim();
  const previewContainer = document.getElementById('ref-preview-container');
  const previewImage = document.getElementById('ref-preview-image');

  if (!url) {
    alert('이미지 URL을 입력해주세요.');
    return;
  }

  previewImage.src = url;
  previewImage.onerror = () => {
    previewContainer.style.display = 'none';
    alert('이미지를 불러올 수 없습니다. URL을 확인해주세요.');
  };
  previewImage.onload = () => {
    previewContainer.style.display = 'block';
  };
}

// 참조 이미지 추가
async function addReferenceImage() {
  const url = document.getElementById('ref-image-url').value.trim();
  const templateType = document.getElementById('ref-template-type').value;
  const styleTags = document.getElementById('ref-style-tags').value.trim();
  const description = document.getElementById('ref-description').value.trim();

  if (!url) {
    alert('이미지 URL을 입력해주세요.');
    return;
  }

  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    alert('올바른 URL 형식이 아닙니다. (http:// 또는 https://로 시작)');
    return;
  }

  try {
    const response = await fetch('/api/banner/references', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        image_url: url,
        template_type: templateType,
        style_tags: styleTags,
        description: description
      })
    });

    const data = await response.json();

    if (data.ok) {
      alert('참조 이미지가 추가되었습니다!');
      // 입력 필드 초기화
      document.getElementById('ref-image-url').value = '';
      document.getElementById('ref-style-tags').value = '';
      document.getElementById('ref-description').value = '';
      document.getElementById('ref-preview-container').style.display = 'none';
      // 목록 새로고침
      loadReferenceImages();
    } else {
      alert('추가 실패: ' + data.error);
    }
  } catch (err) {
    alert('네트워크 오류: ' + err.message);
  }
}

// 참조 이미지 목록 로드
async function loadReferenceImages() {
  try {
    const response = await fetch('/api/banner/references');
    const data = await response.json();

    const listContainer = document.getElementById('ref-images-list');
    const countBadge = document.getElementById('ref-count-badge');

    if (data.ok && data.references.length > 0) {
      countBadge.textContent = data.count + '개';

      const templateNames = {
        general: '일반', revival: '부흥회', christmas: '성탄절',
        easter: '부활절', thanksgiving: '추수감사절', new_year: '신년/송년',
        special_service: '특별집회', bible_school: '성경학교',
        baptism: '세례/침례', ordination: '임직/취임', mission: '선교/전도'
      };

      let html = '<div style="display: flex; flex-direction: column; gap: .5rem;">';

      data.references.forEach(ref => {
        const templateName = templateNames[ref.template_type] || ref.template_type;
        const tags = ref.style_tags ? ref.style_tags.split(',').slice(0, 3).join(', ') : '';
        const colors = ref.color_palette ? ref.color_palette.split(',').slice(0, 3) : [];

        html += `
          <div style="display: flex; gap: .75rem; padding: .75rem; background: #f8f9fa; border-radius: 8px; align-items: center;">
            <img src="${ref.image_url}" style="width: 80px; height: 50px; object-fit: cover; border-radius: 4px; cursor: pointer;" onclick="window.open('${ref.image_url}', '_blank')" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22><rect fill=%22%23ddd%22 width=%22100%22 height=%22100%22/><text fill=%22%23999%22 x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22>No Image</text></svg>'">
            <div style="flex: 1; min-width: 0;">
              <div style="font-weight: 600; font-size: .85rem; color: #333;">${templateName}</div>
              ${tags ? `<div style="font-size: .75rem; color: #666; margin-top: .2rem;">${tags}</div>` : ''}
              ${colors.length > 0 ? `
                <div style="display: flex; gap: .2rem; margin-top: .3rem;">
                  ${colors.map(c => `<span style="width: 16px; height: 16px; border-radius: 3px; background: ${c}; border: 1px solid #ddd;"></span>`).join('')}
                </div>
              ` : ''}
            </div>
            <div style="display: flex; flex-direction: column; gap: .3rem;">
              <div style="font-size: .7rem; color: #888;">품질: ${ref.quality_score}/10</div>
              <button onclick="deleteReferenceImage(${ref.id})" style="padding: .3rem .5rem; background: #fee2e2; color: #dc2626; border: none; border-radius: 4px; cursor: pointer; font-size: .7rem;">삭제</button>
            </div>
          </div>
        `;
      });

      html += '</div>';
      listContainer.innerHTML = html;
    } else {
      countBadge.textContent = '0개';
      listContainer.innerHTML = `
        <div style="text-align: center; color: #888; padding: 2rem; font-size: .85rem;">
          등록된 참조 이미지가 없습니다.<br>
          좋은 현수막 이미지 URL을 추가해주세요.
        </div>
      `;
    }
  } catch (err) {
    console.error('참조 이미지 로드 실패:', err);
  }
}

// 참조 이미지 삭제
async function deleteReferenceImage(refId) {
  if (!confirm('이 참조 이미지를 삭제하시겠습니까?')) {
    return;
  }

  try {
    const response = await fetch(`/api/banner/references/${refId}`, {
      method: 'DELETE'
    });

    const data = await response.json();

    if (data.ok) {
      loadReferenceImages();
    } else {
      alert('삭제 실패: ' + data.error);
    }
  } catch (err) {
    alert('네트워크 오류: ' + err.message);
  }
}

// ===== 웹사이트 크롤링 =====

// 크롤링된 이미지 데이터 저장
let crawledImages = [];

// 웹사이트에서 이미지 크롤링
async function crawlImages() {
  const url = document.getElementById('crawl-url').value.trim();
  if (!url) {
    alert('웹사이트 URL을 입력해주세요.');
    return;
  }

  const btnCrawl = document.getElementById('btn-crawl');
  const loadingDiv = document.getElementById('crawl-loading');
  const resultDiv = document.getElementById('crawl-result');

  btnCrawl.disabled = true;
  btnCrawl.textContent = '수집 중...';
  loadingDiv.style.display = 'block';
  resultDiv.style.display = 'none';

  try {
    const response = await fetch('/api/banner/crawl', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ url: url })
    });

    const data = await response.json();

    if (data.ok && data.images.length > 0) {
      crawledImages = data.images;
      document.getElementById('crawl-count').textContent = `${data.count}개 이미지 발견`;

      // 이미지 그리드 표시
      const imagesContainer = document.getElementById('crawl-images');
      let html = '';

      data.images.forEach((img, index) => {
        html += `
          <div class="crawl-image-item" style="position: relative; cursor: pointer;" onclick="toggleCrawlImage(${index})">
            <img src="${img.url}" style="width: 100%; height: 80px; object-fit: cover; border-radius: 4px; border: 2px solid transparent;"
                 id="crawl-img-${index}"
                 onerror="this.parentElement.style.display='none'">
            <input type="checkbox" id="crawl-check-${index}" style="position: absolute; top: 4px; right: 4px; width: 18px; height: 18px;">
          </div>
        `;
      });

      imagesContainer.innerHTML = html;
      resultDiv.style.display = 'block';
    } else if (data.ok && data.images.length === 0) {
      alert('이미지를 찾을 수 없습니다. 다른 페이지를 시도해보세요.');
    } else {
      alert('크롤링 실패: ' + data.error);
    }
  } catch (err) {
    alert('네트워크 오류: ' + err.message);
  } finally {
    btnCrawl.disabled = false;
    btnCrawl.textContent = '🔍 수집';
    loadingDiv.style.display = 'none';
  }
}

// 크롤링된 이미지 선택 토글
function toggleCrawlImage(index) {
  const checkbox = document.getElementById(`crawl-check-${index}`);
  const img = document.getElementById(`crawl-img-${index}`);

  checkbox.checked = !checkbox.checked;
  img.style.border = checkbox.checked ? '2px solid #f59e0b' : '2px solid transparent';
}

// 전체 선택/해제
function selectAllCrawled(select) {
  crawledImages.forEach((_, index) => {
    const checkbox = document.getElementById(`crawl-check-${index}`);
    const img = document.getElementById(`crawl-img-${index}`);
    if (checkbox) {
      checkbox.checked = select;
      img.style.border = select ? '2px solid #f59e0b' : '2px solid transparent';
    }
  });
}

// 선택한 이미지 일괄 등록
async function bulkAddCrawledImages() {
  const selectedImages = [];

  crawledImages.forEach((img, index) => {
    const checkbox = document.getElementById(`crawl-check-${index}`);
    if (checkbox && checkbox.checked) {
      selectedImages.push(img);
    }
  });

  if (selectedImages.length === 0) {
    alert('등록할 이미지를 선택해주세요.');
    return;
  }

  const templateType = document.getElementById('crawl-template-type').value;
  const styleTags = document.getElementById('crawl-style-tags').value.trim();

  const btnBulkAdd = document.getElementById('btn-bulk-add');
  btnBulkAdd.disabled = true;
  btnBulkAdd.textContent = `⏳ ${selectedImages.length}개 등록 중...`;

  try {
    const response = await fetch('/api/banner/references/bulk', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        images: selectedImages,
        template_type: templateType,
        style_tags: styleTags
      })
    });

    const data = await response.json();

    if (data.ok) {
      alert(`${data.added}개 이미지가 등록되었습니다!` + (data.failed > 0 ? ` (${data.failed}개 실패)` : ''));
      loadReferenceImages();

      // 크롤링 결과 초기화
      document.getElementById('crawl-result').style.display = 'none';
      crawledImages = [];
    } else {
      alert('등록 실패: ' + data.error);
    }
  } catch (err) {
    alert('네트워크 오류: ' + err.message);
  } finally {
    btnBulkAdd.disabled = false;
    btnBulkAdd.textContent = '📥 선택 이미지 등록';
  }
}

// ===== 이벤트 리스너 초기화 =====
function initDesignEvents() {
  // 디자인 도우미가 활성화될 때 참조 이미지 로드
  const designHelperContent = document.getElementById('design-helper-content');
  if (designHelperContent) {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'style') {
          const display = window.getComputedStyle(designHelperContent).display;
          if (display !== 'none') {
            loadReferenceImages();
          }
        }
      });
    });
    observer.observe(designHelperContent, { attributes: true });
  }
}

// 전역 노출
window.initDesignHelper = initDesignHelper;
window.updateModelSelection = updateModelSelection;
window.updateSizePreview = updateSizePreview;
window.cmToAspectRatio = cmToAspectRatio;
window.toggleAdvancedOptions = toggleAdvancedOptions;
window.generateBannerPrompt = generateBannerPrompt;
window.generateBanner = generateBanner;
window.regenerateBanner = regenerateBanner;
window.previewReferenceImage = previewReferenceImage;
window.addReferenceImage = addReferenceImage;
window.loadReferenceImages = loadReferenceImages;
window.deleteReferenceImage = deleteReferenceImage;
window.crawlImages = crawlImages;
window.toggleCrawlImage = toggleCrawlImage;
window.selectAllCrawled = selectAllCrawled;
window.bulkAddCrawledImages = bulkAddCrawledImages;
window.initDesignEvents = initDesignEvents;
