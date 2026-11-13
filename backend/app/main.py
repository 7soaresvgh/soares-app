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
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.8"))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
ACTIVITY_AGENT_TOKEN = os.getenv("ACTIVITY_AGENT_TOKEN", "").strip()
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

def now():
    return datetime.now(timezone.utc).isoformat()

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class ProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)

class ChatIn(BaseModel):
    message: str = Field(default="", max_length=12000)
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
        user = c.execute("SELECT id,name,email,role FROM users WHERE id=%s" if DATABASE_URL else "SELECT id,name,email,role FROM users WHERE id=?", (uid,)).fetchone()
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
                cur = c.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(%s,%s,%s,%s,%s) RETURNING id",
                                (data.name.strip(), email, pwd.hash(data.password), role, now()))
                uid = cur.fetchone()["id"]
            else:
                cur = c.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                                (data.name.strip(), email, pwd.hash(data.password), role, now()))
                uid = cur.lastrowid
        except (sqlite3.IntegrityError, psycopg.IntegrityError):
            raise HTTPException(409, "Este e-mail já possui cadastro.")
        user = c.execute("SELECT id,name,email,role FROM users WHERE id=%s" if DATABASE_URL else "SELECT id,name,email,role FROM users WHERE id=?", (uid,)).fetchone()
    return {"token": make_token(user), "user": dict(user)}

@app.post("/auth/login")
def login(data: LoginIn):
    with db() as c:
        user = c.execute("SELECT * FROM users WHERE email=%s" if DATABASE_URL else "SELECT * FROM users WHERE email=?", (data.email.lower(),)).fetchone()
    if not user or not pwd.verify(data.password, user["password_hash"]):
        raise HTTPException(401, "E-mail ou senha incorretos.")
    public = {k: user[k] for k in ("id","name","email","role")}
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
    return f"""Você é Soares Reserva AI, uma assistente virtual criada especialmente para Heloysa.
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
    body = {"model": AI_MODEL, "messages": messages, "temperature": AI_TEMPERATURE}
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
        history = c.execute("SELECT role,content FROM messages WHERE user_id=%s ORDER BY id DESC LIMIT 20" if DATABASE_URL else "SELECT role,content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 20",
                            (user["id"],)).fetchall()
        history = list(reversed(history))
        c.execute("INSERT INTO messages(user_id,role,content,created_at) VALUES(%s,%s,%s,%s)" if DATABASE_URL else "INSERT INTO messages(user_id,role,content,created_at) VALUES(?,?,?,?)",
                  (user["id"], "user", (data.message.strip() + (" [imagem anexada]" if data.image_data else "")).strip(), now()))
    messages = [{"role":"system","content":system_prompt(user, activity, memories)}]
    messages += [{"role":r["role"],"content":r["content"]} for r in history]
    user_content = [{"type":"text","text":data.message or "Analise a imagem enviada e descreva o que consegue identificar."}]
    if data.image_data:
        user_content.append({"type":"image_url","image_url":{"url":data.image_data}})
    messages += [{"role":"user","content":user_content}]
    answer = await ask_model(messages)
    with db() as c:
        c.execute("INSERT INTO messages(user_id,role,content,created_at) VALUES(%s,%s,%s,%s)" if DATABASE_URL else "INSERT INTO messages(user_id,role,content,created_at) VALUES(?,?,?,?)",
                  (user["id"], "assistant", answer, now()))
    return {"reply": answer}

@app.get("/messages")
def get_messages(limit: int = 60, user=Depends(current_user)):
    limit = max(1, min(limit, 150))
    with db() as c:
        rows = c.execute("SELECT id,role,content,created_at FROM messages WHERE user_id=%s ORDER BY id DESC LIMIT %s" if DATABASE_URL else "SELECT id,role,content,created_at FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
                         (user["id"], limit)).fetchall()
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
