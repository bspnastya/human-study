from __future__ import annotations
import random, time, datetime, secrets, threading, queue, re, itertools, math
from typing import List, Dict

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials


MOBILE_QS_FLAG = "mobile"
st.set_page_config(
    page_title="Визуализация многоканальных изображений",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed",
)

components.html(
    """
<script>
(function() {{
  const flag='{flag}', isMobile = window.innerWidth < 1024;
  if (isMobile) document.documentElement.classList.add('mobile-client');
  const qs = new URLSearchParams(window.location.search);
  if (isMobile && !qs.has(flag)) {{ qs.set(flag,'1'); window.location.search = qs.toString(); }}
}})();
</script>""".format(flag=MOBILE_QS_FLAG),
    height=0,
)

q = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
if q.get(MOBILE_QS_FLAG) == ["1"]:
    st.markdown(
        '''
<style>
body{background:#808080;color:#fff;text-align:center;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
h2{margin:0 auto;line-height:1.4;font-size:1.3rem;font-weight:500;}
</style>
<h2>Уважаемый участник<br>Данное исследование доступно только с <strong>ПК или ноутбука</strong>.</h2>
''',
        unsafe_allow_html=True,
    )
    st.stop()


BASE_URL = "https://storage.yandexcloud.net/test3123234442"
TIME_LIMIT = 15
INTRO_TIME_BTN = 0
INTRO_TIME_AUTO = 3

@st.cache_resource(show_spinner="Подключение…")
def get_sheet():
    try:
        scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        gc = gspread.authorize(
            ServiceAccountCredentials.from_json_keyfile_dict(
                dict(st.secrets["gsp"]), scopes
            )
        )
        return gc.open("human_study_results").sheet1
    except:
        return None

SHEET = get_sheet()

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
CORNER = {
    "img1_dif_corners": "нет",
    "img2_dif_corners": "нет",
    "img3_same_corners_no_symb": "да",
    "img4_same_corners": "да",
    "img5_same_corners": "да",
}
LETTER = {
    "img1_dif_corners": "ж",
    "img2_dif_corners": "фя",
    "img3_same_corners_no_symb": "Не вижу",
    "img4_same_corners": "аб",
    "img5_same_corners": "юэы",
}

def url(g: str, a: str) -> str:
    return f"{BASE_URL}/{g}_{a}.png"

def clean(s: str) -> set[str]:
    return set(re.sub(r"[ ,.;:-]+", "", s.lower()))

def make_qs() -> List[Dict]:
    pg = {g: [] for g in GROUPS}
    for g, a in itertools.product(GROUPS, ALGS):
        pg[g] += [
            {
                "group": g,
                "alg": a,
                "img": url(g, a),
                "qtype": "corners",
                "prompt": "Правый верхний и левый нижний угол — одного цвета?",
                "correct": CORNER[g],
            },
            {
                "group": g,
                "alg": a,
                "img": url(g, a),
                "qtype": "letters",
                "prompt": "Если на изображении вы видите буквы, то укажите, какие именно.",
                "correct": LETTER[g],
            },
        ]
    for v in pg.values():
        random.shuffle(v)
    seq, prev = [], None
    while any(pg.values()):
        choices = [g for g in GROUPS if pg[g] and g != prev] or [
            g for g in GROUPS if pg[g]
        ]
        prev = random.choice(choices)
        seq.append(pg[prev].pop())
    for n, q in enumerate(seq, 1):
        q["№"] = n
    return seq


def init_state():
    st.session_state.questions = make_qs()
    st.session_state.idx = 0
    st.session_state.name = ""
    st.session_state.phase = "intro"
    st.session_state.phase_start = None
    st.session_state.pause_until = 0
    st.session_state.initialized = True

if "initialized" not in st.session_state:
    init_state()

log_q = queue.Queue()

def writer():
    batch = []
    while True:
        row = log_q.get()
        batch.append(row)
        log_q.task_done()
        if len(batch) >= 5:
            if SHEET:
                try:
                    SHEET.append_rows(batch, value_input_option="RAW")
                except:
                    pass
            batch.clear()

threading.Thread(target=writer, daemon=True).start()

def render_timer(sec: int, key: str):
    st.markdown(
        f'<div style="font-size:1.2rem;font-weight:bold;color:#111;margin-bottom:10px;">Осталось&nbsp;времени: {sec}&nbsp;сек</div>',
        unsafe_allow_html=True,
        key=key,
    )

def finish(answer: str):
    q = st.session_state.questions[st.session_state.idx]
    t_ms = (
        int((time.time() - st.session_state.phase_start) * 1000)
        if st.session_state.phase_start
        else 0
    )
    ok = (
        clean(answer) == clean(q["correct"])
        if q["qtype"] == "letters"
        else answer.lower() == q["correct"].lower()
    )
    log_q.put(
        [
            datetime.datetime.utcnow().isoformat(),
            st.session_state.name,
            q["№"],
            q["group"],
            q["alg"],
            q["qtype"],
            q["prompt"],
            answer,
            q["correct"],
            t_ms,
            ok,
        ]
    )
    st.session_state.idx += 1
    st.session_state.phase = "intro"
    st.session_state.phase_start = None
    st.session_state.pause_until = time.time() + 0.5
    st.experimental_rerun()

if st.session_state.pause_until > time.time() and st.session_state.idx < len(
    st.session_state.questions
):
    st.markdown(
        "<div style='text-align:center;font-size:1.5rem;color:#fff;background:#262626;padding:20px;border-radius:12px;margin-top:50px;'>Переходим к следующему вопросу...</div>",
        unsafe_allow_html=True,
    )
    st_autorefresh(interval=500, key=f"pause_{int(st.session_state.pause_until)}")
    st.stop()

if not st.session_state.name:
    st.markdown(
        '''
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
</div>''',
        unsafe_allow_html=True,
    )
    u = st.text_input("", placeholder="Ваш псевдоним", key="username", label_visibility="collapsed")
    if st.button("🎲 Сгенерировать псевдоним"):
        st.session_state.name = f"Участник_{secrets.randbelow(900000)+100000}"
        st.experimental_rerun()
    if u:
        st.session_state.name = u.strip()
        st.experimental_rerun()
    st.stop()

qs = st.session_state.questions
total = len(qs)
idx = st.session_state.idx

if idx >= total:
    st.markdown(
        "<div style='margin-top:50px;padding:40px;text-align:center;font-size:2rem;color:#fff;background:#262626;border-radius:12px;'>Вы завершили прохождение.<br><b>Спасибо за участие!</b></div>",
        unsafe_allow_html=True,
    )
    st.balloons()
    st.stop()

cur = qs[idx]

if st.session_state.phase == "intro":
    if st.session_state.phase_start is None:
        st.session_state.phase_start = time.time()

    if idx < 5:
        st.markdown(
            f"<div style='font-size:1.1rem;line-height:1.6;margin-bottom:30px;'>{'Цель данного вопроса — посмотреть на диаметрально противоположные углы, <b>правый верхний и левый нижний</b>, и определить, окрашены ли они в один цвет.' if cur['qtype']=='corners' else 'Цель данного вопроса — определить, есть ли на представленной картинке <b>буквы русского алфавита</b>.'}<br><br>Картинка будет доступна в течение <b>{TIME_LIMIT}&nbsp;секунд</b>. Время на ответ не ограничено.</div>",
            unsafe_allow_html=True,
        )
        if st.button("Перейти к вопросу"):
            st.session_state.phase = "question"
            st.session_state.phase_start = None
            st.experimental_rerun()
        st.stop()

    remaining_intro = INTRO_TIME_AUTO - (time.time() - st.session_state.phase_start)
    if remaining_intro <= 0:
        st.session_state.phase = "question"
        st.session_state.phase_start = None
        st.experimental_rerun()

    render_timer(math.ceil(remaining_intro), "intro_timer")
    st_autorefresh(interval=1000, key=f"intro_{idx}")
    st.stop()

if st.session_state.phase_start is None:
    st.session_state.phase_start = time.time()

elapsed = time.time() - st.session_state.phase_start
remaining = max(0, TIME_LIMIT - elapsed)

st.markdown(f"### Вопрос №{cur['№']} из {total}")
render_timer(math.ceil(remaining), "question_timer")

if remaining > 0:
    st.image(cur["img"], width=300)
else:
    st.markdown(
        "<div style='text-align:left;font-style:italic;color:#666;padding:40px 0;'>Время показа изображения истекло.</div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

if cur["qtype"] == "corners":
    sel = st.radio(
        cur["prompt"],
        [
            "Да, углы одного цвета.",
            "Нет, углы окрашены в разные цвета.",
            "Затрудняюсь ответить.",
        ],
        index=None,
    )
    if sel:
        finish("да" if sel.startswith("Да") else "нет" if sel.startswith("Нет") else "затрудняюсь")
else:
    txt = st.text_input(cur["prompt"], placeholder="Введите русские буквы и нажмите Enter")
    col1, _ = st.columns([1, 3])
    with col1:
        if st.button("Не вижу букв"):
            finish("Не вижу")
    if txt:
        if re.fullmatch(r"[А-Яа-яЁё ,.;:-]+", txt):
            finish(txt.strip())
        else:
            st.error("Допустимы только русские буквы и знаки пунктуации.")

if remaining > 0:
    st_autorefresh(interval=1000, key=f"question_{idx}")


