from __future__ import annotations
from streamlit_autorefresh import st_autorefresh
import random, time, datetime, secrets, threading, queue, re, itertools
from typing import List, Dict
import streamlit as st, streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Визуализация многоканальных изображений",
                   page_icon="🎯", layout="centered",
                   initial_sidebar_state="collapsed")


st.markdown(r"""
<style>
html,body,.stApp,[data-testid="stAppViewContainer"],.main,.block-container{
  background:#808080!important;color:#111!important;}
h1,h2,h3,h4,h5,h6{color:#111!important;}
.question-card,* .question-card{color:#fff!important;}
/* штатные streamlit-кнопки – оставляем как есть */
.stButton>button{
  min-height:52px!important;padding:0 20px!important;border-radius:8px;
  border:1px solid #555!important;background:#222!important;color:#ddd!important;}
input[data-testid="stTextInput"]{
  height:52px!important;padding:0 16px!important;font-size:1.05rem;}
header[data-testid="stHeader"],div[data-testid="stHeader"]{display:none;}
div[data-testid="column"]{padding:0 5px!important;} div[data-testid="column"]>div{padding:0!important;}

#mobile-overlay{position:fixed;inset:0;z-index:9999;background:#808080;display:none;
  align-items:center;justify-content:center;color:#fff;font:500 1.2rem/1.5 sans-serif;text-align:center;padding:0 20px;}
@media (max-width:1023px){#mobile-overlay{display:flex;}}


.custom-buttons{display:flex;gap:8px;margin-top:12px;justify-content:flex-start;}
.custom-btn{
  flex:0 0 200px;           
  min-height:64px;
  border:1px solid;border-radius:8px;font-size:1.1rem;font-weight:700;
  cursor:pointer;transition:background .15s;}
.btn-submit{background:#2d6a4f;border-color:#2d6a4f;color:#fff;}
.btn-submit:hover{background:#25593f;border-color:#25593f;}
.btn-skip{background:#8d0801;border-color:#8d0801;color:#fff;}
.btn-skip:hover{background:#7a0701;border-color:#7a0701;}
</style>
<div id="mobile-overlay">
  Уважаемый&nbsp;участник,<br>
  данное&nbsp;исследование доступно для прохождения только с&nbsp;ПК или&nbsp;ноутбука.
</div>
""", unsafe_allow_html=True)

@st.cache_resource(show_spinner="…")
def get_sheet() -> gspread.Worksheet:
    scopes=["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    gc=gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gsp"]),scopes))
    return gc.open("human_study_results").sheet1
try: SHEET=get_sheet()
except Exception: SHEET=None

log_q: "queue.Queue[list]" = queue.Queue()
def _writer():
    while True:
        row=log_q.get()
        try:
            if SHEET: SHEET.append_row(row)
        except Exception as e: print("Sheets error:",e)
        log_q.task_done()
threading.Thread(target=_writer,daemon=True).start()


BASE_URL   = "https://storage.yandexcloud.net/test3123234442"
TIME_LIMIT = 15
GROUPS=["img1_dif_corners","img2_dif_corners","img3_same_corners_no_symb","img4_same_corners","img5_same_corners"]
ALGS=["pca_rgb_result","socolov_lab_result","socolov_rgb_result","umap_rgb_result"]
CORNER_ANS={"img1_dif_corners":"нет","img2_dif_corners":"нет","img3_same_corners_no_symb":"да","img4_same_corners":"да","img5_same_corners":"да"}
LETTER_ANS={"img1_dif_corners":"ж","img2_dif_corners":"фя","img3_same_corners_no_symb":"Не вижу",
            "img4_same_corners":"аб","img5_same_corners":"юэы"}

def file_url(g,a): return f"{BASE_URL}/{g}_{a}.png"

def make_questions()->List[Dict]:
    per_group={g:[] for g in GROUPS}
    for g,a in itertools.product(GROUPS,ALGS):
        per_group[g]+=[
            dict(group=g,alg=a,img=file_url(g,a),qtype="corners",
                 prompt="Правый верхний и левый нижний угол — одного цвета?",correct=CORNER_ANS[g]),
            dict(group=g,alg=a,img=file_url(g,a),qtype="letters",
                 prompt="Если на изображении вы видите буквы, то укажите, какие именно.",correct=LETTER_ANS[g])]
    for v in per_group.values(): random.shuffle(v)
    ordered=[]
    while any(per_group.values()):
        cycle=list(GROUPS); random.shuffle(cycle)
        for g in cycle:
            if per_group[g]: ordered.append(per_group[g].pop())
    for n,q in enumerate(ordered,1): q["№"]=n
    return ordered

if "questions" not in st.session_state:
    st.session_state.update(questions=make_questions(),idx=0,name="",q_start=None,phase="intro",intro_start=None)
qs=st.session_state.questions; total_q=len(qs)

if "button_clicked" not in st.session_state: st.session_state.button_clicked=None
if st.session_state.get("blank_until",0)>time.time(): st_autorefresh(interval=250,key="blank"); st.stop()
elif "blank_until" in st.session_state: del st.session_state["blank_until"]


if not st.session_state.name:
    st.markdown("""<div style="color:#111;">
  <h2>Уважаемый участник,<br>добро пожаловать в эксперимент по изучению восприятия изображений.</h2>
  <p><b>Как проходит эксперимент</b><br>
     В ходе эксперимента вам нужно будет отвечать на простые вопросы об изображениях, 
     которые вы увидите на экране. Всего вам предстоит ответить на <b>40</b> вопросов. 
     Прохождение теста займет около 10-15 минут.</p>
  <p><b>Что это за изображения?</b><br>
     Изображения — результат работы разных методов. Ни одно из них не является «эталоном».</p>
  <p><b>Важно</b> — проходить только на ПК/ноутбуке.</p>
  <p>Для начала теста введите псевдоним и нажмите Enter или «Сгенерировать псевдоним».</p>
</div>""",unsafe_allow_html=True)
    uname=st.text_input("",placeholder="Фамилия / псевдоним",key="username",label_visibility="collapsed")
    if st.button("🎲 Сгенерировать псевдоним"):
        st.session_state.name=f"Участник_{secrets.randbelow(900_000)+100_000}"; st.experimental_rerun()
    if uname: st.session_state.name=uname.strip(); st.experimental_rerun()
    st.stop()


def letters_set(s): return set(re.sub(r"[ ,.;:-]+","",s.lower()))
def finish(ans:str):
    q=qs[st.session_state.idx]; ms=int((time.time()-st.session_state.q_start)*1000) if st.session_state.q_start else 0
    ok = letters_set(ans)==letters_set(q["correct"]) if q["qtype"]=="letters" else ans.lower()==q["correct"].lower()
    if SHEET:
        log_q.put([datetime.datetime.utcnow().isoformat(),st.session_state.name,
                   q["№"],q["group"],q["alg"],q["qtype"],q["prompt"],ans,q["correct"],ms,ok])
    q.update({"ответ":ans or "—","время, мс":f"{ms:,}","✓":"✅" if ok else "❌"})
    st.session_state.idx+=1; st.session_state.phase="intro"; st.session_state.intro_start=None
    st.session_state.q_start=None; st.session_state.blank_until=time.time()+1.0; st.session_state.button_clicked=None
    st.experimental_rerun()


i=st.session_state.idx
if i<total_q:
    q=qs[i]

    intro_limit = 8 if i<5 else 2
    if st.session_state.phase=="intro":
        if st.session_state.intro_start is None: st.session_state.intro_start=time.time()
        elapsed=time.time()-st.session_state.intro_start; left_intro=max(int(intro_limit-elapsed),0)
        st_autorefresh(interval=500,key=f"intro{i}")
        st.markdown("""
        <div style="font-size:1.1rem;">%s</div>"""%(
        "Сейчас вы увидите изображение. Цель — посмотреть на углы <b>правый верхний и левый нижний</b> и определить, одинаковы ли цвета.<br><br>Картинка доступна 15&nbsp;с. Время на ответ не ограничено."
        if q["qtype"]=="corners" else
        "Сейчас вы увидите изображение. Нужно указать, есть ли <b>буквы русского алфавита</b>. Буквы вводите через пробел/знаки препинания или слитно.<br><br>Если букв нет — нажмите «Не вижу&nbsp;букв»."),
        unsafe_allow_html=True)
        st.markdown(f"**Начало показа через&nbsp;{left_intro} с**")
        if elapsed>=intro_limit:
            st.session_state.phase="question"; st.session_state.q_start=None; st.experimental_rerun()
        st.stop()


    if st.session_state.q_start is None: st.session_state.q_start=time.time()
    elapsed_q=time.time()-st.session_state.q_start; left=max(TIME_LIMIT-int(elapsed_q),0)
    st_autorefresh(interval=1000,key=f"q{i}")

    components.html(f"""<div style="display:flex;gap:16px;height:70px">
      <div style="position:relative;width:70px;height:70px">
        <svg width="70" height="70"><circle cx="35" cy="35" r="26" stroke="#444" stroke-width="6" fill="none"/>
        <circle cx="35" cy="35" r="26" stroke="#52b788" stroke-width="6" fill="none" stroke-dasharray="163.36"
          stroke-dashoffset="{163.36*(left/15)}" transform="rotate(-90 35 35)"/></svg>
        <span style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
              font:700 1.2rem sans-serif;color:#52b788">{left}</span></div></div>""",height=80)

    st.markdown(f"### Вопрос №{q['№']} из {total_q}")
    st.image(q["img"],width=290,clamp=True) if left>0 else st.markdown("<i>Время показа изображения истекло.</i>",unsafe_allow_html=True)

    if q["qtype"]=="corners":
        sel_map={"Да, углы одного цвета.":"да","Нет, углы окрашены в разные цвета.":"нет","Затрудняюсь ответить.":"затрудняюсь"}
        sel=st.radio(q["prompt"],list(sel_map.keys()),index=None,key=f"radio{i}")
        if sel: finish(sel_map[sel])
    else:
        txt=st.text_input(q["prompt"],key=f"in{i}",placeholder="Введите русские буквы")
        if txt and not re.fullmatch(r"[А-Яа-яЁё ,.;:-]+",txt): st.error("Допустимы только русские буквы и знаки пунктуации.")

 
        sub_click = st.button("Ответить",key=f"submit{i}",disabled=True,label_visibility="collapsed")
        skip_click= st.button("Не вижу букв",key=f"skip{i}",disabled=True,label_visibility="collapsed")

       
        components.html(f"""
        <div class="custom-buttons">
          <button class="custom-btn btn-submit" onclick="
            const v=document.querySelector('input[data-testid=\\'stTextInput\\']').value.trim();
            if(!v){{alert('Введите ответ или нажмите «Не вижу букв».');return;}}
            if(!/^[А-Яа-яЁё ,.;:-]+$/.test(v)){{alert('Допустимы только русские буквы и знаки пунктуации.');return;}}
            parent.document.querySelector('button[id$=\\'submit{i}\\']')?.click();">
            Ответить</button>
          <button class="custom-btn btn-skip" onclick="
            parent.document.querySelector('button[id$=\\'skip{i}\\']')?.click();">
            Не вижу букв</button>
        </div>""",height=90)

        if sub_click and txt and re.fullmatch(r"[А-Яа-яЁё ,.;:-]+",txt): finish(txt.strip())
        if skip_click: finish("Не вижу")

else:
    st.success("Вы завершили прохождение. Спасибо за участие!")










