/**
 * Drama Lab - 메인 모듈
 * Firebase, 전역변수, 세션관리, 네비게이션
 *
 * 화면 Step 기준: Step1(대본) → Step2(이미지) → Step3(TTS) → Step4(영상) → Step5(업로드)
 */

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
      workflowSession = { ...workflowSession, ...parsed };
      console.log('[SESSION] 로드 완료:', workflowSession.sessionId);
      return true;
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
  try {
    const docRef = db.collection('users').doc(USER_CODE).collection('pages').doc(PAGE_NAME);
    const docSnap = await docRef.collection('data').get();

    docSnap.forEach(doc => {
      localStorage.setItem(doc.id, doc.data().value);
    });

    const configData = localStorage.getItem(CONFIG_KEY);
    if (configData) {
      try {
        config = JSON.parse(configData);
      } catch (e) { console.warn('Config 파싱 실패'); }
    }

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
  const configStr = JSON.stringify(config);
  localStorage.setItem(CONFIG_KEY, configStr);
  await saveToFirebase(CONFIG_KEY, configStr);
}

// ===== 진행 상황 관리 =====
const completedSteps = new Set();

function updateProgressIndicator(stepName) {
  completedSteps.add(stepName);

  // 사이드바 Step 버튼 업데이트
  const stepMap = {
    'step1': 'step1', 'step3': 'step1',  // 대본 생성
    'step4': 'step2',  // 이미지 생성
    'step5': 'step3',  // TTS
    'step6': 'step4',  // 영상 제작
    'step7': 'step5'   // 유튜브 업로드
  };

  const sidebarStep = stepMap[stepName] || stepName;

  const sidebarItem = document.querySelector(`.progress-step-sidebar[data-step="${sidebarStep}"]`);
  if (sidebarItem) {
    sidebarItem.classList.add('completed');
    const icon = sidebarItem.querySelector('.progress-icon');
    if (icon) icon.textContent = '✓';
  }

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

  // 세션 로드
  if (!loadSessionFromStorage()) {
    initWorkflowSession();
  }

  // Firebase에서 데이터 로드
  await loadFromFirebase();

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

  console.log('[DramaMain] 초기화 완료');
});

// ===== 전역 노출 =====
window.DramaMain = {
  // 상수
  USER_CODE, PAGE_NAME, GUIDE_PASSWORD, GPT_PRO_PASSWORD, CONFIG_KEY,

  // 전역 변수 접근
  get guideUnlocked() { return guideUnlocked; },
  set guideUnlocked(v) { guideUnlocked = v; },
  get gptProUnlocked() { return gptProUnlocked; },
  set gptProUnlocked(v) { gptProUnlocked = v; },
  get currentCategory() { return currentCategory; },
  set currentCategory(v) { currentCategory = v; },
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

  // Firebase
  loadFromFirebase,
  saveToFirebase,
  saveConfig,

  // 진행상황
  updateProgressIndicator,
  completedSteps
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

// 전역 변수 노출
window.db = db;
window.workflowSession = workflowSession;
window.config = config;
window.stepResults = stepResults;
window.completedSteps = completedSteps;
window.currentCategory = currentCategory;
window.selectedCategory = selectedCategory;
window.customDirective = customDirective;
window.videoCategories = videoCategories;
