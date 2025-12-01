/**
 * Drama Lab - Step 4: 씬별 클립 다운로드
 * 업데이트: 2024-12-01
 * - 전체 영상 생성 → 씬별 MP4 클립 다운로드로 변경
 * - CapCut 등에서 자유롭게 편집 가능
 */

window.DramaStep4 = {
  // 상태
  isCreating: false,
  zipData: null,

  init() {
    console.log('[Step4] 씬별 클립 다운로드 모듈 초기화');
    this.renderClipsList();
  },

  // 이전 단계 데이터 가져오기
  getPreviousStepData() {
    const step2ImagesData = DramaSession.getStepData('step2_images');
    const step3Data = DramaSession.getStepData('step3');

    console.log('[Step4] step2_images 데이터:', step2ImagesData);
    console.log('[Step4] step3 데이터:', step3Data);

    const images = step2ImagesData?.images || [];
    const audios = step3Data?.audios || [];

    // 씬별 이미지-오디오 매칭
    const cuts = [];
    const maxCuts = Math.max(images.length, audios.length);

    for (let i = 0; i < maxCuts; i++) {
      const imageUrl = images[i] || '';
      const audio = audios[i] || {};

      cuts.push({
        sceneId: `scene_${i + 1}`,
        imageUrl: imageUrl,
        audioUrl: audio.audioUrl || '',
        duration: audio.duration || 0,
        text: audio.text || `씬 ${i + 1}`
      });
    }

    console.log('[Step4] 생성된 cuts:', cuts.length, '개');
    return { images, audios, cuts };
  },

  // 클립 목록 렌더링
  renderClipsList() {
    const container = document.getElementById('scene-clips-items');
    if (!container) return;

    const { cuts } = this.getPreviousStepData();

    if (cuts.length === 0 || !cuts[0].imageUrl) {
      container.innerHTML = '<div class="empty-message">Step 2, 3을 먼저 완료해주세요.</div>';
      return;
    }

    const validCuts = cuts.filter(c => c.imageUrl && c.audioUrl);

    if (validCuts.length === 0) {
      container.innerHTML = '<div class="empty-message">이미지와 오디오가 모두 있는 씬이 없습니다.</div>';
      return;
    }

    container.innerHTML = validCuts.map((cut, idx) => `
      <div class="scene-clip-item">
        <div class="clip-thumbnail">
          <img src="${cut.imageUrl.startsWith('data:') ? cut.imageUrl : cut.imageUrl}"
               alt="${cut.sceneId}"
               onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22><rect fill=%22%23ccc%22 width=%22100%22 height=%22100%22/></svg>'">
        </div>
        <div class="clip-info">
          <span class="clip-name">${cut.sceneId}.mp4</span>
          <span class="clip-duration">${cut.duration ? cut.duration.toFixed(1) + '초' : '-'}</span>
        </div>
        <div class="clip-status" id="clip-status-${idx}">⏳ 대기</div>
      </div>
    `).join('');
  },

  // 씬별 클립 생성 (ZIP)
  async createSceneClips() {
    if (this.isCreating) {
      DramaUtils.showStatus('이미 생성 중입니다...', 'warning');
      return;
    }

    const { cuts } = this.getPreviousStepData();
    const validCuts = cuts.filter(c => c.imageUrl && c.audioUrl);

    if (validCuts.length === 0) {
      DramaUtils.showStatus('이미지와 오디오가 모두 있는 씬이 없습니다.', 'error');
      return;
    }

    this.isCreating = true;
    const btn = document.getElementById('btn-create-clips');
    const originalText = btn?.innerHTML;

    try {
      if (btn) {
        btn.innerHTML = '<span class="btn-icon">⏳</span> 생성 중...';
        btn.disabled = true;
      }

      // 진행 상황 표시
      const progressPanel = document.getElementById('clip-progress');
      const progressBar = document.getElementById('clip-progress-bar');
      const progressText = document.getElementById('clip-progress-text');

      if (progressPanel) progressPanel.classList.remove('hidden');
      if (progressBar) progressBar.style.width = '10%';
      if (progressText) progressText.textContent = `${validCuts.length}개 씬 클립 생성 요청 중...`;

      // 각 클립 상태 업데이트
      validCuts.forEach((_, idx) => {
        const statusEl = document.getElementById(`clip-status-${idx}`);
        if (statusEl) statusEl.textContent = '⏳ 대기';
      });

      console.log('[Step4] 씬별 클립 ZIP 생성 요청:', validCuts.length, '개');

      // API 호출
      const response = await fetch('/api/drama/generate-scene-clips-zip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cuts: validCuts })
      });

      if (!response.ok) {
        throw new Error(`서버 오류: ${response.status}`);
      }

      const data = await response.json();

      if (data.ok) {
        // 성공
        if (progressBar) progressBar.style.width = '100%';
        if (progressText) progressText.textContent = '완료!';

        // 클립 상태 업데이트
        validCuts.forEach((_, idx) => {
          const statusEl = document.getElementById(`clip-status-${idx}`);
          if (statusEl) statusEl.textContent = '✅ 완료';
        });

        // ZIP 데이터 저장
        this.zipData = data.zipUrl;

        // 다운로드 영역 표시
        const downloadArea = document.getElementById('clip-download-area');
        const clipCount = document.getElementById('clip-count');
        const zipSize = document.getElementById('zip-size');

        if (downloadArea) downloadArea.classList.remove('hidden');
        if (clipCount) clipCount.textContent = `클립 수: ${data.clipCount}개`;
        if (zipSize) zipSize.textContent = `파일 크기: ${data.fileSizeMB}MB`;

        DramaUtils.showStatus(`${data.clipCount}개 씬 클립 생성 완료! ZIP 다운로드 가능`, 'success');

      } else {
        throw new Error(data.error || '클립 생성 실패');
      }

    } catch (error) {
      console.error('[Step4] 클립 생성 오류:', error);
      DramaUtils.showStatus(`클립 생성 실패: ${error.message}`, 'error');

      const progressText = document.getElementById('clip-progress-text');
      if (progressText) progressText.textContent = `오류: ${error.message}`;

    } finally {
      this.isCreating = false;
      if (btn) {
        btn.innerHTML = originalText || '<span class="btn-icon">🎬</span> 씬별 클립 생성하기';
        btn.disabled = false;
      }
    }
  },

  // ZIP 다운로드 트리거
  triggerDownload() {
    if (!this.zipData) {
      DramaUtils.showStatus('먼저 클립을 생성해주세요.', 'error');
      return;
    }

    try {
      // Base64 데이터 URL → Blob
      const base64Data = this.zipData.split(',')[1];
      const binaryData = atob(base64Data);
      const bytes = new Uint8Array(binaryData.length);
      for (let i = 0; i < binaryData.length; i++) {
        bytes[i] = binaryData.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: 'application/zip' });

      // 다운로드 링크 생성
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `drama_scenes_${new Date().toISOString().slice(0, 10)}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      DramaUtils.showStatus('ZIP 다운로드 시작!', 'success');

    } catch (error) {
      console.error('[Step4] 다운로드 오류:', error);
      DramaUtils.showStatus('다운로드 실패: ' + error.message, 'error');
    }
  },

  // 세션에서 복원
  restoreFromSession() {
    console.log('[Step4] 세션 복원 시도');
    this.renderClipsList();
  }
};

// 전역 등록
window.DramaStep4 = DramaStep4;
