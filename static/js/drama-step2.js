/**
 * Drama Lab - Step2 이미지 생성 모듈
 * 화면 기준 Step2: 이미지 생성 (캐릭터 분석 → 인물 이미지 → 씬 이미지)
 */

// ===== 이미지 생성 관련 변수 =====
let step2GeneratedImages = JSON.parse(localStorage.getItem('_drama-step4-images') || '[]');
let step2Characters = JSON.parse(localStorage.getItem('_drama-step4-characters') || '[]');
let step2CharacterImages = JSON.parse(localStorage.getItem('_drama-step4-character-images') || '{}');
let step2Scenes = JSON.parse(localStorage.getItem('_drama-step4-scenes') || '[]');
let step2ImageProvider = 'gemini';  // 기본: Gemini (OpenRouter)
let isFullAutoMode = false;  // 대본→영상 전체 자동화 모드 플래그

// ===== 이미지 모델 선택 =====
function initImageProviderButtons() {
  document.querySelectorAll('.step4-image-provider').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.step4-image-provider').forEach(b => {
        b.classList.remove('selected');
        b.style.border = '2px solid #ddd';
        b.style.background = 'white';
      });
      btn.classList.add('selected');
      btn.style.border = '2px solid #10b981';
      btn.style.background = 'rgba(16,185,129,0.2)';

      step2ImageProvider = btn.dataset.provider;

      // 버튼 텍스트 업데이트
      const btnGenerateImage = document.getElementById('btn-generate-image');
      if (btnGenerateImage) {
        const modelName = step2ImageProvider === 'gemini' ? 'Gemini' : (step2ImageProvider === 'flux' ? 'FLUX.1 Pro' : 'DALL-E 3');
        btnGenerateImage.textContent = `🖼️ 씬 이미지 생성 (${modelName})`;
      }
    });
  });
}

// ===== Step2 컨테이너 표시 =====
function updateStep2Visibility() {
  const step2Container = document.getElementById('step4-container');
  const step1Result = document.getElementById('step3-result')?.value || '';
  if (step2Container) {
    step2Container.style.display = step1Result.trim() ? 'block' : 'none';
  }
}

// ===== 1단계: 등장인물 분석 =====
async function analyzeCharacters() {
  const step1Result = document.getElementById('step3-result')?.value || '';
  if (!step1Result.trim()) {
    alert('먼저 Step1 대본 완성을 실행해주세요.');
    return;
  }

  const btn = document.getElementById('btn-analyze-characters');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ 분석 중...';
  }

  showStatus('🔍 대본에서 등장인물 분석 중...');
  showLoadingOverlay();

  try {
    const response = await fetch('/api/drama/analyze-characters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script: step1Result })
    });

    const data = await response.json();

    if (data.ok) {
      step2Characters = data.characters || [];
      step2Scenes = data.scenes || [];
      localStorage.setItem('_drama-step4-characters', JSON.stringify(step2Characters));
      localStorage.setItem('_drama-step4-scenes', JSON.stringify(step2Scenes));

      renderCharactersList();
      updateCharacterSelect();
      updateSceneSelect();
      updateSceneCharacterCheckboxes();

      showStatus(`✅ ${step2Characters.length}명의 등장인물, ${step2Scenes.length}개의 씬 분석 완료!`);
    } else {
      alert(`오류: ${data.error}`);
      showStatus('❌ 분석 실패');
    }
  } catch (err) {
    alert(`네트워크 오류: ${err.message}`);
    showStatus('❌ 분석 오류');
  } finally {
    hideLoadingOverlay();
    setTimeout(hideStatus, 3000);
    if (btn) {
      btn.disabled = false;
      btn.textContent = '🔍 대본에서 인물 추출';
    }
  }
}

// ===== 등장인물 목록 렌더링 =====
function renderCharactersList() {
  const container = document.getElementById('step4-characters-list');
  if (!container) return;

  if (step2Characters.length === 0) {
    container.innerHTML = '<div style="color: #999; text-align: center; font-size: .85rem;">대본을 분석하면 등장인물이 여기에 표시됩니다</div>';
    return;
  }

  container.innerHTML = step2Characters.map((char, idx) => `
    <div style="background: #f8f9fa; padding: .5rem; border-radius: 6px; margin-bottom: .5rem; border-left: 4px solid #27ae60;">
      <div style="font-weight: 600; color: #333; margin-bottom: .25rem;">
        👤 ${char.name}
        ${step2CharacterImages[char.name] ? '<span style="color: #27ae60; font-size: .8rem;">✅ 이미지 생성됨</span>' : ''}
      </div>
      <div style="font-size: .85rem; color: #666;">${char.description}</div>
      <div style="font-size: .8rem; color: #888; margin-top: .25rem;">
        <strong>프롬프트:</strong> ${char.imagePrompt || '(생성 전)'}
      </div>
    </div>
  `).join('');
}

// ===== 인물 선택 드롭다운 업데이트 =====
function updateCharacterSelect() {
  const select = document.getElementById('step4-character-select');
  if (!select) return;

  select.innerHTML = '<option value="">-- 인물 선택 --</option>' +
    step2Characters.map((char, idx) => `<option value="${idx}">${char.name}</option>`).join('');
}

// ===== 씬 선택 드롭다운 업데이트 =====
function updateSceneSelect() {
  const select = document.getElementById('step4-scene-select');
  if (!select) return;

  select.innerHTML = '<option value="">-- 씬 선택 --</option>' +
    step2Scenes.map((scene, idx) => `<option value="${idx}">씬 ${idx + 1}: ${scene.title || scene.location || '장면'}</option>`).join('');
}

// ===== 씬에 등장하는 인물 체크박스 업데이트 =====
function updateSceneCharacterCheckboxes() {
  const container = document.getElementById('step4-scene-characters');
  if (!container) return;

  if (step2Characters.length === 0) {
    container.innerHTML = '<span style="color: rgba(255,255,255,0.6); font-size: .85rem;">인물 분석 후 선택 가능</span>';
    return;
  }

  container.innerHTML = step2Characters.map((char, idx) => `
    <label style="display: flex; align-items: center; gap: .25rem; background: rgba(255,255,255,0.9); padding: .3rem .5rem; border-radius: 4px; cursor: pointer; font-size: .85rem;">
      <input type="checkbox" class="scene-character-checkbox" data-name="${char.name}" checked>
      ${char.name}
    </label>
  `).join('');
}

// ===== 2단계: 인물 이미지 생성 =====
async function generateCharacterImage() {
  const selectEl = document.getElementById('step4-character-select');
  const idx = parseInt(selectEl?.value);

  if (isNaN(idx) || !step2Characters[idx]) {
    alert('인물을 선택해주세요.');
    return;
  }

  const characterPrompt = document.getElementById('step4-character-prompt')?.value || step2Characters[idx].imagePrompt;
  if (!characterPrompt?.trim()) {
    alert('인물 프롬프트가 없습니다.');
    return;
  }

  const btn = document.getElementById('btn-generate-character-image');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ 생성 중...';
  }

  showStatus(`🖼️ ${step2Characters[idx].name} 이미지 생성 중...`);
  showLoadingOverlay();

  try {
    const response = await fetch('/api/drama/generate-image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: characterPrompt + ', medium shot, upper body portrait, high quality, detailed face, professional lighting, 16:9 aspect ratio',
        size: '1792x1024',  // YouTube 16:9 비율
        imageProvider: step2ImageProvider
      })
    });

    const data = await response.json();

    if (data.ok) {
      step2CharacterImages[step2Characters[idx].name] = {
        url: data.imageUrl,
        prompt: characterPrompt,
        createdAt: new Date().toISOString()
      };

      // base64가 아닌 외부 URL만 localStorage에 저장
      if (!data.imageUrl.startsWith('data:')) {
        try {
          localStorage.setItem('_drama-step4-character-images', JSON.stringify(step2CharacterImages));
          if (typeof saveToFirebase === 'function') {
            saveToFirebase('_drama-step4-character-images', JSON.stringify(step2CharacterImages));
          }
        } catch (e) {
          console.warn('localStorage 저장 실패 (용량 초과):', e.message);
        }
      }

      renderCharacterImages();
      renderCharactersList();

      // 💰 Step2 캐릭터 이미지 비용 추가
      if (data.cost && typeof window.addCost === 'function') {
        window.addCost('step2', data.cost);
      }

      showStatus(`✅ ${step2Characters[idx].name} 이미지 생성 완료!`);
    } else {
      alert(`오류: ${data.error}`);
      showStatus('❌ 이미지 생성 실패');
    }
  } catch (err) {
    alert(`네트워크 오류: ${err.message}`);
    showStatus('❌ 이미지 생성 오류');
  } finally {
    hideLoadingOverlay();
    setTimeout(hideStatus, 3000);
    if (btn) {
      btn.disabled = false;
      btn.textContent = '🖼️ 인물 이미지 생성';
    }
  }
}

// ===== 인물 이미지 렌더링 =====
function renderCharacterImages() {
  const container = document.getElementById('step4-character-images');
  if (!container) return;

  const images = Object.entries(step2CharacterImages);
  if (images.length === 0) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML = images.map(([name, data]) => `
    <div style="background: #f8f9fa; padding: .5rem; border-radius: 6px; text-align: center;">
      <img src="${data.url}" alt="${name}" style="width: 100%; max-width: 150px; border-radius: 6px; cursor: pointer;" onclick="window.open('${data.url}', '_blank')">
      <div style="font-size: .8rem; font-weight: 600; margin-top: .25rem;">${name}</div>
      <button onclick="downloadImage('${data.url}')" style="margin-top: .25rem; padding: .2rem .4rem; font-size: .7rem; cursor: pointer;">💾 저장</button>
    </div>
  `).join('');
}

// ===== 3단계: 씬 프롬프트 생성 =====
async function generateScenePrompt() {
  const sceneSelect = document.getElementById('step4-scene-select');
  const idx = parseInt(sceneSelect?.value);

  if (isNaN(idx) || !step2Scenes[idx]) {
    alert('씬을 선택해주세요.');
    return;
  }

  // 선택된 인물들 가져오기
  const selectedCharacters = getSelectedCharactersForScene();

  const btn = document.getElementById('btn-generate-scene-prompt');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ 생성 중...';
  }

  showStatus('📝 씬 프롬프트 생성 중...');
  showLoadingOverlay();

  try {
    const response = await fetch('/api/drama/generate-scene-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scene: step2Scenes[idx],
        characters: selectedCharacters,
        backgroundPrompt: document.getElementById('step4-background-prompt')?.value || ''
      })
    });

    const data = await response.json();

    if (data.ok) {
      document.getElementById('step4-combined-prompt').value = data.combinedPrompt || '';
      if (data.backgroundPrompt) {
        document.getElementById('step4-background-prompt').value = data.backgroundPrompt;
      }
      showStatus('✅ 씬 프롬프트 생성 완료!');
    } else {
      alert(`오류: ${data.error}`);
      showStatus('❌ 프롬프트 생성 실패');
    }
  } catch (err) {
    alert(`네트워크 오류: ${err.message}`);
    showStatus('❌ 프롬프트 생성 오류');
  } finally {
    hideLoadingOverlay();
    setTimeout(hideStatus, 3000);
    if (btn) {
      btn.disabled = false;
      btn.textContent = '📝 씬 프롬프트';
    }
  }
}

// ===== 선택된 인물들 가져오기 =====
function getSelectedCharactersForScene() {
  const selectedCharacters = [];
  document.querySelectorAll('.scene-character-checkbox:checked').forEach(cb => {
    const name = cb.dataset.name;
    if (step2CharacterImages[name]) {
      selectedCharacters.push({
        name: name,
        prompt: step2CharacterImages[name].prompt
      });
    } else {
      const char = step2Characters.find(c => c.name === name);
      if (char) {
        selectedCharacters.push({
          name: name,
          prompt: char.imagePrompt
        });
      }
    }
  });
  return selectedCharacters;
}

// ===== 프롬프트 + 이미지 한번에 생성 =====
async function generateScenePromptAndImage() {
  const sceneSelect = document.getElementById('step4-scene-select');
  const idx = parseInt(sceneSelect?.value);

  if (isNaN(idx) || !step2Scenes[idx]) {
    alert('씬을 선택해주세요.');
    return;
  }

  const selectedCharacters = getSelectedCharactersForScene();

  const btn = document.getElementById('btn-generate-scene-all');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ 프롬프트 생성 중...';
  }

  showStatus('📝 Step2: 씬 프롬프트 생성 중...');
  showLoadingOverlay();

  try {
    // 1단계: 프롬프트 생성
    const promptResponse = await fetch('/api/drama/generate-scene-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scene: step2Scenes[idx],
        characters: selectedCharacters,
        backgroundPrompt: document.getElementById('step4-background-prompt')?.value || ''
      })
    });

    const promptData = await promptResponse.json();

    if (!promptData.ok) {
      throw new Error(promptData.error || '프롬프트 생성 실패');
    }

    document.getElementById('step4-combined-prompt').value = promptData.combinedPrompt || '';
    if (promptData.backgroundPrompt) {
      document.getElementById('step4-background-prompt').value = promptData.backgroundPrompt;
    }

    showStatus('✅ 프롬프트 완료! 🖼️ 이미지 생성 중... (약 30초)');
    if (btn) btn.textContent = '⏳ 이미지 생성 중...';

    // 2단계: 이미지 생성
    const imageSize = document.getElementById('step4-image-size')?.value || '1792x1024';
    const imageResponse = await fetch('/api/drama/generate-image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: promptData.combinedPrompt,
        size: imageSize,
        imageProvider: step2ImageProvider
      })
    });

    const imageData = await imageResponse.json();

    if (imageData.ok) {
      addImageToGrid(imageData.imageUrl, idx, imageSize, promptData.combinedPrompt, imageData.cost);
      showStatus('✅ 씬 이미지 생성 완료!');
      if (typeof updateProgressIndicator === 'function') {
        updateProgressIndicator('step4');
      }

      // 썸네일 자동 생성
      setTimeout(() => {
        if (typeof generateYouTubeThumbnail === 'function') {
          console.log('[THUMBNAIL] 이미지 생성 완료, 썸네일 자동 생성 시작...');
          generateYouTubeThumbnail();
        }
      }, 500);
    } else {
      throw new Error(imageData.error || '이미지 생성 실패');
    }
  } catch (err) {
    alert(`오류: ${err.message}`);
    showStatus('❌ 생성 실패');
  } finally {
    hideLoadingOverlay();
    setTimeout(hideStatus, 3000);
    if (btn) {
      btn.disabled = false;
      btn.textContent = '🎬 프롬프트+이미지';
    }
  }
}

// ===== 이미지 그리드에 추가 =====
function addImageToGrid(imageUrl, sceneIndex, imageSize, prompt, cost) {
  const placeholder = document.getElementById('step4-image-placeholder');
  const imageGrid = document.getElementById('step4-image-grid');
  const costInfo = document.getElementById('step4-cost-info');

  if (placeholder) placeholder.style.display = 'none';
  if (imageGrid) {
    imageGrid.style.display = 'grid';

    const sceneName = step2Scenes[sceneIndex]?.sceneName || '';
    const imageItem = document.createElement('div');
    imageItem.className = 'step4-image-item';
    imageItem.innerHTML = `
      <img src="${imageUrl}" alt="Generated scene" loading="lazy" onclick="window.open('${imageUrl}', '_blank')">
      <div class="image-caption">
        씬 ${sceneIndex + 1}: ${sceneName} | ${imageSize}
        <button onclick="downloadImage('${imageUrl}')" style="margin-left: .5rem; padding: .2rem .4rem; font-size: .7rem; cursor: pointer;">💾 저장</button>
      </div>
    `;
    imageGrid.insertBefore(imageItem, imageGrid.firstChild);

    step2GeneratedImages.unshift({
      url: imageUrl,
      prompt: prompt,
      sceneIndex: sceneIndex,
      sceneName: sceneName,
      size: imageSize,
      createdAt: new Date().toISOString()
    });

    // base64가 아닌 외부 URL만 localStorage에 저장
    if (!imageUrl.startsWith('data:')) {
      try {
        localStorage.setItem('_drama-step4-images', JSON.stringify(step2GeneratedImages.slice(0, 20)));
      } catch (e) {
        console.warn('localStorage 저장 실패 (용량 초과):', e.message);
      }
    }
  }

  if (costInfo && cost) {
    document.getElementById('step4-image-cost').textContent = '₩' + cost.toLocaleString();
    costInfo.style.display = 'block';
  }
}

// ===== 씬 이미지 생성 함수 =====
async function generateStep2Image() {
  const combinedPrompt = document.getElementById('step4-combined-prompt')?.value || '';
  if (!combinedPrompt.trim()) {
    alert('먼저 씬 프롬프트를 생성하거나 직접 입력해주세요.');
    return;
  }

  const imageSize = document.getElementById('step4-image-size')?.value || '1792x1024';
  const btnGenerateImage = document.getElementById('btn-generate-image');

  if (btnGenerateImage) {
    btnGenerateImage.disabled = true;
    btnGenerateImage.classList.add('generating');
    btnGenerateImage.textContent = '⏳ 이미지 생성 중... (약 30초)';
  }

  const modelName = step2ImageProvider === 'gemini' ? 'Gemini' : (step2ImageProvider === 'flux' ? 'FLUX.1 Pro' : 'DALL-E 3');
  showStatus(`🖼️ Step2: ${modelName} 씬 이미지 생성 중...`);
  showLoadingOverlay();

  try {
    const response = await fetch('/api/drama/generate-image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: combinedPrompt,
        size: imageSize,
        imageProvider: step2ImageProvider
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`서버 오류 (${response.status}): ${errorText.substring(0, 100)}`);
    }

    const data = await response.json();

    if (data.ok) {
      addImageToGrid(data.imageUrl, -1, imageSize, combinedPrompt, data.cost);
      showStatus('✅ 씬 이미지 생성 완료!');
      if (typeof updateProgressIndicator === 'function') {
        updateProgressIndicator('step4');
      }

      // 💰 Step2 이미지 비용 추가
      if (data.cost && typeof window.addCost === 'function') {
        window.addCost('step2', data.cost);
      }

      // 썸네일 자동 생성
      setTimeout(() => {
        if (typeof generateYouTubeThumbnail === 'function') {
          console.log('[THUMBNAIL] 씬 이미지 생성 완료, 썸네일 자동 생성 시작...');
          generateYouTubeThumbnail();
        }
      }, 500);
    } else {
      alert(`오류: ${data.error}`);
      showStatus('❌ 이미지 생성 실패');
    }
  } catch (err) {
    console.error(`[DEBUG] 이미지 생성 오류:`, err);
    alert(`오류 (${step2ImageProvider}): ${err.message}`);
    showStatus('❌ 이미지 생성 오류');
  } finally {
    hideLoadingOverlay();
    setTimeout(hideStatus, 3000);
    if (btnGenerateImage) {
      btnGenerateImage.disabled = false;
      btnGenerateImage.classList.remove('generating');
      const currentModel = step2ImageProvider === 'gemini' ? 'Gemini' : (step2ImageProvider === 'flux' ? 'FLUX.1 Pro' : 'DALL-E 3');
      btnGenerateImage.textContent = `🖼️ 씬 이미지 생성 (${currentModel})`;
    }
  }
}

// ===== 이미지 다운로드 함수 =====
function downloadImage(url) {
  const a = document.createElement('a');
  a.href = url;
  a.download = `drama-scene-${Date.now()}.png`;
  a.target = '_blank';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ===== Step2 초기화 함수 =====
function clearStep2() {
  if (!confirm('Step2의 모든 데이터(인물, 씬, 이미지)를 초기화하시겠습니까?')) return;

  step2Characters = [];
  step2CharacterImages = {};
  step2Scenes = [];
  step2GeneratedImages = [];

  localStorage.removeItem('_drama-step4-characters');
  localStorage.removeItem('_drama-step4-character-images');
  localStorage.removeItem('_drama-step4-scenes');
  localStorage.removeItem('_drama-step4-images');

  document.getElementById('step4-character-prompt').value = '';
  document.getElementById('step4-background-prompt').value = '';
  document.getElementById('step4-combined-prompt').value = '';

  renderCharactersList();
  updateCharacterSelect();
  updateSceneSelect();
  updateSceneCharacterCheckboxes();
  renderCharacterImages();

  const imageGrid = document.getElementById('step4-image-grid');
  const placeholder = document.getElementById('step4-image-placeholder');
  const costInfo = document.getElementById('step4-cost-info');

  if (imageGrid) {
    imageGrid.innerHTML = '';
    imageGrid.style.display = 'none';
  }
  if (placeholder) placeholder.style.display = 'block';
  if (costInfo) costInfo.style.display = 'none';

  showStatus('🗑️ Step2가 초기화되었습니다.');
  setTimeout(hideStatus, 2000);
}

// ===== 전체 자동 생성 기능 =====
let isAutoGenerating = false;

async function generateAllAuto(skipConfirm = false) {
  if (isAutoGenerating) {
    alert('이미 자동 생성이 진행 중입니다.');
    return;
  }

  const step1Result = document.getElementById('step3-result')?.value || '';
  if (!step1Result.trim()) {
    alert('먼저 Step1 대본 완성을 실행해주세요.');
    return;
  }

  // 자동화 모드에서는 confirm 건너뛰기
  if (!skipConfirm && !isFullAutoMode) {
    if (!confirm('전체 자동 생성을 시작하시겠습니까?\n\n1. 대본에서 인물/씬 분석\n2. 모든 인물 이미지 생성\n3. 모든 씬 배경 이미지 생성 (대본 기반 인물 자동 배치)\n\n⚠️ 많은 API 호출이 발생합니다.')) {
      return;
    }
  }

  isAutoGenerating = true;

  // 🤖 모델 상태 업데이트 - 시작
  if (typeof window.updateModelStatus === 'function') {
    window.updateModelStatus('step2', null, 'running');
  }

  const progressContainer = document.getElementById('auto-generate-progress');
  const progressBar = document.getElementById('auto-generate-progress-bar');
  const statusText = document.getElementById('auto-generate-status');
  const detailsText = document.getElementById('auto-generate-details');
  const btnGenerateAll = document.getElementById('btn-generate-all-auto');

  // Step2 상태 업데이트 - 시작
  if (typeof updateStepStatus === 'function') {
    updateStepStatus('step2', 'working', '대본 분석 중...');
  }

  if (progressContainer) progressContainer.style.display = 'block';
  if (btnGenerateAll) {
    btnGenerateAll.disabled = true;
    btnGenerateAll.textContent = '⏳ 생성 중...';
  }

  const updateProgress = (percent, status, details = '') => {
    if (progressBar) progressBar.style.width = `${percent}%`;
    if (statusText) statusText.textContent = status;
    if (detailsText) detailsText.textContent = details;
    // 사이드바 상태도 업데이트
    if (typeof updateStepStatus === 'function' && percent < 100) {
      updateStepStatus('step2', 'working', status.substring(0, 25));
    }
  };

  try {
    // 1단계: 대본 분석
    updateProgress(5, '📊 대본 분석 중...', '등장인물과 씬 정보를 추출합니다');
    showStatus('🔍 대본에서 등장인물 및 씬 분석 중...');

    const analyzeResponse = await fetch('/api/drama/analyze-characters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script: step1Result })
    });

    const analyzeData = await analyzeResponse.json();
    if (!analyzeData.ok) throw new Error(analyzeData.error || '대본 분석 실패');

    step2Characters = analyzeData.characters || [];
    step2Scenes = analyzeData.scenes || [];

    // ⭐ GPT 분석 프롬프트가 있으면 병합
    const gptPrompts = window.gptAnalyzedPrompts || JSON.parse(localStorage.getItem('_drama-gpt-prompts') || 'null');
    if (gptPrompts) {
      console.log('[Step2] GPT 분석 프롬프트 적용 중...');

      // 캐릭터 프롬프트 병합
      if (gptPrompts.characters && gptPrompts.characters.length > 0) {
        step2Characters = step2Characters.map(char => {
          const gptChar = gptPrompts.characters.find(gc =>
            gc.name === char.name ||
            gc.name.includes(char.name) ||
            char.name.includes(gc.name)
          );
          if (gptChar && gptChar.imagePrompt) {
            console.log(`[Step2] 캐릭터 "${char.name}" GPT 프롬프트 적용`);
            return {
              ...char,
              imagePrompt: gptChar.imagePrompt,
              gptDescription: gptChar.description
            };
          }
          return char;
        });
      }

      // 씬 프롬프트 병합
      if (gptPrompts.scenes && gptPrompts.scenes.length > 0) {
        step2Scenes = step2Scenes.map((scene, idx) => {
          const gptScene = gptPrompts.scenes[idx] || gptPrompts.scenes.find(gs =>
            gs.sceneNumber === (idx + 1)
          );
          if (gptScene && gptScene.backgroundPrompt) {
            console.log(`[Step2] 씬 ${idx + 1} GPT 배경 프롬프트 적용`);
            return {
              ...scene,
              backgroundPrompt: gptScene.backgroundPrompt,
              characterAction: gptScene.characterAction,
              gptDescription: gptScene.description
            };
          }
          return scene;
        });
      }

      // 시각적 스타일 저장
      if (gptPrompts.visualStyle) {
        window.gptVisualStyle = gptPrompts.visualStyle;
      }

      showStatus('✅ GPT 프롬프트가 적용되었습니다.');
    }

    localStorage.setItem('_drama-step4-characters', JSON.stringify(step2Characters));
    localStorage.setItem('_drama-step4-scenes', JSON.stringify(step2Scenes));

    renderCharactersList();
    updateCharacterSelect();
    updateSceneSelect();
    updateSceneCharacterCheckboxes();

    const gptStatus = gptPrompts ? ' (GPT 프롬프트 적용)' : '';
    updateProgress(15, `✅ 분석 완료: ${step2Characters.length}명의 인물, ${step2Scenes.length}개의 씬${gptStatus}`, '인물 이미지 생성을 시작합니다');

    // ⭐ 테스트 모드 확인 (이미지 1개만 생성)
    const isTestMode = document.getElementById('test-mode-checkbox')?.checked || false;
    if (isTestMode) {
      console.log('[TEST MODE] 테스트 모드 활성화 - 이미지 1개씩만 생성');
      showStatus('⚠️ 테스트 모드: 인물 1명, 씬 1개만 생성합니다');
    }

    // 2단계: 인물 이미지 생성
    const maxCharacters = isTestMode ? 1 : step2Characters.length;
    const maxScenes = isTestMode ? 1 : step2Scenes.length;
    const totalCharacters = maxCharacters;
    const totalScenes = maxScenes;
    const totalSteps = totalCharacters + totalScenes;
    let completedSteps = 0;

    for (let i = 0; i < maxCharacters; i++) {
      const char = step2Characters[i];
      completedSteps++;
      const percent = 15 + (completedSteps / totalSteps) * 80;
      updateProgress(percent, `👤 인물 이미지 생성 중: ${char.name} (${i + 1}/${totalCharacters})`, char.imagePrompt?.substring(0, 50) + '...');
      showStatus(`👤 ${char.name} 이미지 생성 중... (${i + 1}/${totalCharacters})`);

      try {
        // GPT 스타일이 있으면 프롬프트에 추가
        let charPrompt = char.imagePrompt || `Portrait of ${char.name}, ${char.description}, Korean drama style, professional photography, soft lighting`;
        if (window.gptVisualStyle && char.imagePrompt) {
          charPrompt = `${char.imagePrompt}, ${window.gptVisualStyle}`;
        }

        const imageResponse = await fetch('/api/drama/generate-image', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: charPrompt + ', medium shot, upper body portrait, 16:9 aspect ratio',
            size: '1792x1024',  // YouTube 16:9 비율
            imageProvider: step2ImageProvider
          })
        });

        const imageData = await imageResponse.json();
        if (imageData.ok) {
          step2CharacterImages[char.name] = {
            url: imageData.imageUrl,
            prompt: char.imagePrompt,
            createdAt: new Date().toISOString()
          };
          localStorage.setItem('_drama-step4-character-images', JSON.stringify(step2CharacterImages));
          renderCharacterImages();

          // 💰 Step2 인물 이미지 비용 추가
          if (imageData.cost && typeof window.addCost === 'function') {
            window.addCost('step2', imageData.cost);
          }
        }
      } catch (imgErr) {
        console.error(`인물 이미지 생성 실패 (${char.name}):`, imgErr);
      }

      // API 과부하 방지
      await new Promise(resolve => setTimeout(resolve, 1500));
    }

    // 3단계: 씬 배경 이미지 생성
    for (let i = 0; i < maxScenes; i++) {
      const scene = step2Scenes[i];
      completedSteps++;
      const percent = 15 + (completedSteps / totalSteps) * 80;

      const sceneCharacterNames = scene.characters || [];
      const sceneCharacters = step2Characters.filter(c => sceneCharacterNames.includes(c.name));

      updateProgress(percent, `🎬 씬 이미지 생성 중: ${scene.title || '씬 ' + (i + 1)} (${i + 1}/${totalScenes})`, `등장인물: ${sceneCharacterNames.join(', ') || '없음'}`);
      showStatus(`🎬 씬 ${i + 1} 이미지 생성 중... (${i + 1}/${totalScenes}) - 등장인물: ${sceneCharacterNames.join(', ')}`);

      try {
        const promptResponse = await fetch('/api/drama/generate-scene-prompt', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            scene: scene,
            characters: sceneCharacters.map(c => ({
              name: c.name,
              prompt: c.imagePrompt || c.description
            })),
            backgroundPrompt: scene.backgroundPrompt || '',
            visualStyle: window.gptVisualStyle || '',
            characterAction: scene.characterAction || ''
          })
        });

        const promptData = await promptResponse.json();
        if (!promptData.ok) throw new Error(promptData.error || '프롬프트 생성 실패');

        // GPT 스타일이 있으면 최종 프롬프트에 추가
        let finalPrompt = promptData.combinedPrompt;
        if (window.gptVisualStyle && !finalPrompt.includes(window.gptVisualStyle)) {
          finalPrompt = `${finalPrompt}, ${window.gptVisualStyle}`;
        }

        const imageResponse = await fetch('/api/drama/generate-image', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: finalPrompt,
            size: '1792x1024',
            imageProvider: step2ImageProvider
          })
        });

        const imageData = await imageResponse.json();
        if (imageData.ok) {
          addImageToGridForAuto(imageData.imageUrl, i, scene, sceneCharacterNames, promptData.combinedPrompt);

          // 첫 번째 씬 이미지를 썸네일로 표시
          if (i === 0 && typeof updateThumbnailPreview === 'function') {
            updateThumbnailPreview(imageData.imageUrl);
          }

          // 💰 Step2 씬 이미지 비용 추가
          if (imageData.cost && typeof window.addCost === 'function') {
            window.addCost('step2', imageData.cost);
          }
        }
      } catch (sceneErr) {
        console.error(`씬 이미지 생성 실패 (씬 ${i + 1}):`, sceneErr);
      }

      // API 과부하 방지
      await new Promise(resolve => setTimeout(resolve, 2000));
    }

    updateProgress(100, '✅ 전체 자동 생성 완료!', `인물 ${totalCharacters}명, 씬 ${totalScenes}개의 이미지가 생성되었습니다`);
    showStatus('🎉 전체 자동 생성 완료!');
    if (typeof updateProgressIndicator === 'function') {
      updateProgressIndicator('step4');
    }

    // 3초 후 진행 상황 숨기기
    setTimeout(() => {
      if (progressContainer) progressContainer.style.display = 'none';
    }, 5000);

    // 썸네일 자동 생성
    if (typeof generateYouTubeThumbnail === 'function') {
      console.log('[AUTO] 이미지 생성 완료, 썸네일 자동 생성 시작...');
      showStatus('🎨 썸네일 자동 생성 중...');
      await generateYouTubeThumbnail();
    }

    // 참고: 병렬 실행 모드에서는 TTS가 별도로 처리되므로 여기서 호출하지 않음
    // runAutoTTSAndVideo는 runStep2AndStep3InParallel에서 별도로 처리됨
    console.log('[AUTO] Step2 이미지 생성 완료 (TTS는 병렬로 처리 중)');

    // 🤖 모델 상태 업데이트 - 완료
    if (typeof window.updateModelStatus === 'function') {
      window.updateModelStatus('step2', null, 'completed');
    }

  } catch (err) {
    console.error('전체 자동 생성 오류:', err);
    updateProgress(0, `❌ 오류 발생: ${err.message}`, '다시 시도해주세요');
    showStatus(`❌ 자동 생성 오류: ${err.message}`);
    if (typeof updateStepStatus === 'function') {
      updateStepStatus('step2', 'error', err.message.substring(0, 30));
    }
    // 🤖 모델 상태 업데이트 - 에러
    if (typeof window.updateModelStatus === 'function') {
      window.updateModelStatus('step2', null, 'error');
    }
  } finally {
    isAutoGenerating = false;
    if (btnGenerateAll) {
      btnGenerateAll.disabled = false;
      btnGenerateAll.textContent = '🚀 전체 생성';
    }
  }
}

// ===== 자동 생성용 이미지 추가 =====
function addImageToGridForAuto(imageUrl, sceneIndex, scene, characterNames, prompt) {
  const placeholder = document.getElementById('step4-image-placeholder');
  const imageGrid = document.getElementById('step4-image-grid');

  if (placeholder) placeholder.style.display = 'none';
  if (imageGrid) {
    imageGrid.style.display = 'grid';

    const imageItem = document.createElement('div');
    imageItem.className = 'step4-image-item';
    imageItem.innerHTML = `
      <img src="${imageUrl}" alt="Scene ${sceneIndex + 1}" loading="lazy" onclick="window.open('${imageUrl}', '_blank')">
      <div class="image-caption">
        씬 ${sceneIndex + 1}: ${scene.title || scene.location || ''} | 등장: ${characterNames.join(', ') || '-'}
        <button onclick="downloadImage('${imageUrl}')" style="margin-left: .5rem; padding: .2rem .4rem; font-size: .7rem; cursor: pointer;">💾 저장</button>
      </div>
    `;
    imageGrid.appendChild(imageItem);

    step2GeneratedImages.push({
      url: imageUrl,
      prompt: prompt,
      sceneIndex: sceneIndex,
      sceneName: scene.title,
      characters: characterNames,
      size: '1792x1024',
      createdAt: new Date().toISOString()
    });

    if (!imageUrl.startsWith('data:')) {
      try {
        localStorage.setItem('_drama-step4-images', JSON.stringify(step2GeneratedImages.slice(-20)));
      } catch (e) {
        console.warn('localStorage 저장 실패:', e.message);
      }
    }
  }
}

// ===== 저장된 데이터 복원 =====
function restoreStep2Data() {
  renderCharactersList();
  updateCharacterSelect();
  updateSceneSelect();
  updateSceneCharacterCheckboxes();
  renderCharacterImages();

  // 이미지 복원
  if (step2GeneratedImages.length === 0) return;

  const imageGrid = document.getElementById('step4-image-grid');
  const placeholder = document.getElementById('step4-image-placeholder');

  if (imageGrid && placeholder) {
    placeholder.style.display = 'none';
    imageGrid.style.display = 'grid';

    step2GeneratedImages.forEach(img => {
      const imageItem = document.createElement('div');
      imageItem.className = 'step4-image-item';
      imageItem.innerHTML = `
        <img src="${img.url}" alt="Generated scene" loading="lazy" onclick="window.open('${img.url}', '_blank')">
        <div class="image-caption">
          ${new Date(img.createdAt).toLocaleString('ko-KR')} | ${img.size}
          <button onclick="downloadImage('${img.url}')" style="margin-left: .5rem; padding: .2rem .4rem; font-size: .7rem; cursor: pointer;">💾 저장</button>
        </div>
      `;
      imageGrid.appendChild(imageItem);
    });
  }
}

// ===== 이벤트 리스너 설정 =====
document.addEventListener('DOMContentLoaded', () => {
  // 이미지 모델 선택 버튼 초기화
  initImageProviderButtons();

  // Step1 결과 변경 감지
  const step1ResultTextarea = document.getElementById('step3-result');
  if (step1ResultTextarea) {
    setInterval(updateStep2Visibility, 1000);
  }

  // 인물 선택 시 프롬프트 표시
  document.getElementById('step4-character-select')?.addEventListener('change', function() {
    const idx = parseInt(this.value);
    const promptArea = document.getElementById('step4-character-prompt');
    if (!isNaN(idx) && step2Characters[idx] && promptArea) {
      promptArea.value = step2Characters[idx].imagePrompt || '';
    }
  });

  // 씬 선택 시 프롬프트 생성
  document.getElementById('step4-scene-select')?.addEventListener('change', function() {
    const idx = parseInt(this.value);
    if (!isNaN(idx) && step2Scenes[idx]) {
      document.getElementById('step4-background-prompt').value = step2Scenes[idx].backgroundPrompt || '';
    }
  });

  // 버튼 이벤트 바인딩
  document.getElementById('btn-analyze-characters')?.addEventListener('click', analyzeCharacters);
  document.getElementById('btn-generate-character-image')?.addEventListener('click', generateCharacterImage);
  document.getElementById('btn-generate-scene-prompt')?.addEventListener('click', generateScenePrompt);
  document.getElementById('btn-generate-scene-all')?.addEventListener('click', generateScenePromptAndImage);
  document.getElementById('btn-generate-image')?.addEventListener('click', generateStep2Image);
  document.getElementById('btn-clear-step4')?.addEventListener('click', clearStep2);
  document.getElementById('btn-generate-all-auto')?.addEventListener('click', generateAllAuto);

  // 저장된 데이터 복원
  setTimeout(restoreStep2Data, 500);

  console.log('[DramaStep2] 초기화 완료');
});

// ===== 전역 노출 =====
window.DramaStep2 = {
  analyzeCharacters,
  generateCharacterImage,
  generateScenePrompt,
  generateScenePromptAndImage,
  generateImage: generateStep2Image,
  generateAllAuto,
  clearStep2,
  downloadImage,
  get generatedImages() { return step2GeneratedImages; },
  get characters() { return step2Characters; },
  get characterImages() { return step2CharacterImages; },
  get scenes() { return step2Scenes; },
  get imageProvider() { return step2ImageProvider; },
  set imageProvider(v) { step2ImageProvider = v; },
  get isFullAutoMode() { return isFullAutoMode; },
  set isFullAutoMode(v) { isFullAutoMode = v; }
};

// 기존 코드 호환
window.analyzeCharacters = analyzeCharacters;
window.generateCharacterImage = generateCharacterImage;
window.generateScenePrompt = generateScenePrompt;
window.generateStep4Image = generateStep2Image;
window.generateAllAuto = generateAllAuto;
window.downloadImage = downloadImage;
window.step4GeneratedImages = step2GeneratedImages;
window.step4Characters = step2Characters;
window.step4CharacterImages = step2CharacterImages;
window.step4Scenes = step2Scenes;
window.step4ImageProvider = step2ImageProvider;
window.isFullAutoMode = isFullAutoMode;
