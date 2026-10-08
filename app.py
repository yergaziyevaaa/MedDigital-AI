import os, sqlite3, hashlib, hmac, secrets
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from html import escape

BASE=Path(__file__).parent
DB=BASE/'meddigital.db'
app=FastAPI(title='MedDigital AI — учебный прототип')
app.add_middleware(SessionMiddleware, secret_key=os.getenv('SESSION_SECRET', 'CHANGE_THIS_SECRET_BEFORE_DEPLOYMENT'), https_only=os.getenv('HTTPS_ONLY')=='1', same_site='lax')

def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

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
  if not c.execute('SELECT id FROM users LIMIT 1').fetchone():
   for username,role,group in [('teacher','teacher',''),('student101','student','101СД-26к'),('student102','student','102СД-26р')]:
    c.execute('INSERT INTO users(username,password,role,group_name) VALUES(?,?,?,?)',(username,hash_pw('Demo2026!'),role,group))
init()

STR={
 'ru':{'title':'Цифровые навыки будущей медсестры','login':'Войти','logout':'Выйти','username':'Логин','password':'Пароль','task':'Виртуальная больница','teacher':'Кабинет преподавателя','student':'Кабинет студента','submit':'Проверить задание','patient':'Учебная карта пациента','date':'Дата рождения (ДД.ММ.ГГГГ)','id':'Идентификатор пациента','privacy':'Можно ли отправить карту пациента в личный мессенджер?','no':'Нет, нельзя','yes':'Да, можно','feedback':'Обратная связь','progress':'История попыток','group':'Группа','score':'Баллы','welcome':'Учебный прототип: только вымышленные данные. Не используйте настоящие данные пациентов.','demo':'Демо-доступ: teacher / Demo2026! или student101 / Demo2026!','hint':'Тренажёр проверяет ответы по правилам. Подключение настоящего ИИ — следующий этап.','badlogin':'Неверный логин или пароль.'},
 'kk':{'title':'Болашақ мейіргердің цифрлық дағдылары','login':'Кіру','logout':'Шығу','username':'Логин','password':'Құпиясөз','task':'Виртуалды аурухана','teacher':'Оқытушы кабинеті','student':'Студент кабинеті','submit':'Тапсырманы тексеру','patient':'Оқу пациентінің картасы','date':'Туған күні (КК.АА.ЖЖЖЖ)','id':'Пациент идентификаторы','privacy':'Пациент картасын жеке мессенджерге жіберуге бола ма?','no':'Жоқ, болмайды','yes':'Иә, болады','feedback':'Кері байланыс','progress':'Әрекеттер тарихы','group':'Топ','score':'Ұпай','welcome':'Оқу прототипі: тек ойдан шығарылған деректер. Нақты пациенттердің деректерін енгізбеңіз.','demo':'Демо: teacher / Demo2026! немесе student101 / Demo2026!','hint':'Жауаптар ережелер бойынша тексеріледі. Нақты ЖИ келесі кезеңде қосылады.','badlogin':'Логин немесе құпиясөз қате.'}}

def page(request, content, lang='ru'):
 t=STR[lang]; user=request.session.get('user'); nav=f'<a href="/logout">{t["logout"]}</a>' if user else ''
 return HTMLResponse(f'''<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MedDigital AI</title><style>body{{font-family:system-ui,Arial;background:#f1f8fa;color:#163548;margin:0}}header{{background:linear-gradient(110deg,#087d8b,#175d87);color:white;padding:26px max(24px,calc((100% - 940px)/2))}}header h1{{margin:0}}nav{{margin-top:12px}}a{{color:inherit;margin-right:15px}}main{{max-width:940px;margin:30px auto;padding:0 20px}}.card{{background:white;border-radius:16px;padding:24px;margin:18px 0;box-shadow:0 6px 25px #16354815}}input,select{{padding:12px;border:1px solid #bfd4db;border-radius:8px;display:block;width:100%;box-sizing:border-box;margin:8px 0 16px}}button{{border:0;border-radius:9px;background:#087d8b;color:white;padding:12px 20px;cursor:pointer}}.note{{color:#496775}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;border-bottom:1px solid #e4eef1;padding:10px}}.badge{{background:#e0f6f3;border-radius:6px;padding:5px 10px}}</style></head><body><header><h1>✚ MedDigital AI</h1><p>{t['title']}</p><nav><a href="/?lang=ru">Русский</a><a href="/?lang=kk">Қазақша</a>{nav}</nav></header><main>{content}<p class="note">© MedDigital AI · ВМК «Эмили» · Демонстрационный прототип</p></main></body></html>''')

def language(request):return 'kk' if request.query_params.get('lang')=='kk' or request.session.get('lang')=='kk' else 'ru'

@app.get('/',response_class=HTMLResponse)
def home(request:Request):
 lang=language(request);request.session['lang']=lang;t=STR[lang];u=request.session.get('user')
 if not u:
  content=f'''<section class="card"><h2>{t['login']}</h2><p>{t['welcome']}</p><form action="/login" method="post"><label>{t['username']}<input name="username" required autocomplete="username"></label><label>{t['password']}<input name="password" type="password" required autocomplete="current-password"></label><button>{t['login']}</button></form><p class="note">{t['demo']}</p></section>'''
 else:
  content=teacher_content(lang) if u['role']=='teacher' else student_content(u,lang)
 return page(request,content,lang)

@app.post('/login')
def login(request:Request,username:str=Form(...),password:str=Form(...)):
 with conn() as c: row=c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
 if not row or not verify(password,row['password']):
  return page(request,f'<section class="card">{STR[language(request)]["badlogin"]} <a href="/">↩</a></section>',language(request))
 request.session['user']={'id':row['id'],'username':row['username'],'role':row['role'],'group':row['group_name']}
 return RedirectResponse('/',status_code=303)

@app.get('/logout')
def logout(request:Request):request.session.clear();return RedirectResponse('/',status_code=303)

def student_content(u,lang):
 t=STR[lang]
 with conn() as c:rows=c.execute('SELECT score,feedback,created_at FROM results WHERE user_id=? ORDER BY id DESC LIMIT 10',(u['id'],)).fetchall()
 history=''.join(f'<tr><td>{escape(r["created_at"])}</td><td>{r["score"]}/100</td><td>{escape(r["feedback"])}</td></tr>' for r in rows) or '<tr><td colspan="3">—</td></tr>'
 return f'''<section class="card"><h2>{t['student']}: {escape(u['username'])}</h2><p>{t['group']}: <span class="badge">{escape(u['group'])}</span></p><p>{t['welcome']}</p></section><section class="card"><h2>🏥 {t['patient']}</h2><p class="note">{t['hint']}</p><p><b>Ситуация:</b> учебный пациент P-104, дата рождения 12.04.2004. Заполните карту без персональных данных реальных людей.</p><form action="/check" method="post"><label>{t['id']}<input name="patient_id" placeholder="P-104" required maxlength="20"></label><label>{t['date']}<input name="dob" placeholder="12.04.2004" required maxlength="20"></label><label>{t['privacy']}<select name="privacy"><option value="no">{t['no']}</option><option value="yes">{t['yes']}</option></select></label><button>{t['submit']}</button></form></section><section class="card"><h2>📈 {t['progress']}</h2><table><tr><th>Дата</th><th>{t['score']}</th><th>{t['feedback']}</th></tr>{history}</table></section>'''

def teacher_content(lang):
 t=STR[lang]
 with conn() as c: rows=c.execute('SELECT u.username,u.group_name,COUNT(r.id) attempts,MAX(r.score) best FROM users u LEFT JOIN results r ON r.user_id=u.id WHERE u.role="student" GROUP BY u.id ORDER BY u.username').fetchall()
 body=''.join(f'<tr><td>{escape(r["username"])}</td><td>{escape(r["group_name"])}</td><td>{r["attempts"]}</td><td>{r["best"] if r["best"] is not None else "—"}</td></tr>' for r in rows)
 return f'<section class="card"><h2>👩‍🏫 {t["teacher"]}</h2><p>{t["welcome"]}</p><table><tr><th>Студент</th><th>{t["group"]}</th><th>Попытки</th><th>Лучший результат</th></tr>{body}</table><p class="note">Это демоверсия: создание аккаунтов и экспорт Excel добавляются на следующем этапе.</p></section>'

@app.post('/check')
def check(request:Request,patient_id:str=Form(...),dob:str=Form(...),privacy:str=Form(...)):
 u=request.session.get('user')
 if not u or u['role']!='student':return RedirectResponse('/',status_code=303)
 lang=language(request);t=STR[lang]
 checks=[(patient_id.strip().upper()=='P-104', 'Идентификатор: P-104' if lang=='ru' else 'Идентификатор: P-104'),(dob.strip()=='12.04.2004','Дата: 12.04.2004' if lang=='ru' else 'Күні: 12.04.2004'),(privacy=='no','Нельзя передавать карту через личный мессенджер' if lang=='ru' else 'Картаны жеке мессенджер арқылы жіберуге болмайды')]
 score=round(sum(ok for ok,_ in checks)/3*100)
 feedback=('; '.join(msg for ok,msg in checks if not ok) or ('Все задания выполнены верно!' if lang=='ru' else 'Барлық тапсырма дұрыс орындалды!'))
 with conn() as c:c.execute('INSERT INTO results(user_id,score,feedback) VALUES(?,?,?)',(u['id'],score,feedback))
 return page(request,f'<section class="card"><h2>{t["feedback"]}</h2><h1>{score}/100</h1><p>{escape(feedback)}</p><p><a href="/">← {t["student"]}</a></p></section>',lang)
