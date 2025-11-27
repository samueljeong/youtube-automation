/**
 * sermon-firebase.js
 * Firebase 초기화, 저장/로드, 동기화, 백업/복원
 */

// ===== 데이터 버전 관리 =====
const CONFIG_VERSION = 3; // 버전 업데이트 시 증가

// ===== 기본 스타일 정의 (복구용) =====
const DEFAULT_STYLES = {
  general: [
    {
      id: "dawn_expository",
      name: "새벽예배 - 강해설교",
      description: "본론 중심",
      steps: [
        {id: "title", name: "제목 추천", order: 1, stepType: "step1"},
        {id: "analysis", name: "본문 분석", order: 2, stepType: "step1"},
        {id: "outline", name: "개요 작성", order: 3, stepType: "step2"}
      ]
    },
    {
      id: "sunday_topical",
      name: "주일예배 - 주제설교",
      description: "주제 중심",
      steps: [
        {id: "title", name: "제목 추천", order: 1, stepType: "step1"},
        {id: "analysis", name: "본문 분석", order: 2, stepType: "step1"},
        {id: "outline", name: "개요 작성", order: 3, stepType: "step2"}
      ]
    }
  ],
  series: [
    {
      id: "series_continuous",
      name: "수요예배 - 연속강해",
      description: "시리즈형 강해",
      steps: [
        {id: "title", name: "제목 추천", order: 1, stepType: "step1"},
        {id: "analysis", name: "본문 분석", order: 2, stepType: "step1"},
        {id: "outline", name: "개요 작성", order: 3, stepType: "step2"}
      ]
    }
  ]
};

// ===== Firebase 초기화 =====
const firebaseConfig = {
  apiKey: "AIzaSyBacmJDk-PG5FaoqnXV8Rg3P__AKOS2vu4",
  authDomain: "my-sermon-guides.firebaseapp.com",
  projectId: "my-sermon-guides",
  storageBucket: "my-sermon-guides.firebasestorage.app",
  messagingSenderId: "539520456089",
  appId: "1:539520456089:web:d6aceb7838baa89e70af08",
  measurementId: "G-KWN8TH7Z26"
};

firebase.initializeApp(firebaseConfig);
const db = firebase.firestore();

const USER_CODE = 'samuel123';
const PAGE_NAME = 'sermon';
const CONFIG_KEY = '_sermon-config';
const AUTO_SAVE_KEY = '_sermon-autosave';

// ===== Config 검증 및 마이그레이션 =====
function validateAndMigrateConfig(config) {
  console.log('[Config] 검증 시작, 현재 버전:', config?._version || '없음');

  // config가 없거나 유효하지 않으면 기본값 반환
  if (!config || typeof config !== 'object') {
    console.log('[Config] config가 없음 - 기본값 사용');
    return null; // 기본값 사용
  }

  // 필수 필드 검증
  if (!config.categories || !Array.isArray(config.categories) || config.categories.length === 0) {
    console.log('[Config] categories 없음 - 기본값 사용');
    return null;
  }

  if (!config.categorySettings || typeof config.categorySettings !== 'object') {
    console.log('[Config] categorySettings 없음 - 기본값 사용');
    return null;
  }

  // 버전별 마이그레이션
  let needsSave = false;

  // 버전 1 -> 2: styles에 stepType 필드 추가
  if (!config._version || config._version < 2) {
    console.log('[Config] 버전 마이그레이션: 1 -> 2');
    Object.values(config.categorySettings).forEach(catSettings => {
      if (catSettings?.styles) {
        catSettings.styles.forEach(style => {
          if (style.steps) {
            style.steps.forEach((step, idx) => {
              // stepType이 없으면 추가
              if (!step.stepType) {
                step.stepType = idx < 2 ? 'step1' : 'step2';
              }
            });
          }
        });
      }
    });
    config._version = 2;
    needsSave = true;
  }

  // 버전 2 -> 3: 빈 스타일 복구 및 steps stepType 보장
  if (config._version < 3) {
    console.log('[Config] 버전 마이그레이션: 2 -> 3');

    // general과 series 카테고리에 기본 스타일 복구
    ['general', 'series'].forEach(catValue => {
      const catSettings = config.categorySettings[catValue];
      if (catSettings && (!catSettings.styles || catSettings.styles.length === 0)) {
        if (DEFAULT_STYLES[catValue]) {
          console.log(`[Config] ${catValue} 카테고리 기본 스타일 복구`);
          catSettings.styles = JSON.parse(JSON.stringify(DEFAULT_STYLES[catValue]));
          needsSave = true;
        }
      }
    });

    // 모든 스타일의 steps에 stepType 보장
    Object.values(config.categorySettings).forEach(catSettings => {
      if (catSettings?.styles) {
        catSettings.styles.forEach(style => {
          if (style.steps) {
            style.steps.forEach((step, idx) => {
              if (!step.stepType) {
                step.stepType = idx < 2 ? 'step1' : 'step2';
              }
            });
          }
        });
      }
    });

    config._version = 3;
    needsSave = true;
  }

  // 각 카테고리 설정 검증 및 복구
  config.categories.forEach(cat => {
    if (!config.categorySettings[cat.value]) {
      console.log('[Config] 카테고리 설정 생성:', cat.value);
      config.categorySettings[cat.value] = {
        masterGuide: '',
        styles: DEFAULT_STYLES[cat.value] ? JSON.parse(JSON.stringify(DEFAULT_STYLES[cat.value])) : []
      };
      needsSave = true;
    }
  });

  // 디버그: 현재 설정 상태 출력
  console.log('[Config] 검증 완료 - 카테고리:', config.categories.map(c => c.value));
  Object.keys(config.categorySettings).forEach(cat => {
    const styles = config.categorySettings[cat]?.styles || [];
    console.log(`[Config] ${cat}: ${styles.length}개 스타일`);
  });

  if (needsSave) {
    console.log('[Config] 마이그레이션 완료 - 저장 필요');
    // 비동기로 저장 (나중에 호출됨)
    setTimeout(() => {
      if (typeof saveConfig === 'function') {
        saveConfig();
        console.log('[Config] 마이그레이션된 설정 저장됨');
      }
    }, 1000);
  }

  return config;
}

// ===== 스타일 자동 선택 =====
function ensureStyleSelected() {
  console.log('[ensureStyleSelected] 호출됨');
  console.log('[ensureStyleSelected] currentCategory:', window.currentCategory);
  console.log('[ensureStyleSelected] currentStyleId:', window.currentStyleId);

  // currentCategory의 첫 번째 스타일 자동 선택
  const catSettings = window.config?.categorySettings?.[window.currentCategory];
  const styles = catSettings?.styles || [];

  console.log('[ensureStyleSelected] 스타일 수:', styles.length);
  if (styles.length > 0) {
    console.log('[ensureStyleSelected] 사용 가능한 스타일:', styles.map(s => s.id).join(', '));
  }

  if (styles.length > 0 && !window.currentStyleId) {
    window.currentStyleId = styles[0].id;
    console.log('[ensureStyleSelected] 스타일 자동 선택:', window.currentStyleId);
    return true;
  }

  // 선택된 스타일이 존재하는지 확인
  if (window.currentStyleId && styles.length > 0) {
    const exists = styles.some(s => s.id === window.currentStyleId);
    if (!exists) {
      window.currentStyleId = styles[0].id;
      console.log('[ensureStyleSelected] 스타일 재선택 (기존 스타일 없음):', window.currentStyleId);
      return true;
    }
    console.log('[ensureStyleSelected] 현재 스타일 유효함:', window.currentStyleId);
  }

  // 스타일이 없는 경우 경고
  if (styles.length === 0) {
    console.warn('[ensureStyleSelected] 경고: 카테고리에 스타일이 없습니다 -', window.currentCategory);
  }

  return false;
}

// ===== Firebase 로드 =====
async function loadFromFirebase() {
  try {
    const snapshot = await db.collection('users').doc(USER_CODE).collection(PAGE_NAME).get();

    if (!snapshot.empty) {
      snapshot.forEach(doc => {
        localStorage.setItem(doc.id, doc.data().value);
      });

      const configData = localStorage.getItem(CONFIG_KEY);
      if (configData) {
        try {
          const parsed = JSON.parse(configData);
          const validated = validateAndMigrateConfig(parsed);
          if (validated) {
            window.config = validated;
          }
          // validated가 null이면 기본 config 유지
        } catch (parseErr) {
          console.error('[Config] JSON 파싱 실패:', parseErr);
          // 파싱 실패시 기본 config 유지
        }
      }

      // 스타일 자동 선택
      ensureStyleSelected();

      console.log('✅ Firebase 동기화 완료');
      return true;
    }
    return false;
  } catch (err) {
    console.error('Firebase 로드 실패:', err);
    return false;
  }
}

// ===== Firebase 저장 (재시도 로직 포함) =====
async function saveToFirebase(key, value, retries = 0) {
  const MAX_RETRIES = 4;
  const RETRY_DELAYS = [2000, 4000, 8000, 16000]; // exponential backoff

  try {
    await db.collection('users').doc(USER_CODE).collection(PAGE_NAME).doc(key).set({
      value: value,
      updatedAt: firebase.firestore.FieldValue.serverTimestamp()
    });
    return true;
  } catch (err) {
    console.error(`Firebase 저장 실패 (시도 ${retries + 1}/${MAX_RETRIES + 1}):`, err);

    // 네트워크 오류인 경우에만 재시도
    const isNetworkError = err.code === 'unavailable' || err.code === 'deadline-exceeded' ||
                           err.message.includes('network') || err.message.includes('offline');

    if (isNetworkError && retries < MAX_RETRIES) {
      const delay = RETRY_DELAYS[retries];
      console.log(`${delay}ms 후 재시도...`);
      await new Promise(resolve => setTimeout(resolve, delay));
      return saveToFirebase(key, value, retries + 1);
    }

    return false;
  }
}

// ===== Config 저장 =====
async function saveConfig() {
  // 버전 정보 추가
  if (!window.config._version) {
    window.config._version = CONFIG_VERSION;
  }

  const configStr = JSON.stringify(window.config);
  localStorage.setItem(CONFIG_KEY, configStr);
  const success = await saveToFirebase(CONFIG_KEY, configStr);
  if (!success) {
    console.warn('⚠️ Firebase 저장 실패 - 로컬에만 저장됨');
  }
}

// ===== 자동 저장 함수 =====
let autoSaveTimeout = null;

async function autoSaveStepResults() {
  // debounce: 마지막 변경 후 2초 뒤에 저장
  if (autoSaveTimeout) {
    clearTimeout(autoSaveTimeout);
  }

  autoSaveTimeout = setTimeout(async () => {
    const autoSaveData = {
      category: window.currentCategory,
      styleId: window.currentStyleId,
      stepResults: window.stepResults,
      titleOptions: window.titleOptions,
      selectedTitle: window.selectedTitle,
      timestamp: new Date().toISOString()
    };

    const autoSaveStr = JSON.stringify(autoSaveData);
    localStorage.setItem(AUTO_SAVE_KEY, autoSaveStr);

    const success = await saveToFirebase(AUTO_SAVE_KEY, autoSaveStr);
    if (success) {
      console.log('💾 자동 저장 완료');
    } else {
      console.warn('⚠️ 자동 저장 실패 - 로컬에만 저장됨');
    }
  }, 2000);
}

function loadAutoSave() {
  try {
    const autoSaveStr = localStorage.getItem(AUTO_SAVE_KEY);
    if (!autoSaveStr) return false;

    const autoSaveData = JSON.parse(autoSaveStr);

    // 자동 저장된 데이터가 현재 카테고리/스타일과 일치하는지 확인
    if (autoSaveData.category === window.currentCategory && autoSaveData.styleId === window.currentStyleId) {
      window.stepResults = autoSaveData.stepResults || {};
      window.titleOptions = autoSaveData.titleOptions || [];
      window.selectedTitle = autoSaveData.selectedTitle || '';

      console.log('✅ 자동 저장된 데이터 복원 완료');
      return true;
    }

    return false;
  } catch (err) {
    console.error('자동 저장 데이터 로드 실패:', err);
    return false;
  }
}

// ===== 실시간 동기화 =====
let realtimeListeners = [];
let isUpdatingFromRemote = false;

function setupRealtimeSync() {
  // 기존 리스너 정리
  realtimeListeners.forEach(unsubscribe => unsubscribe());
  realtimeListeners = [];

  // CONFIG_KEY 실시간 동기화
  const configListener = db.collection('users').doc(USER_CODE).collection(PAGE_NAME).doc(CONFIG_KEY)
    .onSnapshot((doc) => {
      if (doc.exists && !isUpdatingFromRemote) {
        const remoteData = doc.data();
        const localTimestamp = localStorage.getItem(`${CONFIG_KEY}_timestamp`) || '0';
        const remoteTimestamp = remoteData.updatedAt?.toMillis().toString() || '0';

        // 원격 데이터가 로컬보다 최신인 경우에만 업데이트
        if (remoteTimestamp > localTimestamp) {
          isUpdatingFromRemote = true;
          localStorage.setItem(CONFIG_KEY, remoteData.value);
          localStorage.setItem(`${CONFIG_KEY}_timestamp`, remoteTimestamp);
          window.config = JSON.parse(remoteData.value);

          console.log('🔄 설정 동기화: 다른 기기에서 업데이트됨');

          // UI 업데이트
          if (typeof renderCategories === 'function') renderCategories();
          if (typeof renderStyles === 'function') renderStyles();
          if (typeof renderProcessingSteps === 'function') renderProcessingSteps();
          if (typeof renderResultBoxes === 'function') renderResultBoxes();
          if (typeof renderGuideTabs === 'function') renderGuideTabs();

          setTimeout(() => {
            isUpdatingFromRemote = false;
          }, 1000);
        }
      }
    }, (error) => {
      console.error('실시간 동기화 오류 (CONFIG):', error);
    });

  realtimeListeners.push(configListener);

  // AUTO_SAVE_KEY 실시간 동기화
  const autoSaveListener = db.collection('users').doc(USER_CODE).collection(PAGE_NAME).doc(AUTO_SAVE_KEY)
    .onSnapshot((doc) => {
      if (doc.exists && !isUpdatingFromRemote) {
        const remoteData = doc.data();
        const localTimestamp = localStorage.getItem(`${AUTO_SAVE_KEY}_timestamp`) || '0';
        const remoteTimestamp = remoteData.updatedAt?.toMillis().toString() || '0';

        // 원격 데이터가 로컬보다 최신인 경우에만 업데이트
        if (remoteTimestamp > localTimestamp) {
          isUpdatingFromRemote = true;
          localStorage.setItem(AUTO_SAVE_KEY, remoteData.value);
          localStorage.setItem(`${AUTO_SAVE_KEY}_timestamp`, remoteTimestamp);

          const autoSaveData = JSON.parse(remoteData.value);

          // 현재 카테고리/스타일과 일치하는 경우에만 적용
          if (autoSaveData.category === window.currentCategory && autoSaveData.styleId === window.currentStyleId) {
            window.stepResults = autoSaveData.stepResults || {};
            window.titleOptions = autoSaveData.titleOptions || [];
            window.selectedTitle = autoSaveData.selectedTitle || '';

            console.log('🔄 작업 내용 동기화: 다른 기기에서 업데이트됨');
            if (typeof renderResultBoxes === 'function') renderResultBoxes();
          }

          setTimeout(() => {
            isUpdatingFromRemote = false;
          }, 1000);
        }
      }
    }, (error) => {
      console.error('실시간 동기화 오류 (AUTOSAVE):', error);
    });

  realtimeListeners.push(autoSaveListener);
}

// ===== 백업 및 복원 =====
function exportBackup() {
  try {
    const backupData = {
      version: '1.0',
      exportDate: new Date().toISOString(),
      config: window.config,
      guides: {},
      savedSermons: JSON.parse(localStorage.getItem('sermon-saved') || '[]')
    };

    // 모든 지침 데이터 백업
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith('guide-')) {
        backupData.guides[key] = localStorage.getItem(key);
      }
    }

    const dataStr = JSON.stringify(backupData, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `sermon-backup-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showStatus('✅ 백업 다운로드 완료!');
    setTimeout(hideStatus, 2000);
  } catch (err) {
    console.error('백업 실패:', err);
    alert('백업 생성 실패: ' + err.message);
  }
}

async function importBackup(file) {
  try {
    const reader = new FileReader();

    reader.onload = async (e) => {
      try {
        const backupData = JSON.parse(e.target.result);

        if (!backupData.version || !backupData.config) {
          throw new Error('유효하지 않은 백업 파일입니다.');
        }

        const confirmed = confirm(
          `백업 복원 시 현재 모든 설정이 덮어쓰여집니다.\n\n` +
          `백업 날짜: ${new Date(backupData.exportDate).toLocaleString('ko-KR')}\n\n` +
          `계속하시겠습니까?`
        );

        if (!confirmed) return;

        showStatus('♻️ 백업 복원 중...');

        // Config 복원
        window.config = backupData.config;
        await saveConfig();

        // 지침 복원
        if (backupData.guides) {
          for (const [key, value] of Object.entries(backupData.guides)) {
            localStorage.setItem(key, value);
            await saveToFirebase(key, value);
          }
        }

        // 저장된 설교 복원
        if (backupData.savedSermons) {
          localStorage.setItem('sermon-saved', JSON.stringify(backupData.savedSermons));
        }

        showStatus('✅ 백업 복원 완료!');

        // UI 새로고침
        setTimeout(() => {
          location.reload();
        }, 1500);

      } catch (err) {
        console.error('백업 복원 실패:', err);
        alert('백업 복원 실패: ' + err.message);
        hideStatus();
      }
    };

    reader.readAsText(file);
  } catch (err) {
    console.error('파일 읽기 실패:', err);
    alert('파일 읽기 실패: ' + err.message);
  }
}

// 전역 노출
window.db = db;
window.USER_CODE = USER_CODE;
window.PAGE_NAME = PAGE_NAME;
window.CONFIG_KEY = CONFIG_KEY;
window.AUTO_SAVE_KEY = AUTO_SAVE_KEY;
window.CONFIG_VERSION = CONFIG_VERSION;
window.DEFAULT_STYLES = DEFAULT_STYLES;
window.validateAndMigrateConfig = validateAndMigrateConfig;
window.ensureStyleSelected = ensureStyleSelected;
window.loadFromFirebase = loadFromFirebase;
window.saveToFirebase = saveToFirebase;
window.saveConfig = saveConfig;
window.autoSaveStepResults = autoSaveStepResults;
window.loadAutoSave = loadAutoSave;
window.setupRealtimeSync = setupRealtimeSync;
window.exportBackup = exportBackup;
window.importBackup = importBackup;
