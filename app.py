from __future__ import annotations
import streamlit as st, streamlit.components.v1 as components
import random, time, datetime, secrets, re, itertools, math, threading, queue, requests, io, atexit, uuid, html
from typing import List, Dict
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL          = "https://storage.yandexcloud.net/test3123234442"
TIME_IMG_VISIBLE  = 15
INTRO_FIRST       = 5         
INTRO_REST_SEC    = 3
PAUSE_SEC         = .5
MOBILE_QS_FLAG    = "mobile"
BATCH_LIMIT_CELLS = 450         
LOG_Q_MAXSIZE     = 1000        

GROUPS = ["img1_dif_corners", "img2_dif_corners", "img3_same_corners_no_symb",
          "img4_same_corners", "img5_same_corners"]
ALGS   = ["pca_rgb_result", "socolov_lab_result", "socolov_rgb_result", "umap_rgb_result"]
CORNER = {"img1_dif_corners":"нет","img2_dif_corners":"нет",
          "img3_same_corners_no_symb":"да","img4_same_corners":"да","img5_same_corners":"да"}
LETTER = {"img1_dif_corners":"ж","img2_dif_corners":"фя",
          "img3_same_corners_no_symb":"Не вижу","img4_same_corners":"аб","img5_same_corners":"юэы"}


WELCOME_HTML = """ … (тот же текст, что был) … """
INTRO_CORNERS_TEXT = """ … """
INTRO_LETTERS_TEXT = """ … """
INTRO_CORNERS_TIMED = f"<b>Начало показа — через указанное время</b><br><br>{INTRO_CORNERS_TEXT}"
INTRO_LETTERS_TIMED = f"<b>Начало показа — через указанное время</b><br><br>{INTRO_LETTERS_TEXT}"


st.set_page_config("Визуализация многоканальных изображений", "🎯",
                   layout="centered", initial_sidebar_state="collapsed")

components.html(f"""
<script>
(function() {{
  const flag='{MOBILE_QS_FLAG}', m=innerWidth<1024, q=new URLSearchParams(location.search);
  if(m&&!q.has(flag)){{q.set(flag,'1');location.search=q.toString();}}
}})();
</script>""", height=0)

if st.query_params.get(MOBILE_QS_FLAG)==["1"]:
    st.markdown("""<style>body{{background:#808080;color:#fff;text-align:center;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}
    h2{{font-size:1.3rem;font-weight:500;line-height:1.4}}</style>
    <h2>Уважаемый участник<br>Данное исследование доступно только с <strong>ПК или ноутбука</strong>.</h2>""",
                unsafe_allow_html=True)
    st.stop()

st.markdown("""
<style>
html,body,.stApp,[data-testid="stAppViewContainer"],.main,.block-container{background:#808080;color:#111;}
header[data-testid="stHeader"]{display:none;}
.stButton>button{min-height:52px;padding:0 20px;border:1px solid #555;background:#222;color:#ddd;border-radius:8px;}
input[data-testid="stTextInput"]{height:52px;padding:0 16px;font-size:1.05rem;}
body,html{scrollbar-gutter:stable;}          
</style>""", unsafe_allow_html=True)

components.html("""
<script>
window.startTimer=(id,sec)=>{
  clearInterval(window['i_'+id]);
  let t=sec,s=document.getElementById(id);
  window['i_'+id]=setInterval(()=>{if(s)s.textContent=Math.max(0,--t);if(t<=0)clearInterval(window['i_'+id]);},1000);
}
</script>""", height=0)


@st.cache_resource
def sheet():
    scopes=["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    gc=gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gsp"]),scopes))
    sht=gc.open("human_study_results").sheet1
    
    sht.append_row(["—"])  
    return sht
SHEET=sheet()

log_q = queue.Queue(maxsize=LOG_Q_MAXSIZE)

def writer():
    batch, cells = [], 0
    while True:
        row = log_q.get()
        if row=="__FLUSH__":
            pass
        else:
            batch.append(row); cells += len(row)
        if row=="__FLUSH__" or cells >= BATCH_LIMIT_CELLS:
            if batch:
                try: SHEET.append_rows(batch,value_input_option="RAW")
                except Exception: pass
                batch.clear(); cells = 0
        log_q.task_done()
threading.Thread(target=writer, daemon=True).start()
atexit.register(lambda: log_q.put("__FLUSH__"))


_retry = Retry(total=3, backoff_factor=.5, status_forcelist=[500,502,503,504])
session = requests.Session()
session.headers["User-Agent"] = "HumanStudyClient/1.0"
session.mount("https://", HTTPAdapter(max_retries=_retry))

@st.cache_data
def fetch_png(url:str)->bytes:
    return session.get(url, timeout=5).content


def build_questions()->List[Dict]:
    per={g:[] for g in GROUPS}
    for g,a in itertools.product(GROUPS,ALGS):
        per[g]+= [
            {"group":g,"alg":a,"img":f"{BASE_URL}/{g}_{a}.png","qtype":"corners",
             "prompt":"Правый верхний и левый нижний угол — одного цвета?","correct":CORNER[g]},
            {"group":g,"alg":a,"img":f"{BASE_URL}/{g}_{a}.png","qtype":"letters",
             "prompt":"Если на изображении вы видите буквы, то укажите, какие именно.","correct":LETTER[g]}
        ]
    for v in per.values(): random.shuffle(v)
    seq,prev=[],None
    while any(per.values()):
        choices=[g for g in GROUPS if per[g] and g!=prev] or [g for g in GROUPS if per[g]]
        prev=random.choice(choices); seq.append(per[prev].pop())
    for i,q in enumerate(seq,1): q["№"]=i
    return seq


def letters_set(s:str)->set[str]:
    return set(re.sub(r"[ ,.;:-]+","",s.lower()))

def safe(val:str)->str: 
    return html.escape(val, quote=True)


ss = st.session_state
if "seq" not in ss:
    ss.seq        = build_questions()
    ss.idx        = 0
    ss.phase      = "intro"
    ss.name       = ""
    ss.session_id = str(uuid.uuid4())       


if not ss.name:
    st.markdown(WELCOME_HTML, unsafe_allow_html=True)
    nick = st.text_input("", placeholder="Ваш псевдоним", label_visibility="collapsed")
    if st.button("🎲 Сгенерировать псевдоним"):
        ss.name=f"Участник_{secrets.randbelow(900000)+100000}"
        st.rerun()
    if nick:
        ss.name = html.escape(nick.strip(), quote=True)
        st.rerun()
    st.stop()

if ss.idx >= len(ss.seq):
    log_q.put("__FLUSH__")
    st.markdown("<div style='margin-top:40px;padding:40px;text-align:center;font-size:2rem;background:#262626;color:#fff;border-radius:12px;'>Вы завершили прохождение.<br><b>Спасибо за участие!</b></div>", unsafe_allow_html=True)
    st.balloons(); st.stop()

q = ss.seq[ss.idx]


def save(ans:str):
    t_ms = int((time.time()-ss.t0)*1000)
    ok   = letters_set(ans)==letters_set(q["correct"]) if q["qtype"]=="letters" else ans.lower()==q["correct"].lower()
    row  = [datetime.datetime.utcnow().isoformat(), ss.session_id, ss.name,
            q["№"], q["group"], q["alg"], q["qtype"],
            safe(q["prompt"]), safe(ans), safe(q["correct"]), t_ms, ok]
    try:
        log_q.put_nowait(row)
    except queue.Full:
        pass 
    ss.idx  += 1
    ss.phase = "intro"
    time.sleep(PAUSE_SEC)
    st.experimental_rerun()


if ss.phase=="intro":
    if ss.idx < INTRO_FIRST:
        st.markdown(INTRO_CORNERS_TEXT if q["qtype"]=="corners" else INTRO_LETTERS_TEXT,
                    unsafe_allow_html=True)
        if st.button("Перейти к вопросу"):
            ss.phase="question"; ss.t0=time.time(); st.experimental_rerun()
        st.stop()

    if "intro_t0" not in ss: ss.intro_t0=time.time()
    rem = INTRO_REST_SEC - (time.time() - ss.intro_t0)
    if rem <= 0:
        ss.pop("intro_t0",None)
        ss.phase="question"; ss.t0=time.time(); st.experimental_rerun()

    components.html(f"""<span id="cnt_intro"></span><script>startTimer("cnt_intro",{math.ceil(rem)})</script>""",
                    height=0)
    st.markdown(INTRO_CORNERS_TIMED if q["qtype"]=="corners" else INTRO_LETTERS_TIMED,
                unsafe_allow_html=True)
    st.stop()


if "t0" not in ss: ss.t0=time.time()
rem = max(0, TIME_IMG_VISIBLE - (time.time() - ss.t0))

st.markdown(f"### Вопрос №{q['№']} из {len(ss.seq)}")
components.html(f"""<span id="cnt_q"></span><script>startTimer("cnt_q",{math.ceil(rem)})</script>""", height=0)

if rem>0:
    st.image(io.BytesIO(fetch_png(q["img"])), width=300)
else:
    st.markdown("*Время показа изображения истекло.*")

st.markdown("---")

if q["qtype"]=="corners":
    choice = st.radio(q["prompt"],
                      ["Да, углы одного цвета.","Нет, углы окрашены в разные цвета.","Затрудняюсь ответить."],
                      index=None)
    if choice:
        save("да" if choice.startswith("Да") else "нет" if choice.startswith("Нет") else "затрудняюсь")
else:
    txt = st.text_input(q["prompt"])
    col,_ = st.columns([1,3])
    with col:
        if st.button("Не вижу букв"): save("Не вижу")
    if txt and re.fullmatch(r"[А-Яа-яЁё ,.;:-]+", txt):
        save(txt.strip())






