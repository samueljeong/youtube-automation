/**
 * Drama Lab - Step 2: 이미지 생성
 * 초기화됨: 2024-11-28
 */

// Step2 모듈
window.DramaStep2 = {
  // 상태
  analysisResult: null,
  generatedImages: {},
  isAnalyzing: false,
  isGenerating: false,

  init() {
    console.log('[Step2] 이미지 생성 모듈 초기화');
  },

  // 설정값 가져오기
  getConfig() {
    return {
      imageModel: document.getElementById('image-model')?.value || 'gemini',
      imageStyle: document.getElementById('image-style')?.value || 'realistic',
      imageRatio: document.getElementById('image-ratio')?.value || '16:9'
    };
  },

  // Step1 대본 데이터 가져오기
  getStep1Script() {
    const step1Data = DramaSession.getStepData('step1');
    if (step1Data?.content) {
      return step1Data.content;
    }
    return null;
  },

  // 대본 분석 및 이미지 준비
  async analyzeAndPrepare() {
    if (this.isAnalyzing) {
      DramaUtils.showStatus('이미 분석 중입니다...', 'warning');
      return;
    }

    const script = this.getStep1Script();
    if (!script) {
      DramaUtils.showStatus('먼저 Step 1에서 대본을 생성해주세요.', 'error');
      return;
    }

    this.isAnalyzing = true;
    const btn = document.getElementById('btn-analyze-script');
    const originalText = btn?.innerHTML;

    try {
      if (btn) {
        btn.innerHTML = '<span class="btn-icon">⏳</span> 분석 중...';
        btn.disabled = true;
      }

      DramaUtils.showLoading('대본을 분석하고 있습니다...', '등장인물과 씬 정보를 추출 중 (약 30초 소요)');

      console.log('[Step2] 대본 분석 시작');

      const response = await fetch('/api/drama/analyze-characters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script: script })
      });

      const data = await response.json();
      console.log('[Step2] 분석 응답:', data);

      if (!data.ok) {
        throw new Error(data.error || '대본 분석에 실패했습니다.');
      }

      // 결과 저장 (API가 characters, scenes를 직접 반환)
      this.analysisResult = {
        characters: data.characters || [],
        scenes: data.scenes || []
      };
      DramaSession.setStepData('step2_analysis', this.analysisResult);

      // 결과 표시
      this.displayAnalysisResult(this.analysisResult);

      DramaUtils.showStatus('대본 분석 완료! 이미지를 생성할 준비가 되었습니다.', 'success');

    } catch (error) {
      console.error('[Step2] 분석 오류:', error);
      DramaUtils.showStatus(`오류: ${error.message}`, 'error');
    } finally {
      if (btn) {
        btn.innerHTML = originalText;
        btn.disabled = false;
      }
      this.isAnalyzing = false;
      DramaUtils.hideLoading();
    }
  },

  // 분석 결과 표시
  displayAnalysisResult(result) {
    // 캐릭터 분석 영역
    const characterArea = document.getElementById('character-analysis');
    const characterList = document.getElementById('character-list');

    if (characterArea && characterList && result.characters) {
      characterList.innerHTML = result.characters.map((char, idx) => `
        <div class="character-card" data-idx="${idx}">
          <div class="character-placeholder">
            <span class="placeholder-icon">👤</span>
          </div>
          <div class="character-info">
            <h4>${DramaUtils.escapeHtml(char.name)}</h4>
            <p>${DramaUtils.escapeHtml(char.description || '')}</p>
          </div>
          <button class="btn-small" onclick="DramaStep2.generateCharacterImage(${idx})">
            이미지 생성
          </button>
        </div>
      `).join('');
      characterArea.classList.remove('hidden');
    }

    // 씬 이미지 영역
    const sceneArea = document.getElementById('scene-images-area');
    const sceneList = document.getElementById('scene-image-list');

    if (sceneArea && sceneList && result.scenes) {
      sceneList.innerHTML = result.scenes.map((scene, idx) => `
        <div class="scene-card" data-idx="${idx}">
          <div class="scene-image-placeholder" id="scene-image-${idx}">
            <span class="placeholder-icon">🎬</span>
            <span class="placeholder-text">씬 ${idx + 1}</span>
          </div>
          <div class="scene-info">
            <h4>씬 ${idx + 1}: ${DramaUtils.escapeHtml(scene.title || '')}</h4>
            <p class="scene-location">${DramaUtils.escapeHtml(scene.location || '')}</p>
            <p class="scene-desc">${DramaUtils.escapeHtml(scene.description || '')}</p>
          </div>
          <div class="scene-actions">
            <input type="checkbox" id="scene-select-${idx}" class="scene-select">
            <button class="btn-small" onclick="DramaStep2.generateSceneImage(${idx})">
              이미지 생성
            </button>
          </div>
        </div>
      `).join('');
      sceneArea.classList.remove('hidden');
    }

    // 다음 단계 버튼 표시
    const nextButtons = document.getElementById('step2-next');
    if (nextButtons) {
      nextButtons.classList.remove('hidden');
    }
  },

  // 캐릭터 이미지 생성
  async generateCharacterImage(idx) {
    if (!this.analysisResult?.characters?.[idx]) {
      DramaUtils.showStatus('캐릭터 정보가 없습니다.', 'error');
      return;
    }

    const character = this.analysisResult.characters[idx];
    const config = this.getConfig();

    DramaUtils.showStatus(`${character.name} 이미지 생성 중...`, 'info');

    try {
      const response = await fetch('/api/drama/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: character.imagePrompt,
          size: config.imageRatio === '16:9' ? '1792x1024' : '1024x1024',
          imageProvider: config.imageModel
        })
      });

      const data = await response.json();

      if (data.ok && data.imageUrl) {
        // 이미지 표시
        const card = document.querySelector(`.character-card[data-idx="${idx}"]`);
        if (card) {
          const placeholder = card.querySelector('.character-placeholder');
          if (placeholder) {
            placeholder.innerHTML = `<img src="${data.imageUrl}" alt="${character.name}" class="character-image">`;
          }
        }
        this.generatedImages[`char_${idx}`] = data.imageUrl;
        DramaUtils.showStatus(`${character.name} 이미지 생성 완료!`, 'success');
      } else {
        throw new Error(data.error || '이미지 생성 실패');
      }
    } catch (error) {
      console.error('[Step2] 캐릭터 이미지 생성 오류:', error);
      DramaUtils.showStatus(`오류: ${error.message}`, 'error');
    }
  },

  // 씬 이미지 생성
  async generateSceneImage(idx) {
    if (!this.analysisResult?.scenes?.[idx]) {
      DramaUtils.showStatus('씬 정보가 없습니다.', 'error');
      return;
    }

    const scene = this.analysisResult.scenes[idx];
    const config = this.getConfig();

    DramaUtils.showStatus(`씬 ${idx + 1} 이미지 생성 중...`, 'info');

    try {
      const response = await fetch('/api/drama/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: scene.backgroundPrompt,
          size: config.imageRatio === '16:9' ? '1792x1024' : (config.imageRatio === '9:16' ? '1024x1792' : '1024x1024'),
          imageProvider: config.imageModel
        })
      });

      const data = await response.json();

      if (data.ok && data.imageUrl) {
        // 이미지 표시
        const placeholder = document.getElementById(`scene-image-${idx}`);
        if (placeholder) {
          placeholder.innerHTML = `<img src="${data.imageUrl}" alt="씬 ${idx + 1}" class="scene-image">`;
          placeholder.classList.add('has-image');
        }
        this.generatedImages[`scene_${idx}`] = data.imageUrl;

        // 세션에도 저장
        this.saveGeneratedImagesToSession();

        DramaUtils.showStatus(`씬 ${idx + 1} 이미지 생성 완료!`, 'success');
      } else {
        throw new Error(data.error || '이미지 생성 실패');
      }
    } catch (error) {
      console.error('[Step2] 씬 이미지 생성 오류:', error);
      DramaUtils.showStatus(`오류: ${error.message}`, 'error');
    }
  },

  // 생성된 이미지를 세션에 저장
  saveGeneratedImagesToSession() {
    const imageUrls = [];
    // scene_0, scene_1, ... 순서대로 추출
    const keys = Object.keys(this.generatedImages)
      .filter(k => k.startsWith('scene_'))
      .sort((a, b) => parseInt(a.split('_')[1]) - parseInt(b.split('_')[1]));

    for (const key of keys) {
      imageUrls.push(this.generatedImages[key]);
    }

    DramaSession.setStepData('step2_images', {
      images: imageUrls,
      generatedAt: new Date().toISOString()
    });

    console.log('[Step2] 이미지 세션 저장:', imageUrls.length, '개');
  },

  // 모든 이미지 생성
  async generateAllImages() {
    if (!this.analysisResult?.scenes?.length) {
      DramaUtils.showStatus('먼저 대본을 분석해주세요.', 'error');
      return;
    }

    if (this.isGenerating) {
      DramaUtils.showStatus('이미 생성 중입니다...', 'warning');
      return;
    }

    this.isGenerating = true;
    const total = this.analysisResult.scenes.length;

    DramaUtils.showLoading('모든 씬 이미지 생성 중...', `0 / ${total} 완료`);

    try {
      for (let i = 0; i < total; i++) {
        DramaUtils.showLoading('모든 씬 이미지 생성 중...', `${i} / ${total} 완료`);
        await this.generateSceneImage(i);
        // API 호출 간격
        if (i < total - 1) {
          await new Promise(r => setTimeout(r, 2000));
        }
      }
      DramaUtils.showStatus(`모든 씬 이미지 생성 완료! (${total}개)`, 'success');
    } catch (error) {
      console.error('[Step2] 전체 이미지 생성 오류:', error);
      DramaUtils.showStatus(`오류: ${error.message}`, 'error');
    } finally {
      this.isGenerating = false;
      DramaUtils.hideLoading();
    }
  },

  // 선택된 씬 재생성
  async regenerateSelected() {
    const checkboxes = document.querySelectorAll('.scene-select:checked');
    if (checkboxes.length === 0) {
      DramaUtils.showStatus('재생성할 씬을 선택해주세요.', 'warning');
      return;
    }

    for (const checkbox of checkboxes) {
      const idx = parseInt(checkbox.id.replace('scene-select-', ''));
      await this.generateSceneImage(idx);
      await new Promise(r => setTimeout(r, 2000));
    }

    DramaUtils.showStatus(`선택된 ${checkboxes.length}개 씬 재생성 완료!`, 'success');
  },

  // 세션에서 데이터 복원
  restore(data) {
    if (data) {
      this.analysisResult = data;
      this.displayAnalysisResult(data);
    }
  }
};
