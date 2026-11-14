import os, sqlite3, secrets
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field

load_dotenv()
APP_NAME = os.getenv("APP_NAME", "Soares Reserva AI")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))
DB_PATH = os.getenv("DATABASE_PATH", "./soares_reserva.db")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
AI_PRO_MODEL = os.getenv("AI_PRO_MODEL", AI_MODEL)
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.8"))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
ACTIVITY_AGENT_TOKEN = os.getenv("ACTIVITY_AGENT_TOKEN", "").strip()
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
EMAIL_FROM = os.getenv("EMAIL_FROM", "Soares AI <no-reply@soaresdev.com>").strip()
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://soares-reserva-ai-site.onrender.com").rstrip("/")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title=APP_NAME, version="1.0.0")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins or ["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

def db():
    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if DATABASE_URL:
        with db() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS users(
              id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'hel', created_at TIMESTAMPTZ NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS messages(
              id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id), role TEXT NOT NULL,
              content TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS memories(
              id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id), content TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS activity(
              id INTEGER PRIMARY KEY CHECK(id=1), is_playing BOOLEAN NOT NULL DEFAULT FALSE,
              game TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'manual',
              updated_at TIMESTAMPTZ NOT NULL)""")
            c.execute("INSERT INTO activity(id,is_playing,game,source,updated_at) VALUES(1,FALSE,'','manual',NOW()) ON CONFLICT (id) DO NOTHING")
    else:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        with db() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS users(
              id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'hel', created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages(
              id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, role TEXT NOT NULL,
              content TEXT NOT NULL, created_at TEXT NOT NULL,
              FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS memories(
              id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, content TEXT NOT NULL,
              created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS activity(
              id INTEGER PRIMARY KEY CHECK(id=1), is_playing INTEGER NOT NULL DEFAULT 0,
              game TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'manual',
              updated_at TEXT NOT NULL
            );
            INSERT OR IGNORE INTO activity(id,is_playing,game,source,updated_at)
            VALUES(1,0,'','manual',datetime('now'));
            """)
init_db()

def migrate_schema():
    with db() as c:
        if DATABASE_URL:
            c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT TRUE")
            c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'pro'")
            c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub TEXT")
            c.execute("""CREATE TABLE IF NOT EXISTS email_verifications(id BIGSERIAL PRIMARY KEY,email TEXT NOT NULL,code_hash TEXT NOT NULL,expires_at TIMESTAMPTZ NOT NULL,created_at TIMESTAMPTZ NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS conversations(id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,title TEXT NOT NULL DEFAULT 'Nova conversa',created_at TIMESTAMPTZ NOT NULL,updated_at TIMESTAMPTZ NOT NULL)""")
            c.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS conversation_id BIGINT REFERENCES conversations(id) ON DELETE CASCADE")
            c.execute("""INSERT INTO conversations(user_id,title,created_at,updated_at) SELECT u.id,'Histórico anterior',NOW(),NOW() FROM users u WHERE EXISTS(SELECT 1 FROM messages m WHERE m.user_id=u.id AND m.conversation_id IS NULL) AND NOT EXISTS(SELECT 1 FROM conversations v WHERE v.user_id=u.id)""")
            c.execute("""UPDATE messages m SET conversation_id=(SELECT v.id FROM conversations v WHERE v.user_id=m.user_id ORDER BY v.id LIMIT 1) WHERE m.conversation_id IS NULL""")
        else:
            cols={r["name"] for r in c.execute("PRAGMA table_info(users)").fetchall()}
            if "email_verified" not in cols: c.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")
            if "plan" not in cols: c.execute("ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'pro'")
            if "google_sub" not in cols: c.execute("ALTER TABLE users ADD COLUMN google_sub TEXT")
            mcols={r["name"] for r in c.execute("PRAGMA table_info(messages)").fetchall()}
            if "conversation_id" not in mcols: c.execute("ALTER TABLE messages ADD COLUMN conversation_id INTEGER")
            c.execute("""CREATE TABLE IF NOT EXISTS email_verifications(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT NOT NULL,code_hash TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,title TEXT NOT NULL DEFAULT 'Nova conversa',created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
            c.execute("""INSERT INTO conversations(user_id,title,created_at,updated_at) SELECT u.id,'Histórico anterior',datetime('now'),datetime('now') FROM users u WHERE EXISTS(SELECT 1 FROM messages m WHERE m.user_id=u.id AND m.conversation_id IS NULL) AND NOT EXISTS(SELECT 1 FROM conversations v WHERE v.user_id=u.id)""")
            c.execute("""UPDATE messages SET conversation_id=(SELECT v.id FROM conversations v WHERE v.user_id=messages.user_id ORDER BY v.id LIMIT 1) WHERE conversation_id IS NULL""")
migrate_schema()

def now():
    return datetime.now(timezone.utc).isoformat()

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class VerifyEmailIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6,max_length=6)

class ResendCodeIn(BaseModel):
    email: EmailStr

class GoogleLoginIn(BaseModel):
    credential: str = Field(min_length=20,max_length=10000)

class ProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)

class ChatIn(BaseModel):
    message: str = Field(default="", max_length=12000)
    conversation_id: Optional[int] = None
    image_data: Optional[str] = Field(default=None, max_length=7000000)

class ActivityIn(BaseModel):
    is_playing: bool
    game: str = Field(default="", max_length=100)
    source: str = Field(default="manual", pattern="^(manual|automatic)$")

class MemoryIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

def make_token(user):
    payload = {"sub": str(user["id"]), "role": user["role"],
               "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def current_user(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Faça login para continuar.")
    token = authorization.split(" ", 1)[1]
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        uid = int(data["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(401, "Sessão inválida ou expirada.")
    with db() as c:
        user = c.execute("SELECT id,name,email,role,plan FROM users WHERE id=%s" if DATABASE_URL else "SELECT id,name,email,role,plan FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        raise HTTPException(401, "Conta não encontrada.")
    return dict(user)

@app.get("/health")
def health():
    return {"ok": True, "app": APP_NAME, "ai_configured": bool(AI_API_KEY)}

@app.post("/auth/register")
def register(data: RegisterIn):
    email = data.email.lower()
    with db() as c:
        count = c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        role = "admin" if count == 0 or (ADMIN_EMAIL and email == ADMIN_EMAIL) else "hel"
        try:
            if DATABASE_URL:
                uid = c.execute("INSERT INTO users(name,email,password_hash,role,created_at,email_verified,plan) VALUES(%s,%s,%s,%s,%s,TRUE,'pro') RETURNING id",
                    (data.name.strip(), email, pwd.hash(data.password), role, now())).fetchone()["id"]
                user = c.execute("SELECT id,name,email,role,plan FROM users WHERE id=%s", (uid,)).fetchone()
            else:
                uid = c.execute("INSERT INTO users(name,email,password_hash,role,created_at,email_verified,plan) VALUES(?,?,?,?,?,1,'pro')",
                    (data.name.strip(), email, pwd.hash(data.password), role, now())).lastrowid
                user = c.execute("SELECT id,name,email,role,plan FROM users WHERE id=?", (uid,)).fetchone()
        except (sqlite3.IntegrityError, psycopg.IntegrityError):
            raise HTTPException(409, "Este e-mail já possui cadastro.")
    public = dict(user)
    return {"token": make_token(public), "user": public, "message": "Conta criada com sucesso."}

@app.post("/auth/verify")
def verify_email(data: VerifyEmailIn):
    email=data.email.lower()
    with db() as c:
        row=c.execute("SELECT * FROM email_verifications WHERE email=%s ORDER BY id DESC LIMIT 1" if DATABASE_URL else "SELECT * FROM email_verifications WHERE email=? ORDER BY id DESC LIMIT 1",(email,)).fetchone()
        user=c.execute("SELECT id,name,email,role,plan FROM users WHERE email=%s" if DATABASE_URL else "SELECT id,name,email,role,plan FROM users WHERE email=?",(email,)).fetchone()
        expired=not row or row["expires_at"] < (datetime.now(timezone.utc) if DATABASE_URL else datetime.now(timezone.utc).isoformat())
        if expired or not user or not pwd.verify(data.code,row["code_hash"]): raise HTTPException(400,"Código inválido ou expirado. Solicite outro.")
        c.execute("UPDATE users SET email_verified=TRUE WHERE email=%s" if DATABASE_URL else "UPDATE users SET email_verified=1 WHERE email=?",(email,))
        c.execute("DELETE FROM email_verifications WHERE email=%s" if DATABASE_URL else "DELETE FROM email_verifications WHERE email=?",(email,))
    return {"token":make_token(user),"user":dict(user)}

@app.post("/auth/resend")
async def resend_code(data: ResendCodeIn):
    email=data.email.lower()
    with db() as c:
        user=c.execute("SELECT id FROM users WHERE email=%s" if DATABASE_URL else "SELECT id FROM users WHERE email=?",(email,)).fetchone()
    if not user: raise HTTPException(404,"Conta não encontrada.")
    code=f"{secrets.randbelow(1000000):06d}"; exp=datetime.now(timezone.utc)+timedelta(minutes=15)
    with db() as c:
        c.execute("DELETE FROM email_verifications WHERE email=%s" if DATABASE_URL else "DELETE FROM email_verifications WHERE email=?",(email,))
        c.execute("INSERT INTO email_verifications(email,code_hash,expires_at,created_at) VALUES(%s,%s,%s,%s)" if DATABASE_URL else "INSERT INTO email_verifications(email,code_hash,expires_at,created_at) VALUES(?,?,?,?)",(email,pwd.hash(code),exp if DATABASE_URL else exp.isoformat(),now()))
    if not RESEND_API_KEY: raise HTTPException(503,"Envio de e-mail não configurado.")
    async with httpx.AsyncClient(timeout=20) as client:
        r=await client.post("https://api.resend.com/emails",headers={"Authorization":f"Bearer {RESEND_API_KEY}"},json={"from":EMAIL_FROM,"to":[email],"subject":"Seu novo código — Soares AI","html":f"<p>Seu código: <strong style='font-size:28px'>{code}</strong></p><p>Expira em 15 minutos.</p>"})
    if r.status_code>=400: raise HTTPException(502,"Falha ao enviar o e-mail.")
    return {"ok":True}

@app.get("/auth/config")
def auth_config(): return {"google_client_id":GOOGLE_CLIENT_ID}

@app.post("/auth/google")
async def google_login(data: GoogleLoginIn):
    if not GOOGLE_CLIENT_ID: raise HTTPException(503,"Login Google ainda não foi configurado.")
    async with httpx.AsyncClient(timeout=20) as client:
        r=await client.get("https://oauth2.googleapis.com/tokeninfo",params={"id_token":data.credential})
    if r.status_code!=200: raise HTTPException(401,"Credencial Google inválida.")
    info=r.json()
    if info.get("aud")!=GOOGLE_CLIENT_ID or info.get("email_verified")!="true" or info.get("iss") not in ("accounts.google.com","https://accounts.google.com"): raise HTTPException(401,"Não foi possível validar sua conta Google.")
    email=info.get("email","").lower(); name=info.get("name") or email.split("@")[0]; sub=info.get("sub")
    with db() as c:
        user=c.execute("SELECT id,name,email,role,plan FROM users WHERE email=%s" if DATABASE_URL else "SELECT id,name,email,role,plan FROM users WHERE email=?",(email,)).fetchone()
        if user:
            c.execute("UPDATE users SET email_verified=TRUE,google_sub=%s WHERE id=%s" if DATABASE_URL else "UPDATE users SET email_verified=1,google_sub=? WHERE id=?",(sub,user["id"]))
        else:
            ph=pwd.hash(secrets.token_urlsafe(32))
            if DATABASE_URL:
                uid=c.execute("INSERT INTO users(name,email,password_hash,role,created_at,email_verified,plan,google_sub) VALUES(%s,%s,%s,'hel',%s,TRUE,'pro',%s) RETURNING id",(name,email,ph,now(),sub)).fetchone()["id"]
                user=c.execute("SELECT id,name,email,role,plan FROM users WHERE id=%s",(uid,)).fetchone()
            else:
                uid=c.execute("INSERT INTO users(name,email,password_hash,role,created_at,email_verified,plan,google_sub) VALUES(?,?,?,'hel',?,1,'pro',?)",(name,email,ph,now(),sub)).lastrowid
                user=c.execute("SELECT id,name,email,role,plan FROM users WHERE id=?",(uid,)).fetchone()
    return {"token":make_token(user),"user":dict(user)}

@app.post("/auth/login")
def login(data: LoginIn):
    with db() as c:
        user = c.execute("SELECT * FROM users WHERE email=%s" if DATABASE_URL else "SELECT * FROM users WHERE email=?", (data.email.lower(),)).fetchone()
    if not user or not pwd.verify(data.password, user["password_hash"]):
        raise HTTPException(401, "E-mail ou senha incorretos.")
    public = {k: user[k] for k in ("id","name","email","role","plan")}
    return {"token": make_token(public), "user": public}

@app.get("/me")
def me(user=Depends(current_user)):
    return user

@app.patch("/me")
def update_me(data: ProfileIn, user=Depends(current_user)):
    name = data.name.strip()
    if len(name) < 2:
        raise HTTPException(422, "O nome precisa ter pelo menos 2 caracteres.")
    with db() as c:
        c.execute("UPDATE users SET name=%s WHERE id=%s" if DATABASE_URL else "UPDATE users SET name=? WHERE id=?", (name, user["id"]))
        updated = c.execute("SELECT id,name,email,role FROM users WHERE id=%s" if DATABASE_URL else "SELECT id,name,email,role FROM users WHERE id=?", (user["id"],)).fetchone()
    return dict(updated)

def system_prompt(user, activity, memories):
    memory_text = "\n".join(f"- {m}" for m in memories) or "Nenhuma memória salva ainda."
    status = (f"Soares está jogando {activity['game'] or 'um jogo'}."
              if activity["is_playing"] else "Soares não está marcado como jogando.")
    return f"""Você é Soares Reserva AI, uma assistente virtual inteligente e independente.
Fale em português brasileiro, de forma natural, acolhedora, inteligente e espontânea. Use emojis com moderação.
Você é uma companhia virtual e assistente pessoal; nunca finja ser Soares, nunca diga que uma mensagem foi enviada por ele e nunca invente sentimentos ou promessas em nome dele.
Contexto de atividade: {status} Atualização: {activity['updated_at']}.
Se perguntarem por Soares, explique com delicadeza o status conhecido, sem pressionar nem inventar previsão de quando ele responderá.
Ajude com rotina, estudos, ideias, organização, dúvidas e conversas. Seja honesta quando não souber algo.
Memórias fornecidas (use apenas quando relevantes; não invente outras):
{memory_text}
Nome da pessoa conectada: {user['name']}.
Quando a pessoa pedir explicitamente para guardar uma informação, diga que a memória pode ser salva pela área de memórias; não afirme que salvou se não chamou a ferramenta.
"""

async def ask_model(messages):
    if not AI_API_KEY:
        return ("A conexão com o modelo de IA ainda não foi configurada. "
                "O administrador precisa preencher AI_API_KEY no arquivo .env do backend.")
    url = AI_BASE_URL + "/chat/completions"
    body = {"model": AI_PRO_MODEL, "messages": messages, "temperature": AI_TEMPERATURE}
    async with httpx.AsyncClient(timeout=90) as client:
        try:
            r = await client.post(url, json=body, headers={"Authorization": f"Bearer {AI_API_KEY}"})
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            detail = e.response.text[:500]
            raise HTTPException(502, f"Erro do provedor de IA: {detail}")
        except (httpx.HTTPError, KeyError, IndexError):
            raise HTTPException(502, "Não foi possível obter resposta do provedor de IA.")

@app.post("/chat")
async def chat(data: ChatIn, user=Depends(current_user)):
    if not data.message.strip() and not data.image_data:
        raise HTTPException(400, "Escreva uma mensagem ou anexe uma imagem.")
    if data.image_data and not data.image_data.startswith(("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,", "data:image/gif;base64,")):
        raise HTTPException(400, "Imagem inválida ou formato não suportado.")
    with db() as c:
        activity = dict(c.execute("SELECT * FROM activity WHERE id=1").fetchone())
        memories = [r["content"] for r in c.execute(
            "SELECT content FROM memories WHERE user_id=%s ORDER BY id DESC LIMIT 30" if DATABASE_URL else "SELECT content FROM memories WHERE user_id=? ORDER BY id DESC LIMIT 30", (user["id"],)).fetchall()]
        conv_id=data.conversation_id
        if conv_id:
            cv=c.execute("SELECT id FROM conversations WHERE id=%s AND user_id=%s" if DATABASE_URL else "SELECT id FROM conversations WHERE id=? AND user_id=?",(conv_id,user["id"])).fetchone()
            if not cv: raise HTTPException(404,"Conversa não encontrada.")
        else:
            title=data.message.strip()[:48] or "Nova conversa"
            if DATABASE_URL: conv_id=c.execute("INSERT INTO conversations(user_id,title,created_at,updated_at) VALUES(%s,%s,%s,%s) RETURNING id",(user["id"],title,now(),now())).fetchone()["id"]
            else: conv_id=c.execute("INSERT INTO conversations(user_id,title,created_at,updated_at) VALUES(?,?,?,?)",(user["id"],title,now(),now())).lastrowid
        history=c.execute("SELECT role,content FROM messages WHERE user_id=%s AND conversation_id=%s ORDER BY id DESC LIMIT 20" if DATABASE_URL else "SELECT role,content FROM messages WHERE user_id=? AND conversation_id=? ORDER BY id DESC LIMIT 20",(user["id"],conv_id)).fetchall()
        history = list(reversed(history))
        c.execute("INSERT INTO messages(user_id,role,content,created_at,conversation_id) VALUES(%s,%s,%s,%s,%s)" if DATABASE_URL else "INSERT INTO messages(user_id,role,content,created_at,conversation_id) VALUES(?,?,?,?,?)",
                  (user["id"], "user", (data.message.strip() + (" [imagem anexada]" if data.image_data else "")).strip(), now(), conv_id))
    messages = [{"role":"system","content":system_prompt(user, activity, memories)}]
    messages += [{"role":r["role"],"content":r["content"]} for r in history]
    user_content = [{"type":"text","text":data.message or "Analise a imagem enviada e descreva o que consegue identificar."}]
    if data.image_data:
        user_content.append({"type":"image_url","image_url":{"url":data.image_data}})
    messages += [{"role":"user","content":user_content}]
    answer = await ask_model(messages)
    with db() as c:
        c.execute("INSERT INTO messages(user_id,role,content,created_at,conversation_id) VALUES(%s,%s,%s,%s,%s)" if DATABASE_URL else "INSERT INTO messages(user_id,role,content,created_at,conversation_id) VALUES(?,?,?,?,?)",
                  (user["id"], "assistant", answer, now(), conv_id))
    with db() as c:
        c.execute("UPDATE conversations SET title=CASE WHEN title='Nova conversa' THEN %s ELSE title END,updated_at=%s WHERE id=%s" if DATABASE_URL else "UPDATE conversations SET title=CASE WHEN title='Nova conversa' THEN ? ELSE title END,updated_at=? WHERE id=?",(data.message.strip()[:48] or "Nova conversa",now(),conv_id))
    return {"reply":answer,"conversation_id":conv_id}

@app.get("/conversations")
def list_conversations(user=Depends(current_user)):
    with db() as c:
        rows=c.execute("SELECT id,title,created_at,updated_at FROM conversations WHERE user_id=%s ORDER BY updated_at DESC" if DATABASE_URL else "SELECT id,title,created_at,updated_at FROM conversations WHERE user_id=? ORDER BY updated_at DESC",(user["id"],)).fetchall()
    return {"conversations":[dict(r) for r in rows]}

@app.post("/conversations")
def create_conversation(user=Depends(current_user)):
    stamp=now()
    with db() as c:
        if DATABASE_URL: row=c.execute("INSERT INTO conversations(user_id,title,created_at,updated_at) VALUES(%s,'Nova conversa',%s,%s) RETURNING id,title,created_at,updated_at",(user["id"],stamp,stamp)).fetchone()
        else:
            cid=c.execute("INSERT INTO conversations(user_id,title,created_at,updated_at) VALUES(?,'Nova conversa',?,?)",(user["id"],stamp,stamp)).lastrowid
            row=c.execute("SELECT id,title,created_at,updated_at FROM conversations WHERE id=?",(cid,)).fetchone()
    return dict(row)

@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id:int,user=Depends(current_user)):
    with db() as c:
        c.execute("DELETE FROM messages WHERE conversation_id=%s AND user_id=%s" if DATABASE_URL else "DELETE FROM messages WHERE conversation_id=? AND user_id=?",(conversation_id,user["id"]))
        cur=c.execute("DELETE FROM conversations WHERE id=%s AND user_id=%s" if DATABASE_URL else "DELETE FROM conversations WHERE id=? AND user_id=?",(conversation_id,user["id"]))
    if cur.rowcount==0: raise HTTPException(404,"Conversa não encontrada.")
    return {"ok":True}

@app.get("/messages")
def get_messages(limit: int = 60, conversation_id: Optional[int] = None, user=Depends(current_user)):
    limit = max(1, min(limit, 150))
    with db() as c:
        if conversation_id:
            rows=c.execute("SELECT id,role,content,created_at FROM messages WHERE user_id=%s AND conversation_id=%s ORDER BY id DESC LIMIT %s" if DATABASE_URL else "SELECT id,role,content,created_at FROM messages WHERE user_id=? AND conversation_id=? ORDER BY id DESC LIMIT ?",(user["id"],conversation_id,limit)).fetchall()
        else:
            rows=c.execute("SELECT id,role,content,created_at FROM messages WHERE user_id=%s AND conversation_id=(SELECT id FROM conversations WHERE user_id=%s ORDER BY updated_at DESC LIMIT 1) ORDER BY id DESC LIMIT %s" if DATABASE_URL else "SELECT id,role,content,created_at FROM messages WHERE user_id=? AND conversation_id=(SELECT id FROM conversations WHERE user_id=? ORDER BY updated_at DESC LIMIT 1) ORDER BY id DESC LIMIT ?",(user["id"],user["id"],limit)).fetchall()
    return {"messages": [dict(r) for r in reversed(rows)]}

@app.delete("/messages")
def clear_messages(user=Depends(current_user)):
    with db() as c:
        c.execute("DELETE FROM messages WHERE user_id=%s" if DATABASE_URL else "DELETE FROM messages WHERE user_id=?", (user["id"],))
    return {"ok": True}

@app.get("/activity")
def get_activity(user=Depends(current_user)):
    with db() as c:
        a = dict(c.execute("SELECT * FROM activity WHERE id=1").fetchone())
    return {"is_playing": bool(a["is_playing"]), "game": a["game"],
            "source": a["source"], "updated_at": a["updated_at"]}

@app.post("/activity")
def set_activity(data: ActivityIn, user=Depends(current_user)):
    with db() as c:
        c.execute("UPDATE activity SET is_playing=%s,game=%s,source=%s,updated_at=%s WHERE id=1" if DATABASE_URL else "UPDATE activity SET is_playing=?,game=?,source=?,updated_at=? WHERE id=1",
                  (data.is_playing if DATABASE_URL else int(data.is_playing), data.game.strip(), data.source, now()))
    return {"ok": True, "is_playing": data.is_playing, "game": data.game, "source": data.source}

@app.post("/activity/agent")
def set_activity_from_windows(data: ActivityIn, x_agent_token: Optional[str] = Header(default=None)):
    if not ACTIVITY_AGENT_TOKEN or not secrets.compare_digest(x_agent_token or "", ACTIVITY_AGENT_TOKEN):
        raise HTTPException(401, "Agente Windows não autorizado.")
    with db() as c:
        c.execute("UPDATE activity SET is_playing=%s,game=%s,source='automatic',updated_at=%s WHERE id=1" if DATABASE_URL else "UPDATE activity SET is_playing=?,game=?,source='automatic',updated_at=? WHERE id=1",
                  (data.is_playing if DATABASE_URL else int(data.is_playing), data.game.strip(), now()))
    return {"ok": True, "is_playing": data.is_playing, "game": data.game, "source": "automatic"}

@app.get("/memories")
def get_memories(user=Depends(current_user)):
    with db() as c:
        rows = c.execute("SELECT id,content,created_at FROM memories WHERE user_id=%s ORDER BY id DESC" if DATABASE_URL else "SELECT id,content,created_at FROM memories WHERE user_id=? ORDER BY id DESC",
                         (user["id"],)).fetchall()
    return {"memories": [dict(r) for r in rows]}

@app.post("/memories")
def add_memory(data: MemoryIn, user=Depends(current_user)):
    with db() as c:
        if DATABASE_URL:
            cur = c.execute("INSERT INTO memories(user_id,content,created_at) VALUES(%s,%s,%s) RETURNING id",
                            (user["id"], data.content.strip(), now()))
            memory_id = cur.fetchone()["id"]
            row = c.execute("SELECT id,content,created_at FROM memories WHERE id=%s", (memory_id,)).fetchone()
        else:
            cur = c.execute("INSERT INTO memories(user_id,content,created_at) VALUES(?,?,?)",
                            (user["id"], data.content.strip(), now()))
            row = c.execute("SELECT id,content,created_at FROM memories WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)

@app.delete("/memories/{memory_id}")
def delete_memory(memory_id: int, user=Depends(current_user)):
    with db() as c:
        cur = c.execute("DELETE FROM memories WHERE id=%s AND user_id=%s" if DATABASE_URL else "DELETE FROM memories WHERE id=? AND user_id=?", (memory_id, user["id"]))
    if cur.rowcount == 0:
        raise HTTPException(404, "Memória não encontrada.")
    return {"ok": True}

@app.get("/admin/users")
def list_users(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Acesso restrito à administração.")
    with db() as c:
        rows = c.execute("SELECT id,name,email,role,created_at FROM users ORDER BY id").fetchall()
    return {"users": [dict(r) for r in rows]}
