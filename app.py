from __future__ import annotations
from streamlit_autorefresh import st_autorefresh
import random, time, datetime, secrets, threading, queue, re, itertools
from typing import List, Dict
import streamlit as st, streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Визуализация многоканальных изображений", page_icon="🎯", layout="centered", initial_sidebar_state="collapsed")


def render_timer_js(remaining_time: int, timer_key: str, is_intro: bool = False):
    timer_html = f"""
    <div id="timer-{timer_key}" style="font-size: 1.2rem; font-weight: bold; color: #111; margin-bottom: 10px;">
        Осталось времени: <span id="time-{timer_key}">{remaining_time}</span> сек
    </div>
    <script>
    (function() {{
        const timerId = 'timer-{timer_key}';
        const timeId = 'time-{timer_key}';
        
 
        if (window['interval_' + timerId]) {{
            clearInterval(window['interval_' + timerId]);
        }}
        
        let timeLeft = {remaining_time};
        const timeSpan = document.getElementById(timeId);
        
        window['interval_' + timerId] = setInterval(function() {{
            timeLeft--;
            if (timeSpan) {{
                timeSpan.textContent = Math.max(0, timeLeft);
            }}
            
            if (timeLeft <= 0) {{
                clearInterval(window['interval_' + timerId]);
    
                {'window.sessionStorage.setItem("phase_transition", "true");' if is_intro else ''}
                setTimeout(() => {{ window.location.reload(); }}, 100);
            }}
        }}, 1000);
        

        window.addEventListener('beforeunload', function() {{
            if (window['interval_' + timerId]) {{
                clearInterval(window['interval_' + timerId]);
            }}
        }});
    }})();
    </script>
    """
    components.html(timer_html, height=50)

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
def get_sheet():
    try:
        scopes = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
        gc = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gsp"]), scopes))
        return gc.open("human_study_results").sheet1
    except:
        return None

SHEET = get_sheet()

log_q = queue.Queue()
def _writer():
    while True:
        try:
            row = log_q.get()
            if SHEET: SHEET.append_row(row)
            log_q.task_done()
        except: pass

threading.Thread(target=_writer, daemon=True).start()

def letters_set(s: str) -> set[str]:
    s = re.sub(r"[ ,.;:-]+", "", s.lower())
    return set(s)

BASE_URL = "https://storage.yandexcloud.net/test3123234442"
TIME_LIMIT = 15
INTRO_TIME = 8

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
    
    for v in per.values(): random.shuffle(v)
    seq = []; prev = None
    while any(per.values()):
        pick = [g for g in GROUPS if per[g] and g != prev] or [g for g in GROUPS if per[g]]
        g = random.choice(pick); seq.append(per[g].pop()); prev = g
    
    for n, q in enumerate(seq, 1): q["№"] = n
    return seq

if "questions" not in st.session_state:
    st.session_state.questions = make_questions()
    st.session_state.idx = 0
    st.session_state.name = ""
    st.session_state.phase = "intro"
    st.session_state.start_time = None


if st.session_state.phase == "intro":

    check_transition = components.html("""
    <script>
    const transition = window.sessionStorage.getItem("phase_transition");
    if (transition === "true") {
        window.sessionStorage.removeItem("phase_transition");
        window.parent.postMessage({type: "streamlit:setComponentValue", value: true}, "*");
    } else {
        window.parent.postMessage({type: "streamlit:setComponentValue", value: false}, "*");
    }
    </script>
    """, height=0)
    
    if check_transition:
        st.session_state.phase = "question"
        st.session_state.start_time = time.time()
        st.rerun()

qs, total_q = st.session_state.questions, len(st.session_state.questions)

if st.session_state.get("pause_until", 0) > time.time():
    st.markdown("**Переходим к следующему вопросу...**")
    st_autorefresh(interval=1000, key="pause")
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
    ms = int((time.time() - st.session_state.start_time) * 1000) if st.session_state.start_time else 0
    ok = letters_set(ans) == letters_set(q["correct"]) if q["qtype"] == "letters" else ans.lower() == q["correct"].lower()
    
    if SHEET: 
        log_q.put([datetime.datetime.utcnow().isoformat(), st.session_state.name, q["№"], q["group"], q["alg"], q["qtype"], q["prompt"], ans, q["correct"], ms, ok])
    
    st.session_state.idx += 1
    st.session_state.phase = "intro"
    st.session_state.start_time = None
    st.session_state.pause_until = time.time() + 1
    st.rerun()

i = st.session_state.idx
if i < total_q:
    q = qs[i]

    if st.session_state.phase == "intro":
        if st.session_state.start_time is None:
            st.session_state.start_time = time.time()
        
        elapsed = time.time() - st.session_state.start_time
        intro_limit = 8 if i < 5 else 3
        remain = max(intro_limit - int(elapsed), 0)
        
        if remain > 0:
          
            render_timer_js(remain, f"intro{i}", is_intro=True)
            
            if q["qtype"] == "corners":
                st.markdown("""
<div style="font-size:1.1rem;">
<b>Начало показа через указанное время</b><br><br>
Сейчас вы увидите изображение. Цель данного вопроса — посмотреть на
диаметрально противоположные углы, <b>правый верхний и левый нижний</b>,
и определить, окрашены ли они в один цвет.<br><br>
Картинка будет доступна в течение <b>15&nbsp;секунд</b>. Время на ответ не ограничено.
</div>""", unsafe_allow_html=True)
            else:
                st.markdown("""
<div style="font-size:1.1rem;">
<b>Начало показа через указанное время</b><br><br>
Сейчас вы увидите изображение. Цель данного вопроса — определить, есть ли на
представленной картинке <b>буквы русского алфавита</b>.
Найденные буквы необходимо ввести в текстовое поле: допускается разделение
пробелами, запятыми и т.&nbsp;д., а также слитное написание.<br><br>
На некоторых картинках букв нет — тогда нажмите кнопку <b>«Не вижу букв»</b>.
</div>""", unsafe_allow_html=True)
            st.stop()
        else:
            st.session_state.phase = "question"
            st.session_state.start_time = time.time()
            st.rerun()


    if st.session_state.start_time is None:
        st.session_state.start_time = time.time()
    
    elapsed = time.time() - st.session_state.start_time
    left = max(TIME_LIMIT - int(elapsed), 0)
    
    st.markdown(f"### Вопрос №{q['№']} из {total_q}")
    
   
    render_timer_js(left, f"q{i}", is_intro=False)
    
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

