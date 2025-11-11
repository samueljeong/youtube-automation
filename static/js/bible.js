// static/js/bible.js
document.addEventListener("DOMContentLoaded", () => {
  // ===== 요소 =====
  const monthInput = document.getElementById("dateMonth");
  const dayInput = document.getElementById("dateDay");
  const weekdaySpan = document.getElementById("dateWeekday");

  const verseInput = document.getElementById("verse");
  const verseText = document.getElementById("verseText");

  const btnMorning = document.getElementById("btnMakeMorning");
  const btnEvening = document.getElementById("btnMakeEvening");

  const morningBox = document.getElementById("morningMessage");
  const eveningBox = document.getElementById("eveningMessage");

  const toggleGuides = document.getElementById("toggleGuides");
  const guidelineContent = document.getElementById("guidelineContent");
  const guideMorning = document.getElementById("guideMorning");
  const guideEvening = document.getElementById("guideEvening");
  const guideImgPrompt = document.getElementById("guideImgPrompt");
  const guideTranslate = document.getElementById("guideTranslate");
  const btnSaveGuides = document.getElementById("btnSaveGuides");
  const guideSaveStatus = document.getElementById("guideSaveStatus");
  const gTabs = document.querySelectorAll(".g-tab");

  const btnCopyMorning = document.getElementById("btnCopyMorning");
  const btnCopyEvening = document.getElementById("btnCopyEvening");

  const btnTranslateMorning = document.getElementById("btnTranslateMorning");
  const btnTranslateEvening = document.getElementById("btnTranslateEvening");
  const translateBox = document.getElementById("translateBox");
  const btnCopyTranslate = document.getElementById("btnCopyTranslate");
  const translateTarget = document.getElementById("translateTarget");

  const btnGenMorningImg = document.getElementById("btnGenMorningImg");
  const btnGenEveningImg = document.getElementById("btnGenEveningImg");
  const morningImgBox = document.getElementById("morningImgBox");
  const eveningImgBox = document.getElementById("eveningImgBox");
  const morningImgPrompts = document.getElementById("morningImgPrompts");
  const eveningImgPrompts = document.getElementById("eveningImgPrompts");
  const morningMusic = document.getElementById("morningMusic");
  const eveningMusic = document.getElementById("eveningMusic");
  const btnCopyMorningMusic = document.getElementById("btnCopyMorningMusic");
  const btnCopyEveningMusic = document.getElementById("btnCopyEveningMusic");

  const loadingBar = document.getElementById("loadingBar");

  // ===== 공통 유틸 =====
  function showLoading(msg = "GPT 생성 중입니다...") {
    if (loadingBar) {
      loadingBar.textContent = msg;
      loadingBar.classList.remove("hidden");
    }
  }
  function hideLoading() {
    if (loadingBar) loadingBar.classList.add("hidden");
  }

  function autoResize(el) {
    if (!el) return;
    el.style.height = "auto";
    el.style.height = el.scrollHeight + "px";
  }
  document.querySelectorAll("textarea.auto-resize").forEach((el) => {
    autoResize(el);
    el.addEventListener("input", () => autoResize(el));
  });

  // ===== 날짜 처리 =====
  const LS_DATE_KEY = "bible-date";

  function updateWeekday(month, day) {
    try {
      const now = new Date();
      const year = now.getFullYear();
      // 서울 기준 날짜 객체
      const utcDate = new Date(Date.UTC(year, month - 1, day));
      // 요일 계산
      const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
      const w = weekdays[utcDate.getUTCDay()];
      if (weekdaySpan) weekdaySpan.textContent = `(${w})`;
    } catch (e) {
      console.warn("요일 계산 실패", e);
    }
  }

  function loadDate() {
    if (!monthInput || !dayInput) return;
    const saved = localStorage.getItem(LS_DATE_KEY);
    if (saved) {
      const { month, day } = JSON.parse(saved);
      monthInput.value = month;
      dayInput.value = day;
      updateWeekday(month, day);
    } else {
      const now = new Date();
      monthInput.value = now.getMonth() + 1;
      dayInput.value = now.getDate();
      updateWeekday(monthInput.value, dayInput.value);
    }
  }

  function saveDate() {
    if (!monthInput || !dayInput) return;
    const month = Number(monthInput.value);
    const day = Number(dayInput.value);
    localStorage.setItem(LS_DATE_KEY, JSON.stringify({ month, day }));
    updateWeekday(month, day);
  }

  if (monthInput) monthInput.addEventListener("change", saveDate);
  if (dayInput) dayInput.addEventListener("change", saveDate);
  loadDate();

  // ===== 지침 열고 닫기 =====
const btnGuideToggle = document.getElementById("btnGuideToggle");
const guideBox = document.getElementById("guideBox");
if (btnGuideToggle && guideBox) {
  btnGuideToggle.addEventListener("click", () => {
    guideBox.classList.toggle("hidden");
  });
}
  // ===== 지침 탭 =====
  if (gTabs && gTabs.length) {
    gTabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        gTabs.forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        const type = tab.dataset.g;
        // 전부 숨기고
        guideMorning.classList.add("hidden");
        guideEvening.classList.add("hidden");
        guideImgPrompt.classList.add("hidden");
        guideTranslate.classList.add("hidden");
        // 필요한 것만 켜기
        if (type === "morning") {
          guideMorning.classList.remove("hidden");
          autoResize(guideMorning);
        } else if (type === "evening") {
          guideEvening.classList.remove("hidden");
          autoResize(guideEvening);
        } else if (type === "image") {
          guideImgPrompt.classList.remove("hidden");
          autoResize(guideImgPrompt);
        } else if (type === "translate") {
          guideTranslate.classList.remove("hidden");
          autoResize(guideTranslate);
        }
      });
    });
  }

  // ===== 서버에서 지침 불러오기 =====
  async function loadGuidesFromServer() {
    try {
      const res = await fetch("/api/guides");
      const data = await res.json();
      const bible = data.bible || {};
      if (guideMorning) {
        guideMorning.value = bible.morning || "";
        autoResize(guideMorning);
      }
      if (guideEvening) {
        guideEvening.value = bible.evening || "";
        autoResize(guideEvening);
      }
      if (guideImgPrompt) {
        guideImgPrompt.value = bible.image_prompt || "";
        autoResize(guideImgPrompt);
      }
      if (guideTranslate) {
        guideTranslate.value = bible.translate || "";
        autoResize(guideTranslate);
      }
    } catch (e) {
      console.warn("지침 불러오기 실패", e);
    }
  }
  loadGuidesFromServer();

  // ===== 지침 저장 =====
  if (btnSaveGuides) {
    btnSaveGuides.addEventListener("click", async () => {
      const payload = {
        bible: {
          morning: guideMorning ? guideMorning.value : "",
          evening: guideEvening ? guideEvening.value : "",
          image_prompt: guideImgPrompt ? guideImgPrompt.value : "",
          translate: guideTranslate ? guideTranslate.value : "",
        },
      };
      await fetch("/api/guides", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (guideSaveStatus) {
        guideSaveStatus.textContent = "✅ 저장됨";
        setTimeout(() => (guideSaveStatus.textContent = ""), 2000);
      }
    });
  }

  // ===== 메시지 생성 =====
  async function makeMessage(type) {
    const verse = verseInput ? verseInput.value : "";
    const text = verseText ? verseText.value : "";
    const dateInfo =
      monthInput && dayInput
        ? `${monthInput.value}월 ${dayInput.value}일 ${weekdaySpan ? weekdaySpan.textContent : ""}`
        : "";

    const prompt = `날짜: ${dateInfo}\n본문: ${verse}\n본문 내용: ${text}\n`;

    showLoading(type === "morning" ? "아침 메시지 생성 중..." : "저녁 메시지 생성 중...");
    const res = await fetch("/api/bible", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        msg_type: type,
      }),
    });
    const data = await res.json();
    hideLoading();
    return data.reply || "";
  }

  if (btnMorning) {
    btnMorning.addEventListener("click", async () => {
      const msg = await makeMessage("morning");
      if (morningBox) {
        morningBox.value = msg;
        autoResize(morningBox);
      }
      localStorage.setItem("bible-morning-msg", msg);
    });
  }

  if (btnEvening) {
    btnEvening.addEventListener("click", async () => {
      const msg = await makeMessage("evening");
      if (eveningBox) {
        eveningBox.value = msg;
        autoResize(eveningBox);
      }
      localStorage.setItem("bible-evening-msg", msg);
    });
  }

  // ===== 로컬 메시지 복원 =====
  (function restoreMessages() {
    const m = localStorage.getItem("bible-morning-msg");
    const e = localStorage.getItem("bible-evening-msg");
    if (m && morningBox) {
      morningBox.value = m;
      autoResize(morningBox);
    }
    if (e && eveningBox) {
      eveningBox.value = e;
      autoResize(eveningBox);
    }
  })();

  // ===== 복사 버튼 =====
  if (btnCopyMorning && morningBox) {
    btnCopyMorning.addEventListener("click", () => {
      const text = morningBox.value || "";
      if (!text.trim()) return;
      navigator.clipboard.writeText(text);
    });
  }
  if (btnCopyEvening && eveningBox) {
    btnCopyEvening.addEventListener("click", () => {
      const text = eveningBox.value || "";
      if (!text.trim()) return;
      navigator.clipboard.writeText(text);
    });
  }

 // 번역 버튼
const btnTransMorning = document.getElementById("btnTransMorning");
const btnTransEvening = document.getElementById("btnTransEvening");
const btnCopyTrans = document.getElementById("btnCopyTrans");
const selLang = document.getElementById("selLang");
const transOutput = document.getElementById("transOutput");

async function doTranslate(text) {
  if (!text.trim()) return;
  showLoading(); // 너가 쓰고 있는거
  const res = await fetch("/api/translate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      target: selLang.value || "en",
    }),
  });
  const data = await res.json();
  hideLoading();
  if (data.ok) {
    transOutput.value = data.result;
  }
}

if (btnTransMorning) {
  btnTransMorning.addEventListener("click", () => {
    const src = document.getElementById("morningMessage").value || "";
    doTranslate(src);
  });
}
if (btnTransEvening) {
  btnTransEvening.addEventListener("click", () => {
    const src = document.getElementById("eveningMessage").value || "";
    doTranslate(src);
  });
}
if (btnCopyTrans) {
  btnCopyTrans.addEventListener("click", () => {
    if (transOutput.value.trim()) navigator.clipboard.writeText(transOutput.value);
  });
}
  // ===== 이미지 프롬프트 =====
 function renderImgPrompts(list) {
  if (!imgPromptArea) return;
  imgPromptArea.innerHTML = "";
  list.forEach((item, idx) => {
    const div = document.createElement("div");
    div.className = "img-item";
    div.innerHTML = `
      <div class="img-item-header">
        <span>Shot ${idx + 1}</span>
        <button class="btn small copy-shot">복사</button>
      </div>
      <textarea class="auto-resize">${item.en || ""}</textarea>
    `;
    imgPromptArea.appendChild(div);

    div.querySelector(".copy-shot").addEventListener("click", () => {
      navigator.clipboard.writeText(item.en || "");
    });
  });
}

async function askImagePrompts(from) {
  const sourceId = from === "morning" ? "morningMessage" : "eveningMessage";
  const box = document.getElementById(sourceId);
  if (!box) return;
  const text = box.value || "";
  if (!text.trim()) return;

  showLoading();
  const res = await fetch("/api/image-prompts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text, when: from }),
  });
  const data = await res.json();
  hideLoading();

  renderImgPrompts(data.prompts || []);
  if (musicPrompt && data.music) {
    musicPrompt.value = data.music;
  }
}

// 이미 선언된 버튼에 “이벤트만” 붙이기
if (btnGenMorningImg) {
  btnGenMorningImg.addEventListener("click", () => askImagePrompts("morning"));
}
if (btnGenEveningImg) {
  btnGenEveningImg.addEventListener("click", () => askImagePrompts("evening"));
}
if (btnCopyMusic && musicPrompt) {
  btnCopyMusic.addEventListener("click", () => {
    if (musicPrompt.value.trim()) {
      navigator.clipboard.writeText(musicPrompt.value);
    }
  });
}
});