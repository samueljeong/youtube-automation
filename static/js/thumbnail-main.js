/**
 * 썸네일 자동 생성 - 메인 JavaScript
 */

// ===== 상태 관리 =====
const state = {
    selectedImage: null,        // 선택된 이미지 URL 또는 base64
    selectedTemplate: 'sale',   // 선택된 템플릿
    bgStyle: 'blur',            // 배경 스타일
    generatedThumbnail: null,   // 생성된 썸네일 URL
    history: []                 // 생성 히스토리
};

// ===== DOM 요소 =====
const elements = {
    // 이미지 입력
    coupangUrl: document.getElementById('coupangUrl'),
    fetchImageBtn: document.getElementById('fetchImageBtn'),
    uploadArea: document.getElementById('uploadArea'),
    imageUpload: document.getElementById('imageUpload'),
    fetchedImages: document.getElementById('fetchedImages'),
    imageSelectGrid: document.getElementById('imageSelectGrid'),

    // 텍스트 입력
    mainText: document.getElementById('mainText'),
    priceText: document.getElementById('priceText'),
    showOriginalPrice: document.getElementById('showOriginalPrice'),
    originalPrice: document.getElementById('originalPrice'),
    tag1: document.getElementById('tag1'),
    tag2: document.getElementById('tag2'),
    tag3: document.getElementById('tag3'),

    // 스타일 설정
    fontSelect: document.getElementById('fontSelect'),
    bgColor: document.getElementById('bgColor'),
    colorPickerGroup: document.getElementById('colorPickerGroup'),

    // 미리보기 & 결과
    previewFrame: document.getElementById('previewFrame'),
    resultActions: document.getElementById('resultActions'),
    generateBtn: document.getElementById('generateBtn'),
    downloadBtn: document.getElementById('downloadBtn'),
    regenerateBtn: document.getElementById('regenerateBtn'),
    historyGrid: document.getElementById('historyGrid')
};

// ===== 초기화 =====
function init() {
    bindEvents();
    loadHistory();
}

// ===== 이벤트 바인딩 =====
function bindEvents() {
    // 쿠팡 URL 불러오기
    elements.fetchImageBtn.addEventListener('click', fetchCoupangImages);
    elements.coupangUrl.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') fetchCoupangImages();
    });

    // 이미지 업로드
    elements.uploadArea.addEventListener('click', () => elements.imageUpload.click());
    elements.imageUpload.addEventListener('change', handleImageUpload);

    // 드래그 앤 드롭
    elements.uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        elements.uploadArea.style.borderColor = 'var(--primary)';
    });
    elements.uploadArea.addEventListener('dragleave', () => {
        elements.uploadArea.style.borderColor = '';
    });
    elements.uploadArea.addEventListener('drop', handleImageDrop);

    // 원가 표시 토글
    elements.showOriginalPrice.addEventListener('change', (e) => {
        elements.originalPrice.style.display = e.target.checked ? 'block' : 'none';
    });

    // 템플릿 선택
    document.querySelectorAll('.template-card').forEach(card => {
        card.addEventListener('click', () => selectTemplate(card));
    });

    // 배경 스타일 선택
    document.querySelectorAll('.radio-card').forEach(card => {
        card.addEventListener('click', () => selectBgStyle(card));
    });

    // 생성 버튼
    elements.generateBtn.addEventListener('click', generateThumbnail);
    elements.downloadBtn.addEventListener('click', downloadThumbnail);
    elements.regenerateBtn.addEventListener('click', generateThumbnail);
}

// ===== 쿠팡 이미지 불러오기 =====
async function fetchCoupangImages() {
    const url = elements.coupangUrl.value.trim();
    if (!url) {
        alert('쿠팡 상품 URL을 입력해주세요.');
        return;
    }

    if (!url.includes('coupang.com')) {
        alert('쿠팡 상품 링크만 입력해주세요.');
        return;
    }

    elements.fetchImageBtn.disabled = true;
    elements.fetchImageBtn.textContent = '불러오는 중...';

    try {
        const response = await fetch('/api/shorts/fetch-coupang', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const data = await response.json();

        if (data.ok && data.product) {
            displayFetchedImages(data.product);

            // 상품명 자동 입력 (짧게)
            const shortName = data.product.name.slice(0, 20);
            elements.mainText.value = shortName;

            // 가격 자동 입력
            if (data.product.price) {
                elements.priceText.value = data.product.price;
            }
        } else {
            alert('상품 정보를 불러오지 못했습니다: ' + (data.error || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('Fetch error:', error);
        alert('상품 정보 불러오기 실패: ' + error.message);
    } finally {
        elements.fetchImageBtn.disabled = false;
        elements.fetchImageBtn.textContent = '불러오기';
    }
}

// ===== 불러온 이미지 표시 =====
function displayFetchedImages(product) {
    elements.fetchedImages.style.display = 'block';
    elements.imageSelectGrid.innerHTML = '';

    const images = product.images || [];
    if (images.length === 0 && product.thumbnail) {
        images.push(product.thumbnail);
    }

    images.forEach((imgUrl, index) => {
        const item = document.createElement('div');
        item.className = 'image-select-item' + (index === 0 ? ' selected' : '');
        item.innerHTML = `<img src="${imgUrl}" alt="상품 이미지 ${index + 1}">`;

        item.addEventListener('click', () => {
            document.querySelectorAll('.image-select-item').forEach(el => el.classList.remove('selected'));
            item.classList.add('selected');
            state.selectedImage = imgUrl;
            updateUploadPreview(imgUrl);
        });

        elements.imageSelectGrid.appendChild(item);

        // 첫 번째 이미지 자동 선택
        if (index === 0) {
            state.selectedImage = imgUrl;
            updateUploadPreview(imgUrl);
        }
    });
}

// ===== 이미지 업로드 처리 =====
function handleImageUpload(e) {
    const file = e.target.files[0];
    if (file) {
        processImageFile(file);
    }
}

function handleImageDrop(e) {
    e.preventDefault();
    elements.uploadArea.style.borderColor = '';

    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
        processImageFile(file);
    }
}

function processImageFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        state.selectedImage = e.target.result;
        updateUploadPreview(e.target.result);
    };
    reader.readAsDataURL(file);
}

function updateUploadPreview(src) {
    elements.uploadArea.classList.add('has-image');
    elements.uploadArea.innerHTML = `<img src="${src}" alt="선택된 이미지">`;
}

// ===== 템플릿 선택 =====
function selectTemplate(card) {
    document.querySelectorAll('.template-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    state.selectedTemplate = card.dataset.template;
}

// ===== 배경 스타일 선택 =====
function selectBgStyle(card) {
    document.querySelectorAll('.radio-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    state.bgStyle = card.dataset.bg;

    // 단색 선택시 색상 선택기 표시
    elements.colorPickerGroup.style.display = state.bgStyle === 'solid' ? 'block' : 'none';
}

// ===== 썸네일 생성 =====
async function generateThumbnail() {
    if (!state.selectedImage) {
        alert('이미지를 먼저 선택해주세요.');
        return;
    }

    const mainText = elements.mainText.value.trim();
    if (!mainText) {
        alert('메인 텍스트를 입력해주세요.');
        return;
    }

    elements.generateBtn.disabled = true;
    elements.generateBtn.textContent = '생성 중...';

    try {
        const requestData = {
            image: state.selectedImage,
            mainText: mainText,
            price: elements.priceText.value.trim(),
            originalPrice: elements.showOriginalPrice.checked ? elements.originalPrice.value.trim() : null,
            tags: [
                elements.tag1.value.trim(),
                elements.tag2.value.trim(),
                elements.tag3.value.trim()
            ].filter(t => t),
            template: state.selectedTemplate,
            font: elements.fontSelect.value,
            bgStyle: state.bgStyle,
            bgColor: elements.bgColor.value
        };

        const response = await fetch('/api/thumbnail/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        const data = await response.json();

        if (data.ok && data.thumbnailUrl) {
            state.generatedThumbnail = data.thumbnailUrl;
            displayGeneratedThumbnail(data.thumbnailUrl);
            addToHistory(data.thumbnailUrl);
        } else {
            alert('썸네일 생성 실패: ' + (data.error || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('Generate error:', error);
        alert('썸네일 생성 실패: ' + error.message);
    } finally {
        elements.generateBtn.disabled = false;
        elements.generateBtn.textContent = '🎨 썸네일 생성하기';
    }
}

// ===== 생성된 썸네일 표시 =====
function displayGeneratedThumbnail(url) {
    elements.previewFrame.innerHTML = `<img src="${url}" alt="생성된 썸네일">`;
    elements.resultActions.style.display = 'flex';
}

// ===== 썸네일 다운로드 =====
function downloadThumbnail() {
    if (!state.generatedThumbnail) return;

    const link = document.createElement('a');
    link.href = state.generatedThumbnail;
    link.download = `thumbnail_${Date.now()}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// ===== 히스토리 관리 =====
function addToHistory(url) {
    state.history.unshift(url);
    if (state.history.length > 9) {
        state.history.pop();
    }
    saveHistory();
    renderHistory();
}

function saveHistory() {
    try {
        localStorage.setItem('thumbnail_history', JSON.stringify(state.history));
    } catch (e) {
        console.warn('Failed to save history:', e);
    }
}

function loadHistory() {
    try {
        const saved = localStorage.getItem('thumbnail_history');
        if (saved) {
            state.history = JSON.parse(saved);
            renderHistory();
        }
    } catch (e) {
        console.warn('Failed to load history:', e);
    }
}

function renderHistory() {
    if (state.history.length === 0) {
        elements.historyGrid.innerHTML = '<div class="history-empty">아직 생성된 썸네일이 없습니다</div>';
        return;
    }

    elements.historyGrid.innerHTML = state.history.map(url => `
        <div class="history-item" onclick="loadHistoryItem('${url}')">
            <img src="${url}" alt="썸네일">
        </div>
    `).join('');
}

function loadHistoryItem(url) {
    state.generatedThumbnail = url;
    displayGeneratedThumbnail(url);
}

// ===== 초기화 실행 =====
document.addEventListener('DOMContentLoaded', init);

// 전역 함수 노출
window.loadHistoryItem = loadHistoryItem;
