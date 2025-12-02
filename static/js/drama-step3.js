/**
 * Drama Lab - Step 3: TTS 음성합성
 * 초기화됨: 2024-11-28
 */

// Step3 모듈
window.DramaStep3 = {
  // 상태
  generatedAudios: [],
  isGenerating: false,
  currentAudioPlayer: null,

  init() {
    console.log('[Step3] TTS 음성합성 모듈 초기화');
  },

  // 설정값 가져오기
  getConfig() {
    // Step1 설정에서 쇼츠 여부 확인
    const step1Data = DramaSession.getStepData('step1');
    const contentType = step1Data?.config?.contentType || 'drama';
    const duration = step1Data?.config?.duration || '5min';
    const isShorts = contentType === 'shorts' || ['30s', '60s'].includes(duration);

    // 쇼츠일 경우 말하기 속도 자동 조절 (1.15배속)
    let speechRate = parseFloat(document.getElementById('speech-rate')?.value) || 0.95;
    if (isShorts) {
      speechRate = 1.15;  // 쇼츠는 빠른 템포
      console.log('[Step3] 쇼츠 모드 - TTS 속도 1.15배속 적용');
    }

    return {
      ttsEngine: document.getElementById('tts-engine')?.value || 'google',
      voiceStyle: document.getElementById('voice-style')?.value || 'warm',
      speechRate: speechRate,
      isShorts: isShorts
    };
  },

  // Step1 대본에서 순수 나레이션 텍스트만 가져오기 (JSON 메타데이터 제외)
  getScriptTexts() {
    const step1Data = DramaSession.getStepData('step1');
    console.log('[Step3] step1Data 전체:', step1Data);

    // AI 분석 모드 처리 (type: 'analyzed' - 새로운 씬/샷 구조)
    if (step1Data?.type === 'analyzed' && step1Data.scenes) {
      console.log('[Step3] AI 분석 모드 - 씬/샷 구조에서 나레이션 추출');
      const scripts = [];

      step1Data.scenes.forEach((scene, sceneIdx) => {
        const shots = scene.shots || [];
        shots.forEach((shot, shotIdx) => {
          if (shot.narration && shot.narration.length > 0) {
            scripts.push({
              id: shot.shotId || `shot_${sceneIdx + 1}_${shotIdx + 1}`,
              text: shot.narration
            });
          }
        });
      });

      console.log(`[Step3] AI 분석 모드에서 ${scripts.length}개 나레이션 추출`);
      return scripts.filter(s => s.text && s.text.length > 0);
    }

    // 수동 입력 모드 처리 (type: 'manual')
    if (step1Data?.type === 'manual' && step1Data.scenes) {
      console.log('[Step3] 수동 입력 모드 - scenes 배열 사용');
      return step1Data.scenes.map(scene => ({
        id: scene.id,
        text: scene.narration
      })).filter(s => s.text && s.text.length > 0);
    }

    // 기존 자동 생성 모드 처리
    if (!step1Data?.content) {
      console.log('[Step3] step1Data.content가 없음');
      return null;
    }

    const content = step1Data.content;
    console.log('[Step3] content 타입:', typeof content);
    console.log('[Step3] content 길이:', content.length);
    console.log('[Step3] content 시작 100자:', content.substring(0, 100));

    const scenes = [];

    // 1. JSON 형식인지 확인하고 파싱 시도
    let jsonData = null;
    try {
      // JSON 문자열이면 파싱
      if (typeof content === 'string' && content.trim().startsWith('{')) {
        jsonData = JSON.parse(content);
        console.log('[Step3] JSON 대본 감지됨, 최상위 키들:', Object.keys(jsonData));
      } else if (typeof content === 'object') {
        // 이미 객체인 경우
        jsonData = content;
        console.log('[Step3] content가 이미 객체임, 키들:', Object.keys(jsonData));
      }
    } catch (e) {
      console.log('[Step3] JSON 파싱 실패, 텍스트로 처리:', e.message);
    }

    // 2. JSON 형식이면 storyline/scenes에서 나레이션만 추출
    if (jsonData) {
      const narrationTexts = this.extractNarrationFromJson(jsonData);
      if (narrationTexts && narrationTexts.length > 0) {
        narrationTexts.forEach((text, idx) => {
          scenes.push({
            id: `scene_${idx + 1}`,
            text: text
          });
        });
        console.log('[Step3] JSON에서 추출된 나레이션 씬:', scenes.length, '개');
        return scenes;
      }
    }

    // 3. 텍스트 형식 처리 (기존 로직)
    // 메타 설명 패턴 필터링 (TTS에서 읽으면 안 되는 부분)
    const metaPatterns = [
      /^#+\s*주인공\s*설정.*/gm,
      /^#+\s*스토리\s*컨셉.*/gm,
      /^#+\s*배경.*/gm,
      /^-\s*이름[:：].*/gm,
      /^-\s*나이[:：].*/gm,
      /^-\s*직업[:：].*/gm,
      /^-\s*성격\s*특징.*/gm,
      /^-\s*현재\s*상황.*/gm,
      /^-\s*한\s*줄\s*요약.*/gm,
      /^-\s*핵심\s*메시지.*/gm,
      /^-\s*감정\s*흐름.*/gm,
      /^-\s*시대\/장소.*/gm,
      /^-\s*분위기.*/gm,
      /^\d+\.\s*주인공\s*설정.*/gm,
      /^\d+\.\s*스토리\s*컨셉.*/gm,
      /^\d+\.\s*배경.*/gm,
      /^【.*】$/gm,
      /^\[.*\]$/gm,
      // JSON 키 패턴 추가
      /^"metadata":.*/gm,
      /^"title":.*/gm,
      /^"duration":.*/gm,
      /^"target_age":.*/gm,
      /^"highlight":.*/gm,
      /^"storyline":.*/gm,
    ];

    // 메타 설명 제거
    let cleanedContent = content;
    for (const pattern of metaPatterns) {
      cleanedContent = cleanedContent.replace(pattern, '');
    }

    // 4. 씬/장면 단위로 분할
    const scenePatterns = /(?=씬\s*\d|Scene\s*\d|장면\s*\d|###\s*장면)/i;
    const parts = cleanedContent.split(scenePatterns);

    if (parts.length > 1) {
      parts.forEach((part, idx) => {
        // 순수 나레이션만 추출 (대사, 이야기 본문)
        const narration = this.extractNarrationFromScene(part);
        if (narration && narration.length > 30) {
          scenes.push({
            id: `scene_${idx + 1}`,
            text: narration
          });
        }
      });
    }

    // 씬 분할 실패 시 전체에서 나레이션 추출
    if (scenes.length === 0) {
      const narration = this.extractNarrationFromScene(cleanedContent);
      if (narration && narration.length > 30) {
        scenes.push({
          id: 'scene_1',
          text: narration
        });
      }
    }

    console.log('[Step3] 추출된 나레이션 씬:', scenes.length, '개');
    return scenes;
  },

  // JSON 대본에서 순수 나레이션만 추출 (메타데이터, 타이틀 제외)
  // ⚠️ 우선순위: tts_text > narration > text > content
  extractNarrationFromJson(jsonData) {
    const narrations = [];

    console.log('[Step3] JSON 파싱 시작, 키들:', Object.keys(jsonData));
    console.log('[Step3] JSON 전체 구조 (간략):', JSON.stringify(jsonData).substring(0, 500));

    // 1. scenes 배열 찾기 (여러 경로 지원) - 먼저 씬 추출
    // 백엔드 JSON 구조: jsonData.script.scenes 또는 jsonData.scenes
    let scenesArray = null;

    // script.scenes 배열 확인
    if (jsonData.script?.scenes) {
      if (Array.isArray(jsonData.script.scenes)) {
        scenesArray = jsonData.script.scenes;
        console.log('[Step3] script.scenes 배열 발견:', scenesArray.length, '개');
      } else if (typeof jsonData.script.scenes === 'object') {
        // scenes가 객체인 경우 배열로 변환 (scene_1, scene_2 형태)
        scenesArray = Object.values(jsonData.script.scenes);
        console.log('[Step3] script.scenes 객체를 배열로 변환:', scenesArray.length, '개');
      }
    }
    // script 자체가 배열인 경우 (씬 배열로 직접 반환)
    else if (Array.isArray(jsonData.script)) {
      scenesArray = jsonData.script;
      console.log('[Step3] script 자체가 배열:', scenesArray.length, '개');
    }
    // script가 객체이고 opening/development/scene_N 등 스토리 파트가 있는 경우
    else if (jsonData.script && typeof jsonData.script === 'object') {
      const extractedScenes = [];
      const scriptKeys = Object.keys(jsonData.script);
      console.log('[Step3] script 객체 키들:', scriptKeys);

      // 1. opening 먼저 추가
      if (jsonData.script.opening) {
        extractedScenes.push(jsonData.script.opening);
      }

      // 2. scene_1, scene_2, scene_N 패턴 키 추출 (순서대로)
      const sceneKeys = scriptKeys
        .filter(key => /^scene_\d+$/i.test(key))
        .sort((a, b) => {
          const numA = parseInt(a.replace(/\D/g, ''));
          const numB = parseInt(b.replace(/\D/g, ''));
          return numA - numB;
        });

      sceneKeys.forEach(key => {
        extractedScenes.push(jsonData.script[key]);
      });

      // 3. 기타 스토리 파트 추가 (development, climax 등)
      const otherParts = ['development', 'climax', 'resolution', 'turning_point'];
      otherParts.forEach(part => {
        if (jsonData.script[part] && !extractedScenes.includes(jsonData.script[part])) {
          extractedScenes.push(jsonData.script[part]);
        }
      });

      // 4. closing/ending은 마지막에
      if (jsonData.script.closing) {
        extractedScenes.push(jsonData.script.closing);
      } else if (jsonData.script.ending) {
        extractedScenes.push(jsonData.script.ending);
      }

      if (extractedScenes.length > 0) {
        scenesArray = extractedScenes;
        console.log('[Step3] script 객체에서 스토리 파트 추출:', scenesArray.length, '개 (scene_N 포함)');
      }
    }

    // scenes 필드 직접 확인
    if (!scenesArray && jsonData.scenes) {
      if (Array.isArray(jsonData.scenes)) {
        scenesArray = jsonData.scenes;
        console.log('[Step3] scenes 배열 발견:', scenesArray.length, '개');
      } else if (typeof jsonData.scenes === 'object') {
        scenesArray = Object.values(jsonData.scenes);
        console.log('[Step3] scenes 객체를 배열로 변환:', scenesArray.length, '개');
      }
    }

    // 기타 경로
    if (!scenesArray && jsonData.drama?.scenes && Array.isArray(jsonData.drama.scenes)) {
      scenesArray = jsonData.drama.scenes;
      console.log('[Step3] drama.scenes 배열 발견:', scenesArray.length, '개');
    }
    if (!scenesArray && jsonData.content?.scenes && Array.isArray(jsonData.content.scenes)) {
      scenesArray = jsonData.content.scenes;
      console.log('[Step3] content.scenes 배열 발견:', scenesArray.length, '개');
    }

    // 2. scenes 배열에서 tts_text 또는 narration 추출
    if (scenesArray && scenesArray.length > 0) {
      console.log('[Step3] 씬 배열 처리 시작, 총', scenesArray.length, '개');
      scenesArray.forEach((scene, idx) => {
        console.log(`[Step3] scene[${idx}] 키들:`, Object.keys(scene || {}));

        // tts_text 필드 우선 (백엔드에서 TTS용으로 정제한 텍스트)
        if (scene.tts_text && typeof scene.tts_text === 'string' && scene.tts_text.length > 10) {
          console.log(`[Step3] scene[${idx}] tts_text 사용 (${scene.tts_text.length}자):`, scene.tts_text.substring(0, 50));
          narrations.push(scene.tts_text);
        }
        // tts_text가 없으면 narration 사용
        else if (scene.narration && typeof scene.narration === 'string' && scene.narration.length > 10) {
          console.log(`[Step3] scene[${idx}] narration 사용 (${scene.narration.length}자):`, scene.narration.substring(0, 50));
          narrations.push(scene.narration);
        }
        // narration이 배열인 경우
        else if (scene.narration && Array.isArray(scene.narration)) {
          const joined = scene.narration.join('\n\n');
          console.log(`[Step3] scene[${idx}] narration 배열 사용 (${joined.length}자)`);
          narrations.push(joined);
        }
        // 그래도 없으면 일반 추출
        else {
          const text = this.extractTextFromSceneObject(scene);
          if (text && text.length > 30) {
            console.log(`[Step3] scene[${idx}] 일반 추출 (${text.length}자):`, text.substring(0, 50));
            narrations.push(text);
          } else {
            console.log(`[Step3] scene[${idx}] 추출 실패 - 텍스트 없거나 너무 짧음`);
          }
        }
      });
      console.log('[Step3] 씬 배열 처리 완료, 추출된 나레이션:', narrations.length, '개');
    } else {
      console.log('[Step3] scenes 배열을 찾지 못함');
    }

    // 3. highlight.opening_hook은 씬이 없을 때만 추가 (씬에 이미 opening이 포함되어 있을 수 있음)
    if (narrations.length === 0) {
      const openingHook = jsonData.highlight?.opening_hook || jsonData.highlight_preview?.narration;
      if (openingHook) {
        console.log('[Step3] opening_hook 발견 (씬 없음, 폴백):', openingHook.substring(0, 50));
        narrations.push(openingHook);
      }
    }

    // 4. storyline에서 나레이션 추출 (scenes가 비어있을 때)
    if (narrations.length <= 1 && jsonData.storyline) {
      console.log('[Step3] storyline에서 추출 시도');
      // storyline이 배열인 경우
      if (Array.isArray(jsonData.storyline)) {
        jsonData.storyline.forEach((scene, idx) => {
          // tts_text 우선
          if (scene.tts_text && scene.tts_text.length > 10) {
            narrations.push(scene.tts_text);
          } else {
            const text = this.extractTextFromSceneObject(scene);
            if (text && text.length > 30) {
              narrations.push(text);
            }
          }
        });
      }
      // storyline이 객체인 경우 (opening, development, climax, resolution 등)
      else if (typeof jsonData.storyline === 'object') {
        const storyParts = ['opening', 'development', 'climax', 'resolution', 'ending'];
        storyParts.forEach(part => {
          if (jsonData.storyline[part]) {
            const partData = jsonData.storyline[part];
            // tts_text 우선
            if (partData.tts_text && partData.tts_text.length > 10) {
              narrations.push(partData.tts_text);
            } else {
              const text = this.extractTextFromSceneObject(partData);
              if (text && text.length > 30) {
                narrations.push(text);
              }
            }
          }
        });
      }
    }

    // 4. script 필드가 있는 경우
    if (narrations.length === 0 && jsonData.script) {
      console.log('[Step3] script 필드 처리, 타입:', typeof jsonData.script);

      if (typeof jsonData.script === 'string') {
        narrations.push(jsonData.script);
      } else if (jsonData.script.tts_text) {
        narrations.push(jsonData.script.tts_text);
      } else if (jsonData.script.full_text) {
        narrations.push(jsonData.script.full_text);
      } else if (jsonData.script.narration) {
        narrations.push(jsonData.script.narration);
      } else if (typeof jsonData.script === 'object') {
        // script가 객체인 경우: opening, development, climax, resolution 등의 필드 처리
        console.log('[Step3] script 객체의 키들:', Object.keys(jsonData.script));

        const storyParts = ['opening', 'intro', 'development', 'turning_point', 'climax', 'resolution', 'ending', 'closing'];
        const extractedParts = [];

        storyParts.forEach(part => {
          if (jsonData.script[part]) {
            const partData = jsonData.script[part];
            if (typeof partData === 'string' && partData.length > 10) {
              console.log(`[Step3] script.${part} 추출 (${partData.length}자)`);
              extractedParts.push(partData);
            } else if (typeof partData === 'object') {
              // 객체인 경우 텍스트 추출
              const text = this.extractTextFromSceneObject(partData);
              if (text && text.length > 10) {
                console.log(`[Step3] script.${part} 객체에서 추출 (${text.length}자)`);
                extractedParts.push(text);
              }
            }
          }
        });

        // 정의된 키가 없으면 모든 문자열 값 수집
        if (extractedParts.length === 0) {
          console.log('[Step3] 정의된 story parts 없음, 모든 문자열 필드 수집');
          for (const key of Object.keys(jsonData.script)) {
            // scenes 배열은 이미 위에서 처리했으므로 스킵
            if (key === 'scenes') continue;
            const value = jsonData.script[key];
            if (typeof value === 'string' && value.length > 30) {
              console.log(`[Step3] script.${key} 문자열 수집 (${value.length}자)`);
              extractedParts.push(value);
            }
          }
        }

        if (extractedParts.length > 0) {
          // 모든 파트를 하나의 나레이션으로 합치거나, 개별 씬으로 분리
          // 짧으면 합치고, 길면 개별 처리
          const totalLength = extractedParts.reduce((sum, p) => sum + p.length, 0);
          if (totalLength < 3000 && extractedParts.length <= 4) {
            // 짧으면 하나로 합침
            narrations.push(extractedParts.join('\n\n'));
            console.log('[Step3] script 파트들을 하나로 합침');
          } else {
            // 길면 개별 씬으로
            extractedParts.forEach(part => narrations.push(part));
            console.log(`[Step3] script 파트들을 개별 씬으로 분리: ${extractedParts.length}개`);
          }
        }
      }
    }

    // 5. narrations가 비어있으면 opening_hook + key_message 조합
    if (narrations.length === 0 && jsonData.highlight) {
      let combinedText = '';
      if (jsonData.highlight.opening_hook) {
        combinedText += jsonData.highlight.opening_hook + '\n\n';
      }
      if (jsonData.highlight.key_message) {
        combinedText += jsonData.highlight.key_message;
      }
      if (combinedText.length > 30) {
        narrations.push(combinedText.trim());
      }
    }

    console.log('[Step3] 최종 추출된 나레이션:', narrations.length, '개');
    return narrations;
  },

  // 씬 객체에서 나레이션 텍스트 추출
  // ⚠️ 우선순위: tts_text > narration > text > content
  extractTextFromSceneObject(scene) {
    if (!scene) return '';

    // 문자열이면 그대로 반환
    if (typeof scene === 'string') return scene;

    // tts_text 필드 최우선 (백엔드에서 TTS용으로 정제한 텍스트)
    if (scene.tts_text && typeof scene.tts_text === 'string') {
      return scene.tts_text;
    }

    // 객체면 나레이션 관련 필드 찾기 (우선순위 순)
    const narrationFields = ['narration', 'text', 'content', 'dialogue', 'script', 'description'];
    for (const field of narrationFields) {
      if (scene[field] && typeof scene[field] === 'string') {
        return scene[field];
      }
    }

    // 배열인 경우 join
    if (scene.narration && Array.isArray(scene.narration)) {
      return scene.narration.join('\n');
    }
    if (scene.tts_text && Array.isArray(scene.tts_text)) {
      return scene.tts_text.join('\n');
    }

    return '';
  },

  // JSON 객체에서 UI 표시용 텍스트 추출 (메타데이터 제외)
  extractDisplayText(jsonData) {
    if (!jsonData) return '';
    if (typeof jsonData === 'string') return jsonData;

    // 1. narration 필드 우선
    if (jsonData.narration) {
      if (typeof jsonData.narration === 'string') return jsonData.narration;
      if (Array.isArray(jsonData.narration)) return jsonData.narration.join(' ');
    }

    // 2. text / content 필드
    if (jsonData.text) return jsonData.text;
    if (jsonData.content) return jsonData.content;

    // 3. storyline에서 추출
    if (jsonData.storyline) {
      const narrations = this.extractNarrationFromJson(jsonData);
      if (narrations && narrations.length > 0) {
        return narrations.join('\n\n');
      }
    }

    // 4. scenes 배열에서 추출 (script.scenes 또는 scenes)
    const scenesArray = jsonData.script?.scenes || jsonData.scenes;
    if (scenesArray && Array.isArray(scenesArray)) {
      const texts = scenesArray.map(s => this.extractTextFromSceneObject(s)).filter(t => t);
      if (texts.length > 0) return texts.join('\n\n');
    }

    // 5. 기타: 첫 번째 문자열 값 사용
    for (const key of Object.keys(jsonData)) {
      if (typeof jsonData[key] === 'string' && jsonData[key].length > 50) {
        // 메타데이터 키 제외
        if (['title', 'duration', 'target_age', 'category', 'style'].includes(key)) continue;
        return jsonData[key];
      }
    }

    return JSON.stringify(jsonData).substring(0, 200);
  },

  // 씬 텍스트에서 순수 나레이션만 추출 (설명, 지시문 제외)
  extractNarrationFromScene(sceneText) {
    if (!sceneText) return '';

    let text = sceneText;

    // 제목/헤더 제거 (예: "### 장면 1: 도입부")
    text = text.replace(/^#+\s*장면\s*\d+.*$/gm, '');
    text = text.replace(/^씬\s*\d+.*$/gm, '');
    text = text.replace(/^Scene\s*\d+.*$/gm, '');

    // 메타 설명 제거
    text = text.replace(/^-\s*(상황|설명|등장인물|핵심|갈등|감정|깨달음|메시지|여운).*$/gm, '');
    text = text.replace(/^\*\*.*\*\*$/gm, ''); // **볼드** 제목 제거
    text = text.replace(/^\(약\s*\d+%\)$/gm, ''); // (약 20%) 제거

    // 대사 추출 (큰따옴표 안의 내용)
    const dialogues = [];
    const dialogueMatches = text.match(/"([^"]+)"/g);
    if (dialogueMatches) {
      dialogueMatches.forEach(match => {
        dialogues.push(match.replace(/"/g, ''));
      });
    }

    // 나레이션 문장 추출 (마침표로 끝나는 완전한 문장)
    const sentences = text.match(/[^.!?]*[.!?]/g) || [];
    const narrationSentences = sentences.filter(sentence => {
      const s = sentence.trim();
      // 메타 설명이 아닌 문장만 선택
      if (s.length < 10) return false;
      if (/^-\s/.test(s)) return false;
      if (/^#/.test(s)) return false;
      if (/[:：]$/.test(s)) return false;
      // 숫자로 시작하는 목록 제외
      if (/^\d+\.\s*(주인공|스토리|배경|설정|컨셉)/.test(s)) return false;
      return true;
    });

    // 대사와 나레이션 결합
    let result = narrationSentences.join(' ').trim();

    // 연속 공백 정리
    result = result.replace(/\s+/g, ' ');

    return result;
  },

  // 음성 스타일에 따른 음성 선택 (Step1에서 직접 선택한 음성 사용)
  getVoiceSettings(style) {
    // Step1에서 직접 선택한 음성 사용 (최우선)
    const directVoice = dramaApp.session.ttsVoice;
    const gender = dramaApp.session.protagonistGender || 'female';
    const quality = dramaApp.session.ttsVoiceQuality || 'neural2';

    console.log('[Step3] TTS 설정 - 직접선택:', directVoice, ', 성별:', gender, ', 품질:', quality);

    // 스타일별 pitch/volume 조정
    const styleSettings = {
      'warm': { pitch: -2, volume: 0 },
      'neutral': { pitch: 0, volume: 0 },
      'dramatic': { pitch: 2, volume: 2 }
    };

    // Step1에서 직접 선택한 음성이 있으면 그대로 사용
    let speaker = directVoice;

    // 없으면 품질+성별로 기본 음성 매핑
    if (!speaker) {
      const voiceMap = {
        standard: { female: 'ko-KR-Standard-A', male: 'ko-KR-Standard-C' },
        wavenet: { female: 'ko-KR-Wavenet-A', male: 'ko-KR-Wavenet-C' },
        neural2: { female: 'ko-KR-Neural2-A', male: 'ko-KR-Neural2-C' }
      };
      speaker = voiceMap[quality]?.[gender] || 'ko-KR-Neural2-A';
    }

    const settings = styleSettings[style] || styleSettings['warm'];

    console.log('[Step3] 최종 선택 음성:', speaker);

    return {
      speaker: speaker,
      pitch: settings.pitch,
      volume: settings.volume
    };
  },

  // TTS 생성 (병렬 처리 지원)
  async generateTTS() {
    if (this.isGenerating) {
      DramaUtils.showStatus('이미 생성 중입니다...', 'warning');
      return;
    }

    const scenes = this.getScriptTexts();
    if (!scenes || scenes.length === 0) {
      DramaUtils.showStatus('먼저 Step 1에서 대본을 생성해주세요.', 'error');
      return;
    }

    this.isGenerating = true;
    this.generatedAudios = [];

    const btn = document.getElementById('btn-generate-tts');
    const originalText = btn?.innerHTML;
    const config = this.getConfig();
    const voiceSettings = this.getVoiceSettings(config.voiceStyle);

    try {
      if (btn) {
        btn.innerHTML = '<span class="btn-icon">⏳</span> 생성 중...';
        btn.disabled = true;
      }

      // 진행 상황 표시
      const progressPanel = document.getElementById('tts-progress');
      const progressBar = document.getElementById('tts-progress-bar');
      const progressText = document.getElementById('tts-progress-text');

      if (progressPanel) progressPanel.classList.remove('hidden');

      const total = scenes.length;
      let completed = 0;

      // 🚀 병렬 처리: 동시 요청 제한 (API rate limit 대응)
      const CONCURRENT_LIMIT = 3;
      console.log(`[Step3] 🚀 병렬 TTS 생성 시작: ${total}개 씬, 동시 ${CONCURRENT_LIMIT}개`);

      // 단일 TTS 생성 함수
      const generateSingleTTS = async (scene, index) => {
        console.log(`[Step3] TTS 생성 시작: ${scene.id}`);
        try {
          const response = await fetch('/api/drama/generate-tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: scene.text,
              speaker: voiceSettings.speaker,
              speed: config.speechRate,
              pitch: voiceSettings.pitch,
              volume: voiceSettings.volume,
              ttsProvider: config.ttsEngine
            })
          });

          const data = await response.json();

          if (data.ok && data.audioUrl) {
            return {
              success: true,
              index: index,
              result: {
                id: scene.id,
                audioUrl: data.audioUrl,
                duration: data.duration || 0,
                text: scene.text.substring(0, 100) + '...'
              }
            };
          } else {
            console.error(`[Step3] ${scene.id} TTS 실패:`, data.error);
            return { success: false, index: index, error: data.error };
          }
        } catch (err) {
          console.error(`[Step3] ${scene.id} TTS 오류:`, err);
          return { success: false, index: index, error: err.message };
        }
      };

      // 배치 처리 (동시 실행 제한)
      const results = [];
      for (let i = 0; i < total; i += CONCURRENT_LIMIT) {
        const batch = scenes.slice(i, i + CONCURRENT_LIMIT);
        const batchPromises = batch.map((scene, batchIdx) =>
          generateSingleTTS(scene, i + batchIdx)
        );

        if (progressText) progressText.textContent = `${Math.min(i + CONCURRENT_LIMIT, total)} / ${total} 씬 생성 중... (병렬 처리)`;
        if (progressBar) progressBar.style.width = `${(Math.min(i + CONCURRENT_LIMIT, total) / total) * 100}%`;

        // 배치 병렬 실행
        const batchResults = await Promise.all(batchPromises);
        results.push(...batchResults);

        completed += batch.length;

        // 배치 간 짧은 대기 (rate limit 방지)
        if (i + CONCURRENT_LIMIT < total) {
          await new Promise(r => setTimeout(r, 300));
        }
      }

      // 결과 정렬 및 저장 (원래 순서대로)
      results.sort((a, b) => a.index - b.index);
      this.generatedAudios = results
        .filter(r => r.success)
        .map(r => r.result);

      if (progressBar) progressBar.style.width = '100%';
      if (progressText) progressText.textContent = '완료!';

      // 결과 저장 (TTS에 전달한 텍스트도 함께 저장)
      const finalScripts = scenes.map(s => s.text);
      DramaSession.setStepData('step3', {
        audios: this.generatedAudios,
        config: config,
        finalScripts: finalScripts  // TTS에 전달한 순수 나레이션 텍스트
      });

      // 결과 표시
      this.displayResults();

      setTimeout(() => {
        if (progressPanel) progressPanel.classList.add('hidden');
      }, 1000);

      const failedCount = results.filter(r => !r.success).length;
      if (failedCount > 0) {
        DramaUtils.showStatus(`TTS 생성 완료! (${this.generatedAudios.length}개 성공, ${failedCount}개 실패)`, 'warning');
      } else {
        DramaUtils.showStatus(`TTS 생성 완료! (${this.generatedAudios.length}개 음성) 🚀 병렬 처리`, 'success');
      }

    } catch (error) {
      console.error('[Step3] TTS 오류:', error);
      DramaUtils.showStatus(`오류: ${error.message}`, 'error');
    } finally {
      if (btn) {
        btn.innerHTML = originalText;
        btn.disabled = false;
      }
      this.isGenerating = false;
    }
  },

  // 결과 표시
  displayResults() {
    const resultArea = document.getElementById('tts-result-area');
    const audioList = document.getElementById('tts-audio-list');
    const totalDuration = document.getElementById('tts-total-duration');

    if (resultArea) resultArea.classList.remove('hidden');

    if (audioList) {
      audioList.innerHTML = this.generatedAudios.map((audio, idx) => {
        // 나레이션 텍스트 정리 (JSON이 아닌 순수 텍스트만 표시)
        let displayText = audio.text || '';

        // JSON 문자열인 경우 파싱 시도
        if (displayText.trim().startsWith('{') || displayText.trim().startsWith('[')) {
          try {
            const parsed = JSON.parse(displayText);
            // JSON에서 나레이션 추출
            displayText = this.extractDisplayText(parsed);
          } catch (e) {
            // 파싱 실패 시 그대로 사용
          }
        }

        // 200자로 제한하여 미리보기 표시
        const previewText = displayText.length > 200
          ? displayText.substring(0, 200) + '...'
          : displayText;

        return `
        <div class="tts-audio-item" data-idx="${idx}">
          <div class="audio-info">
            <span class="audio-title">${audio.id}</span>
            <span class="audio-duration">${audio.duration ? audio.duration.toFixed(1) + '초' : '-'}</span>
          </div>
          <div class="audio-controls">
            <audio id="audio-${idx}" src="${audio.audioUrl}" preload="metadata"></audio>
            <button class="btn-small" onclick="DramaStep3.playAudio(${idx})">▶️ 재생</button>
            <button class="btn-small" onclick="DramaStep3.downloadAudio(${idx})">💾 저장</button>
          </div>
          <p class="audio-preview">${DramaUtils.escapeHtml(previewText)}</p>
        </div>`;
      }).join('');
    }

    // 총 재생시간 계산
    if (totalDuration) {
      const total = this.generatedAudios.reduce((sum, a) => sum + (a.duration || 0), 0);
      totalDuration.textContent = `총 재생 시간: ${Math.floor(total / 60)}분 ${Math.floor(total % 60)}초`;
    }

    // 다음 단계 버튼 표시
    const nextButtons = document.getElementById('step3-next');
    if (nextButtons) nextButtons.classList.remove('hidden');
  },

  // 개별 재생
  playAudio(idx) {
    console.log('[Step3] playAudio 호출:', idx);

    // 기존 재생 중지
    if (this.currentAudioPlayer) {
      this.currentAudioPlayer.pause();
      this.currentAudioPlayer.currentTime = 0;
    }

    const audio = document.getElementById(`audio-${idx}`);
    console.log('[Step3] audio 요소:', audio);

    if (audio) {
      console.log('[Step3] audio.src:', audio.src?.substring(0, 100));

      audio.play().then(() => {
        console.log('[Step3] 재생 시작됨');
      }).catch(err => {
        console.error('[Step3] 재생 오류:', err);
        DramaUtils.showStatus(`재생 오류: ${err.message}`, 'error');
      });

      this.currentAudioPlayer = audio;
    } else {
      console.error('[Step3] audio 요소를 찾을 수 없음:', `audio-${idx}`);
      DramaUtils.showStatus('오디오 요소를 찾을 수 없습니다.', 'error');
    }
  },

  // 전체 재생
  async playAll() {
    if (this.generatedAudios.length === 0) {
      DramaUtils.showStatus('재생할 음성이 없습니다.', 'warning');
      return;
    }

    DramaUtils.showStatus('전체 재생 시작', 'info');

    for (let i = 0; i < this.generatedAudios.length; i++) {
      const audio = document.getElementById(`audio-${i}`);
      if (audio) {
        audio.play();
        this.currentAudioPlayer = audio;

        // 재생 완료 대기
        await new Promise(resolve => {
          audio.onended = resolve;
          audio.onerror = resolve;
        });
      }
    }

    DramaUtils.showStatus('전체 재생 완료', 'success');
  },

  // 개별 다운로드
  downloadAudio(idx) {
    const audio = this.generatedAudios[idx];
    if (audio?.audioUrl) {
      const a = document.createElement('a');
      a.href = audio.audioUrl;
      a.download = `${audio.id}.mp3`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  },

  // 전체 다운로드 (ZIP은 서버 구현 필요, 여기선 순차 다운로드)
  downloadAll() {
    if (this.generatedAudios.length === 0) {
      DramaUtils.showStatus('다운로드할 음성이 없습니다.', 'warning');
      return;
    }

    this.generatedAudios.forEach((audio, idx) => {
      setTimeout(() => this.downloadAudio(idx), idx * 500);
    });

    DramaUtils.showStatus(`${this.generatedAudios.length}개 파일 다운로드 중...`, 'info');
  },

  // 세션에서 데이터 복원
  restore(data) {
    if (data?.audios) {
      this.generatedAudios = data.audios;
      this.displayResults();
    }
  }
};
