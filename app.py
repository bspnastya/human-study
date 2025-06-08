
from __future__ import annotations
from streamlit_autorefresh import st_autorefresh
import random, time, base64, datetime, secrets, math, os, threading, queue
from typing import List, Dict

import streamlit as st, streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Визуализация многоканальных изображений",
                   page_icon="🎯", layout="centered",
                   initial_sidebar_state="collapsed")


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


#mobile-overlay{
  position:fixed;inset:0;z-index:9999;
  background:#808080;display:none;
  align-items:center;justify-content:center;
  color:#fff;font:500 1.2rem/1.5 sans-serif;
  text-align:center;padding:0 20px;}
@media (max-width:1023px){#mobile-overlay{display:flex;}}
</style>

<div id="mobile-overlay">
  Уважаемый&nbsp;участник,<br>
  данное&nbsp;исследование доступно для прохождения только с&nbsp;ПК или&nbsp;ноутбука.
</div>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Подключаем Google Sheets…")
def get_sheet():
    sc=["https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"]
    gc=gspread.authorize(
        ServiceAccountCredentials.from_json_keyfile_name("gcp-creds.json",sc))
    return gc.open("human_study_results").sheet1
SHEET=get_sheet()

log_q: queue.Queue[List] = queue.Queue()
def _writer():
    while True:
        row=log_q.get()
        try:SHEET.append_row(row)
        except Exception as e:print("Sheets error:",e)
        log_q.task_done()
threading.Thread(target=_writer,daemon=True).start()


TIME_LIMIT=30
#def b64(p:str)->str:
   # return "data:image/png;base64,"+base64.b64encode(open(p,"rb").read()).decode()

CARDS=[   # image_id, method, filename, qtype, prompt, correct
 ("A","PCA" ,"https://storage.yandexcloud.net/test3123234442/pca_rgb_result_1.png","contrast"   ,"Сколько маленьких квадратиков вы видите?","37"),
 ("A","PCA" ,"https://storage.yandexcloud.net/test3123234442/pca_rgb_result_1.png","consistency","Круг и ромб одного цвета?"               ,"да"),
 ("A","UMAP","https://storage.yandexcloud.net/test3123234442/umap_rgb_result_1.png","contrast"   ,"Сколько маленьких квадратиков вы видите?","42"),
 ("A","UMAP","https://storage.yandexcloud.net/test3123234442/umap_rgb_result_1.png","consistency","Все квадраты одного цвета?"              ,"нет"),
 ("B","PCA" ,"https://storage.yandexcloud.net/test3123234442/pca_rgb_result_2.png","contrast"   ,"Сколько маленьких квадратиков вы видите?","35"),
 ("B","PCA" ,"https://storage.yandexcloud.net/test3123234442/pca_rgb_result_2.png","consistency","Круг и ромб одного цвета?"               ,"нет"),
 ("B","UMAP","https://storage.yandexcloud.net/test3123234442/umap_rgb_result_2.png","contrast"   ,"Сколько маленьких квадратиков вы видите?","40"),
 ("B","UMAP","https://storage.yandexcloud.net/test3123234442/umap_rgb_result_2.png","consistency","Все квадраты одного цвета?"              ,"да"),
]
def make_questions():
    qs=[{"image_id":i,"method":m,"qtype":t,"prompt":p,"correct":c,"img":url}
        for i,m,url,t,p,c in CARDS]
    random.shuffle(qs)
    for n,q in enumerate(qs,1):q["№"]=n
    return qs


if "questions" not in st.session_state:
    st.session_state.update(questions=make_questions(),
                            idx=0,name="",q_start=None)


if not st.session_state.name:
    st.markdown("""
    <div style="color:#111;">
      <h2>Добрый день!</h2>
      <p>Это исследование проводится для…<br>
         Данные будут использоваться в обобщенном и анонимизированном виде.</p>
      <p><strong>Тестирование необходимо проходить с компьютера</strong>, поскольку оно связано
         с вопросами визуализации изображений.</p>
      <ul>
        <li>Временное ограничение для ответа на каждый вопрос — <strong>30 секунд</strong></li>
        <li>Прохождение теста займет <strong>≈ 10–15 минут</strong></li>
      </ul>
    </div>""", unsafe_allow_html=True)
    uname=st.text_input("",placeholder="Фамилия / псевдоним",
                        key="username",label_visibility="collapsed")
    if st.button("🎲 Сгенерировать псевдоним"):
        st.session_state.name=f"Участник_{secrets.randbelow(900_000)+100_000}"; st.rerun()
    if uname: st.session_state.name=uname.strip(); st.rerun()
    st.stop()


i,qs=st.session_state.idx,st.session_state.questions
if i<len(qs):
    
    st_autorefresh(interval=1000, limit=TIME_LIMIT+2, key="t")

    q=qs[i]
    if st.session_state.q_start is None:
        st.session_state.q_start=time.time()
    elapsed=time.time()-st.session_state.q_start
    left=max(math.ceil(TIME_LIMIT-elapsed),0)

    
    if elapsed>=TIME_LIMIT:
        ans_val=st.session_state.get(f"ans{i}","")
        ok=str(ans_val).strip().lower()==str(q["correct"]).lower()
        ms=TIME_LIMIT*1000
        log_q.put([datetime.datetime.utcnow().isoformat(),st.session_state.name,
                   q["№"],q["image_id"],q["method"],q["qtype"],
                   q["prompt"],ans_val,q["correct"],ms,ok])
        q.update({"ответ":ans_val if ans_val else "—","время, мс":f"{ms:,}",
                  "✓":"✅" if ok else "❌"})
        st.session_state.idx+=1; st.session_state.q_start=None
        st.experimental_rerun()

    components.html(f"""
    <div style="display:flex;gap:16px;height:70px">
      <div style="position:relative;width:70px;height:70px">
        <svg width="70" height="70">
          <circle cx="35" cy="35" r="26" stroke="#444" stroke-width="6" fill="none"/>
          <circle id="arc" cx="35" cy="35" r="26" stroke="#52b788" stroke-width="6"
                  fill="none" stroke-dasharray="163.3628" stroke-dashoffset="0"
                  transform="rotate(-90 35 35)"/>
        </svg>
        <span id="txt" style="position:absolute;top:50%;left:50%;
              transform:translate(-50%,-50%);font:700 1.2rem sans-serif;color:#52b788">{left}</span>
      </div>
    </div>
    <script>
      const limit={TIME_LIMIT},start=Date.now()/1000-{elapsed:.3f},
            arc=document.getElementById('arc'),txt=document.getElementById('txt');
      function tick(){{
        const l=Math.max(0,Math.ceil(limit-(Date.now()/1000-start)));
        txt.textContent=l;
        if(l<=5){{arc.setAttribute('stroke','#e63946');txt.style.color='#e63946';}}
        arc.setAttribute('stroke-dashoffset',163.3628*(l/limit));
        setTimeout(tick,250);
      }} tick();
    </script>
    """,height=80)

    st.markdown(f"### Вопрос №{q['№']}")
    st.image(q["img"],clamp=True)

    if q["qtype"]=="contrast":
        _=st.number_input(q["prompt"],key=f"ans{i}",min_value=0, step=1, format="%d", placeholder="Введите число")
    else:
        _=st.radio(q["prompt"],["да","нет"],key=f"ans{i}",horizontal=True, index = None)

    if st.button("Далее"):
        ans=st.session_state.get(f"ans{i}","")
        ms=int((time.time()-st.session_state.q_start)*1000)
        ok=str(ans).strip().lower()==str(q["correct"]).lower()
        log_q.put([datetime.datetime.utcnow().isoformat(),st.session_state.name,
                   q["№"],q["image_id"],q["method"],q["qtype"],
                   q["prompt"],ans,q["correct"],ms,ok])
        q.update({"ответ":ans if ans else "—","время, с":f"{ms:,}",
                  "✓":"✅" if ok else "❌"})
        st.session_state.idx+=1; st.session_state.q_start=None
        st.experimental_rerun()

else:
    st.success(f"Готово, {st.session_state.name}!"); st.balloons()
    cols=["№","image_id","method","qtype","prompt",
          "ответ","правильный","время, мс","✓"]
    rows=[cols]+[[str(q.get(c,"")) for c in cols] for q in st.session_state.questions]
    table="""<div style="margin-top:30px;background:#606060;border-radius:12px;padding:20px;">
      <h4 style="color:#fff!important;margin-bottom:15px;">Результаты тестирования</h4>
      <table style="width:100%;border-collapse:collapse;color:#fff;">
      <thead><tr style="border-bottom:1px solid #555;">"""+\
      "".join(f'<th style="padding:10px;text-align:left;">{c}</th>' for c in cols)+\
      "</tr></thead><tbody>"
    for r in rows[1:]:
        table+='<tr style="border-bottom:1px solid #444;">'
        for j,c in enumerate(r):
            if j==len(r)-1:
                table+=f'<td style="padding:10px;color:{"#52b788" if c=="✅" else "#e63946"}">{c}</td>'
            else:
                table+=f'<td style="padding:10px">{c}</td>'
        table+="</tr>"
    st.markdown(table+"</tbody></table></div>",unsafe_allow_html=True)
