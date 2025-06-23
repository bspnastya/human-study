from __future__ import annotations
import random, time, datetime, secrets, threading, queue, re, itertools, json
from typing import List, Dict
import streamlit as st
import streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pathlib import Path

MOBILE_QS_FLAG="mobile"
st.set_page_config(page_title="Визуализация многоканальных изображений",
                   page_icon="🎯",layout="centered",initial_sidebar_state="collapsed")

if "initialized" not in st.session_state:
    st.session_state.update(initialized=True,questions=[],idx=0,name="",
                            phase="intro",phase_start_time=None,pause_until=0.0,
                            _timer_flags={},session_id=secrets.token_hex(8))

components.html(f"""
<script>
(function() {{
  const f='{MOBILE_QS_FLAG}', m=window.innerWidth<1024;
  if(m) document.documentElement.classList.add('mobile-client');
  const qs=new URLSearchParams(window.location.search);
  if(m && !qs.has(f)) {{ qs.set(f,'1'); window.location.search=qs.toString(); }}
}})();
</script>
""",height=0)

q=st.query_params if hasattr(st,"query_params") else st.experimental_get_query_params()
if q.get(MOBILE_QS_FLAG)==["1"]:
    st.markdown("""
    <style>
      body{background:#808080;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
      h2{line-height:1.4;font-size:1.3rem;font-weight:500;}
    </style>
    <h2>Уважаемый участник<br>Данное исследование доступно только с <strong>ПК или ноутбука</strong>.</h2>
    """,unsafe_allow_html=True);st.stop()

BASE_URL="https://storage.yandexcloud.net/test3123234442"
TIME_LIMIT=15

st.markdown("""
<style>
html,body,.stApp,[data-testid="stAppViewContainer"],.main,.block-container{background:#808080!important;color:#111!important;}
h1,h2,h3,h4,h5,h6,p,label,li,span{color:#111!important;}
header[data-testid="stHeader"]{display:none;}
.stButton>button{min-height:52px;padding:0 20px;border:1px solid #555;background:#222;color:#fff;border-radius:8px;}
input[data-testid="stTextInput"]{height:52px;padding:0 16px;font-size:1.05rem;}
</style>
""",unsafe_allow_html=True)

BACKUP_DIR=Path("backup_results");BACKUP_DIR.mkdir(exist_ok=True)
def backup_row(r): BACKUP_DIR.joinpath(f"{int(time.time()*1e6)}.json").write_text(json.dumps(r,ensure_ascii=False),encoding="utf-8")

global_queue=globals().setdefault("_GLOBAL_QUEUE",queue.Queue(maxsize=1000))
if not globals().get("_WRITER_STARTED"):
    globals()["_WRITER_STARTED"]=True
    def writer():
        buf,last=[],time.time()
        while True:
            try: buf.append(global_queue.get(timeout=1))
            except queue.Empty: pass
            if buf and (len(buf)>=5 or time.time()-last>3):
                sh=get_sheet()
                if sh:
                    try: sh.append_rows(buf,value_input_option="RAW");buf.clear();last=time.time()
                    except: [backup_row(r) for r in buf];buf.clear();last=time.time()
                else: [backup_row(r) for r in buf];buf.clear();last=time.time()
    threading.Thread(target=writer,daemon=True).start()

@st.cache_resource(show_spinner="Подключение…")
def get_sheet():
    for _ in range(3):
        try:
            scopes=["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
            gc=gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gsp"]),scopes))
            return gc.open("human_study_results").sheet1
        except: time.sleep(2)
    return None

GROUPS=["img1_dif_corners","img2_dif_corners","img3_same_corners_no_symb","img4_same_corners","img5_same_corners"]
ALGS=["pca_rgb_result","socolov_lab_result","socolov_rgb_result","umap_rgb_result"]
CORNER={"img1_dif_corners":"нет","img2_dif_corners":"нет","img3_same_corners_no_symb":"да","img4_same_corners":"да","img5_same_corners":"да"}
LETTER={"img1_dif_corners":"ж","img2_dif_corners":"фя","img3_same_corners_no_symb":"Не вижу","img4_same_corners":"аб","img5_same_corners":"юэы"}
def url(g,a):return f"{BASE_URL}/{g}_{a}.png"
def clean(s):return set(re.sub("[ ,.;:-]+","",s.lower()))

@st.cache_data
def template():
    d={g:[] for g in GROUPS}
    for g,a in itertools.product(GROUPS,ALGS):
        d[g]+=[
            {"group":g,"alg":a,"img":url(g,a),"qtype":"corners","prompt":"Правый верхний и левый нижний угол — одного цвета?","correct":CORNER[g]},
            {"group":g,"alg":a,"img":url(g,a),"qtype":"letters","prompt":"Если на изображении вы видите буквы, то укажите, какие именно.","correct":LETTER[g]}
        ]
    return d
def make_qs():
    pg={k:v.copy() for k,v in template().items()}
    for v in pg.values(): random.shuffle(v)
    seq,prev=[],None
    while any(pg.values()):
        ch=[g for g in GROUPS if pg[g] and g!=prev] or [g for g in GROUPS if pg[g]]
        prev=random.choice(ch); seq.append(pg[prev].pop())
    for i,q in enumerate(seq,1): q["№"]=i
    return seq
if not st.session_state.questions: st.session_state.questions=make_qs()

def render_timer(sec:int,tid:str):
    if tid in st.session_state.get("_timer_flags", {}):
        return
    components.html(f"""
    <div style="font-size:1.2rem;font-weight:bold;color:#111;margin-bottom:10px;margin-left:-8px;">
      Осталось&nbsp;времени: <span id="t{tid}">{sec}</span>&nbsp;сек
    </div>
    <script>
      (function(){{
        let t={sec};
        const span=document.getElementById('t{tid}');
        const iv=setInterval(()=>{{if(--t<0){{clearInterval(iv);return;}}if(span)span.textContent=t;}},1000);
      }})();
    </script>""",height=50)
    if "_timer_flags" not in st.session_state:
        st.session_state._timer_flags = {}
    st.session_state._timer_flags[tid]=True

def log_row(ans):
    q=st.session_state.questions[st.session_state.idx]
    ms=int((time.time()-st.session_state.phase_start_time)*1000) if st.session_state.phase_start_time else 0
    ok=clean(ans)==clean(q["correct"]) if q["qtype"]=="letters" else ans.lower()==q["correct"].lower()
    r=[datetime.datetime.utcnow().isoformat(),st.session_state.name,q["№"],q["group"],q["alg"],q["qtype"],q["prompt"],ans,q["correct"],ms,ok,st.session_state.session_id]
    try: global_queue.put(r,timeout=1)
    except queue.Full: backup_row(r)

def finish(ans):
    log_row(ans)
    st.session_state.update(idx=st.session_state.idx+1,phase="intro",phase_start_time=None,pause_until=time.time()+0.5,_timer_flags={})
    st.rerun()

if st.session_state.pause_until>time.time():
    components.html("<script>setTimeout(()=>parent.location.reload(),600);</script>",height=0);st.stop()

idx,total=st.session_state.idx,len(st.session_state.questions)
if idx>=total:
    st.markdown("<div style='margin-top:50px;padding:40px;text-align:center;font-size:2rem;color:#fff;background:#262626;border-radius:12px;'>Вы завершили прохождение.<br><b>Спасибо за участие!</b></div>",unsafe_allow_html=True)
    st.balloons();st.stop()

if not st.session_state.name:
    st.markdown("""
    <div style="color:#111;">
      <h2>Уважаемый участник,<br>добро пожаловать в эксперимент по изучению восприятия изображений.</h2>
      <p><b>Как проходит эксперимент</b><br>
      В ходе эксперимента вам нужно будет отвечать на простые вопросы об изображениях, которые вы увидите на экране. Всего вам предстоит ответить на <b>40</b> вопросов. Прохождение теста займет около 10-15 минут.</p>
      <p><b>Пожалуйста, проходите тест спокойно: исследование не направлено на оценку испытуемых.
      Оценивается работа алгоритмов, которые выдают картинки разного качества.</b></p>
      <p><b>Что это за изображения?</b><br>
      Изображения — результат работы разных методов. Ни одно из них не является «эталоном».
      Цель эксперимента — понять, какие методы обработки лучше сохраняют информацию.</p>
      <p><b>Важно</b><br>
      Эксперимент полностью анонимен. Проходить его следует <b>только на компьютере или ноутбуке</b>.</p>
      <p>Для начала теста введите любой псевдоним и нажмите Enter или нажмите «Сгенерировать псевдоним».</p>
    </div>""",unsafe_allow_html=True)
    n=st.text_input("",placeholder="Ваш псевдоним",key="username",label_visibility="collapsed")
    if st.button("🎲 Сгенерировать псевдоним"):
        st.session_state.name=f"Участник_{secrets.randbelow(900000)+100000}";st.rerun()
    if n: st.session_state.name=n.strip(); st.rerun()
    st.stop()

q=st.session_state.questions[idx]

if st.session_state.phase=="intro":
    txt_c="""Сейчас вы увидите изображение. Цель данного вопроса — посмотреть на диаметрально противоположные углы,
<b>правый верхний и левый нижний</b>, и определить, окрашены ли они в один цвет.<br><br>Картинка будет доступна
в течение <b>15&nbsp;секунд</b>. Время на ответ не ограничено."""
    txt_l="""Сейчас вы увидите изображение. Цель данного вопроса — определить, есть ли на представленной картинке
<b>буквы русского алфавита</b>.<br><br>Найденные буквы необходимо ввести в текстовое поле: допускается разделение
пробелами, запятыми и т.&nbsp;д., а также слитное написание.<br><br>На некоторых картинках букв нет — тогда
нажмите кнопку <b>«Не вижу букв»</b>."""
    st.markdown(txt_c if q["qtype"]=="corners" else txt_l,unsafe_allow_html=True)
    if st.button("Перейти к вопросу",key=f"start_{idx}"):
        st.session_state.update(phase="question",phase_start_time=time.time(),_timer_flags={})
        st.rerun()
    st.stop()

st.markdown(f"### Вопрос №{q['№']} из {total}")
render_timer(TIME_LIMIT, str(idx))

remain=TIME_LIMIT-(time.time()-st.session_state.phase_start_time)
placeholder=st.empty()
if remain>0:
    placeholder.image(q["img"],width=300)
else:
    placeholder.markdown("<div style='color:#666;font-style:italic;padding:40px 0;text-align:center;'>Время показа изображения истекло.</div>",unsafe_allow_html=True)

st.markdown("---")
if q["qtype"]=="corners":
    sel=st.radio(q["prompt"],["Да, углы одного цвета.","Нет, углы окрашены в разные цвета.","Затрудняюсь ответить."],index=None,key=f"r_{idx}")
    if sel: finish("да" if sel.startswith("Да") else "нет" if sel.startswith("Нет") else "затрудняюсь")
else:
    a=st.text_input(q["prompt"],key=f"ans_{idx}",placeholder="Введите буквы и Enter")
    col,_=st.columns([1,3])
    with col:
        if st.button("Не вижу букв",key=f"none_{idx}"): finish("Не вижу")
    if a and re.fullmatch(r"[А-Яа-яЁё ,.;:-]+",a): finish(a.strip())
    elif a: st.error("Используйте только русские буквы и знаки пунктуации.")


