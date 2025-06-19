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

@st.cache_data(show_spinner=False)
def load_img(url: str) -> bytes:
    return requests.get(url, timeout=6).content

def html_timer(total_sec: int, key: str = "", prefix: str = ""):
    components.html(
        f"""
<div style="display:flex;gap:16px;height:70px">
  <div style="position:relative;width:70px;height:70px">
    <svg width="70" height="70">
      <circle cx="35" cy="35" r="26" stroke="#444" stroke-width="6" fill="none"/>
      <circle id="bar-{key}" cx="35" cy="35" r="26" stroke="#52b788" stroke-width="6" fill="none"
              stroke-dasharray="163.36" stroke-dashoffset="0" transform="rotate(-90 35 35)"/>
    </svg>
    <span id="lbl-{key}" style="position:absolute;top:50%;left:50%;
          transform:translate(-50%,-50%);font:700 1.2rem sans-serif;color:#52b788">
      {total_sec}
    </span>
  </div>
  {"<div style='font:500 1rem sans-serif;color:#52b788;align-self:center;' id='txt-"+key+"'>"+prefix+str(total_sec)+" с</div>" if prefix else ""}
</div>
<script>
(function () {{
  const dash = 163.36;
  const ttl  = {total_sec};
  let left = ttl;
  const bar = document.getElementById("bar-{key}");
  const lbl = document.getElementById("lbl-{key}");
  const txt = document.getElementById("txt-{key}");
  function tick() {{
    left -= 1;
    if (left < 0) return;
    lbl.textContent = left;
    bar.style.strokeDashoffset = dash * (1 - left/ttl);
    if (txt) txt.textContent = "{prefix}" + left + " с";
    setTimeout(tick, 1000);
  }}
  setTimeout(tick, 1000);
}})();
</script>
""",
        height=80,
    )

BASE_URL = "https://storage.yandexcloud.net/test3123234442"
TIME_LIMIT = 15
INTRO_TIME = 8

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

if "questions" not in st.session_state:
    st.session_state.update(
        questions=make_questions(),
        idx=0,
        name="",
        q_start=None,
        phase="intro",
        intro_start=None,
    )

qs = st.session_state.questions
total_q = len(qs)

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
     Проходить его следует <b>только на компьютере или ноутбуке</b>:  
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
        st.experimental_rerun()
    if uname:
        st.session_state.name = uname.strip()
        st.experimental_rerun()
    st.stop()

def letters_set(s: str) -> set[str]:
    return set(re.sub(r"[ ,.;:-]+", "", s.lower()))

def finish(ans: str):
    q = qs[st.session_state.idx]
    ms = int((time.time() - st.session_state.q_start) * 1000) if st.session_state.q_start else 0
    ok = (
        letters_set(ans) == letters_set(q["correct"])
        if q["qtype"] == "letters"
        else ans.lower() == q["correct"].lower()
    )
    if SHEET:
        log_q.put(
            [
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
            ]
        )
    q.update(
        {
            "ответ": ans or "—",
            "время, мс": f"{ms:,}",
            "✓": "✅" if ok else "❌",
        }
    )
    st.session_state.idx += 1
    st.session_state.phase = "intro"
    st.session_state.intro_start = None
    st.session_state.q_start = None
    st.experimental_rerun()

i = st.session_state.idx
if i < total_q:
    q = qs[i]
    intro_limit = 8 if i < 5 else 2
    if st.session_state.phase == "intro":
        if st.session_state.intro_start is None:
            st.session_state.intro_start = time.time()
        elapsed_intro = time.time() - st.session_state.intro_start
        remain_intro = max(intro_limit - int(elapsed_intro), 0)
        html_timer(remain_intro if remain_intro > 0 else 0, key=f"intro{i}", prefix="Начало показа через ")
        
        if elapsed_intro >= intro_limit:
            st.session_state.phase = "question"
            st.session_state.q_start = None
            st.session_state.intro_start = None
            st.experimental_rerun()
        else:
            st_autorefresh(interval=1000, key=f"intro-refresh-{i}")
        
        if q["qtype"] == "corners":
            st.markdown(
                """
<div style="font-size:1.1rem;">
Сейчас вы увидите изображение. Цель данного вопроса — посмотреть на
диаметрально противоположные углы, <b>правый верхний и левый нижний</b>,
и определить, окрашены ли они в один цвет.<br><br>
Картинка будет доступна в течение <b>15&nbsp;секунд</b>. Время на ответ не ограничено.
</div>""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
<div style="font-size:1.1rem;">
Сейчас вы увидите изображение. Цель данного вопроса — определить, есть ли на
представленной картинке <b>буквы русского алфавита</b>.
Найденные буквы необходимо ввести в текстовое поле: допускается разделение
пробелами, запятыми и т.&nbsp;д., а также слитное написание.<br><br>
На некоторых картинках букв нет — тогда нажмите кнопку <b>«Не&nbsp;вижу&nbsp;букв»</b>.
</div>""",
                unsafe_allow_html=True,
            )
        st.stop()
    
    if st.session_state.phase == "question":
        if st.session_state.q_start is None:
            st.session_state.q_start = time.time()
        
        elapsed_q = time.time() - st.session_state.q_start
        left = max(TIME_LIMIT - int(elapsed_q), 0)
        
        html_timer(left if left > 0 else 0, key=f"q{i}")
        st_autorefresh(interval=1000, key=f"q-refresh-{i}")
        
        st.markdown(f"### Вопрос №{q['№']} из {total_q}")
        if left > 0:
            st.image(load_img(q["img"]), width=290, clamp=True)
        else:
            st.markdown("<i>Время показа изображения истекло.</i>", unsafe_allow_html=True)
        
        if q["qtype"] == "corners":
            sel = st.radio(
                q["prompt"],
                (
                    "Да, углы одного цвета.",
                    "Нет, углы окрашены в разные цвета.",
                    "Затрудняюсь ответить.",
                ),
                index=None,
                key=f"radio{i}",
            )
            if sel:
                if sel.startswith("Да"):
                    finish("да")
                elif sel.startswith("Нет"):
                    finish("нет")
                else:
                    finish("затрудняюсь")
        else:
            txt = st.text_input(q["prompt"], key=f"in{i}", placeholder="Введите русские буквы")
            if txt and not re.fullmatch(r"[А-Яа-яЁё ,.;:-]+", txt):
                st.error("Допустимы только русские буквы и знаки пунктуации.")
            if st.button("Не вижу букв", key=f"skip{i}"):
                finish("Не вижу")
            if txt and re.fullmatch(r"[А-Яа-яЁё ,.;:-]+", txt):
                finish(txt.strip())

else:
    st.markdown("""
    <div style="margin-top:30px;padding:30px;text-align:center;font-size:2rem;
                 color:#fff;background:#262626;border-radius:12px;">
        Вы завершили прохождение.<br><b>Спасибо за участие!</b>
    </div>
    """, unsafe_allow_html=True)
    st.balloons()




