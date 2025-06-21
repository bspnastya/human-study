from __future__ import annotations
from streamlit_autorefresh import st_autorefresh
import random, time, datetime, secrets, threading, queue, re, itertools, math
from typing import List, Dict
import streamlit as st
import streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(
    page_title="Визуализация многоканальных изображений",
    page_icon="🎯", 
    layout="centered", 
    initial_sidebar_state="collapsed"
)


BASE_URL = "https://storage.yandexcloud.net/test3123234442"
TIME_LIMIT = 15  
INTRO_TIME_FIRST = 8 
INTRO_TIME_REST = 3   
REFRESH_INTERVAL = 500  


st.markdown("""
<style>
html,body,.stApp,[data-testid="stAppViewContainer"],.main,.block-container{
    background:#808080!important;color:#111!important;
}
h1,h2,h3,h4,h5,h6{color:#111!important;}
header[data-testid="stHeader"]{display:none;}
.stButton>button{
    min-height:52px!important;
    padding:0 20px!important;
    border:1px solid #555!important;
    background:#222!important;
    color:#ddd!important;
    border-radius:8px;
}
input[data-testid="stTextInput"]{
    height:52px!important;
    padding:0 16px!important;
    font-size:1.05rem;
}
#mobile-overlay{
    position:fixed;
    top:0;
    left:0;
    width:100%;
    height:100%;
    z-index:999999;
    background:#808080;
    display:none;
    align-items:center;
    justify-content:center;
    color:#fff;
    font:500 1.2rem/1.5 sans-serif;
    text-align:center;
    padding:0 20px;
}
@media (max-width:1023px){
    #mobile-overlay{
        display:flex!important;
    }
    body {
        overflow:hidden!important;
    }
}
* {
    -webkit-backface-visibility: hidden;
    -webkit-transform: translateZ(0) scale(1.0, 1.0);
    transform: translateZ(0);
}
.stApp > div {
    transition: opacity 0.1s ease-in-out;
}
.element-container {
    will-change: transform;
}
body {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}
.main > div {
    min-height: 100vh;
}
</style>
<div id="mobile-overlay">
    Уважаемый&nbsp;участник,<br>
    данное&nbsp;исследование доступно для прохождения только с&nbsp;ПК или&nbsp;ноутбука.
</div>
""", unsafe_allow_html=True)


def render_timer(seconds: int, timer_id: str):
    
    components.html(f"""
    <div style="font-size:1.2rem;font-weight:bold;color:#111;margin-bottom:10px;margin-left:-8px;">
        Осталось&nbsp;времени: <span id="timer-{timer_id}">{seconds}</span>&nbsp;сек
    </div>
    <script>
    (function() {{
        const timerId = 'timer-{timer_id}';
        const spanElement = document.getElementById(timerId);
        let timeLeft = {seconds};
        
        if (window['interval_' + timerId]) {{
            clearInterval(window['interval_' + timerId]);
        }}
        
        window['interval_' + timerId] = setInterval(function() {{
            timeLeft--;
            if (spanElement) {{
                spanElement.textContent = Math.max(0, timeLeft);
            }}
            
            if (timeLeft <= 0) {{
                clearInterval(window['interval_' + timerId]);
            }}
        }}, 1000);
        
        window.addEventListener('beforeunload', function() {{
            if (window['interval_' + timerId]) {{
                clearInterval(window['interval_' + timerId]);
            }}
        }});
    }})();
    </script>
    """, height=50)


@st.cache_resource(show_spinner="Подключение...")
def get_sheet():
    try:
        scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        gc = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gsp"]), scopes))
        return gc.open("human_study_results").sheet1
    except Exception:
        return None


SHEET = get_sheet()
log_queue = queue.Queue()

def log_writer():
    while True:
        try:
            row = log_queue.get()
            if SHEET:
                SHEET.append_row(row)
            log_queue.task_done()
        except:
            pass

threading.Thread(target=log_writer, daemon=True).start()


GROUPS = ["img1_dif_corners", "img2_dif_corners", "img3_same_corners_no_symb", "img4_same_corners", "img5_same_corners"]
ALGS = ["pca_rgb_result", "socolov_lab_result", "socolov_rgb_result", "umap_rgb_result"]
CORNER_ANS = {
    "img1_dif_corners": "нет",
    "img2_dif_corners": "нет",
    "img3_same_corners_no_symb": "да",
    "img4_same_corners": "да",
    "img5_same_corners": "да"
}
LETTER_ANS = {
    "img1_dif_corners": "ж",
    "img2_dif_corners": "фя",
    "img3_same_corners_no_symb": "Не вижу",
    "img4_same_corners": "аб",
    "img5_same_corners": "юэы"
}


def file_url(group: str, alg: str) -> str:
    return f"{BASE_URL}/{group}_{alg}.png"


def letters_set(s: str) -> set[str]:
    return set(re.sub(r"[ ,.;:-]+", "", s.lower()))


def make_questions() -> List[Dict]:
    per_group = {g: [] for g in GROUPS}
    
    for g, a in itertools.product(GROUPS, ALGS):
        per_group[g].extend([
            {
                "group": g, "alg": a, "img": file_url(g, a), 
                "qtype": "corners", 
                "prompt": "Правый верхний и левый нижний угол — одного цвета?", 
                "correct": CORNER_ANS[g]
            },
            {
                "group": g, "alg": a, "img": file_url(g, a), 
                "qtype": "letters", 
                "prompt": "Если на изображении вы видите буквы, то укажите, какие именно.", 
                "correct": LETTER_ANS[g]
            }
        ])
    
    for questions in per_group.values():
        random.shuffle(questions)
    
    sequence = []
    prev_group = None
    
    while any(per_group.values()):
        available = [g for g in GROUPS if per_group[g] and g != prev_group]
        if not available:
            available = [g for g in GROUPS if per_group[g]]
        
        chosen_group = random.choice(available)
        sequence.append(per_group[chosen_group].pop())
        prev_group = chosen_group
    
    for n, q in enumerate(sequence, 1):
        q["№"] = n
    
    return sequence


if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.questions = make_questions()
    st.session_state.idx = 0
    st.session_state.name = ""
    st.session_state.phase = "intro"  
    st.session_state.phase_start_time = None
    st.session_state.pause_until = 0


if st.session_state.pause_until > time.time():
    st.markdown(
        "<div style='text-align:center;font-size:1.5rem;color:#fff;background:#262626;padding:20px;border-radius:12px;margin-top:50px;'>"
        "Переходим к следующему вопросу..."
        "</div>", 
        unsafe_allow_html=True
    )
    st_autorefresh(interval=200, key="pause_refresh")
    st.stop()


if not st.session_state.name:
    st.markdown("""
    <div style="color:#111;">
        <h2>Уважаемый участник,<br>добро пожаловать в эксперимент по изучению восприятия изображений.</h2>
        <p><b>Как проходит эксперимент</b><br>
        В ходе эксперимента вам нужно будет отвечать на простые вопросы об изображениях, 
        которые вы увидите на экране. Всего вам предстоит ответить на <b>40</b> вопросов. 
        Прохождение теста займет около 10-15 минут.</p>
        <p><b>Что это за изображения?</b><br>
        Изображения — результат работы разных методов. Ни одно из них не является «эталоном». 
        Цель эксперимента — понять, какие методы обработки лучше сохраняют информацию.</p>
        <p><b>Важно</b><br>
        Эксперимент полностью анонимен. Проходить его следует <b>только на компьютере или ноутбуке</b>.</p>
        <p>Для начала теста введите любой псевдоним и нажмите Enter либо нажмите «Сгенерировать псевдоним».</p>
    </div>
    """, unsafe_allow_html=True)
    
    name_input = st.text_input("", placeholder="Фамилия / псевдоним", key="username", label_visibility="collapsed")
    
    if st.button("🎲 Сгенерировать псевдоним"):
        st.session_state.name = f"Участник_{secrets.randbelow(900000) + 100000}"
        st.rerun()
    
    if name_input:
        st.session_state.name = name_input.strip()
        st.rerun()
    
    st.stop()


def finish_answer(answer: str):
    current_q = st.session_state.questions[st.session_state.idx]
    
    time_ms = 0
    if st.session_state.phase_start_time:
        time_ms = int((time.time() - st.session_state.phase_start_time) * 1000)
    
    if current_q["qtype"] == "letters":
        is_correct = letters_set(answer) == letters_set(current_q["correct"])
    else:
        is_correct = answer.lower() == current_q["correct"].lower()
    
    log_queue.put([
        datetime.datetime.utcnow().isoformat(),
        st.session_state.name,
        current_q["№"],
        current_q["group"],
        current_q["alg"],
        current_q["qtype"],
        current_q["prompt"],
        answer,
        current_q["correct"],
        time_ms,
        is_correct
    ])
    
    st.session_state.idx += 1
    st.session_state.phase = "intro"
    st.session_state.phase_start_time = None
    st.session_state.pause_until = time.time() + 0.5
    st.rerun()


questions = st.session_state.questions
total_questions = len(questions)
current_idx = st.session_state.idx

if current_idx >= total_questions:
    st.markdown("""
    <div style='margin-top:50px;padding:40px;text-align:center;font-size:2rem;color:#fff;background:#262626;border-radius:12px;'>
        Вы завершили прохождение.<br><b>Спасибо за участие!</b>
    </div>
    """, unsafe_allow_html=True)
    st.balloons()
    st.stop()

current_question = questions[current_idx]


if st.session_state.phase == "intro":
    if st.session_state.phase_start_time is None:
        st.session_state.phase_start_time = time.time()
    
    intro_duration = INTRO_TIME_FIRST if current_idx < 5 else INTRO_TIME_REST
    elapsed = time.time() - st.session_state.phase_start_time
    remaining = max(0, intro_duration - elapsed)
    
    if remaining > 0:
     
        render_timer(
            seconds=math.ceil(remaining),
            timer_id=f"intro_{current_idx}"
        )
        

        if current_question["qtype"] == "corners":
            st.markdown("""
            <div style="font-size:1.1rem;line-height:1.6;">
                <b>Начало показа — через указанное время</b><br><br>
                Сейчас вы увидите изображение. Цель данного вопроса — посмотреть на
                диаметрально противоположные углы, <b>правый верхний и левый нижний</b>,
                и определить, окрашены ли они в один цвет.<br><br>
                Картинка будет доступна в течение <b>15&nbsp;секунд</b>. Время на ответ не ограничено.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="font-size:1.1rem;line-height:1.6;">
                <b>Начало показа — через указанное время</b><br><br>
                Сейчас вы увидите изображение. Цель данного вопроса — определить, есть ли на
                представленной картинке <b>буквы русского алфавита</b>.<br><br>
                Найденные буквы необходимо ввести в текстовое поле: допускается разделение
                пробелами, запятыми и т.&nbsp;д., а также слитное написание.<br><br>
                На некоторых картинках букв нет — тогда нажмите кнопку <b>«Не вижу букв»</b>.
            </div>
            """, unsafe_allow_html=True)
        
  
        st_autorefresh(interval=REFRESH_INTERVAL, key=f"intro_refresh_{current_idx}")
    else:
        
        st.session_state.phase = "question"
        st.session_state.phase_start_time = None
        st.rerun()


else:
    if st.session_state.phase_start_time is None:
        st.session_state.phase_start_time = time.time()
    
    elapsed = time.time() - st.session_state.phase_start_time
    remaining = max(0, TIME_LIMIT - elapsed)
    
    st.markdown(f"### Вопрос №{current_question['№']} из {total_questions}")
    
    render_timer(
        seconds=math.ceil(remaining),
        timer_id=f"question_{current_idx}"
    )
    
    image_container = st.container()
    with image_container:
        if remaining > 0:
            components.html(f"""
            <div id="image-container-{current_idx}" style="text-align:left;margin:5px 0;">
                <img src="{current_question['img']}" width="300" style="border:1px solid #444;border-radius:8px;">
            </div>
            <script>
            setTimeout(function() {{
                const container = document.getElementById('image-container-{current_idx}');
                if (container) {{
                    container.innerHTML = '<div style="font-style:italic;color:#666;padding:20px 0;">Время показа изображения истекло.</div>';
                }}
            }}, {TIME_LIMIT * 1000});
            </script>
            """, height=310)
        else:
            st.markdown(
                "<div style='text-align:left;font-style:italic;color:#666;padding:40px 0;'>"
                "Время показа изображения истекло."
                "</div>", 
                unsafe_allow_html=True
            )
    
    st.markdown("---")
    
    if current_question["qtype"] == "corners":
        selection = st.radio(
            current_question["prompt"],
            options=[
                "Да, углы одного цвета.",
                "Нет, углы окрашены в разные цвета.",
                "Затрудняюсь ответить."
            ],
            index=None,
            key=f"radio_{current_idx}"
        )
        
        if selection:
            if selection.startswith("Да"):
                finish_answer("да")
            elif selection.startswith("Нет"):
                finish_answer("нет")
            else:
                finish_answer("затрудняюсь")
    
    else:
        text_input = st.text_input(
            current_question["prompt"],
            key=f"text_{current_idx}",
            placeholder="Введите русские буквы и нажмите Enter"
        )
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("Не вижу букв", key=f"skip_{current_idx}"):
                finish_answer("Не вижу")
        
        if text_input:
            if re.fullmatch(r"[А-Яа-яЁё ,.;:-]+", text_input):
                finish_answer(text_input.strip())
            else:
                st.error("Допустимы только русские буквы и знаки пунктуации.")
    
    if remaining > 0:
        st_autorefresh(interval=1000, key=f"question_refresh_{current_idx}")

