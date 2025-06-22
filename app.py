from __future__ import annotations
import streamlit as st, streamlit.components.v1 as components
import random, time, datetime, secrets, re, itertools, math, threading, queue, requests, io, atexit, uuid, html, gspread
from typing import List, Dict
from oauth2client.service_account import ServiceAccountCredentials
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://storage.yandexcloud.net/test3123234442"
TIME_IMG_VISIBLE = 15
INTRO_FIRST = 5
INTRO_REST_SEC = 3
PAUSE_SEC = .5
MOBILE_QS_FLAG = "mobile"
BATCH_LIMIT_CELLS = 450
LOG_Q_MAXSIZE = 1000

GROUPS = ["img1_dif_corners", "img2_dif_corners", "img3_same_corners_no_symb", "img4_same_corners", "img5_same_corners"]
ALGS = ["pca_rgb_result", "socolov_lab_result", "socolov_rgb_result", "umap_rgb_result"]
CORNER = {"img1_dif_corners": "нет", "img2_dif_corners": "нет", "img3_same_corners_no_symb": "да", "img4_same_corners": "да", "img5_same_corners": "да"}
LETTER = {"img1_dif_corners": "ж", "img2_dif_corners": "фя", "img3_same_corners_no_symb": "Не вижу", "img4_same_corners": "аб", "img5_same_corners": "юэы"}

WELCOME_HTML = """
<div style="color:#111;">
  <h2>Уважаемый участник,<br>добро пожаловать в эксперимент по изучению восприятия изображений.</h2>
  <p><b>Как проходит эксперимент</b><br>
  В ходе эксперимента вам нужно будет отвечать на простые вопросы об изображениях,
  которые вы увидите на экране. Всего вам предстоит ответить на <b>40</b> вопросов.
  Прохождение теста займет около 10-15 минут.</p>
  <p><b>Пожалуйста, проходите тест спокойно: исследование не направлено на оценку испытуемых.
  Оценивается работа алгоритмов, которые выдают картинки разного качества.</b></p>
  <p><b>Что это за изображения?</b><br>
  Изображения — результат работы разных методов. Ни одно из них не является «эталоном».
  Цель эксперимента — понять, какие методы обработки лучше сохраняют информацию.</p>
  <p><b>Важно</b><br>
  Эксперимент полностью анонимен. Проходить его следует <b>только на компьютере или ноутбуке</b>.</p>
  <p>Для начала теста введите любой псевдоним и нажмите Enter или нажмите «Сгенерировать псевдоним».</p>
</div>
"""

INTRO_CORNERS_TEXT = """
Сейчас вы увидите изображение. Цель данного вопроса — посмотреть на
диаметрально противоположные углы, <b>правый верхний и левый нижний</b>,
и определить, окрашены ли они в один цвет.<br><br>
Картинка будет доступна в течение <b>15&nbsp;секунд</b>. Время на ответ не ограничено.
"""

INTRO_LETTERS_TEXT = """
Сейчас вы увидите изображение. Цель данного вопроса — определить, есть ли на
представленной картинке <b>буквы русского алфавита</b>.<br><br>
Найденные буквы необходимо ввести в текстовое поле: допускается разделение
пробелами, запятыми и т.&nbsp;д., а также слитное написание.<br><br>
На некоторых картинках букв нет — тогда нажмите кнопку <b>«Не вижу букв»</b>.
"""

INTRO_CORNERS_TIMED = f"<b>Начало показа — через указанное время</b><br><br>{INTRO_CORNERS_TEXT}"
INTRO_LETTERS_TIMED = f"<b>Начало показа — через указанное время</b><br><br>{INTRO_LETTERS_TEXT}"

st.set_page_config("Визуализация многоканальных изображений", "🎯", layout="centered", initial_sidebar_state="collapsed")

components.html(f"<script>(()=>{{const f='{MOBILE_QS_FLAG}',m=innerWidth<1024,q=new URLSearchParams(location.search);if(m&&!q.has(f)){{q.set(f,'1');location.search=q.toString();}}}})();</script>", height=0)
if st.query_params.get(MOBILE_QS_FLAG) == ["1"]:
    st.markdown("<style>body{background:#808080;color:#fff;text-align:center;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}h2{font-size:1.3rem;font-weight:500;line-height:1.4}</style><h2>Уважаемый участник<br>Данное исследование доступно только с <strong>ПК или ноутбука</strong>.</h2>", unsafe_allow_html=True)
    st.stop()

st.markdown("<style>html,body,.stApp,[data-testid=\"stAppViewContainer\"],.main,.block-container{background:#808080;color:#111;}header[data-testid=\"stHeader\"]{display:none;}h1,h2,h3,h4,h5,h6{color:#111!important;}.stButton>button{min-height:52px;padding:0 20px;border:1px solid #555;background:#222;color:#ddd;border-radius:8px;}input[data-testid=\"stTextInput\"]{height:52px;padding:0 16px;font-size:1.05rem;}body,html{scrollbar-gutter:stable;}</style>", unsafe_allow_html=True)

components.html("<script>window.startTimer=(id,sec)=>{clearInterval(window['i_'+id]);let t=sec,s=document.getElementById(id);window['i_'+id]=setInterval(()=>{if(s)s.textContent=Math.max(0,--t);if(t<=0)clearInterval(window['i_'+id]);},1000);}</script>", height=0)
def render_timer(key: str, sec: int):
    components.html(f"<div style='font-size:1.2rem;font-weight:bold;margin-bottom:10px;'>Осталось&nbsp;времени: <span id=\"{key}\">{sec}</span>&nbsp;сек</div><script>startTimer('{key}',{sec})</script>", height=0)

@st.cache_resource
def sheet():
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    gc = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gsp"]), scopes))
    return gc.open("human_study_results").sheet1
SHEET = sheet()

log_q = queue.Queue(maxsize=LOG_Q_MAXSIZE)
def writer():
    batch, cells = [], 0
    while True:
        row = log_q.get()
        if row != "__FLUSH__":
            batch.append(row); cells += len(row)
        if row == "__FLUSH__" or cells >= BATCH_LIMIT_CELLS:
            if batch:
                try: SHEET.append_rows(batch, value_input_option="RAW")
                except: pass
                batch.clear(); cells = 0
        log_q.task_done()
threading.Thread(target=writer, daemon=True).start()
atexit.register(lambda: log_q.put("__FLUSH__"))

session = requests.Session()
session.headers["User-Agent"] = "HumanStudyClient/1.0"
session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=.5, status_forcelist=[500, 502, 503, 504])))
@st.cache_data(show_spinner=False)
def fetch_png(url: str) -> bytes:
    return session.get(url, timeout=5).content

def build_questions() -> List[Dict]:
    per = {g: [] for g in GROUPS}
    for g, a in itertools.product(GROUPS, ALGS):
        per[g] += [
            {"group": g, "alg": a, "img": f"{BASE_URL}/{g}_{a}.png", "qtype": "corners", "prompt": "Правый верхний и левый нижний угол — одного цвета?", "correct": CORNER[g]},
            {"group": g, "alg": a, "img": f"{BASE_URL}/{g}_{a}.png", "qtype": "letters", "prompt": "Если на изображении вы видите буквы, то укажите, какие именно.", "correct": LETTER[g]}
        ]
    for v in per.values():
        random.shuffle(v)
    seq, prev = [], None
    while any(per.values()):
        choices = [g for g in GROUPS if per[g] and g != prev] or [g for g in GROUPS if per[g]]
        prev = random.choice(choices)
        seq.append(per[prev].pop())
    for i, q in enumerate(seq, 1):
        q["№"] = i
    return seq

def letters_set(s: str) -> set[str]:
    return set(re.sub(r"[ ,.;:-]+", "", s.lower()))

def esc(s: str) -> str:
    return html.escape(s, quote=True)

ss = st.session_state
if "seq" not in ss:
    ss.seq = build_questions(); ss.idx = 0; ss.phase = "intro"; ss.name = ""; ss.sid = str(uuid.uuid4())

if not ss.name:
    st.markdown(WELCOME_HTML, unsafe_allow_html=True)
    nick = st.text_input("", placeholder="Ваш псевдоним", label_visibility="collapsed")
    if st.button("🎲 Сгенерировать псевдоним"):
        ss.name = f"Участник_{secrets.randbelow(900000)+100000}"; st.rerun()
    if nick:
        ss.name = esc(nick.strip()); st.rerun()
    st.stop()

if ss.idx >= len(ss.seq):
    log_q.put("__FLUSH__")
    st.markdown("<div style='margin-top:40px;padding:40px;text-align:center;font-size:2rem;background:#262626;color:#fff;border-radius:12px;'>Вы завершили прохождение.<br><b>Спасибо за участие!</b></div>", unsafe_allow_html=True)
    st.balloons(); st.stop()

q = ss.seq[ss.idx]
def save(ans: str):
    t_ms = int((time.time() - ss.t0) * 1000)
    ok = letters_set(ans) == letters_set(q["correct"]) if q["qtype"] == "letters" else ans.lower() == q["correct"].lower()
    log_q.put_nowait([datetime.datetime.utcnow().isoformat(), ss.sid, ss.name, q["№"], q["group"], q["alg"], q["qtype"], esc(q["prompt"]), esc(ans), esc(q["correct"]), t_ms, ok])
    ss.idx += 1; ss.phase = "intro"; time.sleep(PAUSE_SEC); st.experimental_rerun()

if ss.phase == "intro":
    if ss.idx < INTRO_FIRST:
        st.markdown(INTRO_CORNERS_TEXT if q["qtype"] == "corners" else INTRO_LETTERS_TEXT, unsafe_allow_html=True)
        fetch_png(q["img"])
        if st.button("Перейти к вопросу"):
            ss.phase = "question"; ss.t0 = time.time(); st.experimental_rerun()
        st.stop()
    if "intro_t0" not in ss: ss.intro_t0 = time.time()
    rem = INTRO_REST_SEC - (time.time() - ss.intro_t0)
    if rem <= 0:
        ss.pop("intro_t0"); ss.phase = "question"; ss.t0 = time.time(); st.experimental_rerun()
    render_timer(f"intro_{q['№']}", math.ceil(rem))
    st.markdown(INTRO_CORNERS_TIMED if q["qtype"] == "corners" else INTRO_LETTERS_TIMED, unsafe_allow_html=True)
    fetch_png(q["img"]); st.stop()

if "t0" not in ss: ss.t0 = time.time()
rem = max(0, TIME_IMG_VISIBLE - (time.time() - ss.t0))
st.markdown(f"### Вопрос №{q['№']} из {len(ss.seq)}")
render_timer(f"q_{q['№']}", math.ceil(rem))

if rem > 0:
    st.image(io.BytesIO(fetch_png(q["img"])), width=300)
else:
    st.markdown("*Время показа изображения истекло.*")

st.markdown("---")

if q["qtype"] == "corners":
    opt = st.radio(q["prompt"], ["Да, углы одного цвета.", "Нет, углы окрашены в разные цвета.", "Затрудняюсь ответить."], index=None)
    if opt: save("да" if opt.startswith("Да") else "нет" if opt.startswith("Нет") else "затрудняюсь")
else:
    txt = st.text_input(q["prompt"])
    if st.button("Не вижу букв"): save("Не вижу")
    if txt:
        if re.fullmatch(r"[А-Яа-яЁё ,.;:-]+", txt): save(txt.strip())
        else: st.error("Допустимы только русские буквы и знаки пунктуации.")






