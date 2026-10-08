"""Account/session/business persistence; each knowledge base has an isolated index."""
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
import uuid
from pathlib import Path


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'accounts.db'
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE, salt TEXT, password TEXT);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), expires REAL);
            CREATE TABLE IF NOT EXISTS bases(id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), name TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS history(id TEXT PRIMARY KEY, base_id TEXT REFERENCES bases(id) ON DELETE CASCADE,
              question TEXT, result TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS quizzes(id TEXT PRIMARY KEY, base_id TEXT REFERENCES bases(id) ON DELETE CASCADE,
              topic TEXT, stem TEXT, options TEXT, answer INTEGER, explanation TEXT, source TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY, quiz_id TEXT REFERENCES quizzes(id) ON DELETE CASCADE,
              selected INTEGER, correct INTEGER, created REAL);
            ''')

            columns = {r[1] for r in db.execute('PRAGMA table_info(quizzes)')}
            if 'kind' not in columns:
                db.execute("ALTER TABLE quizzes ADD COLUMN kind TEXT NOT NULL DEFAULT 'single'")

    def conversation(self, base_id, conversation_id=None):
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,base_id TEXT,created REAL)')
            if conversation_id:
                if not db.execute('SELECT 1 FROM conversations WHERE id=? AND base_id=?', (conversation_id,base_id)).fetchone():
                    raise ValueError('对话不存在或不属于当前知识库')
                return conversation_id
            conversation_id = uuid.uuid4().hex
            db.execute('INSERT INTO conversations VALUES(?,?,?)', (conversation_id,base_id,time.time()))
            return conversation_id

    def turns(self, base_id, conversation_id):
        return [h for h in reversed(self.history(base_id)) if h['result'].get('conversation_id') == conversation_id][-4:]

    def db(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def register(self, username, password):
        salt = secrets.token_hex(16)
        with self.db() as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?)', (uuid.uuid4().hex, username, salt, password_hash(password, salt)))

    def login(self, username, password):
        with self.db() as db:
            user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            # Same KDF cost for unknown usernames; no plaintext passwords stored.
            expected = password_hash(password, user['salt'] if user else '00' * 16)
            if not user or not hmac.compare_digest(expected, user['password']):
                return None
            raw = secrets.token_urlsafe(32)
            digest = hashlib.sha256(raw.encode()).hexdigest()
            db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?)', (digest, user['id'], time.time() + 86400))
            return raw

    def user(self, raw):
        digest = hashlib.sha256((raw or '').encode()).hexdigest()
        with self.db() as db:
            row = db.execute('SELECT u.id,u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?', (digest, time.time())).fetchone()
            return dict(row) if row else None

    def logout(self, raw):
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256((raw or '').encode()).hexdigest(),))

    def bases(self, user_id):
        with self.db() as db:
            return [dict(row) for row in db.execute('SELECT id,name,created FROM bases WHERE user_id=? ORDER BY created DESC', (user_id,))]

    def new_base(self, user_id, name):
        base_id = uuid.uuid4().hex
        with self.db() as db:
            if db.execute('SELECT COUNT(*) FROM bases WHERE user_id=?', (user_id,)).fetchone()[0] >= 20:
                raise ValueError('每个账号最多 20 个知识库')
            db.execute('INSERT INTO bases VALUES(?,?,?,?)', (base_id, user_id, name, time.time()))
        return {'id': base_id, 'name': name}

    def owns(self, user_id, base_id):
        with self.db() as db:
            return db.execute('SELECT 1 FROM bases WHERE id=? AND user_id=?', (base_id, user_id)).fetchone() is not None

    def history(self, base_id, question=None, result=None):
        with self.db() as db:
            if question is not None:
                db.execute('INSERT INTO history VALUES(?,?,?,?,?)', (uuid.uuid4().hex, base_id, question, json.dumps(result, ensure_ascii=False), time.time()))
            return [{'id': r['id'], 'question': r['question'], 'result': json.loads(r['result']), 'created': r['created']} for r in db.execute('SELECT * FROM history WHERE base_id=? ORDER BY created DESC LIMIT 100', (base_id,))]
