/**
 * Drama Lab - Step4 영상 제작 모듈
 * 화면 기준 Step4: 영상 제작 (이미지 선택 → 영상 생성 → 다운로드)
 */

// ===== 영상 제작 관련 변수 =====
let step4SelectedImages = [];
let step4VideoUrl = null;
let step4VideoFileUrl = null; // 파일 URL (다운로드용)
let generatedThumbnailUrl = null;

// ===== Step4 컨테이너 업데이트 =====
function updateStep4Visibility() {
  updateStep4ContainerVisibility();
  updateStep4ImageGrid();
  updateStep4AudioStatus();
  updateStep5ContainerVisibility();
}

// ===== Step4 컨테이너 표시/숨김 (Step2 이미지 또는 Step3 오디오 있을 때만 표시) =====
function updateStep4ContainerVisibility() {
  const step6Container = document.getElementById('step6-container');
  if (!step6Container) return;

  // Step2 이미지 확인
  let hasImages = false;
  const step2Images = window.DramaStep2?.generatedImages || window.step4GeneratedImages || [];
  if (step2Images.length > 0) {
    hasImages = step2Images.some(img => img && img.url && img.url.trim() !== '');
  }
  if (!hasImages) {
    try {
      const savedImages = localStorage.getItem('_drama-step4-images');
      if (savedImages) {
        const parsed = JSON.parse(savedImages);
        hasImages = parsed.length > 0 && parsed.some(img => img && img.url);
      }
    } catch (e) {}
  }

  // Step3 오디오 확인
  let hasAudio = false;
  if (window.DramaStep3?.audioUrl || window.step5AudioUrl) {
    hasAudio = true;
  } else {
    const step5AudioPlayer = document.getElementById('step5-audio-player');
    if (step5AudioPlayer && step5AudioPlayer.src && step5AudioPlayer.src !== window.location.href) {
      hasAudio = true;
    }
  }

  // Step2 이미지가 있거나 Step3 오디오가 있으면 Step4 표시
  if (hasImages || hasAudio) {
    step6Container.style.display = 'block';
  } else {
    step6Container.style.display = 'none';
  }
}

// ===== Step5 컨테이너 표시/숨김 (Step4 영상이 있을 때만 표시) =====
function updateStep5ContainerVisibility() {
  const step7Container = document.getElementById('step7-container');
  if (!step7Container) return;

  // Step4 영상 확인
  const hasVideo = step4VideoUrl || step4VideoFileUrl ||
    (window.DramaStep4?.videoUrl) ||
    (document.getElementById('step6-video-player')?.src &&
     document.getElementById('step6-video-player').src !== window.location.href);

  if (hasVideo) {
    step7Container.style.display = 'block';
  } else {
    step7Container.style.display = 'none';
  }
}

// ===== 이미지 그리드 업데이트 =====
function updateStep4ImageGrid() {
  const grid = document.getElementById('step6-image-grid');
  if (!grid) return;

  // Step2에서 생성된 이미지 가져오기 (여러 소스에서 시도)
  let step2Images = [];

  // 1. DramaStep2 모듈에서 가져오기
  if (window.DramaStep2 && typeof window.DramaStep2.generatedImages !== 'undefined') {
    step2Images = window.DramaStep2.generatedImages;
  }
  // 2. 전역 변수에서 가져오기
  else if (window.step4GeneratedImages && window.step4GeneratedImages.length > 0) {
    step2Images = window.step4GeneratedImages;
  }
  // 3. localStorage에서 가져오기
  else {
    try {
      const savedImages = localStorage.getItem('_drama-step4-images');
      if (savedImages) {
        step2Images = JSON.parse(savedImages);
      }
    } catch (e) {
      console.warn('[Step4] localStorage 이미지 로드 실패:', e);
    }
  }

  if (!step2Images || step2Images.length === 0) {
    grid.innerHTML = '<div style="color: #999; text-align: center; padding: 1rem; grid-column: 1/-1;">Step2에서 이미지를 생성하면 여기에 표시됩니다</div>';
    return;
  }

  // 유효한 이미지만 필터링
  const validImages = step2Images.filter(img => img && img.url && img.url.trim() !== '');

  if (validImages.length === 0) {
    grid.innerHTML = '<div style="color: #999; text-align: center; padding: 1rem; grid-column: 1/-1;">Step2에서 이미지를 생성하면 여기에 표시됩니다</div>';
    return;
  }

  grid.innerHTML = validImages.map((img, idx) => `
    <div class="step6-preview-item ${step4SelectedImages.includes(img.url) ? 'selected' : ''}" data-url="${img.url}" onclick="toggleStep4Image('${img.url}')">
      <img src="${img.url}" alt="Scene ${idx + 1}" onerror="this.parentElement.style.display='none'">
    </div>
  `).join('');
}

// ===== 이미지 선택 토글 =====
function toggleStep4Image(url) {
  const idx = step4SelectedImages.indexOf(url);
  if (idx > -1) {
    step4SelectedImages.splice(idx, 1);
  } else {
    step4SelectedImages.push(url);
  }
  updateStep4ImageGrid();
}

// ===== 오디오 상태 업데이트 =====
function updateStep4AudioStatus() {
  const statusDiv = document.getElementById('step6-audio-status');
  const audioPreview = document.getElementById('step6-audio-preview');

  if (!statusDiv) return;

  // Step3에서 생성된 오디오 가져오기 (여러 소스에서 시도)
  let audioUrl = null;

  // 1. DramaStep3 모듈에서 가져오기
  if (window.DramaStep3 && window.DramaStep3.audioUrl) {
    audioUrl = window.DramaStep3.audioUrl;
  }
  // 2. 전역 변수에서 가져오기
  else if (window.step5AudioUrl) {
    audioUrl = window.step5AudioUrl;
  }
  // 3. 오디오 플레이어에서 직접 가져오기
  else {
    const step5AudioPlayer = document.getElementById('step5-audio-player');
    if (step5AudioPlayer && step5AudioPlayer.src && step5AudioPlayer.src !== window.location.href) {
      audioUrl = step5AudioPlayer.src;
    }
  }

  if (audioUrl) {
    statusDiv.innerHTML = '✅ 음성이 연결되었습니다';
    statusDiv.style.color = '#27ae60';
    if (audioPreview) {
      audioPreview.src = audioUrl;
      audioPreview.style.display = 'block';
    }
  } else {
    statusDiv.innerHTML = 'Step3에서 음성을 생성하면 자동으로 연결됩니다';
    statusDiv.style.color = '#666';
    if (audioPreview) {
      audioPreview.style.display = 'none';
    }
  }
}

// ===== 썸네일 복원 =====
function restoreThumbnail() {
  const savedThumbnail = localStorage.getItem('_drama-thumbnail');
  if (!savedThumbnail) return;

  try {
    const thumbnailData = JSON.parse(savedThumbnail);
    const thumbnailPreview = document.getElementById('step4-thumbnail-preview');
    const thumbnailImage = document.getElementById('step4-thumbnail-image');
    const thumbnailTextOverlay = document.getElementById('step4-thumbnail-text-overlay');
    const thumbnailPrompt = document.getElementById('step4-thumbnail-prompt');

    if (thumbnailImage && thumbnailData.url) {
      generatedThumbnailUrl = thumbnailData.url;
      thumbnailImage.src = thumbnailData.url;
      thumbnailTextOverlay.textContent = thumbnailData.text || '드라마';
      thumbnailPrompt.textContent = thumbnailData.prompt || '-';
      thumbnailPreview.style.display = 'block';
      console.log('[THUMBNAIL] 저장된 썸네일 복원:', thumbnailData.url);
    }
  } catch (e) {
    console.error('[THUMBNAIL] 복원 실패:', e);
  }
}

// ===== 썸네일 미리보기 업데이트 =====
function updateThumbnailPreview(imageUrl) {
  const thumbnailImage = document.getElementById('step4-thumbnail-image');
  const thumbnailPreview = document.getElementById('step4-thumbnail-preview');

  if (thumbnailImage && thumbnailPreview) {
    thumbnailImage.src = imageUrl;
    thumbnailPreview.style.display = 'block';
    generatedThumbnailUrl = imageUrl;
  }
}

// ===== 썸네일 자동 생성 (AI) =====
async function generateYouTubeThumbnail() {
  const btn = document.getElementById('btn-generate-thumbnail');
  const thumbnailPreview = document.getElementById('step4-thumbnail-preview');
  const thumbnailImage = document.getElementById('step4-thumbnail-image');
  const thumbnailTextOverlay = document.getElementById('step4-thumbnail-text-overlay');
  const thumbnailPrompt = document.getElementById('step4-thumbnail-prompt');

  const step1Result = document.getElementById('step3-result')?.value || '';
  if (!step1Result || !step1Result.trim()) {
    alert('먼저 Step1에서 대본을 작성해주세요.');
    return;
  }

  btn.disabled = true;
  btn.textContent = '생성 중...';
  showStatus('🎨 썸네일 생성 중... (약 15초 소요)');

  try {
    const titleInput = document.getElementById('step7-title');
    const title = titleInput ? titleInput.value : '';
    const imageProvider = window.DramaStep2?.imageProvider || window.step4ImageProvider || 'gemini';

    const response = await fetch('/api/drama/generate-thumbnail', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        script: step1Result,
        title: title,
        provider: imageProvider
      })
    });

    const data = await response.json();

    if (data.ok && data.thumbnailUrl) {
      generatedThumbnailUrl = data.thumbnailUrl;
      thumbnailImage.src = data.thumbnailUrl;
      thumbnailTextOverlay.textContent = data.thumbnailText || title || '드라마';
      thumbnailPrompt.textContent = data.imagePrompt || '-';
      thumbnailPreview.style.display = 'block';

      // 썸네일 데이터 localStorage에 저장
      const thumbnailData = {
        url: data.thumbnailUrl,
        text: data.thumbnailText || title || '드라마',
        prompt: data.imagePrompt || '-',
        createdAt: new Date().toISOString()
      };
      localStorage.setItem('_drama-thumbnail', JSON.stringify(thumbnailData));
      if (typeof saveToFirebase === 'function') {
        saveToFirebase('_drama-thumbnail', JSON.stringify(thumbnailData));
      }

      showStatus('✅ 썸네일 생성 완료!');
      console.log('[THUMBNAIL] 생성 완료:', data.thumbnailUrl);
    } else {
      throw new Error(data.error || '썸네일 생성 실패');
    }
  } catch (error) {
    console.error('Thumbnail generation error:', error);
    showStatus(`❌ 썸네일 생성 실패: ${error.message}`);
    alert(`썸네일 생성 실패: ${error.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = '📸 썸네일 생성';
  }
}

// ===== 이미지 업로드 함수 (base64 -> 서버 URL) =====
async function uploadImageToServer(imageData) {
  // 이미 HTTP URL인 경우 그대로 반환
  if (imageData.startsWith('http://') || imageData.startsWith('https://') || imageData.startsWith('/')) {
    return imageData;
  }

  // Base64 이미지인 경우 서버에 업로드 (502/503/504 재시도 포함)
  const maxRetries = 3;
  let lastError;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const response = await fetch('/api/drama/upload-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imageData: imageData })
      });

      // 502, 503, 504 서버 오류는 재시도
      if ([502, 503, 504].includes(response.status)) {
        const retryDelay = Math.pow(2, attempt + 1) * 1000;
        console.log(`[UPLOAD] 서버 오류 (${response.status}), ${retryDelay/1000}초 후 재시도... (${attempt + 1}/${maxRetries})`);
        lastError = `서버 오류 (${response.status})`;
        await new Promise(resolve => setTimeout(resolve, retryDelay));
        continue;
      }

      if (!response.ok) {
        throw new Error(`이미지 업로드 실패 (${response.status})`);
      }

      const data = await response.json();
      if (!data.ok) {
        throw new Error(data.error || '이미지 업로드 실패');
      }

      return data.imageUrl;
    } catch (err) {
      lastError = err.message;
      if (attempt < maxRetries - 1 && !err.message.includes('업로드 실패')) {
        const retryDelay = Math.pow(2, attempt + 1) * 1000;
        console.log(`[UPLOAD] 네트워크 오류, ${retryDelay/1000}초 후 재시도... (${attempt + 1}/${maxRetries})`);
        await new Promise(resolve => setTimeout(resolve, retryDelay));
      } else {
        throw err;
      }
    }
  }

  throw new Error(lastError || '이미지 업로드 실패');
}

// ===== 사이드바 진행 상태 업데이트 =====
function updateSidebarStepProgress(stepName, status, message) {
  const stepEl = document.querySelector(`.progress-step-sidebar[data-step="${stepName}"]`);
  if (!stepEl) return;

  const substatus = stepEl.querySelector('.step-substatus');
  const statusIcon = stepEl.querySelector('.step-status-icon');
  const container = stepEl.querySelector('div');
  const indicator = stepEl.querySelector('.step-indicator');

  if (status === 'processing') {
    substatus.textContent = message || '진행 중...';
    substatus.style.color = 'rgba(255, 193, 7, 0.9)';
    statusIcon.textContent = '⏳';
    statusIcon.style.color = '#ffc107';
    container.style.borderLeftColor = '#ffc107';
    container.style.background = 'rgba(255, 193, 7, 0.2)';
    indicator.style.background = '#ffc107';
  } else if (status === 'completed') {
    substatus.textContent = '완료';
    substatus.style.color = 'rgba(16, 185, 129, 0.9)';
    statusIcon.textContent = '✓';
    statusIcon.style.color = '#10b981';
    container.style.borderLeftColor = '#10b981';
    container.style.background = 'rgba(16, 185, 129, 0.2)';
    indicator.style.background = '#10b981';
  } else if (status === 'error') {
    substatus.textContent = message || '오류';
    substatus.style.color = 'rgba(239, 68, 68, 0.9)';
    statusIcon.textContent = '✗';
    statusIcon.style.color = '#ef4444';
    container.style.borderLeftColor = '#ef4444';
    container.style.background = 'rgba(239, 68, 68, 0.2)';
  }
}

// ===== 영상 생성 함수 =====
async function generateVideo() {
  // 유효성 검사
  if (step4SelectedImages.length === 0) {
    alert('최소 1개 이상의 이미지를 선택해주세요.');
    return;
  }

  const audioUrl = window.DramaStep3?.audioUrl || window.step5AudioUrl;
  if (!audioUrl) {
    alert('Step3에서 음성을 먼저 생성해주세요.');
    return;
  }

  // 브라우저 알림 권한 요청
  if (Notification.permission === 'default') {
    await Notification.requestPermission();
  }

  const resolution = document.getElementById('step6-resolution')?.value || '1920x1080';
  const fps = document.getElementById('step6-fps')?.value || '30';
  const transition = document.getElementById('step6-transition')?.value || 'fade';
  const includeSubtitle = document.getElementById('step6-include-subtitle')?.checked || false;
  const burnSubtitle = document.getElementById('step6-burn-subtitle')?.checked || false;

  const subtitleData = window.DramaStep3?.subtitleData || window.step5SubtitleData;

  const btnGenerateVideo = document.getElementById('btn-generate-video');
  const progressDiv = document.getElementById('step6-progress');
  const progressBar = document.getElementById('step6-progress-bar');
  const progressText = document.getElementById('step6-progress-text');

  if (btnGenerateVideo) {
    btnGenerateVideo.disabled = true;
    btnGenerateVideo.classList.add('generating');
    btnGenerateVideo.textContent = '⏳ 영상 생성 중...';
  }

  progressDiv.style.display = 'block';
  progressBar.style.width = '5%';
  progressText.textContent = '이미지 업로드 준비 중...';

  showStatus('🎬 Step4: 영상 생성 시작...');
  updateSidebarStepProgress('step6', 'processing', '준비 중...');

  try {
    // 1. Base64 이미지를 서버에 먼저 업로드
    const uploadedImageUrls = [];
    const totalImages = step4SelectedImages.length;

    for (let i = 0; i < totalImages; i++) {
      progressBar.style.width = (5 + (i / totalImages) * 20) + '%';
      progressText.textContent = `이미지 업로드 중... (${i + 1}/${totalImages})`;
      updateSidebarStepProgress('step6', 'processing', `업로드 ${i + 1}/${totalImages}`);

      try {
        const uploadedUrl = await uploadImageToServer(step4SelectedImages[i]);
        uploadedImageUrls.push(uploadedUrl);
      } catch (uploadErr) {
        console.error(`이미지 ${i + 1} 업로드 실패:`, uploadErr);
        throw new Error(`이미지 ${i + 1} 업로드 실패: ${uploadErr.message}`);
      }
    }

    console.log(`[VIDEO] ${uploadedImageUrls.length}개 이미지 업로드 완료`);

    progressBar.style.width = '25%';
    progressText.textContent = '영상 생성 작업 시작 중...';
    updateSidebarStepProgress('step6', 'processing', '영상 생성 중...');

    // 2. 영상 생성 작업 시작 (즉시 job_id 반환)
    const response = await fetch('/api/drama/generate-video', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        images: uploadedImageUrls,
        audioUrl: audioUrl,
        subtitleData: includeSubtitle ? subtitleData : null,
        burnSubtitle: burnSubtitle,
        resolution: resolution,
        fps: parseInt(fps),
        transition: transition
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`서버 오류 (${response.status}): ${errorText || '응답 없음'}`);
    }

    const data = await response.json();

    if (!data.ok || !data.jobId) {
      throw new Error(data.error || '작업 시작 실패');
    }

    const jobId = data.jobId;
    console.log(`[VIDEO] 작업 시작됨: ${jobId}`);

    progressBar.style.width = '30%';
    progressText.textContent = '백그라운드에서 영상 생성 중... (다른 작업 가능)';
    showStatus('🎬 영상 생성 중... (백그라운드 작업)');

    // 3. Polling으로 상태 체크
    const startTime = Date.now();
    const maxWaitTime = 600000; // 10분
    let lastProgress = 30;

    while (Date.now() - startTime < maxWaitTime) {
      await new Promise(resolve => setTimeout(resolve, 2000)); // 2초마다 체크

      try {
        const statusResponse = await fetch(`/api/drama/video-status/${jobId}`);

        if (!statusResponse.ok) {
          console.error('상태 조회 실패:', statusResponse.status);
          continue;
        }

        const statusData = await statusResponse.json();

        if (!statusData.ok) {
          throw new Error(statusData.error || '상태 조회 실패');
        }

        // 진행률 업데이트
        const serverProgress = statusData.progress || 0;
        const displayProgress = Math.max(lastProgress, 30 + serverProgress * 0.7);
        lastProgress = displayProgress;
        progressBar.style.width = displayProgress + '%';
        progressText.textContent = statusData.message || '영상 생성 중...';
        updateSidebarStepProgress('step6', 'processing', `${Math.round(displayProgress)}%`);

        console.log(`[VIDEO] 상태: ${statusData.status}, 진행률: ${serverProgress}%`);

        // 완료 확인
        if (statusData.status === 'completed' && statusData.result) {
          progressBar.style.width = '100%';
          progressText.textContent = '완료!';

          const result = statusData.result;

          // 영상 플레이어 표시
          const videoSection = document.getElementById('step6-video-section');
          const videoPlayer = document.getElementById('step6-video-player');

          if (videoPlayer && result.videoUrl) {
            step4VideoUrl = result.videoUrl;
            step4VideoFileUrl = result.videoFileUrl || result.videoUrl;
            videoPlayer.src = result.videoUrl;
            videoSection.style.display = 'block';
          }

          showStatus('✅ 영상 생성 완료! Step5에서 YouTube 업로드가 가능합니다.');
          if (typeof updateProgressIndicator === 'function') {
            updateProgressIndicator('step6');
          }
          updateStep5Status();

          // 브라우저 알림
          if (Notification.permission === 'granted') {
            new Notification('✅ 영상 생성 완료!', {
              body: '드라마 영상이 성공적으로 생성되었습니다.',
              icon: '/static/favicon.ico'
            });
          }

          setTimeout(() => {
            progressDiv.style.display = 'none';
          }, 1500);

          break;

        } else if (statusData.status === 'failed') {
          throw new Error(statusData.error || '영상 생성 실패');
        }

      } catch (pollErr) {
        console.error('Polling 오류:', pollErr);
      }
    }

    // 타임아웃 체크
    if (Date.now() - startTime >= maxWaitTime) {
      throw new Error('영상 생성 시간 초과 (10분). 작업은 백그라운드에서 계속 진행될 수 있습니다.');
    }

  } catch (err) {
    progressDiv.style.display = 'none';
    alert(`오류: ${err.message}`);
    showStatus('❌ 영상 생성 실패');
    updateSidebarStepProgress('step6', 'error', '오류 발생');

    // 실패 알림
    if (Notification.permission === 'granted') {
      new Notification('❌ 영상 생성 실패', {
        body: err.message,
        icon: '/static/favicon.ico'
      });
    }
  } finally {
    setTimeout(hideStatus, 3000);
    if (btnGenerateVideo) {
      btnGenerateVideo.disabled = false;
      btnGenerateVideo.classList.remove('generating');
      btnGenerateVideo.textContent = '🎬 영상 생성';
    }
  }
}

// ===== 영상 생성용 이미지 자동 선택 =====
async function autoSelectImagesForVideo() {
  step4SelectedImages = [];

  // Step2에서 생성된 이미지들 가져오기
  const step2Images = window.DramaStep2?.generatedImages || window.step4GeneratedImages || [];

  if (step2Images.length > 0) {
    step2Images.forEach(img => {
      if (img.url) {
        step4SelectedImages.push(img.url);
      }
    });
    console.log(`[AUTO] ${step4SelectedImages.length}개 씬 이미지 선택됨`);
  }

  // 씬 이미지가 없으면 인물 이미지 사용
  const characterImages = window.DramaStep2?.characterImages || window.step4CharacterImages || {};
  if (step4SelectedImages.length === 0 && Object.keys(characterImages).length > 0) {
    Object.values(characterImages).forEach(img => {
      if (img.url) {
        step4SelectedImages.push(img.url);
      }
    });
    console.log(`[AUTO] ${step4SelectedImages.length}개 인물 이미지 선택됨`);
  }

  updateStep4ImageGrid();
}

// ===== 자동 영상 생성 (확인 없이) =====
async function generateVideoAuto() {
  if (step4SelectedImages.length === 0) {
    console.error('[AUTO] 영상 생성 실패: 이미지 없음');
    return;
  }

  const audioUrl = window.DramaStep3?.audioUrl || window.step5AudioUrl;
  if (!audioUrl) {
    console.error('[AUTO] 영상 생성 실패: 오디오 없음');
    return;
  }

  // 브라우저 알림 권한 요청
  if (Notification.permission === 'default') {
    await Notification.requestPermission();
  }

  const resolution = document.getElementById('step6-resolution')?.value || '1920x1080';
  const fps = document.getElementById('step6-fps')?.value || '30';
  const transition = document.getElementById('step6-transition')?.value || 'fade';
  const includeSubtitle = document.getElementById('step6-include-subtitle')?.checked || false;
  const burnSubtitle = document.getElementById('step6-burn-subtitle')?.checked || false;

  const subtitleData = window.DramaStep3?.subtitleData || window.step5SubtitleData;

  const progressDiv = document.getElementById('step6-progress');
  const progressBar = document.getElementById('step6-progress-bar');
  const progressText = document.getElementById('step6-progress-text');

  progressDiv.style.display = 'block';
  progressBar.style.width = '5%';
  progressText.textContent = '[자동화] 이미지 업로드 준비 중...';

  showStatus('🎬 자동화: 영상 생성 시작...');

  try {
    // 1. 이미지 업로드
    const uploadedImageUrls = [];
    const totalImages = step4SelectedImages.length;

    for (let i = 0; i < totalImages; i++) {
      progressBar.style.width = (5 + (i / totalImages) * 20) + '%';
      progressText.textContent = `[자동화] 이미지 업로드 중... (${i + 1}/${totalImages})`;

      try {
        const uploadedUrl = await uploadImageToServer(step4SelectedImages[i]);
        uploadedImageUrls.push(uploadedUrl);
      } catch (uploadErr) {
        console.error(`[AUTO] 이미지 ${i + 1} 업로드 실패:`, uploadErr);
        throw new Error(`이미지 ${i + 1} 업로드 실패: ${uploadErr.message}`);
      }
    }

    console.log(`[AUTO] ${uploadedImageUrls.length}개 이미지 업로드 완료`);

    progressBar.style.width = '25%';
    progressText.textContent = '[자동화] 영상 생성 작업 시작 중...';

    // 2. 영상 생성 작업 시작
    const response = await fetch('/api/drama/generate-video', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        images: uploadedImageUrls,
        audioUrl: audioUrl,
        subtitleData: includeSubtitle ? subtitleData : null,
        burnSubtitle: burnSubtitle,
        resolution: resolution,
        fps: parseInt(fps),
        transition: transition
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`서버 오류 (${response.status}): ${errorText || '응답 없음'}`);
    }

    const data = await response.json();

    if (!data.ok || !data.jobId) {
      throw new Error(data.error || '작업 시작 실패');
    }

    const jobId = data.jobId;
    console.log(`[AUTO] 영상 생성 작업 시작됨: ${jobId}`);

    progressBar.style.width = '30%';
    progressText.textContent = '[자동화] 백그라운드에서 영상 생성 중...';
    showStatus('🎬 자동화: 영상 생성 중... (백그라운드)');

    // 3. Polling으로 상태 체크
    const startTime = Date.now();
    const maxWaitTime = 600000; // 10분
    let lastProgress = 30;

    while (Date.now() - startTime < maxWaitTime) {
      await new Promise(resolve => setTimeout(resolve, 2000));

      try {
        const statusResponse = await fetch(`/api/drama/video-status/${jobId}`);

        if (!statusResponse.ok) {
          console.error('[AUTO] 상태 조회 실패:', statusResponse.status);
          continue;
        }

        const statusData = await statusResponse.json();

        if (!statusData.ok) {
          throw new Error(statusData.error || '상태 조회 실패');
        }

        const serverProgress = statusData.progress || 0;
        const displayProgress = Math.max(lastProgress, 30 + serverProgress * 0.7);
        lastProgress = displayProgress;
        progressBar.style.width = displayProgress + '%';
        progressText.textContent = `[자동화] ${statusData.message || '영상 생성 중...'}`;

        console.log(`[AUTO] 상태: ${statusData.status}, 진행률: ${serverProgress}%`);

        if (statusData.status === 'completed' && statusData.result) {
          progressBar.style.width = '100%';
          progressText.textContent = '🎉 자동화 완료!';

          const result = statusData.result;

          const videoSection = document.getElementById('step6-video-section');
          const videoPlayer = document.getElementById('step6-video-player');

          if (videoPlayer && result.videoUrl) {
            step4VideoUrl = result.videoUrl;
            step4VideoFileUrl = result.videoFileUrl || result.videoUrl;
            videoPlayer.src = result.videoUrl;
            videoSection.style.display = 'block';
          }

          showStatus('🎉 자동화 완료! 영상이 생성되었습니다. YouTube 업로드를 진행하세요.');
          if (typeof updateProgressIndicator === 'function') {
            updateProgressIndicator('step6');
          }
          updateStep5Status();

          // 브라우저 알림
          if (Notification.permission === 'granted') {
            new Notification('🎉 자동화 완료!', {
              body: '드라마 영상이 성공적으로 생성되었습니다.',
              icon: '/static/favicon.ico'
            });
          }

          setTimeout(() => {
            progressDiv.style.display = 'none';
          }, 3000);

          break;

        } else if (statusData.status === 'failed') {
          throw new Error(statusData.error || '영상 생성 실패');
        }

      } catch (pollErr) {
        console.error('[AUTO] Polling 오류:', pollErr);
      }
    }

    // 타임아웃 체크
    if (Date.now() - startTime >= maxWaitTime) {
      throw new Error('영상 생성 시간 초과 (10분)');
    }

  } catch (err) {
    console.error('[AUTO] 영상 생성 오류:', err);
    progressDiv.style.display = 'none';
    showStatus(`❌ 자동화 영상 생성 오류: ${err.message}`);

    // 실패 알림
    if (Notification.permission === 'granted') {
      new Notification('❌ 자동화 실패', {
        body: `영상 생성 오류: ${err.message}`,
        icon: '/static/favicon.ico'
      });
    }
  }
}

// ===== Step5 상태 업데이트 =====
function updateStep5Status() {
  if (typeof window.DramaStep5 !== 'undefined' && typeof window.DramaStep5.updateStatus === 'function') {
    window.DramaStep5.updateStatus();
  }
}

// ===== 영상 다운로드 =====
function downloadVideo() {
  if (!step4VideoUrl && !step4VideoFileUrl) {
    alert('먼저 영상을 생성해주세요.');
    return;
  }
  const a = document.createElement('a');
  a.href = step4VideoFileUrl || step4VideoUrl;
  a.download = `drama-video-${Date.now()}.mp4`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ===== Step4 초기화 =====
function clearStep4() {
  if (!confirm('Step4의 모든 내용을 초기화하시겠습니까?')) return;

  step4SelectedImages = [];
  step4VideoUrl = null;
  step4VideoFileUrl = null;

  document.getElementById('step6-video-section').style.display = 'none';
  document.getElementById('step6-progress').style.display = 'none';

  const videoPlayer = document.getElementById('step6-video-player');
  if (videoPlayer) videoPlayer.src = '';

  updateStep4ImageGrid();

  showStatus('🗑️ Step4가 초기화되었습니다.');
  setTimeout(hideStatus, 2000);
}

// ===== 이벤트 리스너 설정 =====
document.addEventListener('DOMContentLoaded', () => {
  // Step4 가시성 체크 (주기적)
  setInterval(updateStep4Visibility, 2000);

  // 썸네일 복원
  setTimeout(restoreThumbnail, 500);

  // 버튼 이벤트 바인딩
  document.getElementById('btn-generate-thumbnail')?.addEventListener('click', generateYouTubeThumbnail);
  document.getElementById('btn-regenerate-thumbnail')?.addEventListener('click', generateYouTubeThumbnail);
  document.getElementById('btn-generate-video')?.addEventListener('click', generateVideo);
  document.getElementById('btn-download-video')?.addEventListener('click', downloadVideo);
  document.getElementById('btn-clear-step6')?.addEventListener('click', clearStep4);

  console.log('[DramaStep4] 초기화 완료');
});

// ===== 전역 노출 =====
window.DramaStep4 = {
  generateVideo,
  generateVideoAuto,
  generateYouTubeThumbnail,
  downloadVideo,
  clearStep4,
  toggleStep4Image,
  autoSelectImages: autoSelectImagesForVideo,
  updateVisibility: updateStep4Visibility,
  updateThumbnailPreview,
  get selectedImages() { return step4SelectedImages; },
  get videoUrl() { return step4VideoUrl; },
  get videoFileUrl() { return step4VideoFileUrl; },
  get thumbnailUrl() { return generatedThumbnailUrl; }
};

// 기존 코드 호환
window.generateVideo = generateVideo;
window.generateVideoAuto = generateVideoAuto;
window.generateYouTubeThumbnail = generateYouTubeThumbnail;
window.downloadVideo = downloadVideo;
window.toggleStep6Image = toggleStep4Image;
window.updateThumbnailPreview = updateThumbnailPreview;
window.step6SelectedImages = step4SelectedImages;
window.step6VideoUrl = step4VideoUrl;
window.step6VideoFileUrl = step4VideoFileUrl;
window.generatedThumbnailUrl = generatedThumbnailUrl;
