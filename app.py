import os, sqlite3, hashlib, hmac, secrets, csv, io, time, json, re
from urllib.request import Request as HttpRequest, urlopen
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from starlette.middleware.sessions import SessionMiddleware
from html import escape

BASE=Path(__file__).parent
DB=Path(os.getenv('DATABASE_PATH',str(BASE/'meddigital.db')))
PRODUCTION=os.getenv('APP_ENV')=='production'
if PRODUCTION and (len(os.getenv('SESSION_SECRET',''))<32 or os.getenv('HTTPS_ONLY')!='1'):
 raise RuntimeError('Production requires SESSION_SECRET (32+ chars) and HTTPS_ONLY=1')
app=FastAPI(title='MedDigital AI — учебный прототип')
LOGIN_ATTEMPTS={}
app.add_middleware(SessionMiddleware, secret_key=os.getenv('SESSION_SECRET') or secrets.token_urlsafe(48), https_only=os.getenv('HTTPS_ONLY')=='1', same_site='lax')

def conn():
 DB.parent.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(DB,timeout=15); c.row_factory=sqlite3.Row; return c

def hash_pw(p, salt=None):
 salt=salt or secrets.token_hex(16)
 return salt+'$'+hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(salt),250000).hex()

def verify(p, stored):
 try:
  salt,_=stored.split('$'); return hmac.compare_digest(hash_pw(p,salt),stored)
 except Exception:return False

def init():
 with conn() as c:
  c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, group_name TEXT)')
  c.execute('CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY, user_id INTEGER, score INTEGER, feedback TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
  if not c.execute('SELECT id FROM users WHERE role="teacher"').fetchone() and os.getenv('TEACHER_PASSWORD') and len(os.getenv('TEACHER_PASSWORD',''))>=12:
   c.execute('INSERT INTO users(username,password,role,group_name) VALUES(?,?,?,?)',(os.getenv('TEACHER_USERNAME','teacher'),hash_pw(os.environ['TEACHER_PASSWORD']),'teacher',''))
  if not c.execute('SELECT id FROM users LIMIT 1').fetchone() and not PRODUCTION and os.getenv('SEED_DEMO')=='1':
   for username,role,group in [('teacher','teacher',''),('student101','student','101СД-26к'),('student102','student','102СД-26р')]:
    c.execute('INSERT INTO users(username,password,role,group_name) VALUES(?,?,?,?)',(username,hash_pw('Demo2026!'),role,group))
init()

STR={
 'ru':{'title':'Цифровые навыки будущей медсестры','login':'Войти','logout':'Выйти','username':'Логин','password':'Пароль','task':'Виртуальная больница','teacher':'Кабинет преподавателя','student':'Кабинет студента','submit':'Проверить задание','patient':'Учебная карта пациента','date':'Дата рождения (ДД.ММ.ГГГГ)','id':'Идентификатор пациента','privacy':'Можно ли отправить карту пациента в личный мессенджер?','no':'Нет, нельзя','yes':'Да, можно','feedback':'Обратная связь','progress':'История попыток','group':'Группа','score':'Баллы','welcome':'Учебный прототип: только вымышленные данные. Не используйте настоящие данные пациентов.','demo':'Демо-доступ: teacher / Demo2026! или student101 / Demo2026!','hint':'Тренажёр проверяет ответы по правилам. Подключение настоящего ИИ — следующий этап.','badlogin':'Неверный логин или пароль.'},
 'kk':{'title':'Болашақ мейіргердің цифрлық дағдылары','login':'Кіру','logout':'Шығу','username':'Логин','password':'Құпиясөз','task':'Виртуалды аурухана','teacher':'Оқытушы кабинеті','student':'Студент кабинеті','submit':'Тапсырманы тексеру','patient':'Оқу пациентінің картасы','date':'Туған күні (КК.АА.ЖЖЖЖ)','id':'Пациент идентификаторы','privacy':'Пациент картасын жеке мессенджерге жіберуге бола ма?','no':'Жоқ, болмайды','yes':'Иә, болады','feedback':'Кері байланыс','progress':'Әрекеттер тарихы','group':'Топ','score':'Ұпай','welcome':'Оқу прототипі: тек ойдан шығарылған деректер. Нақты пациенттердің деректерін енгізбеңіз.','demo':'Демо: teacher / Demo2026! немесе student101 / Demo2026!','hint':'Жауаптар ережелер бойынша тексеріледі. Нақты ЖИ келесі кезеңде қосылады.','badlogin':'Логин немесе құпиясөз қате.'}}

def csrf_token(request):
 if 'csrf' not in request.session:request.session['csrf']=secrets.token_urlsafe(32)
 return request.session['csrf']

def csrf_valid(request,value):
 return bool(value) and hmac.compare_digest(request.session.get('csrf',''),value)

def csrf_field(request):return f'<input type="hidden" name="csrf" value="{csrf_token(request)}">'

def page(request, content, lang='ru'):
 t=STR[lang]; user=request.session.get('user'); nav=f'<a href="/logout?csrf={csrf_token(request)}">{t["logout"]}</a>' if user else ''
 content=content.replace('<form action="/check" method="post">','<form action="/check" method="post">'+csrf_field(request)).replace('<form method="post" action="/students">','<form method="post" action="/students">'+csrf_field(request))
 return HTMLResponse(f'''<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MedDigital AI</title><style>body{{font-family:system-ui,Arial;background:#f1f8fa;color:#163548;margin:0}}header{{background:linear-gradient(110deg,#087d8b,#175d87);color:white;padding:26px max(24px,calc((100% - 940px)/2))}}header h1{{margin:0}}nav{{margin-top:12px}}a{{color:inherit;margin-right:15px}}main{{max-width:940px;margin:30px auto;padding:0 20px}}.card{{background:white;border-radius:16px;padding:24px;margin:18px 0;box-shadow:0 6px 25px #16354815}}input,select{{padding:12px;border:1px solid #bfd4db;border-radius:8px;display:block;width:100%;box-sizing:border-box;margin:8px 0 16px}}button{{border:0;border-radius:9px;background:#087d8b;color:white;padding:12px 20px;cursor:pointer}}.note{{color:#496775}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;border-bottom:1px solid #e4eef1;padding:10px}}.badge{{background:#e0f6f3;border-radius:6px;padding:5px 10px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:15px}}.grid .card{{margin:0}}button:hover{{background:#055c68}}.note{{background:#e9f7f6;padding:12px;border-radius:8px}}</style></head><body><header><h1>✚ MedDigital AI</h1><p>{t['title']}</p><nav><a href="/?lang=ru">Русский</a><a href="/?lang=kk">Қазақша</a>{nav}</nav></header><main>{content}<p class="note">© MedDigital AI · ВМК «Эмили» · Демонстрационный прототип</p></main></body></html>''')

def language(request):return 'kk' if request.query_params.get('lang')=='kk' or request.session.get('lang')=='kk' else 'ru'

@app.get('/',response_class=HTMLResponse)
def home(request:Request):
 lang=language(request);request.session['lang']=lang;t=STR[lang];u=request.session.get('user')
 if not u:
  content=f'''<section class="card"><h2>{t['login']}</h2><p>{t['welcome']}</p><form action="/login" method="post">{csrf_field(request)}<label>{t['username']}<input name="username" required autocomplete="username"></label><label>{t['password']}<input name="password" type="password" required autocomplete="current-password"></label><button>{t['login']}</button></form><p class="note">{t['demo'] if not PRODUCTION else ''}</p></section>'''
 else:
  content=teacher_content(lang) if u['role']=='teacher' else student_content(u,lang)
 return page(request,content,lang)

@app.post('/login')
def login(request:Request,username:str=Form(...),password:str=Form(...),csrf:str=Form("")):
 if not csrf_valid(request,csrf):return page(request,'Сессия устарела. Обновите страницу.',language(request))
 key=(request.client.host if request.client else 'unknown',username.lower())
 now=time.monotonic();attempts=[t for t in LOGIN_ATTEMPTS.get(key,[]) if now-t<900]
 if len(attempts)>=8:return page(request,'Слишком много попыток входа. Повторите через 15 минут.',language(request))
 with conn() as c: row=c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
 if not row or not verify(password,row['password']):
  LOGIN_ATTEMPTS[key]=attempts+[now]
  return page(request,f'<section class="card">{STR[language(request)]["badlogin"]} <a href="/">↩</a></section>',language(request))
 LOGIN_ATTEMPTS.pop(key,None)
 request.session.clear()
 request.session['user']={'id':row['id'],'username':row['username'],'role':row['role'],'group':row['group_name']}
 return RedirectResponse('/',status_code=303)

@app.get('/logout')
def logout(request:Request,csrf:str=''):
 if not csrf_valid(request,csrf):return RedirectResponse('/',status_code=303)
 request.session.clear();return RedirectResponse('/',status_code=303)

def student_content(u,lang):
 t=STR[lang]
 with conn() as c:rows=c.execute('SELECT score,feedback,created_at FROM results WHERE user_id=? ORDER BY id DESC LIMIT 10',(u['id'],)).fetchall()
 history=''.join(f'<tr><td>{escape(r["created_at"])}</td><td>{r["score"]}/100</td><td>{escape(r["feedback"])}</td></tr>' for r in rows) or '<tr><td colspan="3">—</td></tr>'
 return f'''<section class="card"><h2>{t['student']}: {escape(u['username'])}</h2><p>{t['group']}: <span class="badge">{escape(u['group'])}</span></p><p>{t['welcome']}</p></section><section class="card"><h2>🏥 {t['patient']}</h2><p class="note">{t['hint']}</p><p><b>Ситуация:</b> учебный пациент P-104, дата рождения 12.04.2004. Заполните карту без персональных данных реальных людей.</p><form action="/check" method="post"><label>{t['id']}<input name="patient_id" placeholder="P-104" required maxlength="20"></label><label>{t['date']}<input name="dob" placeholder="12.04.2004" required maxlength="20"></label><label>{t['privacy']}<select name="privacy"><option value="no">{t['no']}</option><option value="yes">{t['yes']}</option></select></label><button>{t['submit']}</button></form></section><div class="grid"><section class="card"><h3>🔐 {'Құпиялылық' if lang=='kk' else 'Защита данных'}</h3><p>{'Оқу жағдайларын талдаңыз' if lang=='kk' else 'Решите задачи о конфиденциальности'}</p><a href="/lesson/privacy">{'Бастау' if lang=='kk' else 'Начать'} →</a></section><section class="card"><h3>📊 Excel</h3><p>{'Орташа мәндерді есептеңіз' if lang=='kk' else 'Рассчитайте средние значения'}</p><a href="/lesson/excel">{'Бастау' if lang=='kk' else 'Начать'} →</a></section><section class="card"><h3>🤖 AI-наставник</h3><p>{'Оқу сұрағын қойыңыз' if lang=='kk' else 'Задайте учебный вопрос'}</p><a href="/mentor">{'Ашу' if lang=='kk' else 'Открыть'} →</a></section></div><section class="card"><h2>📈 {t['progress']}</h2><table><tr><th>Дата</th><th>{t['score']}</th><th>{t['feedback']}</th></tr>{history}</table></section>'''

def teacher_content(lang):
 t=STR[lang]
 with conn() as c: rows=c.execute('SELECT u.username,u.group_name,COUNT(r.id) attempts,MAX(r.score) best FROM users u LEFT JOIN results r ON r.user_id=u.id WHERE u.role="student" GROUP BY u.id ORDER BY u.username').fetchall()
 body=''.join(f'<tr><td>{escape(r["username"])}</td><td>{escape(r["group_name"])}</td><td>{r["attempts"]}</td><td>{r["best"] if r["best"] is not None else "—"}</td></tr>' for r in rows)
 return f'<section class="card"><h2>👩‍🏫 {t["teacher"]}</h2><p>{t["welcome"]}</p><table><tr><th>Студент</th><th>{t["group"]}</th><th>Попытки</th><th>Лучший результат</th></tr>{body}</table><p><a href="/export">⬇ CSV</a></p><h3>Добавить студента</h3><form method="post" action="/students"><label>Логин<input name="username" required pattern="[A-Za-z0-9_-]{3,32}"></label><label>Группа<input name="group_name" required maxlength="60"></label><label>Пароль (12+ символов)<input type="password" name="password" required minlength="12"></label><button>Создать</button></form></section>'

@app.post('/check')
def check(request:Request,patient_id:str=Form(...),dob:str=Form(...),privacy:str=Form(...),csrf:str=Form("")):
 u=request.session.get('user')
 if not u or u['role']!='student':return RedirectResponse('/',status_code=303)
 if not csrf_valid(request,csrf):return page(request,'Сессия устарела',language(request))
 lang=language(request);t=STR[lang]
 checks=[(patient_id.strip().upper()=='P-104', 'Идентификатор: P-104' if lang=='ru' else 'Идентификатор: P-104'),(dob.strip()=='12.04.2004','Дата: 12.04.2004' if lang=='ru' else 'Күні: 12.04.2004'),(privacy=='no','Нельзя передавать карту через личный мессенджер' if lang=='ru' else 'Картаны жеке мессенджер арқылы жіберуге болмайды')]
 score=round(sum(ok for ok,_ in checks)/3*100)
 feedback=('; '.join(msg for ok,msg in checks if not ok) or ('Все задания выполнены верно!' if lang=='ru' else 'Барлық тапсырма дұрыс орындалды!'))
 with conn() as c:c.execute('INSERT INTO results(user_id,score,feedback) VALUES(?,?,?)',(u['id'],score,feedback))
 return page(request,f'<section class="card"><h2>{t["feedback"]}</h2><h1>{score}/100</h1><p>{escape(feedback)}</p><p><a href="/">← {t["student"]}</a></p></section>',lang)


@app.post('/students')
def add_student(request:Request,username:str=Form(...),group_name:str=Form(...),password:str=Form(...),csrf:str=Form("")):
 u=request.session.get('user')
 if not u or u['role']!='teacher':return RedirectResponse('/',303)
 if not csrf_valid(request,csrf):return page(request,'Сессия устарела',language(request))
 if not (3<=len(username)<=32 and all(x.isascii() and (x.isalnum() or x in '_-') for x in username) and 1<=len(group_name)<=60 and len(password)>=12):
  return page(request,'<section class="card">Invalid student details. <a href="/">Back</a></section>',language(request))
 try:
  with conn() as c:c.execute('INSERT INTO users(username,password,role,group_name) VALUES(?,?,?,?)',(username,hash_pw(password),'student',group_name))
 except sqlite3.IntegrityError:return page(request,'<section class="card">Username already exists. <a href="/">Back</a></section>',language(request))
 return RedirectResponse('/',303)

@app.get('/export')
def export(request:Request):
 u=request.session.get('user')
 if not u or u['role']!='teacher':return RedirectResponse('/',303)
 with conn() as c:rows=c.execute('SELECT u.username,u.group_name,r.score,r.feedback,r.created_at FROM results r JOIN users u ON r.user_id=u.id ORDER BY r.id DESC').fetchall()
 output=io.StringIO();w=csv.writer(output);w.writerow(['student','group','score','feedback','date'])
 for r in rows:w.writerow([r[k] for k in ('username','group_name','score','feedback','created_at')])
 return StreamingResponse(iter(["\ufeff"+output.getvalue()]),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="meddigital-results.csv"'})


@app.get('/health')
def health():return {'status':'ok'}

@app.get('/lesson/{kind}')
def lesson(request:Request,kind:str):
 u=request.session.get('user')
 if not u or u['role']!='student':return RedirectResponse('/',303)
 lang=language(request)
 if kind=='privacy':
  intro='Выберите безопасные действия с данными пациента.' if lang=='ru' else 'Пациент деректерімен қауіпсіз әрекеттерді таңдаңыз.'
  questions=[('Можно ли переслать карту пациента в личный чат?','Жеке чатқа пациент картасын жіберуге бола ма?'),('Нужно ли блокировать компьютер при уходе?','Кеткенде компьютерді бұғаттау керек пе?'),('Можно ли делиться паролем с одногруппниками?','Құпиясөзді топтастармен бөлісуге бола ма?')]
  options=[('no','Нет / Жоқ'),('yes','Да / Иә')]
 elif kind=='excel':
  intro='Учебные значения: 110, 120, 130. Найдите среднее и максимум.' if lang=='ru' else 'Оқу мәндері: 110, 120, 130. Орташа және ең үлкен мәнді табыңыз.'
  questions=[('Среднее значение','Орташа мән'),('Максимальное значение','Ең үлкен мән'),('Функция среднего в Excel (английский интерфейс)','Excel орташа функциясы (ағылшынша)')]
 else:return RedirectResponse('/',303)
 fields=''
 for i,(ru,kk) in enumerate(questions):
  label=ru if lang=='ru' else kk
  if kind=='privacy':fields+=f'<label>{escape(label)}<select name="a{i}">'+''.join(f'<option value="{v}">{escape(t)}</option>' for v,t in options)+'</select></label>'
  else:fields+=f'<label>{escape(label)}<input name="a{i}" required maxlength="25"></label>'
 return page(request,f'<section class="card"><h2>{"🔐" if kind=="privacy" else "📊"} {"Защита данных" if kind=="privacy" else "Excel"}</h2><p>{intro}</p><form method="post" action="/lesson/{kind}">{csrf_field(request)}{fields}<button>{STR[lang]["submit"]}</button></form></section>',lang)

@app.post('/lesson/{kind}')
def grade_lesson(request:Request,kind:str,a0:str=Form(...),a1:str=Form(...),a2:str=Form(...),csrf:str=Form('')):
 u=request.session.get('user')
 if not u or u['role']!='student':return RedirectResponse('/',303)
 lang=language(request)
 if not csrf_valid(request,csrf):return page(request,'Сессия устарела',lang)
 if kind=='privacy':checks=[a0=='no',a1=='yes',a2=='no'];explanations=['Нельзя пересылать медицинские документы в личные чаты.','Рабочее устройство необходимо блокировать.','Пароль нельзя передавать другим людям.']
 elif kind=='excel':checks=[a0.strip()=='120',a1.strip()=='130',a2.strip().upper().replace('=','')=='AVERAGE'];explanations=['Среднее (110+120+130)/3 = 120.','Максимальное значение 130.','Функция AVERAGE вычисляет среднее.']
 else:return RedirectResponse('/',303)
 score=round(sum(checks)/3*100);feedback='; '.join(explanations[i] for i,ok in enumerate(checks) if not ok) or ('Отлично! Все ответы верны.' if lang=='ru' else 'Тамаша! Барлық жауап дұрыс.')
 with conn() as c:c.execute('INSERT INTO results(user_id,score,feedback) VALUES(?,?,?)',(u['id'],score,kind+': '+feedback))
 return page(request,f'<section class="card"><h2>{STR[lang]["feedback"]}</h2><h1>{score}/100</h1><p>{escape(feedback)}</p><a href="/">←</a></section>',lang)

@app.get('/mentor')
def mentor(request:Request):
 u=request.session.get('user')
 if not u or u['role']!='student':return RedirectResponse('/',303)
 lang=language(request)
 label='Спросите об Excel, защите данных или цифровой карте пациента' if lang=='ru' else 'Excel, деректерді қорғау немесе электрондық карта туралы сұраңыз'
 return page(request,f'<section class="card"><h2>🤖 AI-наставник</h2><p>{label}</p><form method="post" action="/mentor">{csrf_field(request)}<textarea name="question" rows="4" maxlength="500" required></textarea><button>{STR[lang]["submit"]}</button></form><p class="note">{("Без API-ключа наставник даёт только стандартные подсказки." if lang=="ru" else "API кілтінсіз тек стандартты кеңестер беріледі.")}</p></section>',lang)

@app.post('/mentor')
def mentor_answer(request:Request,question:str=Form(...),csrf:str=Form('')):
 u=request.session.get('user')
 if not u or u['role']!='student':return RedirectResponse('/',303)
 lang=language(request)
 if not csrf_valid(request,csrf):return page(request,'Сессия устарела',lang)
 question=question.strip()[:500]
 if not question:return RedirectResponse('/mentor',303)
 key=os.getenv('OPENAI_API_KEY','')
 answer=''
 if key:
  try:
   payload=json.dumps({'model':os.getenv('OPENAI_MODEL','gpt-4.1-mini'),'messages':[{'role':'system','content':'You are a bilingual Russian/Kazakh educational tutor for first-year nursing students learning digital literacy. Explain informatics, spreadsheets, privacy and fictional patient-record exercises. Do not diagnose or give medical treatment. Never ask for real patient data. Keep answers concise, safe and in the language of the question.'},{'role':'user','content':question}],'max_tokens':350}).encode()
   req=HttpRequest('https://api.openai.com/v1/chat/completions',data=payload,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
   with urlopen(req,timeout=12) as response:answer=json.load(response)['choices'][0]['message']['content']
  except Exception:answer=''
 if not answer:
  answer=('Для Excel используйте формулы AVERAGE, MAX и проверяйте типы данных. Никогда не отправляйте настоящие данные пациентов в учебный сервис.' if lang=='ru' else 'Excel-де AVERAGE, MAX формулаларын қолданыңыз. Нақты пациент деректерін оқу жүйесіне енгізбеңіз.')
  answer+=(' (Стандартная подсказка: ИИ сейчас недоступен.)' if lang=='ru' else ' (Стандартты кеңес: ЖИ қазір қолжетімсіз.)')
 return page(request,f'<section class="card"><h2>🤖 AI-наставник</h2><p><b>{escape(question)}</b></p><p>{escape(answer)}</p><a href="/mentor">←</a></section>',lang)
