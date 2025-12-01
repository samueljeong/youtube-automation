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

    // 수동 입력 모드인 경우
    if (step1Data?.type === 'manual') {
      return step1Data;
    }

    // 기존 자동 생성 모드
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

    const step1Data = DramaSession.getStepData('step1');

    // AI 분석 모드 처리 (새로운 씬/샷 구조)
    if (step1Data?.type === 'analyzed') {
      console.log('[Step2] AI 분석 모드 - 씬/샷 구조 사용');
      this.prepareAnalyzedMode(step1Data);
      return;
    }

    // 수동 입력 모드 처리
    if (step1Data?.type === 'manual') {
      console.log('[Step2] 수동 입력 모드 - 이미지 프롬프트 사용');
      this.prepareManualMode(step1Data);
      return;
    }

    // 기존 자동 생성 모드
    const script = this.getStep1Script();
    if (!script) {
      DramaUtils.showStatus('먼저 Step 1에서 대본을 입력해주세요.', 'error');
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

      // Step1에서 저장된 duration 가져오기
      const duration = step1Data?.config?.duration || '10min';

      console.log('[Step2] 대본 분석 시작 (duration:', duration, ')');

      const response = await fetch('/api/drama/analyze-characters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script: script, duration: duration })
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

  // 수동 입력 모드 처리 (Step1에서 이미지 프롬프트가 제공된 경우)
  prepareManualMode(step1Data) {
    console.log('[Step2] 수동 입력 모드 준비');

    const scenes = step1Data.scenes || [];
    const characterInfo = step1Data.characterInfo || '';

    console.log(`[Step2] 캐릭터 정보: ${characterInfo.substring(0, 50)}...`);
    console.log(`[Step2] 씬 ${scenes.length}개 로드됨`);

    // 씬별 이미지 프롬프트 로그
    scenes.forEach((scene, i) => {
      if (scene.imagePrompt) {
        console.log(`[Step2] 씬 ${i + 1} 프롬프트:`, scene.imagePrompt.substring(0, 60) + '...');
      }
    });

    // 주인공 정보에서 이름 추출 시도
    let protagonistName = '주인공';
    const nameMatch = characterInfo.match(/([가-힣]+)/);  // 첫 번째 한글 이름
    if (nameMatch) {
      protagonistName = nameMatch[1];
    }

    // 씬 데이터 생성 - 각 씬에서 직접 이미지 프롬프트 사용
    const analysisScenes = scenes.map((scene, idx) => {
      // 씬에서 직접 이미지 프롬프트 가져오기
      let prompt = scene.imagePrompt || '';

      if (!prompt) {
        // 기본 프롬프트 생성 (주인공 정보 기반)
        const gender = step1Data.config?.protagonistGender || 'female';
        const koreanDesc = gender === 'female'
          ? 'Korean elderly grandmother, 70s, warm smile, traditional Korean hanok setting'
          : 'Korean elderly grandfather, 70s, wise expression, traditional Korean setting';
        prompt = `${koreanDesc}, scene ${idx + 1}, cinematic lighting, nostalgic 1980s film style`;
      }

      return {
        sceneId: scene.id || `scene_${idx + 1}`,
        sceneNumber: idx + 1,
        description: scene.narration?.substring(0, 100) || `씬 ${idx + 1}`,
        imagePrompt: prompt  // 씬에서 직접 가져온 프롬프트
      };
    });

    // 결과 저장
    this.analysisResult = {
      characters: [{
        name: protagonistName,
        description: characterInfo,
        imagePrompt: ''  // 캐릭터 전용 프롬프트는 별도로 사용 안함
      }],
      scenes: analysisScenes
    };

    DramaSession.setStepData('step2_analysis', this.analysisResult);

    // UI 표시
    this.displayAnalysisResult(this.analysisResult);

    DramaUtils.showStatus(`수동 입력 모드: ${analysisScenes.length}개 씬 준비 완료`, 'success');
  },

  // AI 분석 모드 처리 (새로운 씬/샷 구조)
  prepareAnalyzedMode(step1Data) {
    console.log('[Step2] AI 분석 모드 준비');

    const { character, scenes } = step1Data;

    console.log(`[Step2] 캐릭터: ${character?.name || '?'}`);
    console.log(`[Step2] 씬 ${scenes?.length || 0}개 로드됨`);

    // 모든 샷을 플랫하게 펼침 (각 샷 = 하나의 이미지)
    const flatShots = [];
    let shotIndex = 0;

    scenes?.forEach((scene, sceneIdx) => {
      const shots = scene.shots || [];
      console.log(`[Step2] 씬 ${sceneIdx + 1}: ${scene.title} - ${shots.length}개 샷`);

      shots.forEach((shot, shotIdx) => {
        flatShots.push({
          sceneId: scene.sceneId,
          sceneTitle: scene.title,
          sceneNumber: sceneIdx + 1,
          shotId: shot.shotId,
          shotNumber: shotIdx + 1,
          imagePrompt: shot.imagePrompt || '',
          narration: shot.narration || '',
          globalIndex: shotIndex++
        });
      });
    });

    const totalShots = flatShots.length;
    console.log(`[Step2] 총 ${totalShots}개 샷 준비됨`);

    // 캐릭터 정보 구성
    const characterData = {
      name: character?.name || '주인공',
      description: `${character?.age || '?'}세 ${character?.gender === 'female' ? '여성' : '남성'}`,
      imagePrompt: character?.appearance || '',
      gender: character?.gender || 'female'
    };

    // 씬 데이터 생성 (플랫 샷 배열)
    const analysisScenes = flatShots.map((shot, idx) => ({
      sceneId: shot.sceneId,
      sceneNumber: shot.sceneNumber,
      shotId: shot.shotId,
      shotNumber: shot.shotNumber,
      title: `${shot.sceneTitle} - 샷 ${shot.shotNumber}`,
      description: shot.narration?.substring(0, 100) || `샷 ${idx + 1}`,
      imagePrompt: shot.imagePrompt,
      narration: shot.narration
    }));

    // 결과 저장
    this.analysisResult = {
      characters: [characterData],
      scenes: analysisScenes,
      type: 'analyzed'  // 타입 표시
    };

    DramaSession.setStepData('step2_analysis', this.analysisResult);

    // UI 표시 (샷 기반)
    this.displayAnalyzedResult(this.analysisResult);

    DramaUtils.showStatus(`AI 분석 모드: ${scenes?.length || 0}개 씬, ${totalShots}개 샷 준비 완료`, 'success');
  },

  // AI 분석 결과 표시 (샷 기반 UI)
  displayAnalyzedResult(result) {
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

    // 씬/샷 이미지 영역
    const sceneArea = document.getElementById('scene-images-area');
    const sceneList = document.getElementById('scene-image-list');

    if (sceneArea && sceneList && result.scenes) {
      sceneList.innerHTML = result.scenes.map((scene, idx) => `
        <div class="scene-card shot-card" data-idx="${idx}">
          <div class="scene-image-placeholder" id="scene-image-${idx}">
            <span class="placeholder-icon">📷</span>
            <span class="placeholder-text">샷 ${idx + 1}</span>
          </div>
          <div class="scene-info">
            <h4>${DramaUtils.escapeHtml(scene.title || `샷 ${idx + 1}`)}</h4>
            <p class="scene-desc">${DramaUtils.escapeHtml(scene.narration?.substring(0, 80) || '')}...</p>
            <p class="prompt-preview" title="${DramaUtils.escapeHtml(scene.imagePrompt || '')}">
              🖼️ ${DramaUtils.escapeHtml((scene.imagePrompt || '').substring(0, 50))}...
            </p>
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

  // 씬 이미지 생성 (main_character 정보 포함)
  async generateSceneImage(idx) {
    if (!this.analysisResult?.scenes?.[idx]) {
      DramaUtils.showStatus('씬 정보가 없습니다.', 'error');
      return;
    }

    const scene = this.analysisResult.scenes[idx];
    const config = this.getConfig();
    const characters = this.analysisResult.characters || [];

    // 주인공(첫 번째 캐릭터) 정보 가져오기
    const mainCharacter = characters[0];

    // 씬 프롬프트에 주인공 정보를 강제로 결합
    // 수동 모드: imagePrompt, 자동 모드: backgroundPrompt
    let scenePrompt = scene.imagePrompt || scene.backgroundPrompt || '';
    let enhancedPrompt = scenePrompt;

    if (mainCharacter && scenePrompt) {
      // 캐릭터 일관성 규칙: 주인공 정보를 프롬프트 맨 앞에 배치
      const characterConsistencyPrefix = this.buildCharacterConsistencyPrompt(mainCharacter);
      enhancedPrompt = `${characterConsistencyPrefix} Scene: ${scenePrompt}`;
      console.log('[Step2] 주인공 정보 결합 프롬프트 생성');
    }

    console.log(`[Step2] 씬 ${idx + 1} 프롬프트:`, enhancedPrompt.substring(0, 100) + '...');

    DramaUtils.showStatus(`씬 ${idx + 1} 이미지 생성 중...`, 'info');

    try {
      const response = await fetch('/api/drama/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: enhancedPrompt,
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

  // 모든 이미지 생성 (병렬 처리 지원)
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
    const config = this.getConfig();
    const characters = this.analysisResult.characters || [];
    const mainCharacter = characters[0];

    // 🚀 병렬 처리: 동시 요청 제한 (이미지 API rate limit 대응)
    const CONCURRENT_LIMIT = 2; // 이미지 생성은 무거우므로 2개씩
    console.log(`[Step2] 🚀 병렬 이미지 생성 시작: ${total}개 씬, 동시 ${CONCURRENT_LIMIT}개`);

    DramaUtils.showLoading('모든 씬 이미지 생성 중...', `0 / ${total} 완료 (병렬 처리)`);

    // 단일 이미지 생성 함수
    const generateSingleImage = async (sceneIdx) => {
      const scene = this.analysisResult.scenes[sceneIdx];
      if (!scene) return { success: false, index: sceneIdx, error: '씬 정보 없음' };

      // 씬 프롬프트에 주인공 정보를 강제로 결합
      // 수동 모드: imagePrompt, 자동 모드: backgroundPrompt
      let scenePrompt = scene.imagePrompt || scene.backgroundPrompt || '';
      let enhancedPrompt = scenePrompt;
      if (mainCharacter && scenePrompt) {
        const characterConsistencyPrefix = this.buildCharacterConsistencyPrompt(mainCharacter);
        enhancedPrompt = `${characterConsistencyPrefix} Scene: ${scenePrompt}`;
      }
      console.log(`[Step2] 병렬 생성 - 씬 ${sceneIdx + 1} 프롬프트:`, scenePrompt.substring(0, 50) + '...');

      try {
        const response = await fetch('/api/drama/generate-image', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: enhancedPrompt,
            size: config.imageRatio === '16:9' ? '1792x1024' : (config.imageRatio === '9:16' ? '1024x1792' : '1024x1024'),
            imageProvider: config.imageModel
          })
        });

        const data = await response.json();

        if (data.ok && data.imageUrl) {
          return { success: true, index: sceneIdx, imageUrl: data.imageUrl };
        } else {
          return { success: false, index: sceneIdx, error: data.error || '이미지 생성 실패' };
        }
      } catch (err) {
        console.error(`[Step2] 씬 ${sceneIdx + 1} 이미지 생성 오류:`, err);
        return { success: false, index: sceneIdx, error: err.message };
      }
    };

    try {
      const results = [];

      // 배치 처리 (동시 실행 제한)
      for (let i = 0; i < total; i += CONCURRENT_LIMIT) {
        const batchIndices = [];
        for (let j = i; j < Math.min(i + CONCURRENT_LIMIT, total); j++) {
          batchIndices.push(j);
        }

        DramaUtils.showLoading('모든 씬 이미지 생성 중...', `${Math.min(i + CONCURRENT_LIMIT, total)} / ${total} 완료 (병렬 처리)`);

        // 배치 병렬 실행
        const batchPromises = batchIndices.map(idx => generateSingleImage(idx));
        const batchResults = await Promise.all(batchPromises);
        results.push(...batchResults);

        // 성공한 이미지 바로 UI에 반영
        for (const result of batchResults) {
          if (result.success) {
            const placeholder = document.getElementById(`scene-image-${result.index}`);
            if (placeholder) {
              placeholder.innerHTML = `<img src="${result.imageUrl}" alt="씬 ${result.index + 1}" class="scene-image">`;
              placeholder.classList.add('has-image');
            }
            this.generatedImages[`scene_${result.index}`] = result.imageUrl;
          }
        }

        // 배치 간 대기 (rate limit 방지)
        if (i + CONCURRENT_LIMIT < total) {
          await new Promise(r => setTimeout(r, 1000));
        }
      }

      // 세션에 저장
      this.saveGeneratedImagesToSession();

      const successCount = results.filter(r => r.success).length;
      const failedCount = results.filter(r => !r.success).length;

      if (failedCount > 0) {
        DramaUtils.showStatus(`이미지 생성 완료! (${successCount}개 성공, ${failedCount}개 실패)`, 'warning');
      } else {
        DramaUtils.showStatus(`모든 씬 이미지 생성 완료! (${total}개) 🚀 병렬 처리`, 'success');
      }

      // 썸네일 생성 섹션 표시
      this.showThumbnailSection();
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

  // 캐릭터 일관성 프롬프트 생성
  buildCharacterConsistencyPrompt(mainCharacter) {
    // 주인공 정보에서 이름, 나이, 성별, 외모 특징 추출
    const name = mainCharacter.name || '';
    const description = mainCharacter.description || '';
    const imagePrompt = mainCharacter.imagePrompt || '';

    // 한국인 시니어 관련 키워드 감지
    const descLower = description.toLowerCase();
    const isElderly = /할머니|할아버지|70|80|노인|시니어|elderly|grandmother|grandfather/i.test(description);
    const isGrandmother = /할머니|grandmother|halmeoni|여성|woman/i.test(description);
    const isGrandfather = /할아버지|grandfather|harabeoji|남성|man/i.test(description);

    let consistencyPrompt = '';

    if (isElderly && isGrandmother) {
      // 한국 할머니 캐릭터 일관성 프롬프트
      consistencyPrompt = `CRITICAL CHARACTER CONSISTENCY: The same Korean grandmother main character named ${name}. ` +
        `Authentic Korean halmeoni (grandmother) from South Korea with pure Korean ethnicity, ` +
        `distinct Korean elderly facial features: round face shape, single eyelids (monolid) or narrow double eyelids typical of Korean elderly, ` +
        `flat nose bridge, Korean skin tone (light to medium beige with warm undertones), ` +
        `natural Korean aging patterns with laugh lines, permed short gray/white hair typical of Korean grandmothers. ` +
        `NOT a young woman, clearly elderly. ${imagePrompt ? `Character details: ${imagePrompt}` : ''}`;
    } else if (isElderly && isGrandfather) {
      // 한국 할아버지 캐릭터 일관성 프롬프트
      consistencyPrompt = `CRITICAL CHARACTER CONSISTENCY: The same Korean grandfather main character named ${name}. ` +
        `Authentic Korean harabeoji (grandfather) from South Korea with pure Korean ethnicity, ` +
        `distinct Korean elderly facial features: angular Korean face shape, single eyelids or hooded eyes typical of Korean elderly men, ` +
        `Korean skin tone, weathered kind face with Korean aging characteristics, ` +
        `balding or short gray hair typical of Korean grandfathers. ` +
        `NOT a young person, clearly elderly. ${imagePrompt ? `Character details: ${imagePrompt}` : ''}`;
    } else if (imagePrompt) {
      // 일반 캐릭터 - 기존 이미지 프롬프트 사용
      consistencyPrompt = `CRITICAL CHARACTER CONSISTENCY: The same main character named ${name}. ` +
        `${imagePrompt} Must maintain consistent appearance across all scenes.`;
    } else {
      // 기본 프롬프트
      consistencyPrompt = `Main character: ${name}. ${description}`;
    }

    // 시대 감성 추가 (1970~80년대 한국)
    const vintageSuffix = ` Setting: South Korea, 1970s-1980s nostalgic atmosphere, vintage Korean film photography aesthetic, slightly faded warm colors, film grain texture.`;

    return consistencyPrompt + vintageSuffix;
  },

  // 세션에서 데이터 복원
  restore(data) {
    if (data) {
      this.analysisResult = data;
      this.displayAnalysisResult(data);
    }
  },

  // ========== 썸네일 생성 기능 ==========

  // 썸네일 섹션 표시
  showThumbnailSection() {
    const section = document.getElementById('thumbnail-generate-section');
    if (section) {
      section.classList.remove('hidden');
    }

    // AI 분석 결과에서 thumbnailTitle이 있으면 자동 입력
    const step1Data = DramaSession.getStepData('step1');
    if (step1Data?.thumbnailTitle) {
      const input = document.getElementById('thumbnail-title-input');
      if (input) {
        input.value = step1Data.thumbnailTitle.replace(/\\n/g, ' ');
      }
    }
  },

  // 썸네일 생성
  async generateThumbnail() {
    const titleInput = document.getElementById('thumbnail-title-input');
    const styleSelect = document.getElementById('thumbnail-style');
    const thumbnailTitle = titleInput?.value || '';
    const style = styleSelect?.value || 'emotional';

    // 대본 데이터 가져오기
    const step1Data = DramaSession.getStepData('step1');
    let script = '';

    if (step1Data?.type === 'analyzed' && step1Data.scenes) {
      // AI 분석 모드: 씬들의 나레이션 합치기
      script = step1Data.scenes.map(scene =>
        (scene.shots || []).map(shot => shot.narration || '').join(' ')
      ).join('\n');
    } else if (step1Data?.content) {
      script = typeof step1Data.content === 'string'
        ? step1Data.content
        : JSON.stringify(step1Data.content);
    }

    if (!script) {
      DramaUtils.showStatus('대본 데이터가 없습니다. Step1을 먼저 완료해주세요.', 'error');
      return;
    }

    DramaUtils.showLoading('썸네일 생성 중...', 'AI가 클릭을 유도하는 썸네일을 생성합니다');

    try {
      const config = this.getConfig();

      const response = await fetch('/api/drama/generate-thumbnail', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: script.substring(0, 5000),  // 대본 앞부분만
          title: thumbnailTitle,
          style: style,
          provider: config.imageModel  // gemini, dalle, flux
        })
      });

      const data = await response.json();

      if (data.ok && data.imageUrl) {
        // 썸네일 미리보기 표시
        const preview = document.getElementById('thumbnail-preview');
        const thumbnailImg = document.getElementById('thumbnail-image');
        const textPreview = document.getElementById('thumbnail-text-preview');

        if (thumbnailImg) {
          thumbnailImg.src = data.imageUrl;
        }
        if (textPreview) {
          textPreview.textContent = data.thumbnailText || thumbnailTitle || '썸네일';
        }
        if (preview) {
          preview.classList.remove('hidden');
        }

        // 세션에 저장
        DramaSession.setStepData('thumbnail', {
          imageUrl: data.imageUrl,
          text: data.thumbnailText || thumbnailTitle,
          style: style,
          generatedAt: new Date().toISOString()
        });

        DramaUtils.showStatus('썸네일 생성 완료!', 'success');
      } else {
        throw new Error(data.error || '썸네일 생성 실패');
      }
    } catch (error) {
      console.error('[Step2] 썸네일 생성 오류:', error);
      DramaUtils.showStatus(`썸네일 생성 실패: ${error.message}`, 'error');
    } finally {
      DramaUtils.hideLoading();
    }
  },

  // 썸네일 재생성
  async regenerateThumbnail() {
    await this.generateThumbnail();
  },

  // 썸네일 다운로드
  downloadThumbnail() {
    const thumbnailImg = document.getElementById('thumbnail-image');
    if (!thumbnailImg?.src) {
      DramaUtils.showStatus('다운로드할 썸네일이 없습니다.', 'error');
      return;
    }

    const link = document.createElement('a');
    link.href = thumbnailImg.src;
    link.download = `thumbnail_${Date.now()}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    DramaUtils.showStatus('썸네일 다운로드 시작!', 'success');
  }
};
