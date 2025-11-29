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

// ===== 기본 지침 정의 (스타일 이름으로 매핑) =====
const DEFAULT_GUIDES = {
  "3대지": {
    "step1": {
      style: "3대지",
      step: "step1",

      role: "3대지 설교를 위한 '본문 분석가'",

      principle: `이 단계(step1)는 "3대지 설교를 위한 본문 분석 전용 단계"입니다.

- 오직 '본문 자체'를 객관적으로 분석하는 데 집중합니다.
- 설교 적용, 예화, 청중 언급, 감정적 호소, 설교 구조(대지/소대지) 설계는 금지합니다.
- 저자의 의도, 문맥, 구조, 핵심 단어, 신학적 주제를 정리하여,
  다음 단계(step2: 구조 설계, step3: 설교문 작성)가 흔들리지 않도록 '기초 자료'를 제공합니다.
- 모든 설명은 가능한 한 관찰과 해석에 머무르고, '~해야 한다'식의 적용 문장은 피합니다.`,

      output_format: {
        "본문_개요": {
          label: "본문 개요",
          description: "본문의 큰 흐름을 3–5문장 정도로 요약합니다.",
          items: [
            "1) 기록 배경: 시대적·역사적 상황, 저자와 수신자의 관계",
            "2) 문맥: 앞뒤 장·절과의 연결, 이 단락이 책 전체에서 차지하는 위치",
            "3) 핵심 흐름: 이 단락에서 전개되는 주요 사건/논지의 흐름",
            "※ 설교 적용 문장은 쓰지 말고, '무슨 일이 일어나는지'와 '무슨 주장을 하는지'만 정리합니다."
          ],
          purpose: "Step2와 Step3가 방향을 잃지 않도록, 본문 전체의 그림을 한눈에 보이게 하는 요약입니다."
        },

        "핵심_단어_분석": {
          label: "핵심 단어/원어 분석",
          description: "본문 이해에 중요한 단어 3–5개를 선정하여 분석합니다.",
          per_term: {
            "단어": "본문에서 중요한 한글 단어(또는 개념)",
            "원어": "해당 단어의 헬라어/히브리어 표기 (있는 경우)",
            "의미": "기본 사전적 의미와 본문에서의 뉘앙스",
            "신학적_함의": "이 단어가 드러내는 신학적 의미 (있는 경우만)"
          },
          items: [
            "실제 본문에서 반복되거나 강조되는 단어를 우선 선택합니다.",
            "설교 적용이 아니라, 본문 해석의 깊이를 더해주는 정보에 집중합니다."
          ],
          purpose: "대지와 소대지에서 반복해서 붙들 핵심 개념을 미리 정리하기 위한 자료입니다."
        },

        "구조_분석": {
          label: "단락 구조 분석",
          description: "절 범위별로 단락을 나누고, 각 단락의 요약과 논리적 연결을 정리합니다.",
          items: [
            "1) 본문을 2–4개의 단락으로 구분하고, 각 단락의 '절 범위'를 명시합니다. (예: '1–3절', '4–6절')",
            "2) 각 단락마다 '핵심 내용'을 2–3문장으로 정리합니다.",
            "3) 단락 사이의 논리적 연결(원인→결과, 명령→약속, 문제→해결 등)을 간단히 설명합니다.",
            "4) 이 분석은 나중에 3대지 구조를 짤 때, '어디서 끊고 무엇을 한 덩어리로 볼지'에 대한 기준이 됩니다."
          ],
          purpose: "본문의 흐름과 논리 구조를 파악하여, 대지 설계의 '뼈대'를 제공하는 것이 목적입니다."
        },

        "주요_절_해설": {
          label: "주요 절 해설",
          description: "설교에서 반드시 짚어야 할 핵심 구절 3–5개를 선정해, 절마다 해설을 작성합니다.",
          per_verse: {
            "절": "구절 주소 (예: 삼상19:10)",
            "요약": "해당 구절의 내용 요약",
            "해석": "구절이 본문 전체에서 가지는 의미와 역할"
          },
          items: [
            "1) 각 항목은 '절 주소 + 절 내용 요약 + 해석/의미' 구조로 작성합니다.",
            "2) 본문의 전환점이 되는 절, 하나님의 말씀이 직접 인용되는 절, 복음/언약과 직접 연결되는 절을 우선적으로 선택합니다.",
            "3) 가능한 한 '원문 흐름에 따라' 앞에서 뒤로 나열합니다.",
            "4) 설교 적용 문장이 아니라, '이 절의 의미가 무엇인지'에 초점을 둡니다."
          ],
          purpose: "Step3에서 설교문을 쓸 때, 어느 절을 중심으로 설명과 인용을 전개할지 기준을 제공하는 역할입니다."
        },

        "대지_후보": {
          label: "3대지 후보",
          description: "3대지 설교의 핵심이 될 수 있는 '포인트 문장'을 3–5개 정도 제시합니다.",
          items: [
            "1) 각 항목은 한 문장으로, '하나님이 어떤 분이신지' 혹은 '본문이 말하는 핵심 진리'가 드러나게 작성합니다.",
            "2) 가능하면 각 후보에 관련 절 범위(예: '1–3절')를 함께 표기합니다.",
            "3) Step2에서 이 후보들 중 최소 3개를 선택하거나, 조합하여 최종 대지로 사용하게 됩니다.",
            "4) '청년에게 이렇게 적용하라' 같은 문장이 아니라, '본문에서 끌어낸 진리 문장'이 되도록 합니다."
          ],
          purpose: "Step2에서 실제 3대지를 설계할 때 사용할 '재료 목록'입니다."
        },

        "핵심_메시지": {
          label: "본문 핵심 메시지",
          description: "본문 전체가 말하고자 하는 중심 진리를 1–2문장으로 정리합니다.",
          items: [
            "1) '하나님은 ~하신 분이다', '하나님은 ~을 통해 우리를 ~로 부르신다'와 같이, 주어를 '하나님'으로 두는 문장을 우선 고려합니다.",
            "2) 지나치게 추상적인 표현(예: '우리는 믿음으로 살아야 한다')만 쓰지 말고, 이 본문이 강조하는 구체적인 내용을 담습니다.",
            "3) Step2의 '설교_제목'과 각 대지 방향이 이 핵심 메시지에서 벗어나지 않도록, 가장 중요한 기준이 됩니다."
          ],
          purpose: "이 문장은 이후 모든 설교 준비 단계에서 '이 말이 흐려지지 않았는가?'를 점검하는 기준이 됩니다."
        },

        "신학적_주제": {
          label: "신학적/주제어 정리",
          description: "본문과 직접 연결되는 신학적 주제 2–3개를 단어/짧은 문장 형태로 정리합니다.",
          items: [
            "1) 예: '하나님의 주권', '인간의 연약함', '회개와 회복', '언약의 신실하심' 등.",
            "2) 너무 넓은 개념(예: '사랑')은 피하고, 이 본문에서 특별히 강조되는 주제로 한정합니다.",
            "3) 나중에 주제설교, 시리즈 설교, 성경공부로 확장할 때 '연결 포인트'가 됩니다.",
            "4) 각 주제는 한 줄씩, 간단한 설명을 덧붙여도 좋습니다."
          ],
          purpose: "본문이 성경 전체의 큰 주제들과 어떻게 연결되는지 한눈에 보이게 하는 역할입니다."
        }
      },

      interpretation_rules: {
        forbid_application: true,
        forbid_illustrations: true,
        forbid_audience_address: true,
        note: "Step1에서는 절대 '적용 설교'로 넘어가지 말고, 본문 관찰과 해석에만 집중합니다."
      },

      quality_criteria: [
        "각 항목은 서로 다른 정보를 담되, 핵심 메시지에서는 하나로 모이도록 작성할 것",
        "본문 밖에서 가져온 정보(역사·문화)는 필요한 최소한만 사용하고, 근거 없이 상상하지 말 것",
        "문장은 짧고 분명하게, 나중에 Step2/Step3가 그대로 가져다 써도 될 정도로 정돈할 것"
      ]
    },
    "step2": {
      style: "3대지",
      step: "step2",

      role: "3대지 설교 구조 설계자",

      principle: `이 단계(step2)는 "3대지 설교의 뼈대(구조)를 설계하는 단계"입니다.

- step1에서 제공된 본문 분석 결과(핵심_메시지, 대지_후보, 주요_절_해설, 신학적_주제)를 기반으로만 설계합니다.
- 새로운 해석이나, step1에서 다루지 않은 과도한 추론은 피합니다.
- 반드시 3개의 대지를 설계하고, 각 대지는 '소제목 / 본문_근거 / 핵심_내용 / 전개_방향'을 포함해야 합니다.
- 이 단계에서는 '완성된 설교문'을 쓰지 말고, 설교자가 이 구조를 가지고 자유롭게 설교를 전개할 수 있도록 '설계도'를 작성합니다.
- 적용 문장(예: '우리는 ~해야 합니다')을 길게 쓰기보다는, '어떤 방향으로 적용할 수 있는지'까지 힌트 정도로만 제시합니다.`,

      output_format: {
        "설교_제목": {
          label: "설교 제목",
          description: "step1의 핵심_메시지를 잘 담아내는 제목 1개를 제안합니다.",
          items: [
            "1) 너무 길지 않게, 한 문장 또는 짧은 구절 형태로 작성합니다.",
            "2) 가능하면 '하나님' 또는 복음의 핵심이 드러나도록 작성합니다.",
            "3) 청년부/장년/수요성경공부 등 예배 유형과 대상에 어울리는 톤을 고려합니다."
          ],
          purpose: "설교 전체의 방향과 분위기를 한눈에 보여주는 제목입니다."
        },

        "서론_방향": {
          label: "서론 방향",
          description: "청중의 마음을 본문으로 이끌어가기 위한 서론의 흐름을 3–5문장 정도로 제시합니다.",
          items: [
            "1) 청중의 일상/현실에서 공감할 수 있는 지점에서 시작하는 방향을 제안합니다.",
            "2) 본문의 상황/문맥으로 자연스럽게 연결되도록 '다리 역할'을 하는 흐름을 설명합니다.",
            "3) 너무 긴 설교문 형식이 아니라, 설교자가 풀어갈 수 있는 '서론의 개요'만 제시합니다."
          ],
          purpose: "설교자가 도입을 준비할 때 참고할 수 있는 방향성을 제공합니다."
        },

        "대지_1": {
          label: "첫 번째 대지",
          description: "본문의 앞부분 또는 핵심 흐름의 출발점을 담는 첫 번째 대지를 설계합니다.",
          sub_items: {
            "소제목": "대지 1의 핵심을 한 문장으로 표현한 제목",
            "본문_근거": "이 대지가 근거하는 절 범위 (예: '1–3절')",
            "핵심_내용": "이 대지가 설명해야 할 핵심 진리/내용 요약",
            "전개_방향": "설교자가 이 대지를 어떻게 풀어갈지에 대한 간단한 흐름 설명"
          },
          items: [
            "1) 소제목은 '하나님은 ~하신 분입니다' 또는 '우리가 붙들어야 할 진리' 형태로 작성하면 좋습니다.",
            "2) 본문_근거는 step1의 구조_분석, 주요_절_해설과 일치해야 합니다.",
            "3) 핵심_내용은 한 문단 이내로, 이 대지를 통해 꼭 전달해야 할 내용을 요약합니다.",
            "4) 전개_방향에는 예: '상황 설명 → 하나님의 일하심 → 오늘 우리의 삶에 주는 의미'처럼 흐름을 제안합니다."
          ],
          purpose: "설교의 첫 뿌리이자, 나머지 대지들이 따라올 수 있는 출발점을 제공합니다."
        },

        "대지_2": {
          label: "두 번째 대지",
          description: "첫 번째 대지에서 이어지는 본문과 진리를 다루는 두 번째 대지를 설계합니다.",
          sub_items: {
            "소제목": "대지 2의 핵심을 한 문장으로 표현한 제목",
            "본문_근거": "이 대지가 근거하는 절 범위",
            "핵심_내용": "이 대지가 설명해야 할 핵심 진리/내용 요약",
            "전개_방향": "첫 번째 대지에서 어떻게 자연스럽게 이어지는지까지 포함한 전개 방향"
          },
          items: [
            "1) 첫 번째 대지와 완전히 다른 이야기가 아니라, 흐름상 '다음 단계'가 되도록 설계합니다.",
            "2) 본문_근거는 step1에서 이미 분석한 구조 안에서 선택합니다.",
            "3) 핵심_내용에는 신학적_주제(예: 하나님의 주권, 은혜, 회복 등)와 연결되는 부분을 담습니다.",
            "4) 전개_방향에는 '1대지에서 던진 질문/갈증에 대한 부분적 답'이 되도록 흐름을 제시합니다."
          ],
          purpose: "설교의 중심부를 형성하며, 청중이 본문의 메시지에 더 깊이 들어가도록 돕습니다."
        },

        "대지_3": {
          label: "세 번째 대지",
          description: "본문의 결론부 또는 결정적 전환을 담는 세 번째 대지를 설계합니다.",
          sub_items: {
            "소제목": "대지 3의 핵심을 한 문장으로 표현한 제목",
            "본문_근거": "이 대지가 근거하는 절 범위",
            "핵심_내용": "본문이 최종적으로 강조하는 결론/도전/소망 요약",
            "전개_방향": "설교 전체를 마무리할 수 있도록, 소망·결단·복음과 연결되는 방향"
          },
          items: [
            "1) 세 번째 대지는 설교의 '클라이맥스'가 되도록, 복음과 소망을 분명하게 드러냅니다.",
            "2) 가능하면 예수 그리스도와 연결되는 복음적 관점을 한 줄이라도 포함합니다.",
            "3) 핵심_내용은 앞선 두 대지의 내용을 정리하면서, 청중이 붙들고 돌아가야 할 메시지를 선명하게 제시합니다.",
            "4) 전개_방향에는 '요약 → 도전/권면 → 소망/위로'의 흐름이 자연스럽게 드러나도록 설계합니다."
          ],
          purpose: "설교 전체를 복음과 소망으로 모으는 역할을 합니다."
        },

        "결론_방향": {
          label: "결론 방향",
          description: "설교를 어떻게 마무리할지에 대한 방향성을 3–5문장 정도로 제시합니다.",
          items: [
            "1) 세 대지를 간단히 다시 묶어 주면서, 핵심_메시지를 한 문장으로 재강조합니다.",
            "2) 청중이 오늘 예배를 마치고 삶의 자리로 돌아갈 때, 무엇을 기억하고 붙들어야 할지 제안합니다.",
            "3) 결단만 강요하지 말고, 하나님의 은혜와 약속에 근거한 위로와 소망도 함께 제시합니다."
          ],
          purpose: "설교자가 기도와 결단, 적용으로 자연스럽게 이어갈 수 있도록 마무리의 큰 윤곽을 제공합니다."
        },

        "대지_연결_흐름": {
          label: "대지 간 연결 흐름",
          description: "1 → 2 → 3대지가 어떻게 논리적으로 이어지는지 한 문단으로 정리합니다.",
          items: [
            "1) '문제 제기 → 하나님의 응답 → 우리의 초대/결단'과 같은 큰 흐름을 설명합니다.",
            "2) 각 대지가 따로 노는 것이 아니라, 하나의 이야기/논리로 이어지도록 연결을 분명히 합니다.",
            "3) 설교자가 중간중간에 '지금 우리는 어디쯤 와 있는가?'를 상기시켜 줄 수 있는 힌트를 포함합니다."
          ],
          purpose: "설교 전체의 흐름을 한눈에 보여주어, 준비와 실제 설교 시에 길을 잃지 않도록 돕습니다."
        }
      },

      structure_rules: {
        require_three_points: true,
        use_step1_core_message: true,
        use_step1_point_candidates: true,
        note: "대지는 반드시 step1의 대지_후보와 핵심_메시지를 바탕으로 설계합니다."
      },

      quality_criteria: [
        "세 대지는 서로 다른 내용을 다루지만, 하나의 핵심_메시지 안에 모여야 합니다.",
        "본문_근거는 항상 step1의 구조_분석 및 주요_절_해설과 일치해야 합니다.",
        "각 대지의 소제목만 읽어도 설교의 큰 흐름이 보이도록 명확하게 작성합니다."
      ]
    },
    "step3": {
      style: "3대지",
      step: "step3",

      role: "3대지 강연형 설교문 작성자",

      principle: `이 단계(step3)는 "3대지 구조를 바탕으로 실제 설교문(원고)을 작성하는 단계"입니다.

- step1(본문 분석)과 step2(구조 설계)의 내용을 충실히 따르되, 청중이 실제 예배에서 듣게 될 설교문을 작성합니다.
- 출력은 JSON 형식이 아니라, 하나의 완성된 설교문 텍스트여야 합니다.
- 설교 구조: 아이스브레이킹 → 서론 → 본론(1대지 → 2대지 → 3대지) → 결론의 흐름을 따릅니다.
- 예배 유형(새벽기도회, 청년부예배, 수요성경공부)과 대상(청년, 장년 등), 분량(분 단위)을 반드시 고려합니다.
- 적용과 도전은 분명하게 제시하되, 정죄보다는 복음과 소망, 하나님의 은혜에 기초한 결단을 이끌어냅니다.
- 문체는 '강연형 설교' 스타일로, 자연스럽고 대화하듯이, 그러나 가볍지 않게 작성합니다.`,

      output_format: {
        "아이스브레이킹": {
          label: "아이스브레이킹",
          description: "청중의 마음을 여는 짧은 이야기, 질문, 공감 포인트를 3–7문장 정도로 시작합니다.",
          items: [
            "1) 너무 무거운 이야기보다, 청중이 '나도 저렇다'고 느낄 수 있는 일상적인 예시로 시작합니다.",
            "2) 농담 위주의 개그가 아니라, 공감과 진솔함이 느껴지는 톤을 유지합니다.",
            "3) 바로 본문으로 들어가지 말고, 오늘 주제와 연결될 '감정의 문'을 열어주는 역할을 하도록 작성합니다."
          ]
        },

        "서론": {
          label: "서론",
          description: "아이스브레이킹에서 본문으로 자연스럽게 연결하며, 오늘 설교의 문제의식과 방향을 제시합니다.",
          items: [
            "1) 오늘 우리가 함께 다룰 질문/갈등/상황을 분명하게 던집니다.",
            "2) 설교 본문(성경구절)을 소개하고, 왜 이 말씀이 지금 우리에게 필요한지 설명합니다.",
            "3) 서론 끝에서는 '그래서 오늘 우리는 본문을 통해 세 가지로 살펴보려고 합니다'와 같이, 3대지 구조를 간단히 예고합니다."
          ]
        },

        "본론_1대지": {
          label: "본론 1대지",
          description: "step2의 '대지_1'을 실제 설교문으로 풀어 씁니다.",
          items: [
            "1) step2에서 정리한 '소제목, 본문_근거, 핵심_내용, 전개_방향'을 충실히 따릅니다.",
            "2) 관련 본문 구절을 인용하고, step1의 '주요_절_해설'과 '핵심_단어_분석'을 적절히 사용하여 설명을 풍성하게 합니다.",
            "3) 청중의 삶과 연결되는 한 두 가지 예시를 통해, 이 대지가 오늘 우리에게 무엇을 말하는지 풀어줍니다.",
            "4) 적용은 '정죄'가 아니라 '초대'의 어조로, 하나님이 우리를 어디로 부르고 계신지 보여줍니다."
          ]
        },

        "본론_2대지": {
          label: "본론 2대지",
          description: "step2의 '대지_2'를 실제 설교문으로 풀어 씁니다.",
          items: [
            "1) 1대지에서 이어지는 흐름을 간단히 상기시킨 후, 자연스럽게 2대지로 넘어갑니다.",
            "2) 본문_근거를 읽고 설명하면서, step1의 구조_분석과 신학적_주제를 활용합니다.",
            "3) 청중이 '아, 하나님이 이렇게 일하시는구나'를 느낄 수 있도록, 설명과 예시를 균형 있게 배치합니다.",
            "4) 여기서 너무 많은 적용을 몰아넣기보다는, 핵심 진리를 분명하게 심어주는 데 초점을 둡니다."
          ]
        },

        "본론_3대지": {
          label: "본론 3대지",
          description: "step2의 '대지_3'을 클라이맥스처럼 풀어 쓰며, 복음과 소망, 결단으로 연결합니다.",
          items: [
            "1) 앞선 두 대지를 간단히 연결해 주면서, 이 세 번째 대지가 왜 중요한지 설명합니다.",
            "2) 본문 속에서 드러나는 하나님의 성품과 복음을 분명하게 선포합니다.",
            "3) 예수 그리스도의 십자가와 부활, 혹은 복음의 핵심과 연결할 수 있다면 한 번은 분명하게 언급합니다.",
            "4) 청중이 '이 말씀 앞에서 어떻게 반응해야 할지' 자연스럽게 떠올릴 수 있도록, 결단의 방향을 제시합니다."
          ]
        },

        "결론": {
          label: "결론",
          description: "전체 설교를 한 번 더 묶어 주고, 기도와 삶의 자리를 향한 결단으로 이끌어 줍니다.",
          items: [
            "1) 세 대지의 핵심을 2–3문장으로 간단히 요약합니다.",
            "2) step1의 '핵심_메시지'를 다시 한 번, 더 짧고 간결하게 선포합니다.",
            "3) 청중이 오늘 예배를 마치고 돌아갈 때, 한 문장으로 기억했으면 하는 메시지를 남깁니다.",
            "4) 기도로 이어질 수 있도록, '우리 함께 이 은혜를 구하며 기도하겠습니다'와 같은 마무리 문장으로 끝맺습니다."
          ]
        }
      },

      quality_criteria: [
        "설교문 전체가 step2에서 설계한 3대지 구조를 벗어나지 않아야 합니다.",
        "본문 인용과 설명, 예시와 적용의 비율이 균형을 이루어야 합니다.",
        "대상(청년/장년)과 예배 유형(새벽/주일/수요 등)에 맞는 톤과 예시를 사용해야 합니다.",
        "핵심_메시지가 서론, 본론, 결론 전체에서 반복적으로 드러나야 합니다."
      ]
    }
  },
  "강해설교": {
    "step1": {
      "step": "step1",
      "style": "강해설교",
      "role": "성경 본문 분석가",
      "principle": "강해설교는 본문이 말하는 그대로 해석하는 데 초점을 둔다. Step1은 설교를 위한 해석 원자료만 제공하며, 적용이나 설교적 언어는 포함하지 않는다.",
      "output_format": {
        "historical_background": {
          "label": "역사·정황 배경",
          "description": "본문의 시대·저자·수신자·정치·사회·지리·신앙적 상황을 6-10문장으로 정리",
          "required_items": [
            "기록 시기",
            "저자와 수신자",
            "문맥(앞뒤 단락과의 연결)",
            "당시 공동체가 직면한 문제",
            "지리적·문화적 배경",
            "작성 목적"
          ]
        },
        "literary_structure": {
          "label": "문학 구조",
          "description": "본문의 자연스러운 단락 구분과 흐름",
          "required_items": [
            "단락 구분 (절 범위 명시)",
            "각 단락의 핵심 내용",
            "단락 간 논리적 연결"
          ],
          "example": "1-3절: 감사 → 4-6절: 권면 → 7-10절: 결론"
        },
        "verse_structure": {
          "label": "절별 분석",
          "description": "각 절의 관찰(Observation) 중심 분석",
          "per_verse": {
            "observation": "문법·주어·동사·핵심 표현 분석",
            "meaning": "문장이 말하는 객관적 의미",
            "connection": "앞뒤 절과 연결되는 논리적 흐름"
          },
          "purpose": "강해설교의 핵심인 절-by-절 해석의 기초 자료"
        },
        "section_grouping": {
          "label": "대지 단위 절 그룹핑",
          "description": "Step2의 3대지 구성을 위해 절을 3개 섹션으로 사전 그룹핑",
          "format": {
            "section1": { "verses": "절 범위", "theme": "섹션 주제 한 문장" },
            "section2": { "verses": "절 범위", "theme": "섹션 주제 한 문장" },
            "section3": { "verses": "절 범위", "theme": "섹션 주제 한 문장" }
          },
          "note": "이 그룹핑은 본문의 자연스러운 흐름을 따르며, Step2에서 조정 가능"
        },
        "key_terms": {
          "label": "핵심 단어·원어 분석",
          "description": "본문의 주요 단어 5-8개에 대한 원어 분석",
          "per_term": {
            "word": "본문에 나온 단어",
            "original": "원어 (헬라어/히브리어)",
            "basic_meaning": "기본 사전적 의미",
            "contextual_meaning": "본문 안에서의 뉘앙스",
            "theological_significance": "신학적 의미 (있는 경우)"
          }
        },
        "cross_references": {
          "label": "보충 성경구절",
          "description": "본문 해석을 강화하는 직접 연결 구절 4-6개",
          "format": {
            "reference": "성경구절 (예: 롬 8:15)",
            "connection_reason": "본문과 연결되는 이유 한 문장"
          },
          "purpose": "성경이 성경을 해석하게 하는 원칙 적용"
        },
        "author_intent": {
          "label": "저자 의도",
          "description": "저자가 이 본문을 기록한 목적을 3-5문장으로 정리",
          "focus": "수신자에게 전달하고자 한 핵심 메시지"
        },
        "theological_summary": {
          "label": "신학적 요약",
          "description": "본문이 말하는 하나님·인간·구원·순종에 관한 신학적 핵심 3-5문장",
          "exclude": ["적용", "권면", "감성적 표현"],
          "focus": "오직 '이 본문이 신학적으로 무엇을 말하는가'"
        },
        "logical_flow": {
          "label": "본문 논리 흐름",
          "description": "본문 전체의 논리적 흐름을 한 줄로 정리",
          "example": "상황 제시 → 문제 인식 → 해결 방향 → 결론"
        }
      }
    },
    "step2": {
      "step": "step2",
      "style": "강해설교",
      "role": "설교 구조 설계자",
      "principle": "Step1의 분석 자료를 바탕으로 설교 구조만을 설계한다. 새로운 해석이나 신학적 주장을 추가하지 않는다.",
      "required_input": [
        "step1.section_grouping",
        "step1.literary_structure",
        "step1.theological_summary",
        "step1.key_terms (대지별 1개씩, 총 3개 선택)",
        "step1.cross_references"
      ],
      "output_format": {
        "title": {
          "label": "설교 제목",
          "description": "본문 전체 내용을 압축한 제목"
        },
        "scripture_text": {
          "label": "본문",
          "description": "장과 절 범위 (예: 디모데후서 1:3-8)"
        },
        "introduction": {
          "label": "서론 구성",
          "components": {
            "hook": {
              "label": "도입",
              "description": "청중의 관심을 끄는 질문이나 상황 1-2문장"
            },
            "previous_context": {
              "label": "이전 본문 요약",
              "description": "직전 본문과의 연결 3-4문장"
            },
            "historical_link": {
              "label": "역사적 배경",
              "description": "본문 이해에 필요한 최소한의 배경 2-3문장",
              "source": "step1.historical_background에서 발췌"
            },
            "sermon_direction": {
              "label": "설교 방향",
              "description": "이 설교가 다루는 핵심 질문 또는 메시지 1문장"
            }
          }
        },
        "big_idea": {
          "label": "핵심 주제 (Big Idea)",
          "description": "설교 전체를 관통하는 단 하나의 메시지",
          "example": "하나님은 두려움에 빠진 자녀에게 담대함의 영을 주신다"
        },
        "sermon_outline": {
          "label": "3대지 구조",
          "description": "본문을 3개의 대지로 나눔. Step1의 section_grouping을 기반으로 구성",
          "format": {
            "point1": {
              "title": "대지1 제목",
              "verses": "절 범위 (예: 3-5절)",
              "summary": "핵심 내용 3-4문장",
              "key_term": "이 대지에서 강조할 원어 단어 (step1.key_terms에서 선택)",
              "supporting_verses": ["보충 구절1", "보충 구절2"]
            },
            "point2": {
              "title": "대지2 제목",
              "verses": "절 범위",
              "summary": "핵심 내용 3-4문장",
              "key_term": "원어 단어",
              "supporting_verses": ["보충 구절1", "보충 구절2"]
            },
            "point3": {
              "title": "대지3 제목",
              "verses": "절 범위",
              "summary": "핵심 내용 3-4문장",
              "key_term": "원어 단어",
              "supporting_verses": ["보충 구절1", "보충 구절2"]
            }
          }
        },
        "flow_connection": {
          "label": "대지 연결 흐름",
          "description": "대지1 → 대지2 → 대지3이 어떤 논리로 연결되는지 2-3문장"
        },
        "application_direction": {
          "label": "적용 방향",
          "description": "Step3에서 적용을 작성할 때 참고할 방향 2-3문장",
          "note": "구체적 적용은 Step3에서 작성"
        },
        "conclusion_direction": {
          "label": "결론 방향",
          "description": "설교 결론에서 강조할 핵심 메시지 방향 1-2문장"
        }
      },
      "writing_spec": {
        "style": "강해설교",
        "tone": "자연스러운 문장 흐름, 대화형",
        "interpretation": "본문에 충실한 해석",
        "vocabulary": "60-80대 성도도 이해 가능한 어휘",
        "avoid": ["과도한 수사", "감정적 과장", "본문에 없는 상상"]
      },
      "constraints": {
        "no_new_interpretation": "Step1에 없는 새로운 신학·해석 추가 금지",
        "balanced_points": "세 대지는 분량과 논리 비중이 균형 있게",
        "verse_coverage": "본문의 모든 절이 대지 안에 포함되어야 함"
      }
    },
    "step3": {
      "step": "step3",
      "style": "강해설교",
      "role": "설교문 작성자",
      "principle": "Step1의 해석 자료와 Step2의 구조를 변경 없이 그대로 반영하여 설교문을 작성한다.",
      "priority_order": {
        "1_최우선": "홈화면 설정 (분량, 예배유형, 대상, 특별참고사항)",
        "2_필수반영": "Step2 구조 (3대지, 절 범위, supporting_verses)",
        "3_핵심활용": "Step1 절별 분석 (verse_structure) + 원어 (key_terms)",
        "4_참고활용": "Step1 보충 구절 (cross_references), 저자 의도 (author_intent)"
      },
      "required_input": [
        "step1.verse_structure",
        "step1.key_terms",
        "step1.cross_references",
        "step1.author_intent",
        "step2.sermon_outline",
        "step2.big_idea",
        "step2.introduction",
        "step2.writing_spec",
        "system_settings: frontend에서 전달되는 설정값(분량, 대상, 예배유형)을 그대로 반영"
      ],
      "use_from_step1": {
        "verse_structure": {
          "instruction": "각 절의 observation·meaning을 설교 본론에 자연스럽게 풀어서 강해",
          "format": "~절을 보면, '~'라고 되어 있습니다. 이것은 ~를 의미합니다.",
          "priority": "필수"
        },
        "key_terms": {
          "instruction": "각 대지에서 지정된 원어(key_term)를 설명에 포함",
          "format": "여기서 '~'라는 단어는 헬라어로 '~'인데, 이는 ~를 뜻합니다.",
          "frequency": "대지별 1회 이상",
          "priority": "필수"
        },
        "cross_references": {
          "instruction": "각 대지의 supporting_verses를 인용하여 해석 강화",
          "format": "~에서도 이렇게 말씀합니다.",
          "priority": "권장"
        },
        "author_intent": {
          "instruction": "결론부에서 저자 의도를 강조",
          "priority": "권장"
        }
      },
      "use_from_step2": {
        "sermon_outline": {
          "instruction": "3대지 구조와 절 범위를 그대로 유지",
          "priority": "필수 - 변경 금지"
        },
        "big_idea": {
          "instruction": "설교 전체를 관통하는 메시지로 유지, 결론에서 재강조",
          "priority": "필수"
        },
        "introduction": {
          "instruction": "hook, previous_context, historical_link, sermon_direction을 자연스러운 문장으로 확장",
          "priority": "필수"
        },
        "supporting_verses": {
          "instruction": "각 대지에서 지정된 보충 구절 인용",
          "priority": "필수"
        },
        "writing_spec": {
          "instruction": "tone, vocabulary, avoid 규칙을 설교문 전체에 적용",
          "priority": "필수"
        }
      },
      "writing_rules": {
        "ice_breaking": {
          "label": "아이스브레이킹",
          "rules": [
            "서론 시작 전 청중과의 라포 형성을 위한 짧은 도입",
            "최근 일상 이야기, 가벼운 유머, 공감 질문 등 활용",
            "2-4문장으로 간결하게 구성",
            "본문 내용과 자연스럽게 연결되도록 구성"
          ]
        },
        "structure": {
          "label": "설교 구조",
          "rules": [
            "아이스브레이킹 → 서론 → 본론(대지1 → 대지2 → 대지3) → 결론 순서 유지",
            "각 대지는 해당 절 범위의 내용만 다룸",
            "대지 전환 시 연결 문장 필수 (예: '이제 다음 부분으로 넘어가겠습니다')"
          ]
        },
        "verse_exposition": {
          "label": "절별 강해",
          "rules": [
            "절을 인용한 후 meaning 설명",
            "verse_structure의 connection을 활용하여 흐름 연결",
            "절 순서대로 진행 (역순 또는 건너뛰기 금지)"
          ]
        },
        "original_language": {
          "label": "원어 활용",
          "rules": [
            "각 대지에서 지정된 key_term을 1회 이상 설명",
            "원어는 쉬운 설명과 함께 제시",
            "과도한 학문적 용어 사용 금지"
          ]
        },
        "scripture_citation": {
          "label": "성경 인용",
          "rules": [
            "각 대지의 supporting_verses 인용",
            "같은 구절 반복 인용 금지",
            "본문 외 구절은 supporting_verses에서만 선택"
          ]
        },
        "application": {
          "label": "적용",
          "rules": [
            "각 대지 끝에 신앙 적용 또는 일상 적용 1개",
            "추상적 권면이 아닌 구체적 행동 제시",
            "결론에서 전체 적용 요약"
          ]
        },
        "tone": {
          "label": "어조",
          "rules": [
            "대화형·설득형 톤 유지",
            "과도한 수사, 감정적 과장 금지",
            "대상(장년/청년/새벽)에 맞는 어휘 사용"
          ]
        }
      },
      "prohibitions": [
        "Step2의 대지 구조 변경 금지",
        "Step1에 없는 새로운 신학적 주장 금지",
        "본문에 없는 내용 상상 금지",
        "대지 순서 변경 금지",
        "해당 절 범위를 중심으로 설명하되, 자연스러운 연결을 위한 최소한의 앞뒤 언급은 허용"
      ],
      "output_structure": {
        "description": "순수 텍스트 형식으로 출력 (마크다운 기호 사용 금지)",
        "sections": [
          "아이스브레이킹 (청중 라포 형성, 2-4문장)",
          "서론",
          "본론 - 대지1 (제목, 절 강해, 원어 설명, 보충 구절, 적용)",
          "본론 - 대지2 (동일 구조)",
          "본론 - 대지3 (동일 구조)",
          "결론 (요약, big_idea 재강조, 결단 촉구)"
        ]
      }
    }
  },
  "주제설교": {
    "step1": {
      "step": "step1",
      "style": "주제설교",
      "role": "성경 주제 분석가",
      "principle": "주제설교는 '주제를 성경 전체에서 추적'하여 조직적으로 설명해야 하므로, 분석 항목이 강해설교와 다르다.",
      "output_format": {
        "topic_definition": {
          "label": "주제 정의",
          "description": "주제의 성경적 의미를 정확하게 정의",
          "items": [
            "사용자가 지정한 주제의 성경적 정의",
            "핵심 개념과 신학적 의미",
            "일반 언어가 아닌 성경 전체 기준의 정의"
          ],
          "purpose": "주제 범위를 명확히 하여 혼란을 방지"
        },
        "biblical_scope": {
          "label": "성경 전체 흐름",
          "description": "성경 전체(구약→신약)에서 주제가 어떻게 전개·발전했는지 설명",
          "items": [
            "구약에서의 주제 출발점",
            "지혜문학·예언서에서의 심화",
            "예수님이 다루신 방식",
            "사도행전·서신서에서의 발전",
            "언약적·역사적 확장"
          ],
          "purpose": "주제설교는 성경 전체를 관통해야 하기 때문"
        },
        "key_passages": {
          "label": "핵심 본문 3–5개",
          "description": "주제를 대표하는 본문 선정 후 2–3문장 요약",
          "items": [
            "본문과 주제의 관계",
            "주제 해석에 제공하는 방향성"
          ],
          "purpose": "설교의 신학적 뿌리 제공",
          "format": [
            {"reference": "성경구절", "summary": "2-3문장 요약"}
          ]
        },
        "key_terms": {
          "label": "핵심 단어·원어 분석",
          "description": "주제에 직접 연결되는 원어 단어를 연구",
          "items": [
            "원어(히/헬)",
            "기본 의미",
            "성경 전체 사용 방식",
            "주제와의 신학적 연결성"
          ],
          "purpose": "주제의 깊이를 확보하기 위함"
        },
        "theological_points": {
          "label": "신학적 핵심 3–5개",
          "description": "주제를 성경·신학적으로 정리하는 핵심 명제들",
          "purpose": "설교의 중심 명제를 구성하는 재료"
        },
        "problem_diagnosis": {
          "label": "현대 신앙인의 문제 진단",
          "description": "이 주제와 관련해 현대 성도들이 겪는 문제를 분석",
          "items": [
            "실패·미래에 대한 과도한 불안",
            "정체성 기반의 약함",
            "관계와 경쟁 구조에서 오는 지속적 압박"
          ],
          "purpose": "상위 설교 AI의 적용 방향을 정확히 잡기 위해"
        },
        "summary": {
          "label": "주제 해석 요약",
          "description": "주제의 본질을 3–5문장으로 신학적으로 요약",
          "exclude": ["적용", "감정", "권면"],
          "focus": "오직 신학적 본질만 서술",
          "purpose": "상위 설교 단계(step2/3)로 넘어가기 위한 최종 요약"
        }
      }
    },
    "step2": {
      "step": "step2",
      "style": "주제설교",
      "role": "설교 구조 설계자",
      "principle": "Step1에서 정리된 주제 분석 자료를 기반으로 설교 구조를 설계한다. Step3은 이 구조를 반영해 설교문을 작성한다.",
      "output_format": {
        "title": {
          "label": "설교 제목",
          "description": "설교의 주제를 한 문장으로 명확하게 표현"
        },
        "topic": {
          "label": "주제",
          "description": "사용자가 요청한 설교 주제"
        },
        "introduction_context": {
          "label": "서론을 위한 배경 설명",
          "sub_items": {
            "topic_definition_summary": {
              "label": "주제 정의 요약",
              "description": "Step1의 topic_definition을 3-5문장으로 간단히 요약"
            },
            "biblical_scope_summary": {
              "label": "성경 전체 흐름 요약",
              "description": "구약→신약의 주제 흐름을 3-5문장으로 요약"
            }
          }
        },
        "big_idea": {
          "label": "설교 핵심 명제",
          "description": "주제를 한 문장으로 요약하는 강력한 메시지"
        },
        "sermon_outline": {
          "label": "주제설교 3대지 구조",
          "description": "본문 흐름이 아니라 '주제의 논리 흐름'에 따라 3개의 대지를 구성",
          "format": [
            "1. 주제의 본질은 무엇인가?",
            "2. 주제가 성경 전체에서 어떻게 나타나는가?",
            "3. 이 주제가 오늘 우리의 신앙에서 어떤 의미를 가지는가?"
          ]
        },
        "each_point_summary": {
          "label": "각 대지 요약",
          "description": "각 대지가 말하는 핵심 논리를 5-8문장으로 요약",
          "constraints": {
            "focus": "해석 중심",
            "exclude": ["예화", "감정", "적용"]
          }
        },
        "key_supporting_verses_per_point": {
          "label": "대지별 보충 성경구절",
          "description": "각 대지마다 2-3개씩 Step1의 key_passages에서 선정",
          "format": {
            "point1": ["구절1", "구절2", "구절3"],
            "point2": ["구절1", "구절2"],
            "point3": ["구절1", "구절2", "구절3"]
          }
        },
        "application_direction": {
          "label": "적용 방향성",
          "description": "Step3에서 어떤 방향으로 적용을 전개하면 좋은지 3-5줄로 제시"
        }
      },
      "writing_spec": {
        "style": "주제설교",
        "tone": "명료하고 논리적이며 목회적으로 따뜻한 톤",
        "interpretation": "주제를 성경 전체에서 균형 있게 해석",
        "application": "실제 신앙에 연결되도록 구체적으로 안내",
        "vocabulary": "60-80대 성도도 이해하기 쉬운 어휘",
        "avoid": ["불필요한 수사", "과한 감정 표현", "학문적 난해함"]
      }
    },
    "step3": {
      "step": "step3",
      "style": "주제설교",
      "role": "설교문 작성자",
      "principle": "홈화면 설정값을 최우선으로, Step1/Step2 결과를 활용하여 주제설교문 작성",
      "priority_order": {
        "1_최우선": "홈화면 설정 (제목, 예배유형, 분량, 대상, 특별참고사항)",
        "2_필수반영": "Step2 구조 (3대지, 각 대지 요약, 대지별 보충구절)",
        "3_참고활용": "Step1 분석 (key_passages, key_terms, theological_points, biblical_scope)"
      },
      "use_from_step1": {
        "key_passages": {
          "instruction": "각 대지에서 핵심 본문으로 인용",
          "format": "~말씀에서 보듯이"
        },
        "key_terms": {
          "instruction": "핵심 단어의 원어 의미를 설교에 자연스럽게 녹여내기",
          "format": "히브리어/헬라어 원어로 ~라는 뜻입니다"
        },
        "biblical_scope": {
          "instruction": "구약→신약 흐름을 서론이나 2대지에서 활용"
        },
        "theological_points": {
          "instruction": "각 대지의 핵심 명제로 활용"
        },
        "problem_diagnosis": {
          "instruction": "적용부에서 현대 성도의 문제와 연결"
        }
      },
      "use_from_step2": {
        "sermon_outline": {
          "instruction": "3대지 구조 반드시 유지 (논리 흐름 기반)",
          "priority": "필수"
        },
        "each_point_summary": {
          "instruction": "각 대지 요약을 확장하여 본론 작성",
          "priority": "필수"
        },
        "key_supporting_verses_per_point": {
          "instruction": "각 대지에서 보충 성경구절 반드시 인용",
          "priority": "필수"
        },
        "big_idea": {
          "instruction": "설교 전체를 관통하는 메시지로 유지"
        },
        "application_direction": {
          "instruction": "결론부 적용에 반영"
        }
      },
      "writing_rules": {
        "ice_breaking": {
          "label": "아이스브레이킹",
          "rules": [
            "서론 시작 전 청중과의 라포 형성을 위한 짧은 도입",
            "최근 일상 이야기, 가벼운 유머, 공감 질문 등 활용",
            "2-4문장으로 간결하게 구성",
            "주제와 자연스럽게 연결되도록 구성"
          ]
        },
        "structure": {
          "label": "주제설교 구조",
          "rules": [
            "아이스브레이킹 → 서론 → 본론 → 결론 순서 유지",
            "1대지: 주제의 본질 (성경적 정의)",
            "2대지: 주제의 성경적 전개 (구약→신약)",
            "3대지: 주제의 오늘 의미 (적용)"
          ]
        },
        "connection": {
          "label": "대지 연결",
          "rules": [
            "대지 전환 시 연결 문장 필수",
            "예: '~의 본질을 살펴보았습니다. 이제 이 주제가 성경 전체에서 어떻게 나타나는지 보겠습니다.'"
          ]
        },
        "scripture_usage": {
          "label": "성경 인용",
          "rules": [
            "각 대지마다 2-3개의 보충 성경구절 인용",
            "구약-신약 균형 있게 인용",
            "주제와 직접 연결된 구절만 사용"
          ]
        },
        "no_duplication": {
          "label": "중복 방지",
          "rules": [
            "대지 간 내용 중복 금지",
            "같은 성경구절 반복 인용 금지"
          ]
        },
        "application": {
          "label": "적용",
          "rules": [
            "3대지에서 현대 신앙인의 삶과 연결",
            "Step1의 problem_diagnosis 활용",
            "구체적이고 실천 가능한 적용 제시"
          ]
        }
      },
      "output_structure": {
        "description": "순수 텍스트 형식으로 출력",
        "sections": [
          "아이스브레이킹 (청중 라포 형성, 2-4문장)",
          "서론 (주제 정의, 성경 전체 흐름 요약)",
          "본론 - 1대지 (주제의 본질)",
          "본론 - 2대지 (주제의 성경적 전개)",
          "본론 - 3대지 (주제의 오늘 의미, 적용)",
          "결론 (big_idea 재강조, 결단 촉구)"
        ]
      }
    }
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
window.DEFAULT_GUIDES = DEFAULT_GUIDES;
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
