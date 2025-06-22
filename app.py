from __future__ import annotations
from streamlit_autorefresh import st_autorefresh
import random, time, datetime, secrets, threading, queue, re, itertools, math
from typing import List, Dict
import streamlit as st
import streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials

MOBILE_QS_FLAG = "mobile"
st.set_page_config(page_title="Визуализация многоканальных изображений",
                   page_icon="🎯", layout="centered",
                   initial_sidebar_state="collapsed")

components.html("""
<style>
    .stApp { background-color: #FFFFFF; }
    div[data-testid="stSidebar"] { display: none; }
</style>
""", height=0)

q = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
if q.get(MOBILE_QS_FLAG) == ["1"]:
    st.markdown("""
    <style>
        .mobile-warning {
            text-align: center;
            padding: 50px 20px;
            background: #f8f9fa;
            border-radius: 10px;
            margin: 20px;
        }
    </style>
    <div class="mobile-warning">
        <h2>Уважаемый участник</h2>
        <p>Данное исследование доступно только с <strong>ПК или ноутбука</strong>.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

BASE_URL = "https://storage.yandexcloud.net/test3123234442"
TIME_LIMIT = 15
INTRO_TIME_REST = 3
REFRESH_INTERVAL = 500

def render_timer(sec: int, tid: str):
    components.html(f"""
    <style>
        .timer-container {{
            background: #f0f2f6;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            font-weight: bold;
            font-size: 16px;
        }}
    </style>
    <div class="timer-container">
        Осталось времени: {sec} сек
    </div>
    """, height=50)

@st.cache_resource(show_spinner="Подключение…")
def get_sheet():
    try:
        scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        gc = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gsp"]), scopes))
        return gc.open("human_study_results").sheet1
    except:
        return None

SHEET = get_sheet()
log_q = queue.Queue()

def writer():
    while True:
        try:
            r = log_q.get()
            if SHEET:
                SHEET.append_row(r)
            log_q.task_done()
        except:
            pass

threading.Thread(target=writer, daemon=True).start()

GROUPS = ["img1_dif_corners", "img2_dif_corners", "img3_same_corners_no_symb", "img4_same_corners", "img5_same_corners"]
ALGS = ["pca_rgb_result", "socolov_lab_result", "socolov_rgb_result", "umap_rgb_result"]
CORNER = {"img1_dif_corners": "нет", "img2_dif_corners": "нет", "img3_same_corners_no_symb": "да", "img4_same_corners": "да", "img5_same_corners": "да"}
LETTER = {"img1_dif_corners": "ж", "img2_dif_corners": "фя", "img3_same_corners_no_symb": "Не вижу", "img4_same_corners": "аб", "img5_same_corners": "юэы"}

def url(g: str, a: str) -> str:
    return f"{BASE_URL}/{g}_{a}.png"

def clean(s: str) -> set[str]:
    return set(re.sub(r"[ ,.;:-]+", "", s.lower()))

def make_qs() -> List[Dict]:
    pg = {g: [] for g in GROUPS}
    for g, a in itertools.product(GROUPS, ALGS):
        pg[g] += [
            {"group": g, "alg": a, "img": url(g, a), "qtype": "corners", "prompt": "Правый верхний и левый нижний угол — одного цвета?", "correct": CORNER[g]},
            {"group": g, "alg": a, "img": url(g, a), "qtype": "letters", "prompt": "Если на изображении вы видите буквы, то укажите, какие именно.", "correct": LETTER[g]}
        ]
    for v in pg.values():
        random.shuffle(v)
    seq, prev = [], None
    while any(pg.values()):
        choices = [g for g in GROUPS if pg[g] and g != prev] or [g for g in GROUPS if pg[g]]
        prev = random.choice(choices)
        seq.append(pg[prev].pop())
    for n, q in enumerate(seq, 1):
        q["№"] = n
    return seq

if "initialized" not in st.session_state:
    st.session_state.update(
        initialized=True, questions=make_qs(), idx=0, name="",
        phase="intro", phase_start_time=None, pause_until=0)

if (st.session_state.pause_until > time.time() and st.session_state.idx < len(st.session_state.questions)):
    st.markdown('<div style="text-align: center; padding: 20px;">Переходим к следующему вопросу...</div>', unsafe_allow_html=True)
    stamp = int(st.session_state.pause_until)
    st_autorefresh(interval=500, key=f"pause_{stamp}")
    st.stop()

if not st.session_state.name:
    st.markdown("""
    <style>
        .intro-container {
            background: #f8f9fa;
            padding: 30px;
            border-radius: 10px;
            margin: 20px 0;
        }
        .intro-container h2 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
        }
        .intro-container h3 {
            color: #555;
            margin-top: 25px;
            margin-bottom: 15px;
        }
        .intro-container p {
            color: #666;
            line-height: 1.6;
            margin-bottom: 15px;
        }
    </style>
    <div class="intro-container">
        <h2>Уважаемый участник,<br>добро пожаловать в эксперимент по изучению восприятия изображений.</h2>
        
        <h3>Как проходит эксперимент</h3>
        <p>В ходе эксперимента вам нужно будет отвечать на простые вопросы об изображениях, которые вы увидите на экране. Всего вам предстоит ответить на <strong>40</strong> вопросов. Прохождение теста займет около 10-15 минут.</p>
        
        <p><strong>Пожалуйста, проходите тест спокойно: исследование не направлено на оценку испытуемых. Оценивается работа алгоритмов, которые выдают картинки разного качества.</strong></p>
        
        <h3>Что это за изображения?</h3>
        <p>Изображения — результат работы разных методов. Ни одно из них не является «эталоном». Цель эксперимента — понять, какие методы обработки лучше сохраняют информацию.</p>
        
        <h3>Важно</h3>
        <p>Эксперимент полностью анонимен. Проходить его следует <strong>только на компьютере или ноутбуке</strong>.</p>
        
        <p style="text-align: center; margin-top: 20px;">Для начала теста введите любой псевдоним и нажмите Enter или нажмите «Сгенерировать псевдоним».</p>
    </div>
    """, unsafe_allow_html=True)
    
    u = st.text_input("", placeholder="Ваш псевдоним", key="username", label_visibility="collapsed")
    
    if st.button("🎲 Сгенерировать псевдоним"):
        st.session_state.name = f"Участник_{secrets.randbelow(900000) + 100000}"
        st.rerun()
    
    if u:
        st.session_state.name = u.strip()
        st.rerun()
    
    st.stop()

def finish(a: str):
    q = st.session_state.questions[st.session_state.idx]
    t_ms = int((time.time() - st.session_state.phase_start_time) * 1000) if st.session_state.phase_start_time else 0
    ok = (clean(a) == clean(q["correct"]) if q["qtype"] == "letters" else a.lower() == q["correct"].lower())
    log_q.put([datetime.datetime.utcnow().isoformat(), st.session_state.name, q["№"], q["group"], q["alg"], q["qtype"], q["prompt"], a, q["correct"], t_ms, ok])
    st.session_state.update(idx=st.session_state.idx + 1, phase="intro", phase_start_time=None, pause_until=time.time() + 0.5)
    st.rerun()

qs, total = st.session_state.questions, len(st.session_state.questions)
idx = st.session_state.idx

if idx >= total:
    st.markdown("""
    <style>
        .completion-container {
            text-align: center;
            padding: 50px;
            background: #f8f9fa;
            border-radius: 10px;
            margin: 20px;
        }
        .completion-container h2 {
            color: #333;
            margin-bottom: 20px;
        }
        .completion-container h3 {
            color: #666;
        }
    </style>
    <div class="completion-container">
        <h2>Вы завершили прохождение.</h2>
        <h3>Спасибо за участие!</h3>
    </div>
    """, unsafe_allow_html=True)
    st.balloons()
    st.stop()

cur = qs[idx]

if st.session_state.phase == "intro":
    if idx < 5:
        txt_c = """Сейчас вы увидите изображение. Цель данного вопроса — посмотреть на диаметрально противоположные углы, <strong>правый верхний и левый нижний</strong>, и определить, окрашены ли они в один цвет.<br><br>Картинка будет доступна в течение <strong>15 секунд</strong>. Время на ответ не ограничено."""
        txt_l = """Сейчас вы увидите изображение. Цель данного вопроса — определить, есть ли на представленной картинке <strong>буквы русского алфавита</strong>.<br><br>Найденные буквы необходимо ввести в текстовое поле: допускается разделение пробелами, запятыми и т. д., а также слитное написание.<br><br>На некоторых картинках букв нет — тогда нажмите кнопку <strong>«Не вижу букв»</strong>."""
        
        st.markdown(f"""
        <style>
            .instruction-box {{
                background: #e8f4f8;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }}
        </style>
        <div class="instruction-box">
            {txt_c if cur['qtype'] == 'corners' else txt_l}
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Перейти к вопросу", key=f"go_{idx}"):
            st.session_state.update(phase="question", phase_start_time=None)
            st.rerun()
        st.stop()
    
    if st.session_state.phase_start_time is None:
        st.session_state.phase_start_time = time.time()
    
    remaining = INTRO_TIME_REST - (time.time() - st.session_state.phase_start_time)
    if remaining <= 0:
        st.session_state.update(phase="question", phase_start_time=None)
        st.rerun()
    
    render_timer(math.ceil(remaining), f"intro_{idx}")
    
    if cur["qtype"] == "corners":
        st.markdown("""
        <style>
            .preview-container {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                text-align: center;
            }
            .preview-container h3 {
                color: #333;
                margin-bottom: 15px;
            }
            .preview-container p {
                color: #666;
                line-height: 1.5;
            }
        </style>
        <div class="preview-container">
            <h3>Начало показа — через указанное время</h3>
            <p>Сейчас вы увидите изображение. Цель данного вопроса — посмотреть на диаметрально противоположные углы, <strong>правый верхний и левый нижний</strong>, и определить, окрашены ли они в один цвет.</p>
            <p>Картинка будет доступна в течение <strong>15 секунд</strong>. Время на ответ не ограничено.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
            .preview-container {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                text-align: center;
            }
            .preview-container h3 {
                color: #333;
                margin-bottom: 15px;
            }
            .preview-container p {
                color: #666;
                line-height: 1.5;
            }
        </style>
        <div class="preview-container">
            <h3>Начало показа — через указанное время</h3>
            <p>Сейчас вы увидите изображение. Цель данного вопроса — определить, есть ли на представленной картинке <strong>буквы русского алфавита</strong>.</p>
            <p>Найденные буквы необходимо ввести в текстовое поле: допускается разделение пробелами, запятыми и т. д., а также слитное написание.</p>
            <p>На некоторых картинках букв нет — тогда нажмите кнопку <strong>«Не вижу букв»</strong>.</p>
        </div>
        """, unsafe_allow_html=True)
    
    st_autorefresh(interval=REFRESH_INTERVAL, key=f"intro_refresh_{idx}")
    st.stop()

if st.session_state.phase_start_time is None:
    st.session_state.phase_start_time = time.time()

elapsed = time.time() - st.session_state.phase_start_time
remaining = max(0, TIME_LIMIT - elapsed)

st.markdown(f"### Вопрос №{cur['№']} из {total}")
render_timer(math.ceil(remaining), f"question_{idx}")

with st.container():
    if remaining > 0:
        components.html(f"""
        <style>
            .image-container {{
                display: flex;
                justify-content: center;
                align-items: center;
                height: 300px;
                margin: 10px 0;
            }}
            .image-container img {{
                max-width: 100%;
                max-height: 100%;
                object-fit: contain;
            }}
        </style>
        <div class="image-container">
            <img src="{cur['img']}" alt="Изображение для анализа">
        </div>
        """, height=310)
    else:
        st.markdown("""
        <style>
            .timeout-message {
                text-align: center;
                padding: 50px;
                background: #f0f0f0;
                border-radius: 10px;
                margin: 20px 0;
                color: #666;
            }
        </style>
        <div class="timeout-message">
            Время показа изображения истекло.
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

if cur["qtype"] == "corners":
    sel = st.radio(cur["prompt"],
                   ["Да, углы одного цвета.", "Нет, углы окрашены в разные цвета.", "Затрудняюсь ответить."],
                   index=None, key=f"r_{idx}")
    if sel:
        finish("да" if sel.startswith("Да") else "нет" if sel.startswith("Нет") else "затрудняюсь")
else:
    txt = st.text_input(cur["prompt"], key=f"t_{idx}", placeholder="Введите русские буквы и нажмите Enter")
    col1, _ = st.columns([1, 3])
    with col1:
        if st.button("Не вижу букв", key=f"s_{idx}"): 
            finish("Не вижу")
    if txt:
        if re.fullmatch(r"[А-Яа-яЁё ,.;:-]+", txt): 
            finish(txt.strip())
        else: 
            st.error("Допустимы только русские буквы и знаки пунктуации.")

if remaining > 0:
    st_autorefresh(interval=1000, key=f"question_refresh_{idx}")










