
from __future__ import annotations
from streamlit_autorefresh import st_autorefresh
import random, time, base64, datetime, secrets, math, os, threading, queue
from typing import List, Dict
import json
import streamlit as st, streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(
    page_title="Визуализация многоканальных изображений",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed",
)


st.markdown("""
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
""", unsafe_allow_html=True)


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


SHEET = get_sheet()


log_q: queue.Queue[List] = queue.Queue()
def _writer():
    while True:
        row=log_q.get()
        try:SHEET.append_row(row)
        except Exception as e:print("Sheets error:",e)
        log_q.task_done()
threading.Thread(target=_writer,daemon=True).start()


TIME_LIMIT = 30
CARDS = [
    ("A","PCA" ,"https://storage.yandexcloud.net/test3123234442/pca_rgb_result_1.png","contrast","Сколько маленьких квадратиков вы видите?","37"),
    ("A","PCA" ,"https://storage.yandexcloud.net/test3123234442/pca_rgb_result_1.png","consistency","Круг и ромб одного цвета?","да"),
    ("A","UMAP","https://storage.yandexcloud.net/test3123234442/umap_rgb_result_1.png","contrast","Сколько маленьких квадратиков вы видите?","42"),
    ("A","UMAP","https://storage.yandexcloud.net/test3123234442/umap_rgb_result_1.png","consistency","Все квадраты одного цвета?","нет"),
    ("B","PCA" ,"https://storage.yandexcloud.net/test3123234442/pca_rgb_result_2.png","contrast","Сколько маленьких квадратиков вы видите?","35"),
    ("B","PCA" ,"https://storage.yandexcloud.net/test3123234442/pca_rgb_result_2.png","consistency","Круг и ромб одного цвета?","нет"),
    ("B","UMAP","https://storage.yandexcloud.net/test3123234442/umap_rgb_result_2.png","contrast","Сколько маленьких квадратиков вы видите?","40"),
    ("B","UMAP","https://storage.yandexcloud.net/test3123234442/umap_rgb_result_2.png","consistency","Все квадраты одного цвета?","да"),
]

def make_questions() -> List[Dict]:
    qs = [{"image_id":i, "method":m, "qtype":t, "prompt":p, "correct":c, "img":url}
          for i,m,url,t,p,c in CARDS]
    random.shuffle(qs)
    for n,q in enumerate(qs, 1):
        q["№"] = n
    return qs

if "questions" not in st.session_state:
    st.session_state.update(questions=make_questions(),
                            idx=0, name="", q_start=None)

qs = st.session_state.questions
total_q = len(qs)


if st.session_state.get("blank_until", 0) > time.time():
    st_autorefresh(interval=250, key="blank")
    
    st.markdown("")
    st.stop()
elif "blank_until" in st.session_state:
    del st.session_state["blank_until"]


if not st.session_state.name:
    st.markdown("""
<div style="color:#111;">
  <h2>Уважаемый участник,<br>добро пожаловать в эксперимент по изучению восприятия изображений.</h2>
  <p><b>Как проходит эксперимент</b><br>
     В ходе эксперимента вам нужно будет отвечать на простые вопросы об изображениях, 
     которые вы увидите на экране. У вас будет 30 секунд на каждый вопрос. 
     Всего вам предстоит ответить на <b>N</b> вопросов. 
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

    uname = st.text_input("", placeholder="Фамилия / псевдоним",
                          key="username", label_visibility="collapsed")
    if st.button("🎲 Сгенерировать псевдоним"):
        st.session_state.name = f"Участник_{secrets.randbelow(900_000)+100_000}"
        st.rerun()
    if uname:
        st.session_state.name = uname.strip()
        st.rerun()
    st.stop()


i = st.session_state.idx
if i < total_q:
    
    st_autorefresh(interval=1000, limit=TIME_LIMIT+2, key=f"t_{i}")

    q = qs[i]
    if st.session_state.q_start is None:
        st.session_state.q_start = time.time()

    elapsed = time.time() - st.session_state.q_start
    left = max(math.ceil(TIME_LIMIT - elapsed), 0)

    
    if elapsed >= TIME_LIMIT:
        ans = st.session_state.get(f"ans{i}", "")
        ok = str(ans).strip().lower() == str(q["correct"]).lower()
        ms = TIME_LIMIT * 1000
        log_q.put([datetime.datetime.utcnow().isoformat(), st.session_state.name,
                   q["№"], q["image_id"], q["method"], q["qtype"],
                   q["prompt"], ans, q["correct"], ms, ok])
        q.update({"ответ": ans if ans else "—", "время, мс": f"{ms:,}",
                  "✓": "✅" if ok else "❌"})
        st.session_state.idx += 1
        st.session_state.q_start = None
        
        st.session_state.blank_until = time.time() + 1.5
        st.experimental_rerun()

   
    components.html(f"""
    <div style="display:flex;gap:16px;height:70px">
      <div style="position:relative;width:70px;height:70px">
        <svg width="70" height="70">
          <circle cx="35" cy="35" r="26" stroke="#444" stroke-width="6" fill="none"/>
          <circle cx="35" cy="35" r="26" stroke="#52b788" stroke-width="6"
                  fill="none" stroke-dasharray="163.3628"
                  stroke-dashoffset="{163.3628*(left/TIME_LIMIT)}"
                  transform="rotate(-90 35 35)"/>
        </svg>
        <span style="position:absolute;top:50%;left:50%;
              transform:translate(-50%,-50%);font:700 1.2rem sans-serif;color:#52b788">
          {left}
        </span>
      </div>
    </div>
    """, height=80)

    st.markdown(f"### Вопрос №{q['№']} из {total_q}")
    st.image(q["img"], clamp=True)

    if q["qtype"] == "contrast":
        _ = st.number_input(q["prompt"], key=f"ans{i}",
                            min_value=0, step=1, format="%d")
    else:
        _ = st.radio(q["prompt"], ["да", "нет"],
                     key=f"ans{i}", horizontal=True, index=None)

    if st.button("Далее"):
        ans = st.session_state.get(f"ans{i}", "")
        ms = int((time.time() - st.session_state.q_start) * 1000)
        ok = str(ans).strip().lower() == str(q["correct"]).lower()
        log_q.put([datetime.datetime.utcnow().isoformat(), st.session_state.name,
                   q["№"], q["image_id"], q["method"], q["qtype"],
                   q["prompt"], ans, q["correct"], ms, ok])
        q.update({"ответ": ans if ans else "—", "время, мс": f"{ms:,}",
                  "✓": "✅" if ok else "❌"})
        st.session_state.idx += 1
        st.session_state.q_start = None
        
        st.session_state.blank_until = time.time() + 1.5
        st.experimental_rerun()


else:
    correct = sum(1 for q in qs if q.get("✓") == "✅")
    st.success(f"Готово, {st.session_state.name}!")
    st.markdown(f"""
    <div style="margin-top:30px;padding:30px;text-align:center;font-size:2rem;
                color:#fff;background:#262626;border-radius:12px;">
        Ваш результат:<br><b>{correct} / {total_q}</b> верных ответов
    </div>
    """, unsafe_allow_html=True)
    st.balloons()
