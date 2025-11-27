/**
 * Drama Lab - Step3 TTS 음성합성 모듈
 * 화면 기준 Step3: TTS 음성합성 (지문 추출 → 음성 생성 → SRT 자막)
 */

// ===== TTS 관련 변수 =====
let step3TtsProvider = 'google';  // 기본: Google Cloud TTS
let step3SelectedVoice = 'ko-KR-Wavenet-A';  // Google 기본 음성
let step3AudioUrl = null;
let step3SubtitleData = null;
let step3PreviewAudio = null;  // 미리듣기용 오디오

// ===== Step3 컨테이너 표시 =====
function updateStep3Visibility() {
  const step3Container = document.getElementById('step5-container');
  const step1Result = document.getElementById('step3-result')?.value || '';
  if (step3Container) {
    step3Container.style.display = step1Result.trim() ? 'block' : 'none';
  }
}

// ===== TTS 제공자 선택 초기화 =====
function initTTSProviderButtons() {
  document.querySelectorAll('.step5-tts-provider').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.step5-tts-provider').forEach(b => {
        b.classList.remove('selected');
        b.style.border = '2px solid #ddd';
        b.style.background = 'white';
      });
      btn.classList.add('selected');
      btn.style.border = '2px solid #10b981';
      btn.style.background = 'rgba(16,185,129,0.2)';

      step3TtsProvider = btn.dataset.provider;

      // 음성 선택 영역 전환
      const googleVoices = document.getElementById('step5-voice-google');
      const naverVoices = document.getElementById('step5-voice-naver');
      const voiceLabel = document.getElementById('step5-voice-label');

      if (step3TtsProvider === 'google') {
        googleVoices.style.display = 'grid';
        naverVoices.style.display = 'none';
        voiceLabel.textContent = '🎤 음성 선택 (Google Cloud)';
        step3SelectedVoice = 'ko-KR-Wavenet-A';
        googleVoices.querySelectorAll('.step5-voice-option').forEach((o, i) => {
          o.classList.toggle('selected', i === 0);
        });
      } else {
        googleVoices.style.display = 'none';
        naverVoices.style.display = 'grid';
        voiceLabel.textContent = '🎤 음성 선택 (네이버 클로바)';
        step3SelectedVoice = 'nara';
        naverVoices.querySelectorAll('.step5-voice-option').forEach((o, i) => {
          o.classList.toggle('selected', i === 0);
        });
      }
    });
  });
}

// ===== 음성 선택 초기화 =====
function initVoiceOptions() {
  document.querySelectorAll('.step5-voice-option').forEach(option => {
    option.addEventListener('click', () => {
      const provider = option.dataset.provider;
      const container = provider === 'google' ? document.getElementById('step5-voice-google') : document.getElementById('step5-voice-naver');
      container.querySelectorAll('.step5-voice-option').forEach(o => o.classList.remove('selected'));
      option.classList.add('selected');
      step3SelectedVoice = option.dataset.voice;
    });
  });
}

// ===== 음성 미리듣기 함수 =====
async function previewVoice(voice, provider) {
  const sampleText = "안녕하세요. 이 목소리로 드라마 나레이션을 진행합니다. 감동적인 이야기를 전해드릴게요.";

  // 기존 재생 중인 오디오 중지
  if (step3PreviewAudio) {
    step3PreviewAudio.pause();
    step3PreviewAudio = null;
  }

  // 버튼 로딩 상태
  const btn = event.target;
  const originalText = btn.textContent;
  btn.textContent = '⏳';
  btn.classList.add('loading');

  try {
    const response = await fetch('/api/drama/generate-tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: sampleText,
        speaker: voice,
        speed: 0,
        pitch: 0,
        volume: 0,
        ttsProvider: provider
      })
    });

    const data = await response.json();

    if (data.ok && data.audioUrl) {
      step3PreviewAudio = new Audio(data.audioUrl);
      step3PreviewAudio.play();

      // 재생 중 버튼 표시
      btn.textContent = '⏸️';

      // 재생 완료 시 버튼 복원
      step3PreviewAudio.onended = () => {
        btn.textContent = '▶️';
        btn.classList.remove('loading');
      };

      // 클릭하면 정지
      btn.onclick = (e) => {
        e.stopPropagation();
        if (step3PreviewAudio) {
          step3PreviewAudio.pause();
          step3PreviewAudio = null;
        }
        btn.textContent = '▶️';
        btn.classList.remove('loading');
        btn.onclick = (e) => {
          e.stopPropagation();
          previewVoice(voice, provider);
        };
      };
    } else {
      alert(`미리듣기 실패: ${data.error || '알 수 없는 오류'}`);
      btn.textContent = '▶️';
      btn.classList.remove('loading');
    }
  } catch (err) {
    alert(`미리듣기 오류: ${err.message}`);
    btn.textContent = '▶️';
    btn.classList.remove('loading');
  }
}

// ===== 지문 추출 함수 (JSON 파싱 지원) =====
function extractNarration() {
  const step1Result = document.getElementById('step3-result')?.value || '';
  if (!step1Result.trim()) {
    alert('먼저 Step1 대본 완성을 실행해주세요.');
    return;
  }

  // 1. JSON 형태인지 확인하고 파싱 시도
  try {
    let jsonStr = step1Result;
    const jsonMatch = step1Result.match(/```json\s*([\s\S]*?)\s*```/);
    if (jsonMatch) {
      jsonStr = jsonMatch[1];
    }

    const data = JSON.parse(jsonStr);
    const narrations = [];

    // 다양한 JSON 구조 지원
    let scenes = null;
    if (data.script && data.script.scenes && Array.isArray(data.script.scenes)) {
      scenes = data.script.scenes;
      console.log('[extractNarration] data.script.scenes 구조 사용');
    } else if (data.scenes && Array.isArray(data.scenes)) {
      scenes = data.scenes;
      console.log('[extractNarration] data.scenes 구조 사용');
    }

    if (scenes && scenes.length > 0) {
      scenes.forEach((scene) => {
        if (scene.narration) {
          narrations.push(scene.narration);
        }
        if (scene.scene_narration) {
          narrations.push(scene.scene_narration);
        }
      });

      if (narrations.length > 0) {
        document.getElementById('step5-script-text').value = narrations.join('\n\n');
        showStatus(`📝 JSON에서 ${narrations.length}개의 나레이션이 추출되었습니다.`);
        setTimeout(hideStatus, 2000);
        console.log('[extractNarration] JSON에서 나레이션 추출 성공:', narrations.length + '개');
        return;
      }
    }

    console.log('[extractNarration] JSON 파싱 성공했으나 narration 없음, 구조:', Object.keys(data));
  } catch (e) {
    console.log('[extractNarration] JSON 파싱 실패, 기존 방식으로 처리:', e.message);
  }

  // 2. 기존 텍스트 기반 추출 방식 (fallback)
  let narration = step1Result;

  // "인물명: 대사" 패턴 제거
  narration = narration.replace(/^[가-힣a-zA-Z]+\s*[:：]\s*.+$/gm, '');

  // (감정/행동) 형식의 지시문은 유지하되 괄호 제거
  narration = narration.replace(/\(([^)]+)\)/g, '$1');

  // 빈 줄 정리
  narration = narration.replace(/\n{3,}/g, '\n\n').trim();

  document.getElementById('step5-script-text').value = narration;
  showStatus('📝 지문이 추출되었습니다. (텍스트 기반)');
  setTimeout(hideStatus, 2000);
}

// ===== TTS 생성 함수 =====
async function generateTTS() {
  const scriptText = document.getElementById('step5-script-text')?.value || '';
  if (!scriptText.trim()) {
    alert('TTS용 대본 텍스트를 입력해주세요.');
    return;
  }

  const speed = document.getElementById('step5-speed')?.value || 0;
  const pitch = document.getElementById('step5-pitch')?.value || 0;
  const volume = document.getElementById('step5-volume')?.value || 0;

  const btnGenerateTTS = document.getElementById('btn-generate-tts');
  if (btnGenerateTTS) {
    btnGenerateTTS.disabled = true;
    btnGenerateTTS.classList.add('generating');
    btnGenerateTTS.textContent = '⏳ 음성 생성 중...';
  }

  const providerName = step3TtsProvider === 'google' ? 'Google Cloud' : '네이버 클로바';
  showStatus(`🎙️ Step3: ${providerName} TTS 음성 생성 중...`);
  showLoadingOverlay();

  try {
    const response = await fetch('/api/drama/generate-tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: scriptText,
        speaker: step3SelectedVoice,
        speed: parseInt(speed),
        pitch: parseInt(pitch),
        volume: parseInt(volume),
        ttsProvider: step3TtsProvider
      })
    });

    const data = await response.json();

    if (data.ok) {
      // 오디오 플레이어 표시
      const audioSection = document.getElementById('step5-audio-section');
      const audioPlayer = document.getElementById('step5-audio-player');
      const costInfo = document.getElementById('step5-cost-info');

      if (audioPlayer && data.audioUrl) {
        step3AudioUrl = data.audioUrl;
        audioPlayer.src = data.audioUrl;
        audioSection.style.display = 'block';

        // 오디오 로드 후 길이를 구해서 자막 생성
        audioPlayer.onloadedmetadata = async function() {
          const audioDuration = audioPlayer.duration;
          console.log('[TTS] 오디오 길이:', audioDuration, '초');

          // 비용 정보 표시
          if (costInfo && data.cost) {
            document.getElementById('step5-tts-cost').textContent = '₩' + data.cost.toLocaleString();
            document.getElementById('step5-char-count').textContent = data.charCount?.toLocaleString() || '0';
            costInfo.style.display = 'block';
          }

          showStatus('✅ TTS 음성 생성 완료! SRT 자막 생성 중...');
          if (typeof updateProgressIndicator === 'function') {
            updateProgressIndicator('step5');
          }
          updateStep4Visibility();

          // TTS 완료 후 SRT 자막 자동 생성
          await generateSubtitleAuto(audioDuration);
        };

        // onloadedmetadata가 이미 발생한 경우 대비
        if (audioPlayer.readyState >= 1) {
          audioPlayer.onloadedmetadata();
        }
      } else {
        // 비용 정보 표시
        if (costInfo && data.cost) {
          document.getElementById('step5-tts-cost').textContent = '₩' + data.cost.toLocaleString();
          document.getElementById('step5-char-count').textContent = data.charCount?.toLocaleString() || '0';
          costInfo.style.display = 'block';
        }

        showStatus('✅ TTS 음성 생성 완료! SRT 자막 생성 중...');
        if (typeof updateProgressIndicator === 'function') {
          updateProgressIndicator('step5');
        }
        updateStep4Visibility();

        // TTS 완료 후 SRT 자막 자동 생성 (오디오 길이 없음)
        await generateSubtitleAuto(0);
      }
    } else {
      alert(`오류: ${data.error}`);
      showStatus('❌ TTS 생성 실패');
    }
  } catch (err) {
    alert(`네트워크 오류: ${err.message}`);
    showStatus('❌ TTS 생성 오류');
  } finally {
    hideLoadingOverlay();
    setTimeout(hideStatus, 3000);
    if (btnGenerateTTS) {
      btnGenerateTTS.disabled = false;
      btnGenerateTTS.classList.remove('generating');
      btnGenerateTTS.textContent = '음성 생성 (TTS)';
    }
  }
}

// ===== SRT 자막 자동 생성 (TTS 완료 후 호출) =====
async function generateSubtitleAuto(audioDuration = 0) {
  const scriptText = document.getElementById('step5-script-text')?.value || '';
  if (!scriptText.trim()) return;

  try {
    const response = await fetch('/api/drama/generate-subtitle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: scriptText,
        speed: parseInt(document.getElementById('step5-speed')?.value || 0),
        audioDuration: audioDuration || 0
      })
    });

    const data = await response.json();

    if (data.ok) {
      // 자막 미리보기 표시
      const subtitleSection = document.getElementById('step5-subtitle-section');
      const subtitlePreview = document.getElementById('step5-subtitle-preview');

      if (subtitlePreview && data.srt) {
        step3SubtitleData = data;
        subtitlePreview.textContent = data.srt;
        subtitleSection.style.display = 'block';
      }

      // 자막 정보 표시
      const subtitleInfo = document.getElementById('step5-subtitle-info');
      if (subtitleInfo && data.sentenceCount) {
        document.getElementById('step5-sentence-count').textContent = data.sentenceCount;
        document.getElementById('step5-total-duration').textContent = formatDuration(data.totalDuration);
        subtitleInfo.style.display = 'block';
      }

      showStatus('✅ TTS + SRT 자막 생성 완료!');
      console.log('[TTS+SRT] 자동 생성 완료');
    }
  } catch (err) {
    console.error('[SRT 자동생성 오류]', err);
    showStatus('⚠️ TTS 완료, SRT 자막 생성 실패');
  }
}

// ===== 자막 생성 함수 (수동) =====
async function generateSubtitle() {
  const scriptText = document.getElementById('step5-script-text')?.value || '';
  if (!scriptText.trim()) {
    alert('TTS용 대본 텍스트를 입력해주세요.');
    return;
  }

  const btnGenerateSubtitle = document.getElementById('btn-generate-subtitle');
  if (btnGenerateSubtitle) {
    btnGenerateSubtitle.disabled = true;
    btnGenerateSubtitle.classList.add('generating');
    btnGenerateSubtitle.textContent = '⏳ 자막 생성 중...';
  }

  showStatus('📝 Step3: 자막 생성 중...');
  showLoadingOverlay();

  try {
    // 오디오 길이 가져오기 (있으면)
    const audioPlayer = document.getElementById('step5-audio-player');
    const audioDuration = audioPlayer?.duration || 0;

    const response = await fetch('/api/drama/generate-subtitle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: scriptText,
        speed: parseInt(document.getElementById('step5-speed')?.value || 0),
        audioDuration: audioDuration || 0
      })
    });

    const data = await response.json();

    if (data.ok) {
      // 자막 미리보기 표시
      const subtitleSection = document.getElementById('step5-subtitle-section');
      const subtitlePreview = document.getElementById('step5-subtitle-preview');

      if (subtitlePreview && data.srt) {
        step3SubtitleData = data;
        subtitlePreview.textContent = data.srt;
        subtitleSection.style.display = 'block';
      }

      showStatus('✅ 자막 생성 완료!');
    } else {
      alert(`오류: ${data.error}`);
      showStatus('❌ 자막 생성 실패');
    }
  } catch (err) {
    alert(`네트워크 오류: ${err.message}`);
    showStatus('❌ 자막 생성 오류');
  } finally {
    hideLoadingOverlay();
    setTimeout(hideStatus, 3000);
    if (btnGenerateSubtitle) {
      btnGenerateSubtitle.disabled = false;
      btnGenerateSubtitle.classList.remove('generating');
      btnGenerateSubtitle.textContent = '📝 자막 생성 (SRT)';
    }
  }
}

// ===== 시간 형식 변환 =====
function formatDuration(seconds) {
  if (!seconds) return '00:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// ===== 오디오 다운로드 =====
function downloadAudio() {
  if (!step3AudioUrl) {
    alert('먼저 음성을 생성해주세요.');
    return;
  }
  const a = document.createElement('a');
  a.href = step3AudioUrl;
  a.download = `drama-tts-${Date.now()}.mp3`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ===== SRT 다운로드 =====
function downloadSRT() {
  if (!step3SubtitleData?.srt) {
    alert('먼저 자막을 생성해주세요.');
    return;
  }
  const blob = new Blob([step3SubtitleData.srt], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `drama-subtitle-${Date.now()}.srt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ===== VTT 다운로드 =====
function downloadVTT() {
  if (!step3SubtitleData?.vtt) {
    alert('먼저 자막을 생성해주세요.');
    return;
  }
  const blob = new Blob([step3SubtitleData.vtt], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `drama-subtitle-${Date.now()}.vtt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ===== Step4 (영상제작) 가시성 업데이트 =====
function updateStep4Visibility() {
  if (typeof window.DramaStep4 !== 'undefined' && typeof window.DramaStep4.updateVisibility === 'function') {
    window.DramaStep4.updateVisibility();
  }
}

// ===== Step3 초기화 =====
function clearStep3() {
  if (!confirm('Step3의 모든 내용을 초기화하시겠습니까?')) return;

  document.getElementById('step5-script-text').value = '';
  document.getElementById('step5-audio-section').style.display = 'none';
  document.getElementById('step5-subtitle-section').style.display = 'none';
  document.getElementById('step5-cost-info').style.display = 'none';

  const audioPlayer = document.getElementById('step5-audio-player');
  if (audioPlayer) audioPlayer.src = '';

  step3AudioUrl = null;
  step3SubtitleData = null;

  showStatus('🗑️ Step3가 초기화되었습니다.');
  setTimeout(hideStatus, 2000);
}

// ===== 자동화 모드용 TTS 및 영상 생성 =====
async function runAutoTTSAndVideo() {
  try {
    // 1. 지문 추출 (자동)
    console.log('[AUTO] 지문 추출 중...');
    extractNarration();
    await new Promise(resolve => setTimeout(resolve, 500));

    const scriptText = document.getElementById('step5-script-text')?.value || '';
    if (!scriptText.trim()) {
      console.error('[AUTO] 지문 추출 실패: 텍스트 없음');
      showStatus('❌ 자동화 오류: 지문 추출 실패');
      return;
    }

    // 2. TTS 생성
    console.log('[AUTO] TTS 생성 시작...');
    showLoadingOverlay('TTS 음성 생성 중', '자동화 모드: 음성을 생성하고 있습니다...');

    const speed = document.getElementById('step5-speed')?.value || 0;
    const pitch = document.getElementById('step5-pitch')?.value || 0;
    const volume = document.getElementById('step5-volume')?.value || 0;

    const ttsResponse = await fetch('/api/drama/generate-tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: scriptText,
        speaker: step3SelectedVoice,
        speed: parseInt(speed),
        pitch: parseInt(pitch),
        volume: parseInt(volume),
        ttsProvider: step3TtsProvider
      })
    });

    const ttsData = await ttsResponse.json();
    hideLoadingOverlay();

    if (!ttsData.ok) {
      throw new Error(ttsData.error || 'TTS 생성 실패');
    }

    // TTS 결과 표시
    const audioSection = document.getElementById('step5-audio-section');
    const audioPlayer = document.getElementById('step5-audio-player');
    if (audioPlayer && ttsData.audioUrl) {
      step3AudioUrl = ttsData.audioUrl;
      audioPlayer.src = ttsData.audioUrl;
      audioSection.style.display = 'block';
    }

    console.log('[AUTO] TTS 완료, SRT 자막 생성...');
    showStatus('✅ TTS 완료! SRT 자막 생성 중...');

    // 3. SRT 자막 자동 생성
    await generateSubtitleAuto();
    if (typeof updateProgressIndicator === 'function') {
      updateProgressIndicator('step5');
    }

    // 4. 영상 생성을 위한 이미지 자동 선택
    console.log('[AUTO] 영상 생성용 이미지 자동 선택...');
    if (typeof window.DramaStep4 !== 'undefined' && typeof window.DramaStep4.autoSelectImages === 'function') {
      await window.DramaStep4.autoSelectImages();
    }

    // 5. 영상 생성
    if (typeof window.DramaStep4 !== 'undefined') {
      const selectedImages = window.DramaStep4.selectedImages || [];
      if (selectedImages.length > 0 && step3AudioUrl) {
        console.log('[AUTO] 영상 생성 시작...');
        showStatus('🎬 자동화: 영상 생성 시작...');
        if (typeof window.DramaStep4.generateVideoAuto === 'function') {
          await window.DramaStep4.generateVideoAuto();
        }
      } else {
        console.error('[AUTO] 영상 생성 불가: 이미지 또는 오디오 없음');
        showStatus('⚠️ 자동화 완료 (영상 생성은 수동으로 진행해주세요)');
      }
    }

  } catch (err) {
    console.error('[AUTO] 자동화 오류:', err);
    showStatus(`❌ 자동화 오류: ${err.message}`);
    hideLoadingOverlay();
  } finally {
    if (typeof window.DramaStep2 !== 'undefined') {
      window.DramaStep2.isFullAutoMode = false;
    }
    window.isFullAutoMode = false;
  }
}

// ===== 이벤트 리스너 설정 =====
document.addEventListener('DOMContentLoaded', () => {
  // TTS 제공자 및 음성 선택 초기화
  initTTSProviderButtons();
  initVoiceOptions();

  // Step3 가시성 체크
  setInterval(updateStep3Visibility, 1000);

  // 버튼 이벤트 바인딩
  document.getElementById('btn-extract-narration')?.addEventListener('click', extractNarration);
  document.getElementById('btn-generate-tts')?.addEventListener('click', generateTTS);
  document.getElementById('btn-generate-subtitle')?.addEventListener('click', generateSubtitle);
  document.getElementById('btn-download-audio')?.addEventListener('click', downloadAudio);
  document.getElementById('btn-download-srt')?.addEventListener('click', downloadSRT);
  document.getElementById('btn-download-vtt')?.addEventListener('click', downloadVTT);
  document.getElementById('btn-clear-step5')?.addEventListener('click', clearStep3);

  console.log('[DramaStep3] 초기화 완료');
});

// ===== 전역 노출 =====
window.DramaStep3 = {
  extractNarration,
  generateTTS,
  generateSubtitle,
  generateSubtitleAuto,
  downloadAudio,
  downloadSRT,
  downloadVTT,
  clearStep3,
  previewVoice,
  runAutoTTSAndVideo,
  get audioUrl() { return step3AudioUrl; },
  set audioUrl(v) { step3AudioUrl = v; },
  get subtitleData() { return step3SubtitleData; },
  get ttsProvider() { return step3TtsProvider; },
  get selectedVoice() { return step3SelectedVoice; }
};

// 기존 코드 호환
window.extractNarration = extractNarration;
window.generateTTS = generateTTS;
window.generateSubtitle = generateSubtitle;
window.downloadAudio = downloadAudio;
window.downloadSRT = downloadSRT;
window.downloadVTT = downloadVTT;
window.previewVoice = previewVoice;
window.runAutoTTSAndVideo = runAutoTTSAndVideo;
window.step5AudioUrl = step3AudioUrl;
window.step5SubtitleData = step3SubtitleData;
window.step5TtsProvider = step3TtsProvider;
window.step5SelectedVoice = step3SelectedVoice;
