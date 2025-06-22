from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import time
import datetime
import secrets
import threading
import queue
import re
import itertools
import math
from typing import List, Dict, Optional
import logging
from contextlib import contextmanager
from functools import lru_cache


MOBILE_QS_FLAG = "mobile"
BASE_URL = "https://storage.yandexcloud.net/test3123234442"
TIME_LIMIT = 15
INTRO_TIME_REST = 3
REFRESH_INTERVAL = 1000  
MAX_RETRY_ATTEMPTS = 3
QUEUE_TIMEOUT = 5


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Визуализация многоканальных изображений",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed"
)


st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; }
    div[data-testid="stSidebar"] { display: none; }
    .main-timer { 
        background: #f0f2f6; 
        padding: 10px; 
        border-radius: 8px; 
        text-align: center; 
        font-weight: bold;
        margin: 10px 0;
    }
    .question-container {
        background: #fafafa;
        padding: 20px;
        border-radius: 10px;
        margin: 20px 0;
    }
    .intro-text {
        background: #e8f4f8;
        padding: 20px;
        border-radius: 10px;
        margin: 20px 0;
    }
</style>
""", unsafe_allow_html=True)


q = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
if q.get(MOBILE_QS_FLAG) == ["1"]:
    st.markdown("""
    <div style='text-align: center; padding: 50px;'>
        <h2>Уважаемый участник</h2>
        <p>Данное исследование доступно только с <strong>ПК или ноутбука</strong>.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


GROUPS = ["img1_dif_corners", "img2_dif_corners", "img3_same_corners_no_symb", 
          "img4_same_corners", "img5_same_corners"]
ALGS = ["pca_rgb_result", "socolov_lab_result", "socolov_rgb_result", "umap_rgb_result"]
CORNER = {
    "img1_dif_corners": "нет",
    "img2_dif_corners": "нет",
    "img3_same_corners_no_symb": "да",
    "img4_same_corners": "да",
    "img5_same_corners": "да"
}
LETTER = {
    "img1_dif_corners": "ж",
    "img2_dif_corners": "фя",
    "img3_same_corners_no_symb": "Не вижу",
    "img4_same_corners": "аб",
    "img5_same_corners": "юэы"
}


@lru_cache(maxsize=256)
def url(g: str, a: str) -> str:
    """Генерация URL с кешированием"""
    return f"{BASE_URL}/{g}_{a}.png"

def clean(s: str) -> set[str]:
    return set(re.sub(r"[ ,.;:-]+", "", s.lower()))

def render_timer(sec: int):
    """Отображение таймера без лишних компонентов"""
    st.markdown(
        f'<div class="main-timer">Осталось времени: {sec} сек</div>',
        unsafe_allow_html=True
    )


@st.cache_resource(show_spinner="Подключение к базе данных...")
def get_sheet() -> Optional[gspread.Worksheet]:

    try:
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            dict(st.secrets["gsp"]), scopes
        )
        gc = gspread.authorize(creds)
        sheet = gc.open("human_study_results").sheet1
        logger.info("Успешное подключение к Google Sheets")
        return sheet
    except Exception as e:
        logger.error(f"Ошибка подключения к Google Sheets: {e}")
        return None


SHEET = get_sheet()


log_queue = queue.Queue(maxsize=100)

def async_writer():
    """Асинхронная запись в Google Sheets с обработкой ошибок"""
    while True:
        try:
            
            row_data = log_queue.get(timeout=QUEUE_TIMEOUT)
            
            if row_data is None:
                break
                
            if SHEET:
                retry_count = 0
                while retry_count < MAX_RETRY_ATTEMPTS:
                    try:
                        SHEET.append_row(row_data)
                        logger.info(f"Успешно записана строка: {row_data[1]}")
                        break
                    except Exception as e:
                        retry_count += 1
                        logger.warning(f"Попытка {retry_count}/{MAX_RETRY_ATTEMPTS} не удалась: {e}")
                        time.sleep(1)
                        
            log_queue.task_done()
            
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Критическая ошибка в writer: {e}")


writer_thread = threading.Thread(target=async_writer, daemon=True)
writer_thread.start()


@st.cache_data
def make_questions() -> List[Dict]:
    """Генерация списка вопросов с кешированием"""
    pg = {g: [] for g in GROUPS}
    
    for g, a in itertools.product(GROUPS, ALGS):
        pg[g].extend([
            {
                "group": g,
                "alg": a,
                "img": url(g, a),
                "qtype": "corners",
                "prompt": "Правый верхний и левый нижний угол — одного цвета?",
                "correct": CORNER[g]
            },
            {
                "group": g,
                "alg": a,
                "img": url(g, a),
                "qtype": "letters",
                "prompt": "Если на изображении вы видите буквы, то укажите, какие именно.",
                "correct": LETTER[g]
            }
        ])
    

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
        initialized=True,
        questions=make_questions(),
        idx=0,
        name="",
        phase="intro",
        phase_start_time=None,
        pause_until=0,
        last_refresh=0  
    )


current_time = time.time()
if st.session_state.pause_until > current_time and st.session_state.idx < len(st.session_state.questions):
    st.markdown(
        '<div style="text-align: center; padding: 20px;">Переходим к следующему вопросу...</div>',
        unsafe_allow_html=True
    )

    if current_time - st.session_state.get('last_refresh', 0) > 0.5:
        st.session_state.last_refresh = current_time
        st_autorefresh(interval=500, key=f"pause_{int(st.session_state.pause_until)}")
    st.stop()


if not st.session_state.name:
    st.markdown("""
    <div class="intro-text">
        <h2 style="text-align: center;">Уважаемый участник,<br>добро пожаловать в эксперимент по изучению восприятия изображений.</h2>
        
        <h3>Как проходит эксперимент</h3>
        <p>В ходе эксперимента вам нужно будет отвечать на простые вопросы об изображениях, 
        которые вы увидите на экране. Всего вам предстоит ответить на <strong>40</strong> вопросов. 
        Прохождение теста займет около 10-15 минут.</p>
        
        <p><strong>Пожалуйста, проходите тест спокойно: исследование не направлено на оценку испытуемых.
        Оценивается работа алгоритмов, которые выдают картинки разного качества.</strong></p>
        
        <h3>Что это за изображения?</h3>
        <p>Изображения — результат работы разных методов. Ни одно из них не является «эталоном».
        Цель эксперимента — понять, какие методы обработки лучше сохраняют информацию.</p>
        
        <h3>Важно</h3>
        <p>Эксперимент полностью анонимен. Проходить его следует <strong>только на компьютере или ноутбуке</strong>.</p>
        
        <p style="text-align: center; margin-top: 20px;">
        Для начала теста введите любой псевдоним и нажмите Enter или нажмите «Сгенерировать псевдоним».</p>
    </div>
    """, unsafe_allow_html=True)
    
    username = st.text_input("", placeholder="Ваш псевдоним", key="username", label_visibility="collapsed")
    
    if st.button("🎲 Сгенерировать псевдоним"):
        st.session_state.name = f"Участник_{secrets.randbelow(900000) + 100000}"
        st.rerun()
    
    if username:
        st.session_state.name = username.strip()
        st.rerun()
    
    st.stop()


def finish_question(answer: str):

    q = st.session_state.questions[st.session_state.idx]
    

    t_ms = int((time.time() - st.session_state.phase_start_time) * 1000) if st.session_state.phase_start_time else 0
    

    if q["qtype"] == "letters":
        ok = clean(answer) == clean(q["correct"])
    else:
        ok = answer.lower() == q["correct"].lower()
    

    log_data = [
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
        ok
    ]
    
    try:
        log_queue.put_nowait(log_data)
    except queue.Full:
        logger.warning("Очередь логов переполнена")
    

    st.session_state.update(
        idx=st.session_state.idx + 1,
        phase="intro",
        phase_start_time=None,
        pause_until=time.time() + 0.5
    )
    st.rerun()


questions = st.session_state.questions
total = len(questions)
idx = st.session_state.idx


if idx >= total:
    st.markdown("""
    <div style="text-align: center; padding: 50px;">
        <h2>Вы завершили прохождение.</h2>
        <h3>Спасибо за участие!</h3>
    </div>
    """, unsafe_allow_html=True)
    st.balloons()

    log_queue.put(None)
    st.stop()

current_question = questions[idx]


if st.session_state.phase == "intro":

    if idx < 5:
        if current_question['qtype'] == 'corners':
            instruction_text = """
            <div class="question-container">
                <p>Сейчас вы увидите изображение. Цель данного вопроса — посмотреть на диаметрально противоположные углы,
                <strong>правый верхний и левый нижний</strong>, и определить, окрашены ли они в один цвет.</p>
                
                <p>Картинка будет доступна в течение <strong>15 секунд</strong>. Время на ответ не ограничено.</p>
            </div>
            """
        else:
            instruction_text = """
            <div class="question-container">
                <p>Сейчас вы увидите изображение. Цель данного вопроса — определить, есть ли на представленной картинке
                <strong>буквы русского алфавита</strong>.</p>
                
                <p>Найденные буквы необходимо ввести в текстовое поле: допускается разделение
                пробелами, запятыми и т. д., а также слитное написание.</p>
                
                <p>На некоторых картинках букв нет — тогда нажмите кнопку <strong>«Не вижу букв»</strong>.</p>
            </div>
            """
        
        st.markdown(instruction_text, unsafe_allow_html=True)
        
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
    
    render_timer(math.ceil(remaining))
    
 
    if current_question["qtype"] == "corners":
        st.markdown("""
        <div class="question-container">
            <h3>Начало показа — через указанное время</h3>
            <p>Определите, окрашены ли <strong>правый верхний и левый нижний</strong> углы в один цвет.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="question-container">
            <h3>Начало показа — через указанное время</h3>
            <p>Определите, есть ли на картинке <strong>буквы русского алфавита</strong>.</p>
        </div>
        """, unsafe_allow_html=True)
    

    if current_time - st.session_state.get('last_refresh', 0) > 0.9:
        st.session_state.last_refresh = current_time
        st_autorefresh(interval=REFRESH_INTERVAL, key=f"intro_refresh_{idx}")
    st.stop()


if st.session_state.phase_start_time is None:
    st.session_state.phase_start_time = time.time()

elapsed = time.time() - st.session_state.phase_start_time
remaining = max(0, TIME_LIMIT - elapsed)


st.markdown(f"### Вопрос №{current_question['№']} из {total}")
render_timer(math.ceil(remaining))


with st.container():
    if remaining > 0:
        st.image(current_question["img"], use_column_width=True)
    else:
        st.markdown(
            '<div style="text-align: center; padding: 100px; background: #f0f0f0;">Время показа изображения истекло.</div>',
            unsafe_allow_html=True
        )

st.markdown("---")


if current_question["qtype"] == "corners":
    selection = st.radio(
        current_question["prompt"],
        ["Да, углы одного цвета.", "Нет, углы окрашены в разные цвета.", "Затрудняюсь ответить."],
        index=None,
        key=f"r_{idx}"
    )
    
    if selection:
        if selection.startswith("Да"):
            finish_question("да")
        elif selection.startswith("Нет"):
            finish_question("нет")
        else:
            finish_question("затрудняюсь")
else:
    text_input = st.text_input(
        current_question["prompt"],
        key=f"t_{idx}",
        placeholder="Введите русские буквы и нажмите Enter"
    )
    
    col1, _ = st.columns([1, 3])
    with col1:
        if st.button("Не вижу букв", key=f"s_{idx}"):
            finish_question("Не вижу")
    
    if text_input:
        if re.fullmatch(r"[А-Яа-яЁё ,.;:-]+", text_input):
            finish_question(text_input.strip())
        else:
            st.error("Допустимы только русские буквы и знаки пунктуации.")


if remaining > 0 and current_time - st.session_state.get('last_refresh', 0) > 0.9:
    st.session_state.last_refresh = current_time
    st_autorefresh(interval=1000, key=f"question_refresh_{idx}")





