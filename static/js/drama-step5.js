/**
 * Drama Lab - Step5 유튜브 업로드 모듈
 * 화면 기준 Step5: 유튜브 업로드 (메타데이터 → 인증 → 업로드)
 */

// ===== 유튜브 업로드 관련 변수 =====
let youtubeAuthenticated = false;

// ===== Step5 업로드 상태 메시지 업데이트 =====
function updateStep5Status() {
  const statusEl = document.getElementById('step7-upload-status');
  const uploadBtn = document.getElementById('btn-upload-youtube');
  const videoSrc = getStep4Video();

  if (!statusEl) return;

  if (!youtubeAuthenticated) {
    statusEl.style.background = '#fff3cd';
    statusEl.style.color = '#856404';
    statusEl.textContent = 'YouTube 인증을 먼저 진행해주세요';
    if (uploadBtn) uploadBtn.disabled = true;
  } else if (!videoSrc) {
    statusEl.style.background = '#fff3cd';
    statusEl.style.color = '#856404';
    statusEl.textContent = 'Step4에서 영상을 먼저 생성해주세요';
    if (uploadBtn) uploadBtn.disabled = true;
  } else {
    statusEl.style.background = '#d4edda';
    statusEl.style.color = '#155724';
    statusEl.textContent = '영상이 준비되었습니다. 업로드할 수 있습니다!';
    if (uploadBtn) uploadBtn.disabled = false;
  }
}

// ===== Step4 비디오 가져오기 =====
function getStep4Video() {
  const videoPlayer = document.getElementById('step6-video-player');
  if (videoPlayer && videoPlayer.src && videoPlayer.src !== window.location.href) {
    return videoPlayer.src;
  }
  return null;
}

// ===== 개인정보 옵션 선택 =====
function selectStep5Privacy(value) {
  document.querySelectorAll('.step7-privacy-option').forEach(opt => {
    opt.classList.remove('selected');
    const input = opt.querySelector('input[type="radio"]');
    if (input) input.checked = false;
    if (opt.dataset.privacy === value) {
      opt.classList.add('selected');
      if (input) input.checked = true;
    }
  });
}

// ===== 대본 기반 자동 메타데이터 생성 =====
async function generateAutoMetadata() {
  const btn = document.getElementById('btn-auto-metadata');
  const step1Result = document.getElementById('step3-result')?.value || '';

  if (!step1Result.trim()) {
    showStatus('Step1 대본 결과가 없습니다. 먼저 대본을 작성해주세요.');
    return;
  }

  btn.disabled = true;
  btn.textContent = '생성 중...';
  showStatus('대본을 분석하여 제목, 설명, 태그를 생성 중...');

  try {
    const response = await fetch('/api/drama/generate-metadata', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script: step1Result })
    });

    const data = await response.json();

    if (data.ok && data.metadata) {
      document.getElementById('step7-title').value = data.metadata.title || '';
      document.getElementById('step7-description').value = data.metadata.description || '';
      document.getElementById('step7-tags').value = data.metadata.tags || '';
      showStatus('메타데이터가 자동으로 입력되었습니다!');
    } else {
      throw new Error(data.error || '메타데이터 생성 실패');
    }
  } catch (error) {
    console.error('Auto metadata error:', error);
    showStatus(`메타데이터 생성 실패: ${error.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = '대본 기반 자동 입력';
  }
}

// ===== 유튜브 인증 =====
async function authenticateYouTube() {
  const authBtn = document.getElementById('btn-youtube-auth');
  const authStatus = document.getElementById('youtube-auth-status');

  authBtn.disabled = true;
  authBtn.textContent = '🔄 인증 중...';
  authStatus.innerHTML = '<span style="color: #f39c12;">⏳ YouTube 인증을 진행 중입니다...</span>';

  try {
    const response = await fetch('/api/drama/youtube-auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await response.json();
    console.log('[YOUTUBE-AUTH] 응답 데이터:', data);

    if (data.success) {
      youtubeAuthenticated = true;
      authBtn.textContent = '✅ 인증 완료';
      authBtn.style.background = 'linear-gradient(135deg, #27ae60, #2ecc71)';
      authStatus.innerHTML = '<span style="color: #27ae60;">✅ YouTube 인증이 완료되었습니다.</span>';
      updateStep5Status();
      await loadYouTubeChannels();
    } else if (data.auth_url) {
      console.log('[YOUTUBE-AUTH] OAuth URL:', data.auth_url);
      const popup = window.open(data.auth_url, '_blank', 'width=600,height=700');

      if (!popup) {
        authBtn.disabled = false;
        authBtn.textContent = '🔑 YouTube 연결';
        authStatus.innerHTML = '<span style="color: #e74c3c;">❌ 팝업이 차단되었습니다. 브라우저 설정에서 팝업을 허용해주세요.</span>';
        return;
      }

      authBtn.textContent = '🔗 인증 대기 중';
      authStatus.innerHTML = '<span style="color: #f39c12;">⏳ 새 창에서 YouTube 인증을 완료해주세요.</span>';

      // postMessage 리스너 등록
      window.youtubeAuthPollActive = true;
      const messageHandler = async (event) => {
        if (event.data && event.data.type === 'youtube-auth-success') {
          console.log('[YOUTUBE-AUTH] postMessage로 인증 완료 수신');
          window.youtubeAuthPollActive = false;
          window.removeEventListener('message', messageHandler);
          await handleYouTubeAuthSuccess();
        }
      };
      window.addEventListener('message', messageHandler);

      // 인증 상태 폴링 (백업)
      pollYouTubeAuth();
    } else {
      const errorMsg = data.error || '인증 실패 (알 수 없는 오류)';
      console.error('[YOUTUBE-AUTH] 에러:', errorMsg);
      throw new Error(errorMsg);
    }
  } catch (error) {
    console.error('YouTube auth error:', error);
    authBtn.disabled = false;
    authBtn.textContent = '🔗 YouTube 인증';
    authStatus.innerHTML = `<span style="color: #e74c3c;">❌ 인증 실패: ${error.message}</span>`;
  }
}

// ===== YouTube 채널 목록 로드 =====
async function loadYouTubeChannels() {
  try {
    const response = await fetch('/api/drama/youtube-channels');
    const data = await response.json();

    if (data.success && data.channels && data.channels.length > 0) {
      const channelSelect = document.getElementById('step7-channel-select');
      const channelSection = document.getElementById('youtube-channel-section');

      channelSelect.innerHTML = '<option value="">채널을 선택하세요</option>';

      data.channels.forEach(channel => {
        const option = document.createElement('option');
        option.value = channel.id;
        option.textContent = channel.title;
        channelSelect.appendChild(option);
      });

      if (data.channels.length === 1) {
        channelSelect.value = data.channels[0].id;
      }

      channelSection.style.display = 'block';
      showStatus(`✅ YouTube 채널이 로드되었습니다! ${data.channels.length}개 채널 중 업로드할 채널을 선택해주세요.`);

      setTimeout(() => {
        channelSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 500);
    }
  } catch (error) {
    console.error('채널 목록 로드 실패:', error);
  }
}

// ===== YouTube 인증 성공 처리 =====
async function handleYouTubeAuthSuccess() {
  const authBtn = document.getElementById('btn-youtube-auth');
  const authStatus = document.getElementById('youtube-auth-status');

  youtubeAuthenticated = true;
  authBtn.textContent = '✅ 인증 완료';
  authBtn.style.background = 'linear-gradient(135deg, #27ae60, #2ecc71)';
  authBtn.disabled = true;
  authStatus.innerHTML = '<span style="color: #27ae60;">✅ YouTube 인증이 완료되었습니다.</span>';
  updateStep5Status();
  await loadYouTubeChannels();
}

// ===== 인증 상태 폴링 =====
async function pollYouTubeAuth() {
  const authBtn = document.getElementById('btn-youtube-auth');
  const authStatus = document.getElementById('youtube-auth-status');

  for (let i = 0; i < 60; i++) {
    if (!window.youtubeAuthPollActive) {
      console.log('[YOUTUBE-AUTH] 폴링 중단 (postMessage로 처리됨)');
      return;
    }

    await new Promise(resolve => setTimeout(resolve, 2000));

    try {
      const response = await fetch('/api/drama/youtube-auth-status');
      const data = await response.json();
      console.log('[YOUTUBE-AUTH] 폴링 상태:', data);

      if (data.authenticated) {
        window.youtubeAuthPollActive = false;
        await handleYouTubeAuthSuccess();
        return;
      }
    } catch (e) {
      console.error('Poll error:', e);
    }
  }

  window.youtubeAuthPollActive = false;
  authBtn.disabled = false;
  authBtn.textContent = '🔗 YouTube 인증';
  authStatus.innerHTML = '<span style="color: #e74c3c;">❌ 인증 시간이 초과되었습니다. 다시 시도해주세요.</span>';
}

// ===== Blob을 Base64로 변환 =====
function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = reader.result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

// ===== 유튜브 업로드 =====
async function uploadToYouTube() {
  const videoSrc = getStep4Video();
  if (!videoSrc) {
    showStatus('❌ 업로드할 비디오가 없습니다. Step4에서 먼저 비디오를 생성해주세요.');
    return;
  }

  const title = document.getElementById('step7-title').value.trim();
  if (!title) {
    showStatus('❌ 비디오 제목을 입력해주세요.');
    return;
  }

  // 선택된 채널 확인
  const channelSelect = document.getElementById('step7-channel-select');
  const selectedChannelId = channelSelect.value;
  if (!selectedChannelId) {
    showStatus('❌ 업로드할 채널을 선택해주세요.');
    return;
  }

  const description = document.getElementById('step7-description').value.trim();
  const tags = document.getElementById('step7-tags').value.trim();
  const category = document.getElementById('step7-category').value;
  const privacyOption = document.querySelector('.step7-privacy-option.selected');
  const privacyValue = privacyOption ? privacyOption.dataset.privacy : 'scheduled';

  // 예약 업로드인 경우 30분 후 공개 시간 계산
  let privacy = privacyValue;
  let publishAt = null;
  if (privacyValue === 'scheduled') {
    privacy = 'private';
    const scheduledTime = new Date(Date.now() + 30 * 60 * 1000);
    publishAt = scheduledTime.toISOString();
  }

  const uploadBtn = document.getElementById('btn-upload-youtube');
  const progressContainer = document.getElementById('step7-progress');
  const progressFill = document.getElementById('step7-progress-bar');
  const progressText = document.getElementById('step7-progress-text');
  const resultContainer = document.getElementById('step7-result');

  uploadBtn.disabled = true;
  uploadBtn.textContent = '⏳ 업로드 중...';
  progressContainer.style.display = 'block';
  resultContainer.style.display = 'none';

  try {
    // 비디오 데이터 가져오기
    progressText.textContent = '비디오 데이터 준비 중...';
    progressFill.style.width = '10%';

    const videoResponse = await fetch(videoSrc);
    const videoBlob = await videoResponse.blob();
    const videoBase64 = await blobToBase64(videoBlob);

    progressText.textContent = publishAt ? '유튜브에 예약 업로드 중...' : '유튜브에 업로드 중...';
    progressFill.style.width = '30%';

    const response = await fetch('/api/drama/upload-youtube', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        video_data: videoBase64,
        title: title,
        description: description,
        tags: tags.split(',').map(t => t.trim()).filter(t => t),
        category_id: category,
        privacy_status: privacy,
        publish_at: publishAt,
        channel_id: selectedChannelId
      })
    });

    progressFill.style.width = '80%';

    const data = await response.json();

    if (data.success) {
      progressFill.style.width = '100%';
      progressText.textContent = publishAt ? '예약 업로드 완료!' : '업로드 완료!';

      resultContainer.style.display = 'block';
      document.getElementById('step7-video-link').href = data.video_url;
      document.getElementById('step7-video-link').textContent = data.video_url;
      document.getElementById('step7-video-id').textContent = data.video_id;

      const scheduledMsg = publishAt ? ` (${new Date(publishAt).toLocaleString('ko-KR')}에 공개 예정)` : '';
      showStatus(`🎉 YouTube 업로드가 완료되었습니다!${scheduledMsg}`);
      if (typeof updateProgressIndicator === 'function') {
        updateProgressIndicator('step7');
      }
    } else {
      throw new Error(data.error || '업로드 실패');
    }
  } catch (error) {
    console.error('Upload error:', error);
    progressText.textContent = `업로드 실패: ${error.message}`;
    progressFill.style.background = '#e74c3c';
    showStatus(`❌ 업로드 실패: ${error.message}`);
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.textContent = '📤 YouTube 업로드';
  }
}

// ===== Step5 초기화 =====
function clearStep5() {
  document.getElementById('step7-title').value = '';
  document.getElementById('step7-description').value = '';
  document.getElementById('step7-tags').value = '';
  document.getElementById('step7-category').value = '22';
  selectStep5Privacy('scheduled');

  document.getElementById('step7-progress').style.display = 'none';
  document.getElementById('step7-progress-bar').style.width = '0%';
  document.getElementById('step7-progress-bar').style.background = 'linear-gradient(135deg, #ff0000, #cc0000)';
  document.getElementById('step7-result').style.display = 'none';

  showStatus('Step5이 초기화되었습니다.');
  setTimeout(hideStatus, 2000);
}

// ===== 이벤트 리스너 설정 =====
document.addEventListener('DOMContentLoaded', () => {
  // 주기적으로 Step5 상태 업데이트
  setInterval(updateStep5Status, 3000);

  // 개인정보 옵션 이벤트
  document.querySelectorAll('.step7-privacy-option').forEach(opt => {
    opt.addEventListener('click', () => selectStep5Privacy(opt.dataset.privacy));
  });

  // 기본 공개 설정은 예약 (30분 후 공개)
  selectStep5Privacy('scheduled');

  // 버튼 이벤트 바인딩
  document.getElementById('btn-auto-metadata')?.addEventListener('click', generateAutoMetadata);
  document.getElementById('btn-youtube-auth')?.addEventListener('click', authenticateYouTube);
  document.getElementById('btn-upload-youtube')?.addEventListener('click', uploadToYouTube);
  document.getElementById('btn-clear-step7')?.addEventListener('click', clearStep5);

  console.log('[DramaStep5] 초기화 완료');
});

// ===== 전역 노출 =====
window.DramaStep5 = {
  authenticateYouTube,
  uploadToYouTube,
  generateAutoMetadata,
  clearStep5,
  updateStatus: updateStep5Status,
  get authenticated() { return youtubeAuthenticated; }
};

// 기존 코드 호환
window.authenticateYouTube = authenticateYouTube;
window.uploadToYouTube = uploadToYouTube;
window.generateAutoMetadata = generateAutoMetadata;
window.selectStep7Privacy = selectStep5Privacy;
window.youtubeAuthenticated = youtubeAuthenticated;
