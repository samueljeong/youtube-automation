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
    return {
      ttsEngine: document.getElementById('tts-engine')?.value || 'google',
      voiceStyle: document.getElementById('voice-style')?.value || 'warm',
      speechRate: parseFloat(document.getElementById('speech-rate')?.value) || 0.95
    };
  },

  // Step1 대본에서 씬 텍스트 가져오기
  getScriptTexts() {
    const step1Data = DramaSession.getStepData('step1');
    if (!step1Data?.content) return null;

    // 대본을 씬 단위로 분할 (간단한 분할)
    const content = step1Data.content;
    const scenes = [];

    // 씬 번호나 구분자로 분할
    const parts = content.split(/(?=씬\s*\d|Scene\s*\d|#\s*\d|\d+\.\s)/i);

    if (parts.length > 1) {
      parts.forEach((part, idx) => {
        const text = part.trim();
        if (text && text.length > 20) {
          scenes.push({
            id: `scene_${idx + 1}`,
            text: text
          });
        }
      });
    } else {
      // 분할 불가시 전체를 하나로
      scenes.push({
        id: 'scene_1',
        text: content
      });
    }

    return scenes;
  },

  // 음성 스타일에 따른 음성 선택
  getVoiceSettings(style) {
    const config = this.getConfig();
    const voiceMap = {
      'warm': { speaker: 'ko-KR-Wavenet-A', pitch: -2, volume: 0 },
      'neutral': { speaker: 'ko-KR-Wavenet-B', pitch: 0, volume: 0 },
      'dramatic': { speaker: 'ko-KR-Wavenet-C', pitch: 2, volume: 2 }
    };
    return voiceMap[style] || voiceMap['warm'];
  },

  // TTS 생성
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

      for (const scene of scenes) {
        if (progressBar) progressBar.style.width = `${(completed / total) * 100}%`;
        if (progressText) progressText.textContent = `${completed + 1} / ${total} 씬 생성 중...`;

        console.log(`[Step3] TTS 생성: ${scene.id}`);

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
            this.generatedAudios.push({
              id: scene.id,
              audioUrl: data.audioUrl,
              duration: data.duration || 0,
              text: scene.text.substring(0, 100) + '...'
            });
          } else {
            console.error(`[Step3] ${scene.id} TTS 실패:`, data.error);
          }
        } catch (err) {
          console.error(`[Step3] ${scene.id} TTS 오류:`, err);
        }

        completed++;
        await new Promise(r => setTimeout(r, 500)); // API 간격
      }

      if (progressBar) progressBar.style.width = '100%';
      if (progressText) progressText.textContent = '완료!';

      // 결과 저장
      DramaSession.setStepData('step3', {
        audios: this.generatedAudios,
        config: config
      });

      // 결과 표시
      this.displayResults();

      setTimeout(() => {
        if (progressPanel) progressPanel.classList.add('hidden');
      }, 1000);

      DramaUtils.showStatus(`TTS 생성 완료! (${this.generatedAudios.length}개 음성)`, 'success');

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
      audioList.innerHTML = this.generatedAudios.map((audio, idx) => `
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
          <p class="audio-preview">${DramaUtils.escapeHtml(audio.text)}</p>
        </div>
      `).join('');
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
    // 기존 재생 중지
    if (this.currentAudioPlayer) {
      this.currentAudioPlayer.pause();
      this.currentAudioPlayer.currentTime = 0;
    }

    const audio = document.getElementById(`audio-${idx}`);
    if (audio) {
      audio.play();
      this.currentAudioPlayer = audio;
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
