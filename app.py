from __future__ import annotations
from streamlit_autorefresh import st_autorefresh
import random, time, datetime, secrets, threading, queue, re, itertools, math
from typing import List, Dict
import streamlit as st
import streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
from pathlib import Path
import atexit

MOBILE_QS_FLAG="mobile"
st.set_page_config(page_title="Визуализация многоканальных изображений",page_icon="🎯",layout="centered",initial_sidebar_state="collapsed")


if "initialized" not in st.session_state:
    st.session_state.update(
        initialized=True,
        questions=[],
        idx=0,
        name="",
        phase="intro",
        phase_start_time=None,
        pause_until=0,
        _timer_flags={},
        session_id=secrets.token_hex(8)  
    )


import sys
module = sys.modules[__name__]

if not hasattr(module, '_queues_initialized'):
    module._queues_initialized = True
    module.global_log_queue = queue.Queue(maxsize=1000) 
    module.batch_queue = queue.Queue(maxsize=1000)
    
    BATCH_SIZE = 5 
    BATCH_TIMEOUT = 3 
  
    BACKUP_DIR = Path("backup_results")
    BACKUP_DIR.mkdir(exist_ok=True)
    
    def save_to_backup(row):

        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = BACKUP_DIR / f"backup_{timestamp}_{secrets.token_hex(4)}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(row, f, ensure_ascii=False)
        except:
            pass
    
    def batch_writer():
     
        batch = []
        last_send = time.time()
        consecutive_errors = 0
        
        while True:
            try:
          
                timeout = 0.1 if batch else 1 
                row = module.batch_queue.get(timeout=timeout)
                batch.append(row)
                
                
                if len(batch) >= BATCH_SIZE or (time.time() - last_send > BATCH_TIMEOUT and batch):
                    sheet = get_sheet()
                    if sheet:
                        try:
                          
                            sheet.append_rows(batch, value_input_option="RAW", table_range="A1")
                            batch = []
                            last_send = time.time()
                            consecutive_errors = 0
                        except Exception as e:
                    
                            for r in batch:
                                save_to_backup(r)
                            batch = []
                            consecutive_errors += 1
                           
                            time.sleep(min(30, 2 ** consecutive_errors))
                    else:
                     
                        for r in batch:
                            save_to_backup(r)
                        batch = []
                        time.sleep(5)  
                        
            except queue.Empty:
      
                if batch and time.time() - last_send > BATCH_TIMEOUT:
                    sheet = get_sheet()
                    if sheet:
                        try:
                            sheet.append_rows(batch, value_input_option="RAW", table_range="A1")
                            consecutive_errors = 0
                        except:
                            for r in batch:
                                save_to_backup(r)
                            consecutive_errors += 1
                    else:
                        for r in batch:
                            save_to_backup(r)
                    batch = []
                    last_send = time.time()
            except Exception:
         
                time.sleep(1)
    
    def queue_processor():
       
        while True:
            try:
                row = module.global_log_queue.get(timeout=1)
             
                try:
                    module.batch_queue.put(row, timeout=1)
                except queue.Full:
                   
                    save_to_backup(row)
                module.global_log_queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                time.sleep(0.1)
    

    thread1 = threading.Thread(target=queue_processor, daemon=True, name="QueueProcessor")
    thread2 = threading.Thread(target=batch_writer, daemon=True, name="BatchWriter")
    thread1.start()
    thread2.start()


try:
    components.html("""
    <script>
    (function(){{
      try {{
        const flag='{flag}',isMobile=window.innerWidth<1024;
        if(isMobile)document.documentElement.classList.add('mobile-client');
        const qs=new URLSearchParams(window.location.search);
        if(isMobile&&!qs.has(flag)){{qs.set(flag,'1');window.location.search=qs.toString();}}
      }} catch(e) {{
        console.error('Mobile check error:', e);
      }}
    }})();
    </script>""".format(flag=MOBILE_QS_FLAG),height=0)
except Exception:
    pass

q=st.query_params if hasattr(st,"query_params") else st.experimental_get_query_params()
if q.get(MOBILE_QS_FLAG)==["1"]:
    st.markdown("""
    <style>
      body{background:#808080;color:#fff;text-align:center;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
      h2{margin:0 auto;line-height:1.4;font-size:1.3rem;font-weight:500;}
    </style>
    <h2>Уважаемый участник<br>Данное исследование доступно только с <strong>ПК или ноутбука</strong>.</h2>
    """,unsafe_allow_html=True)
    st.stop()

BASE_URL="https://storage.yandexcloud.net/test3123234442"
TIME_LIMIT=15

st.markdown("""
<style>
html,body,.stApp,[data-testid="stAppViewContainer"],.main,.block-container{background:#808080!important;color:#111!important;}
body{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;}
h1,h2,h3,h4,h5,h6{color:#111!important;}
header[data-testid="stHeader"]{display:none;}
.stButton>button{min-height:52px!important;padding:0 20px!important;border:1px solid #555!important;background:#222!important;color:#ddd!important;border-radius:8px;}
input[data-testid="stTextInput"]{height:52px!important;padding:0 16px!important;font-size:1.05rem;}
#mobile-overlay{position:fixed;inset:0;z-index:2147483647;display:none;align-items:center;justify-content:center;color:#fff;font:500 1.2rem/1.5 sans-serif;text-align:center;padding:0 20px;background:#808080;}
@media(max-width:1023px){#mobile-overlay{display:flex;}.block-container>.element-container:nth-child(n+2){display:none!important;}html,body{overflow:hidden!important;height:100%!important;}}
.stApp>div{-webkit-backface-visibility:hidden;backface-visibility:hidden;transition:opacity .1s ease-in-out;}
</style>
<div id="mobile-overlay">Уважаемый&nbsp;участник,<br>данное&nbsp;исследование доступно для прохождения только с&nbsp;ПК или&nbsp;ноутбука.</div>
""",unsafe_allow_html=True)

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

@st.cache_resource(show_spinner="Подключение…")
def get_sheet():

    max_retries = 3
    for attempt in range(max_retries):
        try:
            scopes=["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
            gc=gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gsp"]),scopes))
            sheet = gc.open("human_study_results").sheet1
            return sheet
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt) 
                continue
            else:
                return None

GROUPS=["img1_dif_corners","img2_dif_corners","img3_same_corners_no_symb","img4_same_corners","img5_same_corners"]
ALGS=["pca_rgb_result","socolov_lab_result","socolov_rgb_result","umap_rgb_result"]
CORNER={"img1_dif_corners":"нет","img2_dif_corners":"нет","img3_same_corners_no_symb":"да","img4_same_corners":"да","img5_same_corners":"да"}
LETTER={"img1_dif_corners":"ж","img2_dif_corners":"фя","img3_same_corners_no_symb":"Не вижу","img4_same_corners":"аб","img5_same_corners":"юэы"}

def url(g:str,a:str)->str:return f"{BASE_URL}/{g}_{a}.png"
def clean(s:str)->set[str]:return set(re.sub(r"[ ,.;:-]+","",s.lower()))


@st.cache_data
def get_question_template():

    pg={g:[] for g in GROUPS}
    for g,a in itertools.product(GROUPS,ALGS):
        pg[g]+=[
            {"group":g,"alg":a,"img":url(g,a),"qtype":"corners","prompt":"Правый верхний и левый нижний угол — одного цвета?","correct":CORNER[g]},
            {"group":g,"alg":a,"img":url(g,a),"qtype":"letters","prompt":"Если на изображении вы видите буквы, то укажите, какие именно.","correct":LETTER[g]}
        ]
    return pg

def make_qs()->List[Dict]:

    pg = {}
    template = get_question_template()
    for k, v in template.items():
        pg[k] = [item.copy() for item in v] 
    
    for v in pg.values():
        random.shuffle(v)
    seq,prev=[],None
    while any(pg.values()):
        choices=[g for g in GROUPS if pg[g] and g!=prev] or [g for g in GROUPS if pg[g]]
        prev=random.choice(choices);seq.append(pg[prev].pop())
    for n,q in enumerate(seq,1):q["№"]=n
    return seq

if st.session_state.initialized and not st.session_state.questions:
    st.session_state.questions=make_qs()

if st.session_state.pause_until>time.time() and st.session_state.idx<len(st.session_state.questions):
    st.markdown("<div style='text-align:center;font-size:1.5rem;color:#fff;background:#262626;padding:20px;border-radius:12px;margin-top:50px;'>Переходим к следующему вопросу...</div>",unsafe_allow_html=True)
    stamp=int(st.session_state.pause_until)
    st_autorefresh(interval=500,key=f"pause_{stamp}")
    st.stop()

if not st.session_state.name:
    st.markdown("""
    <div style="color:#111;">
      <h2>Уважаемый участник,<br>добро пожаловать в эксперимент по изучению восприятия изображений.</h2>
      <p><b>Как проходит эксперимент</b><br>
      В ходе эксперимента вам нужно будет отвечать на простые вопросы об изображениях, которые вы увидите на экране. Всего вам предстоит ответить на <b>40</b> вопросов. Прохождение теста займет около 10-15 минут.</p>
      <p><b>Пожалуйста, проходите тест спокойно: исследование не направлено на оценку испытуемых. Оценивается работа алгоритмов, которые выдают картинки разного качества.</b></p>
      <p><b>Что это за изображения?</b><br>
      Изображения — результат работы разных методов. Ни одно из них не является «эталоном». Цель эксперимента — понять, какие методы обработки лучше сохраняют информацию.</p>
      <p><b>Важно</b><br>
      Эксперимент полностью анонимен. Проходить его следует <b>только на компьютере или ноутбуке</b>.</p>
      <p>Для начала теста введите любой псевдоним и нажмите Enter или нажмите «Сгенерировать псевдоним».</p>
    </div>""",unsafe_allow_html=True)
    u=st.text_input("",placeholder="Ваш псевдоним",key="username",label_visibility="collapsed")
    if st.button("🎲 Сгенерировать псевдоним"):
        st.session_state.name=f"Участник_{secrets.randbelow(900000)+100000}"
        st.rerun()
    if u:
        st.session_state.name=u.strip()
        st.rerun()
    st.stop()

def finish(a:str):
    q=st.session_state.questions[st.session_state.idx]
    t_ms=int((time.time()-st.session_state.phase_start_time)*1000) if st.session_state.phase_start_time else 0
    ok=(clean(a)==clean(q["correct"]) if q["qtype"]=="letters" else a.lower()==q["correct"].lower())
    
 
    try:
        module.global_log_queue.put([
            datetime.datetime.utcnow().isoformat(),
            st.session_state.name,
            q["№"],
            q["group"],
            q["alg"],
            q["qtype"],
            q["prompt"],
            a,
            q["correct"],
            t_ms,
            ok,
            st.session_state.session_id 
        ], timeout=1)
    except queue.Full:
     
        save_to_backup([
            datetime.datetime.utcnow().isoformat(),
            st.session_state.name,
            q["№"],
            q["group"],
            q["alg"],
            q["qtype"],
            q["prompt"],
            a,
            q["correct"],
            t_ms,
            ok,
            st.session_state.session_id
        ])
    
    st.session_state.update(idx=st.session_state.idx+1,phase="intro",phase_start_time=None,pause_until=time.time()+0.5)
    st.rerun()

qs,total=st.session_state.questions,len(st.session_state.questions)
idx=st.session_state.idx
if idx>=total:
    st.markdown("<div style='margin-top:50px;padding:40px;text-align:center;font-size:2rem;color:#fff;background:#262626;border-radius:12px;'>Вы завершили прохождение.<br><b>Спасибо за участие!</b></div>",unsafe_allow_html=True)
    st.balloons()
    st.stop()

cur=qs[idx]

if st.session_state.phase=="intro":
    txt_c="""Сейчас вы увидите изображение. Цель данного вопроса — посмотреть на диаметрально противоположные углы,
    <b>правый верхний и левый нижний</b>, и определить, окрашены ли они в один цвет.<br><br>Картинка будет доступна
    в течение <b>15&nbsp;секунд</b>. Время на ответ не ограничено."""
    txt_l="""Сейчас вы увидите изображение. Цель данного вопроса — определить, есть ли на представленной картинке
    <b>буквы русского алфавита</b>.<br><br>Найденные буквы необходимо ввести в текстовое поле: допускается разделение
    пробелами, запятыми и т.&nbsp;д., а также слитное написание.<br><br>На некоторых картинках букв нет — тогда
    нажмите кнопку <b>«Не вижу букв»</b>."""
    st.markdown(f"<div style='font-size:1.1rem;line-height:1.6;margin-bottom:30px;'>{txt_c if cur['qtype']=='corners' else txt_l}</div>",unsafe_allow_html=True)
    if st.button("Перейти к вопросу",key=f"go_{idx}"):
        st.session_state.update(phase="question",phase_start_time=None)
        st.rerun()
    st.stop()

if st.session_state.phase_start_time is None:
    st.session_state.phase_start_time=time.time()
elapsed=time.time()-st.session_state.phase_start_time
remaining=max(0,TIME_LIMIT-elapsed)

st.markdown(f"### Вопрос №{cur['№']} из {total}")
render_timer(math.ceil(remaining),f"{idx}")

with st.container():
    if remaining>0:
        components.html(f"""
        <div id="img_{idx}" style="text-align:left;margin:5px 0;">
          <img src="{cur['img']}" width="300" style="border:1px solid #444;border-radius:8px;">
        </div>
        <script>
          setTimeout(()=>{{const c=document.getElementById('img_{idx}');
            if(c)c.innerHTML='<div style="font-style:italic;color:#666;padding:20px 0;">Время показа изображения истекло.</div>';}},
            {TIME_LIMIT*1000});
        </script>""",height=310)
    else:
        st.markdown("<div style='text-align:left;font-style:italic;color:#666;padding:40px 0;'>Время показа изображения истекло.</div>",unsafe_allow_html=True)

st.markdown("---")

if cur["qtype"]=="corners":
    sel=st.radio(cur["prompt"],["Да, углы одного цвета.","Нет, углы окрашены в разные цвета.","Затрудняюсь ответить."],index=None,key=f"r_{idx}")
    if sel:
        finish("да" if sel.startswith("Да") else "нет" if sel.startswith("Нет") else "затрудняюсь")
else:
    txt=st.text_input(cur["prompt"],key=f"t_{idx}",placeholder="Введите русские буквы и нажмите Enter")
    col1,_=st.columns([1,3])
    with col1:
        if st.button("Не вижу букв",key=f"s_{idx}"):
            finish("Не вижу")
    if txt:
        if re.fullmatch(r"[А-Яа-яЁё ,.;:-]+",txt):
            finish(txt.strip())
        else:
            st.error("Допустимы только русские буквы и знаки пунктуации.")


def restore_backups():
   
    BACKUP_DIR = Path("backup_results")
    if BACKUP_DIR.exists():
        sheet = get_sheet()
        if not sheet:
            print("Нет подключения к Google Sheets")
            return
        
        files = sorted(BACKUP_DIR.glob("backup_*.json"))
        rows = []
        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    rows.append(json.load(file))
            except:
                pass
        
        if rows:
            try:
                sheet.append_rows(rows, value_input_option="RAW")
                print(f"Восстановлено {len(rows)} записей")
                for f in files:
                    f.unlink()
            except Exception as e:
                print(f"Ошибка: {e}")
