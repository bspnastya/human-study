from __future__ import annotations
from streamlit_autorefresh import st_autorefresh
import random, time, datetime, secrets, threading, queue, re, itertools, requests
from typing import List, Dict
import streamlit as st, streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Визуализация многоканальных изображений", page_icon="🎯", layout="centered", initial_sidebar_state="collapsed")
st.markdown("""
<style>
html,body,.stApp,[data-testid="stAppViewContainer"],.main,.block-container{background:#808080!important;color:#111!important;}
h1,h2,h3,h4,h5,h6{color:#111!important;}
.question-card,* .question-card{color:#fff!important;}
.stButton>button{color:#fff!important;}
header[data-testid="stHeader"],div[data-testid="stHeader"]{display:none;}
.question-card{background:transparent!important;border:none!important;}
input[data-testid="stTextInput"]{height:52px!important;padding:0 16px!important;font-size:1.05rem;}
.stButton>button{min-height:52px!important;padding:0 20px!important;border:1px solid #555!important;background:#222!important;color:#ddd!important;border-radius:8px;}
#mobile-overlay{position:fixed;inset:0;z-index:9999;background:#808080;display:none;align-items:center;justify-content:center;color:#fff;font:500 1.2rem/1.5 sans-serif;text-align:center;padding:0 20px;}
@media (max-width:1023px){#mobile-overlay{display:flex;}}
</style>
<div id="mobile-overlay">Уважаемый&nbsp;участник,<br>данное&nbsp;исследование доступно для прохождения только с&nbsp;ПК или&nbsp;ноутбука.</div>
""", unsafe_allow_html=True)

@st.cache_resource(show_spinner="…")
def get_sheet() -> gspread.Worksheet:
    try:
        scopes = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
        gc = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gsp"]), scopes))
        return gc.open("human_study_results").sheet1
    except Exception:
        return None

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
        except Exception:
            pass
        log_q.task_done()

threading.Thread(target=_writer, daemon=True).start()

def letters_set(s: str) -> set[str]:
    s = re.sub(r"[ ,.;:-]+", "", s.lower())
    return set(s)

def ring_html(left: int, total: int, label: str = ""):
    off = 163.36 * left / total
    return f"""
<div style='display:flex;gap:16px;align-items:center;height:70px'>
  <div style='position:relative;width:70px;height:70px'>
    <svg width='70' height='70'><circle cx='35' cy='35' r='26' stroke='#444' stroke-width='6' fill='none'/><circle cx='35' cy='35' r='26' stroke='#52b788' stroke-width='6' fill='none' stroke-dasharray='163.36' stroke-dashoffset='{off}' transform='rotate(-90 35 35)'/></svg>
    <span style='position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font:700 1.2rem sans-serif;color:#52b788'>{left}</span>
  </div>
  {f"<div style='font:500 1rem sans-serif;color:#52b788;'>{label}{left}&nbsp;с</div>" if label else ""}
</div>"""

BASE_URL = "https://storage.yandexcloud.net/test3123234442"
TIME_LIMIT = 15
GROUPS = ["img1_dif_corners","img2_dif_corners","img3_same_corners_no_symb","img4_same_corners","img5_same_corners"]
ALGS = ["pca_rgb_result","socolov_lab_result","socolov_rgb_result","umap_rgb_result"]
CORNER_ANS = {"img1_dif_corners":"нет","img2_dif_corners":"нет","img3_same_corners_no_symb":"да","img4_same_corners":"да","img5_same_corners":"да"}
LETTER_ANS = {"img1_dif_corners":"ж","img2_dif_corners":"фя","img3_same_corners_no_symb":"Не вижу","img4_same_corners":"аб","img5_same_corners":"юэы"}

def file_url(g: str, a: str) -> str:
    return f"{BASE_URL}/{g}_{a}.png"

def make_questions() -> List[Dict]:
    per = {g: [] for g in GROUPS}
    for g, a in itertools.product(GROUPS, ALGS):
        per[g].append(dict(group=g, alg=a, img=file_url(g, a), qtype="corners", prompt="Правый верхний и левый нижний угол — одного цвета?", correct=CORNER_ANS[g]))
        per[g].append(dict(group=g, alg=a, img=file_url(g, a), qtype="letters", prompt="Если на изображении вы видите буквы, то укажите, какие именно.", correct=LETTER_ANS[g]))
    
    for v in per.values(): 
        random.shuffle(v)
    
    seq = []
    prev = None
    while any(per.values()):
        pick = [g for g in GROUPS if per[g] and g != prev] or [g for g in GROUPS if per[g]]
        g = random.choice(pick)
        seq.append(per[g].pop())
        prev = g
    
    for n, q in enumerate(seq, 1): 
        q["№"] = n
    return seq


if "questions" not in st.session_state:
    st.session_state.update(
        questions=make_questions(),
        idx=0,
        name="",
        phase="intro",
        intro_start=None,
        q_start=None
    )


if st.session_state.get("blank_until", 0) > time.time():
    st_autorefresh(interval=250, key="blank")
    st.stop()
elif "blank_until" in st.session_state:
    del st.session_state["blank_until"]

qs, total_q = st.session_state.questions, len(st.session_state.questions)

if not st.session_state.name:
    st.markdown("""
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
""", unsafe_allow_html=True)
    nm = st.text_input("", placeholder="Фамилия / псевдоним", key="username", label_visibility="collapsed")
    if st.button("🎲 Сгенерировать псевдоним"): 
        st.session_state.name = f"Участник_{secrets.randbelow(900000)+100000}"
        st.rerun()
    if nm: 
        st.session_state.name = nm.strip()
        st.rerun()
    st.stop()

def finish(ans: str):
    q = qs[st.session_state.idx]
    ms = int((time.time() - st.session_state.q_start) * 1000) if st.session_state.q_start else 0
    ok = letters_set(ans) == letters_set(q["correct"]) if q["qtype"] == "letters" else ans.lower() == q["correct"].lower()
    
    if SHEET: 
        log_q.put([datetime.datetime.utcnow().isoformat(), st.session_state.name, q["№"], q["group"], q["alg"], q["qtype"], q["prompt"], ans, q["correct"], ms, ok])
    
    q.update({"ответ": ans or "—", "время, мс": f"{ms:,}", "✓": "✅" if ok else "❌"})
    st.session_state.idx += 1
    st.session_state.phase = "intro"
    st.session_state.intro_start = None
    st.session_state.q_start = None
    st.session_state.blank_until = time.time() + 0.5  
    st.rerun()

i = st.session_state.idx
if i < total_q:
    q = qs[i]

    intro_limit = 8 if i < 5 else 2
    if st.session_state.phase == "intro":
        if st.session_state.intro_start is None: 
            st.session_state.intro_start = time.time()
        elapsed = time.time() - st.session_state.intro_start
        remain = max(intro_limit - int(elapsed), 0)
        
        components.html(ring_html(remain, intro_limit, "Начало показа через "), height=80)
        st_autorefresh(interval=500, key=f"intro{i}")
        
        if remain == 0: 
            st.session_state.phase = "question"
            st.session_state.q_start = None
            st.rerun()
        
        if q["qtype"] == "corners":
            st.markdown("""
<div style="font-size:1.1rem;">
Сейчас вы увидите изображение. Цель данного вопроса — посмотреть на
диаметрально противоположные углы, <b>правый верхний и левый нижний</b>,
и определить, окрашены ли они в один цвет.<br><br>
Картинка будет доступна в течение <b>15&nbsp;секунд</b>. Время на ответ не ограничено.
</div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
<div style="font-size:1.1rem;">
Сейчас вы увидите изображение. Цель данного вопроса — определить, есть ли на
представленной картинке <b>буквы русского алфавита</b>.
Найденные буквы необходимо ввести в текстовое поле: допускается разделение
пробелами, запятыми и т.&nbsp;д., а также слитное написание.<br><br>
На некоторых картинках букв нет — тогда нажмите кнопку <b>«Не вижу букв»</b>.
</div>""", unsafe_allow_html=True)
        st.stop()

    if st.session_state.q_start is None: 
        st.session_state.q_start = time.time()
    
    left = max(TIME_LIMIT - int(time.time() - st.session_state.q_start), 0)
    components.html(ring_html(left, TIME_LIMIT), height=80)
    st_autorefresh(interval=500, key=f"q{i}")
    
    st.markdown(f"### Вопрос №{q['№']} из {total_q}")
    
    if left > 0: 
        st.image(q["img"], width=290, clamp=True)
    else: 
        st.markdown("<i>Время показа изображения истекло.</i>", unsafe_allow_html=True)
    
    if q["qtype"] == "corners":
        sel = st.radio(q["prompt"], ("Да, углы одного цвета.", "Нет, углы окрашены в разные цвета.", "Затрудняюсь ответить."), index=None, key=f"radio{i}")
        if sel: 
            finish("да" if sel.startswith("Да") else "нет" if sel.startswith("Нет") else "затрудняюсь")
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
<div style="margin-top:30px;padding:30px;text-align:center;font-size:2rem;color:#fff;background:#262626;border-radius:12px;">
    Вы завершили прохождение.<br><b>Спасибо за участие!</b>
</div>""", unsafe_allow_html=True)
    st.balloons()




