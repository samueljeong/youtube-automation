/**
 * Drama Lab - 메인 모듈
 * Firebase, 전역변수, 세션관리, 네비게이션
 *
 * 화면 Step 기준: Step1(대본) → Step2(이미지) → Step3(TTS) → Step4(영상) → Step5(업로드)
 */

// ===== 데이터 버전 관리 =====
const CONFIG_VERSION = 2; // 버전 업데이트 시 증가

// ===== 안전한 localStorage 저장 함수 (용량 초과 방지) =====
window.safeLocalStorageSet = function(key, value) {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch (e) {
    if (e.name === 'QuotaExceededError' || e.code === 22) {
      console.warn(`[localStorage] 용량 초과 - ${key} 저장 실패, 오래된 데이터 정리 중...`);
      // 오래된 drama 데이터 정리
      window.cleanupOldDramaData();
      try {
        localStorage.setItem(key, value);
        return true;
      } catch (e2) {
        console.error(`[localStorage] 정리 후에도 저장 실패 - ${key}`);
        showStatus('⚠️ 저장 공간 부족 - 이전 데이터를 정리해주세요');
        return false;
      }
    }
    console.error(`[localStorage] 저장 오류 - ${key}:`, e);
    return false;
  }
};

// ===== 오래된 drama 데이터 정리 =====
window.cleanupOldDramaData = function() {
  const keysToClean = [
    '_drama-step3-audio-url',
    '_drama-step3-subtitle',
    '_drama-step3-script-text',
    '_drama-step4-images',
    '_drama-step4-character-images',
    '_drama-gpt-prompts',
    '_drama-step1-result'
  ];

  let totalCleaned = 0;
  keysToClean.forEach(key => {
    try {
      const data = localStorage.getItem(key);
      if (data && data.length > 100000) {  // 100KB 이상은 삭제
        localStorage.removeItem(key);
        totalCleaned += data.length;
        console.log(`[localStorage] 대용량 데이터 삭제: ${key} (${Math.round(data.length / 1024)}KB)`);
      }
    } catch (e) {}
  });

  if (totalCleaned > 0) {
    console.log(`[localStorage] 총 ${Math.round(totalCleaned / 1024)}KB 정리됨`);
  }
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

// ===== 상수 =====
const USER_CODE = 'samuel123';
const PAGE_NAME = 'drama';
const GUIDE_PASSWORD = '5555';
const GPT_PRO_PASSWORD = '6039';
const CONFIG_KEY = '_drama-config';

// ===== 전역 변수 =====
let guideUnlocked = false;
let gptProUnlocked = false;
let currentCategory = '10min';
let currentGuideStep = '';
let stepResults = {};

// 워크플로우 박스 관련
let workflowBoxes = [];
let nextBoxId = 1;
let nextStep1BoxNum = 1;
let nextStep2BoxNum = 1;
let step1Collapsed = false;
let step2Collapsed = false;

// 카테고리/설정
let customDurationText = localStorage.getItem('_drama-duration-text') || '';
const videoCategories = [
  // 기존 카테고리
  '간증', '드라마', '명언', '마음', '철학', '인간관계',
  // 시니어 타겟 신규 카테고리
  '옛날이야기', '마음위로', '인생명언'
];
let selectedCategory = localStorage.getItem('_drama-video-category') || '간증';
let customDirective = localStorage.getItem('_drama-custom-directive') || '';

// ===== 💰 비용 추적 시스템 =====
window.dramaCosts = {
  step1: 0,      // Claude 대본 생성
  step1_5: 0,    // GPT 프롬프트 분석
  step2: 0,      // 이미지 생성 (FLUX)
  step3: 0,      // TTS (Google/Naver)
  step4: 0       // 영상 생성 (Creatomate)
};

// 비용 추가 함수
window.addCost = function(step, amount) {
  if (typeof amount !== 'number' || isNaN(amount)) return;

  const stepKey = step.replace('step', 'step').replace('.', '_');
  if (window.dramaCosts.hasOwnProperty(stepKey)) {
    window.dramaCosts[stepKey] += amount;
  } else if (step === 'step1.5' || step === 'step1_5') {
    window.dramaCosts.step1_5 += amount;
  }

  window.updateCostDisplay();
  console.log(`[Cost] ${step}: +₩${amount.toLocaleString()} (총: ₩${window.getTotalCost().toLocaleString()})`);
};

// 총 비용 계산
window.getTotalCost = function() {
  return Object.values(window.dramaCosts).reduce((sum, cost) => sum + cost, 0);
};

// 비용 초기화
window.resetCosts = function() {
  window.dramaCosts = { step1: 0, step1_5: 0, step2: 0, step3: 0, step4: 0 };
  window.updateCostDisplay();
};

// UI 업데이트
window.updateCostDisplay = function() {
  const totalEl = document.getElementById('total-cost-display');
  const step1El = document.getElementById('cost-step1');
  const step1_5El = document.getElementById('cost-step1-5');
  const step2El = document.getElementById('cost-step2');
  const step3El = document.getElementById('cost-step3');
  const step4El = document.getElementById('cost-step4');

  if (totalEl) totalEl.textContent = '₩' + window.getTotalCost().toLocaleString();
  if (step1El) step1El.textContent = '₩' + window.dramaCosts.step1.toLocaleString();
  if (step1_5El) step1_5El.textContent = '₩' + window.dramaCosts.step1_5.toLocaleString();
  if (step2El) step2El.textContent = '₩' + window.dramaCosts.step2.toLocaleString();
  if (step3El) step3El.textContent = '₩' + window.dramaCosts.step3.toLocaleString();
  if (step4El) step4El.textContent = '₩' + window.dramaCosts.step4.toLocaleString();
};

// 설정 객체
let config = {
  categories: ['10min', '20min', '30min'],
  processingSteps: [
    { id: 'character', name: '캐릭터 설정' },
    { id: 'storyline', name: '스토리라인' },
    { id: 'scene', name: '씬 구성' },
    { id: 'dialogue', name: '대사 작성' }
  ]
};

// ===== Config 검증 및 마이그레이션 =====
function validateAndMigrateConfig(loadedConfig) {
  console.log('[Drama Config] 검증 시작');
  console.log('[Drama Config] 입력 버전:', loadedConfig?._version || '없음');
  console.log('[Drama Config] 현재 CONFIG_VERSION:', CONFIG_VERSION);

  // config가 없거나 유효하지 않으면 기본값 반환
  if (!loadedConfig || typeof loadedConfig !== 'object') {
    console.log('[Drama Config] config가 없음 - 기본값 사용');
    return null;
  }

  // 필수 필드 검증
  if (!loadedConfig.categories || !Array.isArray(loadedConfig.categories)) {
    console.log('[Drama Config] categories 없음 - 기본값 사용');
    return null;
  }

  console.log('[Drama Config] 카테고리 목록:', loadedConfig.categories);

  let needsSave = false;

  // 버전 1 -> 2: processingSteps 필드 확인 및 추가
  if (!loadedConfig._version || loadedConfig._version < 2) {
    console.log('[Drama Config] 버전 마이그레이션: 1 -> 2');

    // processingSteps가 없으면 추가
    if (!loadedConfig.processingSteps) {
      console.log('[Drama Config] processingSteps 추가');
      loadedConfig.processingSteps = [
        { id: 'character', name: '캐릭터 설정' },
        { id: 'storyline', name: '스토리라인' },
        { id: 'scene', name: '씬 구성' },
        { id: 'dialogue', name: '대사 작성' }
      ];
    }

    loadedConfig._version = 2;
    needsSave = true;
  }

  // 디버그: 최종 config 상태 출력
  console.log('[Drama Config] 검증 완료');
  console.log('[Drama Config] - 카테고리:', loadedConfig.categories.length + '개');
  console.log('[Drama Config] - processingSteps:', (loadedConfig.processingSteps || []).length + '개');
  console.log('[Drama Config] - 버전:', loadedConfig._version);

  if (needsSave) {
    console.log('[Drama Config] 마이그레이션 완료 - 저장 필요');
    setTimeout(() => {
      saveConfig();
      console.log('[Drama Config] 마이그레이션된 설정 저장됨');
    }, 1000);
  }

  return loadedConfig;
}

// ===== 워크플로우 세션 검증 및 마이그레이션 =====
function validateAndMigrateSession(session) {
  if (!session || typeof session !== 'object') {
    return null;
  }

  let needsSave = false;

  // 필수 필드 확인 및 추가
  if (!session.step1) {
    session.step1 = { topic: '', mainCharacter: '', benchmark: {}, script: '' };
    needsSave = true;
  }
  if (!session.step2) {
    session.step2 = { provider: 'gemini', images: [], characters: [], scenes: [] };
    needsSave = true;
  }
  if (!session.step3) {
    session.step3 = { provider: 'google', voice: '', audioUrl: '', subtitle: '' };
    needsSave = true;
  }
  if (!session.step4) {
    session.step4 = { videoUrl: '', duration: '', format: 'mp4' };
    needsSave = true;
  }
  if (!session.step5) {
    session.step5 = { status: 'draft', youtubeId: '', youtubeUrl: '', scheduledAt: '' };
    needsSave = true;
  }
  if (!session.metadata) {
    session.metadata = { title: '', description: '', tags: [], thumbnail: { prompt: '', url: '' } };
    needsSave = true;
  }

  if (needsSave) {
    console.log('[Drama Session] 세션 구조 마이그레이션 완료');
  }

  return session;
}

// ===== Step 네비게이션 함수 =====
function scrollToStep(containerId) {
  const container = document.getElementById(containerId);
  if (container) {
    container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    const stepNum = containerId.replace('-container', '');
    updateStepNavActive(stepNum);
  }
}

function updateStepNavActive(stepNum) {
  document.querySelectorAll('.step-nav-btn').forEach(btn => {
    btn.classList.remove('active');
    if (btn.dataset.step === stepNum) {
      btn.classList.add('active');
    }
  });
}

function updateStepNavCompleted(stepNum, completed = true) {
  const btn = document.querySelector(`.step-nav-btn[data-step="${stepNum}"]`);
  if (btn) {
    if (completed) {
      btn.classList.add('completed');
      const status = btn.querySelector('.step-status');
      if (status) status.textContent = '✓';
    } else {
      btn.classList.remove('completed');
      const status = btn.querySelector('.step-status');
      if (status) status.textContent = '○';
    }
  }
}

function detectCurrentStep() {
  // 화면 기준 Step 목록
  const steps = ['step1', 'step2', 'step3', 'step4', 'step5'];
  const contentArea = document.querySelector('.content-area');
  if (!contentArea) return;

  const scrollTop = contentArea.scrollTop;
  let currentStep = 'step1';

  for (const step of steps) {
    const container = document.getElementById(`${step}-container`);
    if (container && container.offsetTop <= scrollTop + 100) {
      currentStep = step;
    }
  }

  updateStepNavActive(currentStep);
}

// ===== 워크플로우 세션 관리 시스템 =====
let workflowSession = {
  sessionId: null,
  createdAt: null,
  updatedAt: null,
  category: '10min',
  contentType: 'testimony',

  metadata: {
    title: '',
    description: '',
    tags: [],
    thumbnail: { prompt: '', url: '' }
  },

  // 화면 기준 Step 데이터
  step1: { topic: '', mainCharacter: '', benchmark: {}, script: '' },
  step2: { provider: 'gemini', images: [], characters: [], scenes: [] },
  step3: { provider: 'google', voice: '', audioUrl: '', subtitle: '' },
  step4: { videoUrl: '', duration: '', format: 'mp4' },
  step5: { status: 'draft', youtubeId: '', youtubeUrl: '', scheduledAt: '' }
};

function initWorkflowSession() {
  workflowSession.sessionId = 'session_' + Date.now().toString(36) + '_' + Math.random().toString(36).substr(2, 9);
  workflowSession.createdAt = new Date().toISOString();
  workflowSession.updatedAt = new Date().toISOString();
  console.log('[SESSION] 새 세션 생성:', workflowSession.sessionId);
  return workflowSession;
}

function updateSession(path, value) {
  const keys = path.split('.');
  let obj = workflowSession;
  for (let i = 0; i < keys.length - 1; i++) {
    if (!obj[keys[i]]) obj[keys[i]] = {};
    obj = obj[keys[i]];
  }
  obj[keys[keys.length - 1]] = value;
  workflowSession.updatedAt = new Date().toISOString();
  saveSessionToStorage();
  console.log(`[SESSION] 업데이트: ${path}`, value);
}

function getSession(path, defaultValue = null) {
  const keys = path.split('.');
  let value = workflowSession;
  try {
    for (const key of keys) {
      value = value[key];
    }
    return value !== undefined ? value : defaultValue;
  } catch {
    return defaultValue;
  }
}

function updateMetadata(data) {
  if (data.title) workflowSession.metadata.title = data.title;
  if (data.description) workflowSession.metadata.description = data.description;
  if (data.tags) workflowSession.metadata.tags = data.tags;
  if (data.thumbnail) workflowSession.metadata.thumbnail = data.thumbnail;
  workflowSession.updatedAt = new Date().toISOString();
  saveSessionToStorage();
  console.log('[SESSION] 메타데이터 업데이트:', workflowSession.metadata);
  syncMetadataToStep5();
}

function syncMetadataToStep5() {
  // Step5 (유튜브 업로드) UI에 메타데이터 동기화
  const titleInput = document.getElementById('step5-title') || document.getElementById('youtube-title');
  const descInput = document.getElementById('step5-description') || document.getElementById('youtube-description');
  const tagsInput = document.getElementById('step5-tags') || document.getElementById('youtube-tags');

  if (titleInput && workflowSession.metadata.title) {
    titleInput.value = workflowSession.metadata.title;
  }
  if (descInput && workflowSession.metadata.description) {
    descInput.value = workflowSession.metadata.description;
  }
  if (tagsInput && workflowSession.metadata.tags?.length) {
    tagsInput.value = workflowSession.metadata.tags.join(', ');
  }
}

function saveSessionToStorage() {
  try {
    localStorage.setItem('_drama-workflow-session', JSON.stringify(workflowSession));
  } catch (e) {
    console.warn('[SESSION] 저장 실패:', e);
  }
}

function loadSessionFromStorage() {
  try {
    const saved = localStorage.getItem('_drama-workflow-session');
    if (saved) {
      const parsed = JSON.parse(saved);
      // 세션 검증 및 마이그레이션
      const validated = validateAndMigrateSession(parsed);
      if (validated) {
        workflowSession = { ...workflowSession, ...validated };
        console.log('[SESSION] 로드 완료:', workflowSession.sessionId);
        return true;
      }
    }
  } catch (e) {
    console.warn('[SESSION] 로드 실패:', e);
  }
  return false;
}

function resetSession() {
  if (confirm('현재 작업 내용이 모두 초기화됩니다. 계속하시겠습니까?')) {
    localStorage.removeItem('_drama-workflow-session');
    localStorage.removeItem('_drama-qa-history');
    initWorkflowSession();
    location.reload();
  }
}

function getFullSession() {
  return JSON.parse(JSON.stringify(workflowSession));
}

function getSessionContext() {
  return `【 현재 작업 세션 정보 】
- 카테고리: ${workflowSession.category}
- 콘텐츠 유형: ${workflowSession.contentType === 'testimony' ? '간증' : '드라마'}
- 주제: ${workflowSession.step1.topic || '(미설정)'}
- 주인공: ${workflowSession.step1.mainCharacter || '(미설정)'}
- 제목: ${workflowSession.metadata.title || '(미생성)'}
`;
}

// ===== Firebase 함수 =====
async function loadFromFirebase() {
  console.log('[Firebase] 데이터 로드 시작');
  console.log('[Firebase] 경로: users/' + USER_CODE + '/pages/' + PAGE_NAME + '/data');

  try {
    const docRef = db.collection('users').doc(USER_CODE).collection('pages').doc(PAGE_NAME);
    const docSnap = await docRef.collection('data').get();

    console.log('[Firebase] 문서 수:', docSnap.size);

    docSnap.forEach(doc => {
      localStorage.setItem(doc.id, doc.data().value);
      console.log('[Firebase] 로드됨:', doc.id);
    });

    const configData = localStorage.getItem(CONFIG_KEY);
    console.log('[Firebase] CONFIG_KEY 데이터 존재:', !!configData);

    if (configData) {
      try {
        const parsed = JSON.parse(configData);
        console.log('[Firebase] Config 파싱 성공');
        // Config 검증 및 마이그레이션
        const validated = validateAndMigrateConfig(parsed);
        if (validated) {
          config = validated;
          console.log('[Firebase] Config 적용 완료');
        } else {
          console.log('[Firebase] Config 검증 실패 - 기본값 유지');
        }
      } catch (e) {
        console.warn('[Drama Config] 파싱 실패:', e);
      }
    } else {
      console.log('[Firebase] 저장된 Config 없음 - 기본값 사용');
    }

    console.log('[Firebase] 최종 config:', JSON.stringify(config));
    console.log('[Firebase] 데이터 로드 완료');
  } catch (err) {
    console.error('[Firebase] 로드 실패:', err);
  }
}

async function saveToFirebase(key, value) {
  try {
    const docRef = db.collection('users').doc(USER_CODE).collection('pages').doc(PAGE_NAME);
    await docRef.collection('data').doc(key).set({ value, updatedAt: new Date() });
    console.log(`[Firebase] ${key} 저장 완료`);
  } catch (err) {
    console.error('[Firebase] 저장 실패:', err);
  }
}

async function saveConfig() {
  // 버전 정보 추가
  if (!config._version) {
    config._version = CONFIG_VERSION;
  }

  const configStr = JSON.stringify(config);
  localStorage.setItem(CONFIG_KEY, configStr);
  await saveToFirebase(CONFIG_KEY, configStr);
}

// ===== 진행 상황 관리 =====
const completedSteps = new Set();

// 내부 step name을 사이드바 step으로 매핑
const stepMap = {
  'step1': 'step1', 'step3': 'step1',  // 대본 생성
  'step1_5': 'step1_5',  // GPT 프롬프트 분석
  'step4': 'step2',  // 이미지 생성
  'step5': 'step3',  // TTS
  'step6': 'step4',  // 영상 제작
  'step7': 'step5'   // 유튜브 업로드
};

/**
 * 단계별 상세 상태 업데이트
 * @param {string} stepName - 스텝 이름 (step1, step2, step3, step4, step5)
 * @param {string} status - 상태 ('idle', 'working', 'completed', 'error')
 * @param {string} message - 상세 메시지 (예: "GPT 기획 중...", "이미지 생성 3/5")
 */
function updateStepStatus(stepName, status, message = '') {
  const sidebarStep = stepMap[stepName] || stepName;
  const sidebarItem = document.querySelector(`.progress-step-sidebar[data-step="${sidebarStep}"]`);

  if (!sidebarItem) return;

  const innerDiv = sidebarItem.querySelector('div > div');
  const substatus = sidebarItem.querySelector('.step-substatus');
  const statusIcon = sidebarItem.querySelector('.step-status-icon');
  const indicator = sidebarItem.querySelector('.step-indicator');

  // 상태에 따른 스타일 및 아이콘 설정
  const statusStyles = {
    idle: { icon: '○', borderColor: 'rgba(255,255,255,0.3)', bgColor: 'rgba(255,255,255,0.1)' },
    working: { icon: '⏳', borderColor: '#fbbf24', bgColor: 'rgba(251,191,36,0.2)' },
    completed: { icon: '✓', borderColor: '#22c55e', bgColor: 'rgba(34,197,94,0.2)' },
    error: { icon: '✗', borderColor: '#ef4444', bgColor: 'rgba(239,68,68,0.2)' }
  };

  const style = statusStyles[status] || statusStyles.idle;

  if (innerDiv) {
    innerDiv.style.borderLeftColor = style.borderColor;
    innerDiv.style.background = style.bgColor;
  }

  if (statusIcon) {
    statusIcon.textContent = style.icon;
    statusIcon.style.color = status === 'working' ? '#fbbf24' :
                             status === 'completed' ? '#22c55e' :
                             status === 'error' ? '#ef4444' : 'white';
  }

  if (indicator) {
    indicator.style.background = status === 'working' ? '#fbbf24' :
                                  status === 'completed' ? '#22c55e' :
                                  status === 'error' ? '#ef4444' : 'rgba(255,255,255,0.3)';
  }

  // 메시지 업데이트
  if (substatus) {
    substatus.textContent = message || (status === 'idle' ? '대기' :
                                        status === 'working' ? '진행 중...' :
                                        status === 'completed' ? '완료' : '오류');
    substatus.style.color = status === 'working' ? '#fbbf24' :
                            status === 'completed' ? '#a5f3a0' :
                            status === 'error' ? '#fca5a5' : 'rgba(255,255,255,0.7)';
  }

  // 완료 시 completedSteps에 추가
  if (status === 'completed') {
    completedSteps.add(stepName);
  }

  console.log(`[Progress] ${sidebarStep}: ${status} - ${message}`);
}

function updateProgressIndicator(stepName) {
  completedSteps.add(stepName);

  const sidebarStep = stepMap[stepName] || stepName;

  // 상태를 'completed'로 업데이트
  updateStepStatus(sidebarStep, 'completed', '완료');

  // Step 네비게이션 버튼 업데이트
  updateStepNavCompleted(sidebarStep, true);
}

// ===== 패널 네비게이션 =====
function setActivePanel(panelId) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  const panel = document.getElementById(panelId);
  if (panel) panel.classList.add('active');

  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.remove('active');
    if (btn.dataset.panelTarget === panelId) {
      btn.classList.add('active');
    }
  });
}

// ===== 초기화 =====
document.addEventListener('DOMContentLoaded', async () => {
  console.log('[DramaMain] 초기화 시작...');
  console.log('[DramaMain] 초기 currentCategory:', currentCategory);
  console.log('[DramaMain] 초기 config:', JSON.stringify(config));

  // Firebase에서 데이터 먼저 로드 (중요: 세션보다 먼저!)
  console.log('[DramaMain] Firebase 로드 시작');
  await loadFromFirebase();
  console.log('[DramaMain] Firebase 로드 완료');
  console.log('[DramaMain] Firebase 후 config:', JSON.stringify(config));

  // 세션 로드 (Firebase 이후)
  console.log('[DramaMain] 세션 로드 시작');
  if (!loadSessionFromStorage()) {
    console.log('[DramaMain] 저장된 세션 없음 - 새 세션 생성');
    initWorkflowSession();
  } else {
    console.log('[DramaMain] 세션 로드 완료:', workflowSession.sessionId);
  }

  // 전역 변수 동기화 (중요!)
  syncGlobalVariables();

  // 스크롤 이벤트 리스너
  const contentArea = document.querySelector('.content-area');
  if (contentArea) {
    contentArea.addEventListener('scroll', detectCurrentStep);
  }

  // 네비게이션 버튼 이벤트
  document.querySelectorAll('.nav-btn[data-panel-target]').forEach(btn => {
    btn.addEventListener('click', () => {
      const panelId = btn.dataset.panelTarget;
      setActivePanel(panelId);

      if (btn.dataset.scrollTarget) {
        setTimeout(() => {
          scrollToStep(btn.dataset.scrollTarget);
        }, 100);
      }
    });
  });

  // 워크플로우 박스 로드 및 렌더링
  loadWorkflowBoxes();
  renderWorkflowBoxes();

  console.log('[DramaMain] 초기화 완료');
});

// ===== 전역 변수 동기화 함수 =====
function syncGlobalVariables() {
  // 전역 객체에 현재 값 동기화
  window.workflowSession = workflowSession;
  window.config = config;
  window.stepResults = stepResults;
  window.completedSteps = completedSteps;
  window.currentCategory = currentCategory;
  window.selectedCategory = selectedCategory;
  window.customDirective = customDirective;
  console.log('[DramaMain] 전역 변수 동기화 완료');
}

// ===== 전역 노출 =====
window.DramaMain = {
  // 상수
  USER_CODE, PAGE_NAME, GUIDE_PASSWORD, GPT_PRO_PASSWORD, CONFIG_KEY, CONFIG_VERSION,

  // 전역 변수 접근 (getter/setter로 항상 최신 값 반환)
  get guideUnlocked() { return guideUnlocked; },
  set guideUnlocked(v) { guideUnlocked = v; },
  get gptProUnlocked() { return gptProUnlocked; },
  set gptProUnlocked(v) { gptProUnlocked = v; },
  get currentCategory() { return currentCategory; },
  set currentCategory(v) { currentCategory = v; window.currentCategory = v; },
  get stepResults() { return stepResults; },
  get config() { return config; },
  get workflowSession() { return workflowSession; },

  // 네비게이션
  scrollToStep,
  updateStepNavActive,
  updateStepNavCompleted,
  setActivePanel,

  // 세션
  initWorkflowSession,
  updateSession,
  getSession,
  updateMetadata,
  saveSessionToStorage,
  loadSessionFromStorage,
  resetSession,
  getFullSession,
  getSessionContext,

  // 마이그레이션
  validateAndMigrateConfig,
  validateAndMigrateSession,

  // Firebase
  loadFromFirebase,
  saveToFirebase,
  saveConfig,

  // 진행상황
  updateProgressIndicator,
  completedSteps,

  // 전역 동기화
  syncGlobalVariables
};

// 전역 함수로도 노출 (기존 코드 호환)
window.scrollToStep = scrollToStep;
window.updateStepNavActive = updateStepNavActive;
window.updateStepNavCompleted = updateStepNavCompleted;
window.setActivePanel = setActivePanel;
window.initWorkflowSession = initWorkflowSession;
window.updateSession = updateSession;
window.getSession = getSession;
window.updateMetadata = updateMetadata;
window.saveSessionToStorage = saveSessionToStorage;
window.loadSessionFromStorage = loadSessionFromStorage;
window.resetSession = resetSession;
window.getFullSession = getFullSession;
window.getSessionContext = getSessionContext;
window.loadFromFirebase = loadFromFirebase;
window.saveToFirebase = saveToFirebase;
window.updateProgressIndicator = updateProgressIndicator;
window.updateStepStatus = updateStepStatus;
window.validateAndMigrateConfig = validateAndMigrateConfig;
window.validateAndMigrateSession = validateAndMigrateSession;
window.syncGlobalVariables = syncGlobalVariables;

// 전역 변수 노출 (초기값 - DOMContentLoaded 후 syncGlobalVariables로 업데이트됨)
window.db = db;
window.workflowSession = workflowSession;
window.config = config;
window.stepResults = stepResults;
window.completedSteps = completedSteps;
window.currentCategory = currentCategory;
window.selectedCategory = selectedCategory;
window.customDirective = customDirective;
window.videoCategories = videoCategories;
window.CONFIG_VERSION = CONFIG_VERSION;
window.workflowBoxes = workflowBoxes;
window.customDurationText = customDurationText;
window.nextBoxId = nextBoxId;
window.nextStep1BoxNum = nextStep1BoxNum;
window.nextStep2BoxNum = nextStep2BoxNum;
window.guideUnlocked = guideUnlocked;
window.gptProUnlocked = gptProUnlocked;

// ===== 메타데이터 생성 함수 =====
async function generateMetadataFromScript(script, contentType) {
  if (!script) return;

  console.log('[METADATA] 메타데이터 생성 시작...');
  showStatus('🏷️ 메타데이터 생성 중...');

  try {
    const response = await fetch('/api/drama/generate-metadata', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script, contentType })
    });

    const data = await response.json();

    if (data.ok && data.metadata) {
      updateMetadata({
        title: data.metadata.title,
        description: data.metadata.description,
        tags: data.metadata.tags
      });

      console.log('[METADATA] 생성 완료:', data.metadata);
      showStatus('✅ 메타데이터 자동 생성 완료!');
      showMetadataNotification(data.metadata);
    } else {
      console.warn('[METADATA] 생성 실패:', data.error);
    }
  } catch (err) {
    console.error('[METADATA] 오류:', err);
  }

  setTimeout(hideStatus, 3000);
}

function showMetadataNotification(metadata) {
  const titleField = document.getElementById('step7-title');
  const descField = document.getElementById('step7-description');
  const tagsField = document.getElementById('step7-tags');

  if (titleField && metadata.title) titleField.value = metadata.title;
  if (descField && metadata.description) descField.value = metadata.description;
  if (tagsField && metadata.tags) tagsField.value = metadata.tags;

  console.log('[METADATA] Step5 필드 자동 채움 완료:', metadata);

  const notification = document.createElement('div');
  notification.className = 'metadata-notification';
  notification.innerHTML = `
    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border: 1px solid #4CAF50; border-radius: 12px; padding: 16px;
                position: fixed; bottom: 20px; right: 20px; z-index: 10000;
                max-width: 400px; box-shadow: 0 8px 32px rgba(0,0,0,0.3);">
      <div style="color: #4CAF50; font-weight: bold; margin-bottom: 8px;">
        🏷️ YouTube 메타데이터 자동 생성 완료
      </div>
      <div style="color: #aaa; font-size: 13px; margin-bottom: 4px;">
        <strong>제목:</strong> ${metadata.title}
      </div>
      <div style="color: #888; font-size: 12px;">
        ✅ Step5 업로드 필드에 자동 입력되었습니다
      </div>
      <button onclick="this.parentElement.parentElement.remove()"
              style="position: absolute; top: 8px; right: 8px; background: none;
                     border: none; color: #666; cursor: pointer; font-size: 16px;">×</button>
    </div>
  `;
  document.body.appendChild(notification);
  setTimeout(() => notification.remove(), 5000);
}

window.generateMetadataFromScript = generateMetadataFromScript;
window.showMetadataNotification = showMetadataNotification;

// ===== 워크플로우 박스 시스템 =====

// 워크플로우 박스 저장
async function saveWorkflowBoxes() {
  localStorage.setItem('_drama-workflow-boxes', JSON.stringify(workflowBoxes));
  localStorage.setItem('_drama-next-box-id', nextBoxId.toString());
  localStorage.setItem('_drama-next-step1-num', nextStep1BoxNum.toString());
  localStorage.setItem('_drama-next-step2-num', nextStep2BoxNum.toString());
  await saveToFirebase('_drama-workflow-boxes', JSON.stringify(workflowBoxes));
  await saveToFirebase('_drama-next-box-id', nextBoxId.toString());
  await saveToFirebase('_drama-next-step1-num', nextStep1BoxNum.toString());
  await saveToFirebase('_drama-next-step2-num', nextStep2BoxNum.toString());
}

// 워크플로우 박스 불러오기
function loadWorkflowBoxes() {
  const saved = localStorage.getItem('_drama-workflow-boxes');
  const savedNextId = localStorage.getItem('_drama-next-box-id');
  const savedStep1Num = localStorage.getItem('_drama-next-step1-num');
  const savedStep2Num = localStorage.getItem('_drama-next-step2-num');

  if (saved) {
    workflowBoxes = JSON.parse(saved);
  }
  if (savedNextId) {
    nextBoxId = parseInt(savedNextId);
  }
  if (savedStep1Num) {
    nextStep1BoxNum = parseInt(savedStep1Num);
  }
  if (savedStep2Num) {
    nextStep2BoxNum = parseInt(savedStep2Num);
  }
  // Reset collapsed state to false to ensure boxes are visible
  step1Collapsed = false;
  step2Collapsed = false;
}

// 워크플로우 박스 렌더링
function renderWorkflowBoxes() {
  const container = document.getElementById('workflow-boxes-container');
  if (!container) return;

  if (workflowBoxes.length === 0) {
    container.innerHTML = `
      <div class="box" style="padding: .75rem;">
        <div style="display: flex; gap: 1rem; align-items: flex-start;">
          <!-- 왼쪽: 시간 지정 -->
          <div style="flex: 0 0 140px;">
            <div style="font-weight: 700; font-size: .85rem; color: #4b5563; margin-bottom: .35rem; display: flex; align-items: center; gap: .3rem;">
              <span style="font-size: 1rem;">⏱️</span> 시간
            </div>
            <input
              type="text"
              id="custom-duration-input"
              value="${customDurationText}"
              placeholder="예: 2분"
              style="width: 100%; padding: .5rem .55rem; font-size: .85rem; border-radius: 8px; border: 1px solid #e5e7eb; background: #f9fafb;"
            />
          </div>
          <!-- 오른쪽: 카테고리 선택 -->
          <div style="flex: 1;">
            <div style="font-weight: 700; font-size: .85rem; color: #4b5563; margin-bottom: .35rem; display: flex; align-items: center; gap: .3rem; justify-content: space-between;">
              <div style="display: flex; align-items: center; gap: .3rem;">
                <span style="font-size: 1rem;">🎬</span> 카테고리
              </div>
              <button
                id="btn-view-category-prompts"
                onclick="openCategoryPromptsModal(selectedCategory || '옛날이야기')"
                style="padding: .3rem .6rem; font-size: .7rem; border-radius: 6px; border: 1px solid #8b5cf6; background: white; color: #8b5cf6; cursor: pointer; font-weight: 500; transition: all 0.2s ease;"
                onmouseover="this.style.background='#8b5cf6'; this.style.color='white';"
                onmouseout="this.style.background='white'; this.style.color='#8b5cf6';"
              >📚 지침 보기</button>
            </div>
            <div id="category-toggle-container" style="display: flex; flex-wrap: wrap; gap: .4rem;">
              ${videoCategories.map(cat => `
                <button
                  class="category-toggle-btn ${selectedCategory === cat ? 'active' : ''}"
                  data-category="${cat}"
                  style="padding: .45rem .7rem; font-size: .8rem; border-radius: 20px; border: 2px solid ${selectedCategory === cat ? '#6366f1' : '#e5e7eb'}; background: ${selectedCategory === cat ? 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)' : '#fff'}; color: ${selectedCategory === cat ? '#fff' : '#6b7280'}; cursor: pointer; font-weight: ${selectedCategory === cat ? '600' : '500'}; transition: all 0.2s ease; box-shadow: ${selectedCategory === cat ? '0 2px 8px rgba(99, 102, 241, 0.3)' : 'none'};"
                >${cat}</button>
              `).join('')}
            </div>
          </div>
        </div>
        <!-- 사용자 지침 입력 (선택사항) -->
        <div style="margin-top: .75rem;">
          <div style="font-weight: 700; font-size: .85rem; color: #4b5563; margin-bottom: .35rem; display: flex; align-items: center; gap: .3rem;">
            <span style="font-size: 1rem;">📝</span> 지침 <span style="font-weight: 400; font-size: .75rem; color: #9ca3af;">(선택)</span>
          </div>
          <input
            type="text"
            id="custom-directive-input"
            value="${customDirective}"
            placeholder="예: 쇼팬하우어 명언, 부모님과의 갈등 이야기, 직장 스트레스 주제..."
            style="width: 100%; padding: .5rem .65rem; font-size: .85rem; border-radius: 8px; border: 1px solid #e5e7eb; background: #f9fafb;"
          />
          <div style="font-size: .7rem; color: #9ca3af; margin-top: .3rem;">
            구체적인 주제나 방향을 지시하면 해당 내용이 최우선으로 반영됩니다.
          </div>
        </div>
      </div>
    `;

    // 시간 입력 이벤트
    const durationInput = document.getElementById('custom-duration-input');
    if (durationInput) {
      durationInput.addEventListener('input', (e) => {
        customDurationText = e.target.value.trim();
        window.customDurationText = customDurationText;
        localStorage.setItem('_drama-duration-text', customDurationText);
        saveToFirebase('_drama-duration-text', customDurationText);
      });
    }

    // 사용자 지침 입력 이벤트
    const directiveInput = document.getElementById('custom-directive-input');
    if (directiveInput) {
      directiveInput.addEventListener('input', (e) => {
        customDirective = e.target.value.trim();
        window.customDirective = customDirective;
        localStorage.setItem('_drama-custom-directive', customDirective);
        saveToFirebase('_drama-custom-directive', customDirective);
      });
    }

    // 카테고리 토글 버튼 이벤트
    const categoryButtons = document.querySelectorAll('.category-toggle-btn');
    categoryButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const cat = e.target.dataset.category;
        selectedCategory = cat;
        window.selectedCategory = selectedCategory;
        localStorage.setItem('_drama-video-category', cat);
        saveToFirebase('_drama-video-category', cat);
        renderWorkflowBoxes(); // UI 갱신
      });
    });
    return;
  }

  // workflowBoxes가 있을 경우의 렌더링은 여기에 추가 가능
  // 현재는 기본 UI만 표시
}

// ===== 카테고리 프롬프트 모달 관련 =====
let categoryPromptsData = null;
let currentCategoryForPrompts = null;
let currentPromptStep = 'step1_1_meta';

// 카테고리별 프롬프트 JSON 키 매핑
const categoryPromptKeyMap = {
  '옛날이야기': '옛날이야기',
  '마음위로': '마음위로',
  '인생명언': '인생명언',
  // 기존 카테고리는 nostalgia-drama-prompts.json에 없으므로 기본값 사용
  '간증': null,
  '드라마': null,
  '명언': null,
  '마음': null,
  '철학': null,
  '인간관계': null
};

// 프롬프트 데이터 로드
async function loadCategoryPrompts() {
  if (categoryPromptsData) return categoryPromptsData;

  try {
    const response = await fetch('/guides/nostalgia-drama-prompts.json');
    if (response.ok) {
      categoryPromptsData = await response.json();
      console.log('[CategoryPrompts] 프롬프트 데이터 로드 완료');
      return categoryPromptsData;
    }
  } catch (err) {
    console.error('[CategoryPrompts] 프롬프트 데이터 로드 실패:', err);
  }
  return null;
}

// 카테고리 프롬프트 모달 열기
async function openCategoryPromptsModal(category) {
  const modal = document.getElementById('category-prompts-modal');
  if (!modal) return;

  currentCategoryForPrompts = category;

  // 데이터 로드
  const data = await loadCategoryPrompts();
  if (!data) {
    alert('프롬프트 데이터를 불러올 수 없습니다.');
    return;
  }

  // 카테고리 키 확인
  const categoryKey = categoryPromptKeyMap[category];
  if (!categoryKey || !data.categories[categoryKey]) {
    alert(`"${category}" 카테고리의 프롬프트가 아직 정의되지 않았습니다.`);
    return;
  }

  // 모달 제목 업데이트
  document.getElementById('category-prompts-title').textContent = `${category} 프롬프트 지침`;

  // 첫 번째 Step 표시
  currentPromptStep = 'step1_1_meta';
  showCategoryPromptStep('step1_1_meta');

  modal.style.display = 'flex';
}

// 카테고리 프롬프트 모달 닫기
function closeCategoryPromptsModal() {
  const modal = document.getElementById('category-prompts-modal');
  if (modal) modal.style.display = 'none';
}

// Step 탭 전환
function showCategoryPromptStep(stepKey) {
  currentPromptStep = stepKey;

  // 탭 버튼 활성화 상태 업데이트
  document.querySelectorAll('.category-step-tab').forEach(btn => {
    if (btn.dataset.step === stepKey) {
      btn.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
      btn.style.color = 'white';
    } else {
      btn.style.background = '#e5e7eb';
      btn.style.color = '#374151';
    }
  });

  // 프롬프트 데이터 표시
  if (!categoryPromptsData || !currentCategoryForPrompts) return;

  const categoryKey = categoryPromptKeyMap[currentCategoryForPrompts];
  const categoryData = categoryPromptsData.categories[categoryKey];
  if (!categoryData || !categoryData.prompts[stepKey]) {
    document.getElementById('category-prompt-content').textContent = '해당 Step의 프롬프트가 정의되지 않았습니다.';
    return;
  }

  const promptData = categoryData.prompts[stepKey];

  // 메타 정보 업데이트
  document.getElementById('prompt-meta-name').textContent = promptData.name || '-';
  document.getElementById('prompt-meta-model').textContent = promptData.model || '-';
  document.getElementById('prompt-meta-input').textContent = promptData.inputFrom ? promptData.inputFrom.join(', ') : '없음 (첫 단계)';
  document.getElementById('prompt-meta-description').textContent = promptData.description || '-';

  // 시스템 프롬프트 표시
  const systemPrompt = promptData.systemPrompt || 'TODO';
  document.getElementById('category-prompt-content').textContent = systemPrompt;

  // 출력 스키마 표시
  const schema = promptData.outputSchema;
  if (schema) {
    document.getElementById('category-prompt-schema').textContent = JSON.stringify(schema, null, 2);
  } else {
    document.getElementById('category-prompt-schema').textContent = '스키마 정의 없음';
  }
}

// 프롬프트 복사
function copyCategoryPrompt() {
  const content = document.getElementById('category-prompt-content').textContent;
  if (content) {
    navigator.clipboard.writeText(content);
    alert('프롬프트가 클립보드에 복사되었습니다.');
  }
}

// 전역 노출
window.saveWorkflowBoxes = saveWorkflowBoxes;
window.loadWorkflowBoxes = loadWorkflowBoxes;
window.renderWorkflowBoxes = renderWorkflowBoxes;
window.openCategoryPromptsModal = openCategoryPromptsModal;
window.closeCategoryPromptsModal = closeCategoryPromptsModal;
window.showCategoryPromptStep = showCategoryPromptStep;
window.copyCategoryPrompt = copyCategoryPrompt;

// ===== 🧪 테스트 모드 관리 =====
window.testMode = localStorage.getItem('_drama-test-mode') === 'true';

// 테스트 모드 초기화
function initTestMode() {
  const toggle = document.getElementById('test-mode-toggle');
  const switchEl = document.getElementById('test-mode-switch');
  const knobEl = document.getElementById('test-mode-knob');
  const boxEl = document.getElementById('test-mode-box');
  const indicatorEl = document.getElementById('step3-mode-indicator');

  if (!toggle || !switchEl || !knobEl) return;

  // 초기 상태 설정
  toggle.checked = window.testMode;
  updateTestModeUI(window.testMode);

  // 토글 이벤트
  toggle.addEventListener('change', function() {
    window.testMode = this.checked;
    localStorage.setItem('_drama-test-mode', this.checked);
    updateTestModeUI(this.checked);
    console.log('[TestMode]', this.checked ? '활성화' : '비활성화');
  });

  // 스위치 클릭 이벤트 (라벨 외 직접 클릭 시)
  switchEl.addEventListener('click', function() {
    toggle.checked = !toggle.checked;
    toggle.dispatchEvent(new Event('change'));
  });
}

// 테스트 모드 UI 업데이트
function updateTestModeUI(isTestMode) {
  const switchEl = document.getElementById('test-mode-switch');
  const knobEl = document.getElementById('test-mode-knob');
  const boxEl = document.getElementById('test-mode-box');
  const indicatorEl = document.getElementById('step3-mode-indicator');

  if (switchEl && knobEl) {
    if (isTestMode) {
      switchEl.style.background = '#4CAF50';
      knobEl.style.left = '26px';
    } else {
      switchEl.style.background = 'rgba(0,0,0,0.3)';
      knobEl.style.left = '2px';
    }
  }

  if (boxEl) {
    if (isTestMode) {
      boxEl.style.background = 'linear-gradient(135deg, #4CAF50 0%, #45a049 100%)';
    } else {
      boxEl.style.background = 'linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%)';
    }
  }

  if (indicatorEl) {
    if (isTestMode) {
      indicatorEl.innerHTML = '<span style="color: #4CAF50; font-weight: 700;">🧪 테스트 모드 활성화</span> - 비용 최소화 (500자, 2씬, 2명)';
    } else {
      indicatorEl.textContent = 'OpenRouter의 Claude Sonnet 4.5 기본 프롬프트로 최종 대본을 생성합니다.';
    }
  }
}

// DOM 로드 후 테스트 모드 초기화
document.addEventListener('DOMContentLoaded', initTestMode);

// 전역 노출
window.initTestMode = initTestMode;
window.updateTestModeUI = updateTestModeUI;
