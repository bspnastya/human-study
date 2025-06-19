from __future__ import annotations
import random, time, datetime, secrets, threading, queue, re, itertools, requests
from typing import List, Dict
import streamlit as st, streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(
    page_title="Визуализация многоканальных изображений",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
html,body,.stApp,[data-testid="stAppViewContainer"],.main,.block-container{
  background:#808080!important;color:#111!important;}
h1,h2,h3,h4,h5,h6{color:#111!important;}
.question-card,* .question-card{color:#fff!important;}
.stButton>button{color:#fff!important;}
header[data-testid="stHeader"],div[data-testid="stHeader"]{display:none;}
.question-card{background:transparent!important;border:none!important;}
input[data-testid="stTextInput"]{height:52px!important;padding:0 16px!important;
                                 font-size:1.05rem;}
.stButton>button{min-height:52px!important;padding:0 20px!important;
                 border:1px solid #555!important;background:#222!important;
                 color:#ddd!important;border-radius:8px;}
#mobile-overlay{position:fixed;inset:0;z-index:9999;background:#808080;display:none;
  align-items:center;justify-content:center;color:#fff;font:500 1.2rem/1.5 sans-serif;
  text-align:center;padding:0 20px;}
@media (max-width:1023px){#mobile-overlay{display:flex;}}
</style>
<div id="mobile-overlay">
  Уважаемый&nbsp;участник,<br>
  данное&nbsp;исследование доступно для прохождения только с&nbsp;ПК или&nbsp;ноутбука.
</div>
""",
    unsafe_allow_html=True,
)

@st.cache_resource(show_spinner="…")
def get_sheet() -> gspread.Worksheet:
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_dict = dict(st.secrets["gsp"])
    gc = gspread.authorize(
        ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)
    )
    return gc.open("human_study_results").sheet1

try:
    SHEET = get_sheet()
except Exception:
    SHEET = None

log_q: queue.Queue[List] = queue.Queue()

def _writer():
    while True:
        row = log_q.get()
        try:
            if SHEET:
                SHEET.append_row(row)
        except Exception as e:
            print("Sheets error:", e)
        log_q.task_done()

threading.Thread(target=_writer, daemon=True).start()

@st.cache_data(show_spinner=False, ttl=300)
def load_img(url: str) -> bytes:
    return requests.get(url, timeout=10).content

def create_timer_js(total_sec: int, key: str, prefix: str = ""):
    """Создает JavaScript для таймера с автопереходом"""
    return f"""
<div style="display:flex;gap:16px;height:70px;align-items:center;">
  <div style="position:relative;width:70px;height:70px;">
    <svg width="70" height="70">
      <circle cx="35" cy="35" r="26" stroke="#444" stroke-width="6" fill="none"/>
      <circle id="bar-{key}" cx="35" cy="35" r="26" stroke="#52b788" stroke-width="6" fill="none"
              stroke-dasharray="163.36" stroke-dashoffset="0" transform="rotate(-90 35 35)"/>
    </svg>
    <span id="lbl-{key}" style="position:absolute;top:50%;left:50%;
          transform:translate(-50%,-50%);font:700 1.2rem sans-serif;color:#52b788;">
      {total_sec}
    </span>
  </div>
  <div style="font:500 1rem sans-serif;color:#52b788;" id="txt-{key}">
    {prefix}{total_sec} с
  </div>
</div>
<script>
window.timer_{key} = (function() {{
  const dash = 163.36;
  const ttl = {total_sec};
  let left = ttl;
  let running = true;
  const bar = document.getElementById("bar-{key}");
  const lbl = document.getElementById("lbl-{key}");
  const txt = document.getElementById("txt-{key}");
  
  function update() {{
    if (!running || left < 0) return;
    
    lbl.textContent = left;
    bar.style.strokeDashoffset = dash * (1 - left / ttl);
    txt.textContent = "{prefix}" + left + " с";
    
    if (left === 0) {{
      running = false;
      // Запускаем автопереход через небольшую задержку
      setTimeout(function() {{
        window.parent.postMessage({{type: 'timer_finished', key: '{key}'}}, '*');
      }}, 100);
      return;
    }}
    
    left--;
    setTimeout(update, 1000);
  }}
  
  // Начинаем отсчет
  setTimeout(update, 1000);
  
  return {{
    stop: function() {{ running = false; }}
  }};
}})();
</script>
"""

BASE_URL = "https://storage.yandexcloud.net/test3123234442"
INTRO_TIME_FIRST = 8
INTRO_TIME_NEXT = 2
QUESTION_TIME = 15

GROUPS = [
    "img1_dif_corners",
    "img2_dif_corners", 
    "img3_same_corners_no_symb",
    "img4_same_corners",
    "img5_same_corners",
]
ALGS = [
    "pca_rgb_result",
    "socolov_lab_result",
    "socolov_rgb_result", 
    "umap_rgb_result",
]

CORNER_ANS = {
    "img1_dif_corners": "нет",
    "img2_dif_corners": "нет",
    "img3_same_corners_no_symb": "да",
    "img4_same_corners": "да", 
    "img5_same_corners": "да",
}
LETTER_ANS = {
    "img1_dif_corners": "ж",
    "img2_dif_corners": "фя",
    "img3_same_corners_no_symb": "Не вижу",
    "img4_same_corners": "аб",
    "img5_same_corners": "юэы",
}

def file_url(g: str, a: str) -> str:
    return f"{BASE_URL}/{g}_{a}.png"

def make_questions() -> List[Dict]:
    per_group: dict[str, list] = {g: [] for g in GROUPS}
    for g, a in itertools.product(GROUPS, ALGS):
        per_group[g].append(
            dict(
                group=g,
                alg=a,
                img=file_url(g, a),
                qtype="corners",
                prompt="Правый верхний и левый нижний угол — одного цвета?",
                correct=CORNER_ANS[g],
            )
        )
        per_group[g].append(
            dict(
                group=g,
                alg=a,
                img=file_url(g, a),
                qtype="letters",
                prompt="Если на изображении вы видите буквы, то укажите, какие именно.",
                correct=LETTER_ANS[g],
            )
        )
    for lst in per_group.values():
        random.shuffle(lst)
    ordered = []
    while any(per_group.values()):
        cycle = list(GROUPS)
        random.shuffle(cycle)
        for g in cycle:
            if per_group[g]:
                ordered.append(per_group[g].pop())
    for n, q in enumerate(ordered, 1):
        q["№"] = n
    return ordered

# Инициализация состояния
if "questions" not in st.session_state:
    st.session_state.update(
        questions=make_questions(),
        idx=0,
        name="",
        phase="intro",
        phase_start=None,
        transition_trigger=0,  # Счетчик для форсирования обновлений
    )

qs = st.session_state.questions
total_q = len(qs)

# Экран ввода имени
if not st.session_state.name:
    st.markdown(
        """
<div style="color:#111;">
  <h2>Уважаемый участник,<br>добро пожаловать в эксперимент по изучению восприятия изображений.</h2>
  <p><b>Как проходит эксперимент</b><br>
     В ходе эксперимента вам нужно будет отвечать на простые вопросы об изображениях, 
     которые вы увидите на экране. Всего вам предстоит ответить на <b>40</b> вопросов. 
     Прохождение теста займет около 10-15 минут.</p>
  <p><b>Что это за изображения?</b><br>
     Изображения — результат работы разных методов. 
     Ни одно из них не является «эталоном». 
     Цель эксперимента — понять, какие методы обработки лучше сохраняют информацию.</p>
  <p><b>Важно</b><br>
     Эксперимент полностью анонимен.  
     Проходить их следует <b>только на компьютере или ноутбуке</b>:  
     использование телефонов или планшетов запрещено.</p>
  <p>Для начала теста введите любой псевдоним и нажмите Enter  
     или нажмите «Сгенерировать псевдоним».</p>
</div>
""",
        unsafe_allow_html=True,
    )
    uname = st.text_input(
        "", placeholder="Фамилия / псевдоним", key="username", label_visibility="collapsed"
    )
    if st.button("🎲 Сгенерировать псевдоним"):
        st.session_state.name = f"Участник_{secrets.randbelow(900_000)+100_000}"
        st.rerun()
    if uname:
        st.session_state.name = uname.strip()
        st.rerun()
    st.stop()

def letters_set(s: str) -> set[str]:
    return set(re.sub(r"[ ,.;:-]+", "", s.lower()))

def save_answer_and_continue(ans: str):
    """Сохраняет ответ и переходит к следующему вопросу"""
    q = qs[st.session_state.idx]
    
    # Рассчитываем время ответа
    ms = 0
    if st.session_state.get('answer_start'):
        ms = int((time.time() - st.session_state.answer_start) * 1000)
    
    # Проверяем правильность ответа
    ok = (
        letters_set(ans) == letters_set(q["correct"])
        if q["qtype"] == "letters"
        else ans.lower() == q["correct"].lower()
    )
    
    # Сохраняем в Google Sheets
    if SHEET:
        log_q.put([
            datetime.datetime.utcnow().isoformat(),
            st.session_state.name,
            q["№"],
            q["group"],
            q["alg"],
            q["qtype"],
            q["prompt"],
            ans,
            q["correct"],
            ms,
            ok,
        ])
    
    # Переходим к следующему вопросу
    st.session_state.idx += 1
    st.session_state.phase = "intro"
    st.session_state.phase_start = None
    st.session_state.transition_trigger += 1
    if 'answer_start' in st.session_state:
        del st.session_state.answer_start
    
    st.rerun()

def force_transition_to_question():
    """Принудительный переход к фазе вопроса"""
    st.session_state.phase = "question"
    st.session_state.phase_start = time.time()
    st.session_state.transition_trigger += 1
    st.rerun()

def force_transition_to_answer():
    """Принудительный переход к фазе ответа"""
    st.session_state.phase = "answer"
    st.session_state.answer_start = time.time()
    st.session_state.transition_trigger += 1
    st.rerun()

# Основная логика приложения
i = st.session_state.idx

if i < total_q:
    q = qs[i]
    current_time = time.time()
    
    # === ФАЗА INTRO ===
    if st.session_state.phase == "intro":
        # Инициализируем время начала фазы
        if st.session_state.phase_start is None:
            st.session_state.phase_start = current_time
        
        elapsed = current_time - st.session_state.phase_start
        intro_limit = INTRO_TIME_FIRST if i < 5 else INTRO_TIME_NEXT
        remaining = max(intro_limit - elapsed, 0)
        
        # Проверяем, нужно ли перейти к следующей фазе
        if remaining <= 0:
            force_transition_to_question()
            st.stop()
        
        # Показываем таймер
        components.html(
            create_timer_js(int(remaining), f"intro_{i}_{st.session_state.transition_trigger}", "Начало показа через "),
            height=80
        )
        
        # Показываем инструкции
        if q["qtype"] == "corners":
            st.markdown("""
<div style="font-size:1.1rem;color:#111;margin-top:20px;">
Сейчас вы увидите изображение. Цель данного вопроса — посмотреть на
диаметрально противоположные углы, <b>правый верхний и левый нижний</b>,
и определить, окрашены ли они в один цвет.<br><br>
Картинка будет доступна в течение <b>15&nbsp;секунд</b>. Время на ответ не ограничено.
</div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
<div style="font-size:1.1rem;color:#111;margin-top:20px;">
Сейчас вы увидите изображение. Цель данного вопроса — определить, есть ли на
представленной картинке <b>буквы русского алфавита</b>.
Найденные буквы необходимо ввести в текстовое поле: допускается разделение
пробелами, запятыми и т.&nbsp;д., а также слитное написание.<br><br>
На некоторых картинках букв нет — тогда нажмите кнопку <b>«Не&nbsp;вижу&nbsp;букв»</b>.
</div>""", unsafe_allow_html=True)
        
        # Кнопка принудительного перехода (для отладки)
        if st.button("Перейти к вопросу", key=f"debug_intro_{i}"):
            force_transition_to_question()
        
        # Авто-обновление каждые 0.5 сек
        st_autorefresh(interval=500, key=f"intro_auto_{i}_{st.session_state.transition_trigger}")
    
    # === ФАЗА QUESTION ===
    elif st.session_state.phase == "question":
        # Инициализируем время начала фазы
        if st.session_state.phase_start is None:
            st.session_state.phase_start = current_time
        
        elapsed = current_time - st.session_state.phase_start
        remaining = max(QUESTION_TIME - elapsed, 0)
        
        st.markdown(f"### Вопрос №{q['№']} из {total_q}")
        
        # Проверяем, нужно ли перейти к следующей фазе
        if remaining <= 0:
            force_transition_to_answer()
            st.stop()
        
        # Показываем таймер
        components.html(
            create_timer_js(int(remaining), f"question_{i}_{st.session_state.transition_trigger}"),
            height=80
        )
        
        # Показываем изображение
        try:
            st.image(load_img(q["img"]), width=290, clamp=True)
        except Exception as e:
            st.error(f"Ошибка загрузки изображения: {e}")
        
        # Кнопка принудительного перехода (для отладки)
        if st.button("Перейти к ответу", key=f"debug_question_{i}"):
            force_transition_to_answer()
        
        # Авто-обновление каждые 0.5 сек
        st_autorefresh(interval=500, key=f"question_auto_{i}_{st.session_state.transition_trigger}")
    
    # === ФАЗА ANSWER ===
    elif st.session_state.phase == "answer":
        if 'answer_start' not in st.session_state:
            st.session_state.answer_start = current_time
        
        st.markdown(f"### Вопрос №{q['№']} из {total_q}")
        st.markdown("<i>Время показа изображения истекло.</i>", unsafe_allow_html=True)
        
        if q["qtype"] == "corners":
            sel = st.radio(
                q["prompt"],
                [
                    "Да, углы одного цвета.",
                    "Нет, углы окрашены в разные цвета.", 
                    "Затрудняюсь ответить.",
                ],
                index=None,
                key=f"radio_{i}_{st.session_state.transition_trigger}",
            )
            if sel:
                if sel.startswith("Да"):
                    save_answer_and_continue("да")
                elif sel.startswith("Нет"):
                    save_answer_and_continue("нет")
                else:
                    save_answer_and_continue("затрудняюсь")
        else:
            txt = st.text_input(
                q["prompt"], 
                key=f"input_{i}_{st.session_state.transition_trigger}", 
                placeholder="Введите русские буквы"
            )
            
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("Не вижу букв", key=f"no_letters_{i}_{st.session_state.transition_trigger}"):
                    save_answer_and_continue("Не вижу")
            
            if txt:
                if not re.fullmatch(r"[А-Яа-яЁё ,.;:-]+", txt):
                    st.error("Допустимы только русские буквы и знаки пунктуации.")
                else:
                    with col2:
                        if st.button("Отправить ответ", key=f"submit_{i}_{st.session_state.transition_trigger}"):
                            save_answer_and_continue(txt.strip())

else:
    # === ЗАВЕРШЕНИЕ ===
    st.markdown("""
    <div style="margin-top:30px;padding:30px;text-align:center;font-size:2rem;
                 color:#fff;background:#262626;border-radius:12px;">
        Вы завершили прохождение.<br><b>Спасибо за участие!</b>
    </div>
    """, unsafe_allow_html=True)
    st.balloons()





