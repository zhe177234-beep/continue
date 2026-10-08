import logging
import os
import re
import sqlite3
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, StrictInt, StrictStr
from engine import Engine, MAX_FILE
from models import Ollama
from store import Store
from retrieval import retrieve, reindex
from jobs import Jobs, extract_relations
from learning import generate_quiz, submit, progress


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r'^[a-zA-Z0-9_]+$')
    password: str = Field(min_length=10, max_length=128)


class BaseInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    @field_validator('name')
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip(): raise ValueError('名称不能为空')
        return value.strip()


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    mode: Literal['auto', 'bm25', 'cosine', 'hybrid', 'graph', 'semantic'] = 'auto'
    k: int = Field(default=5, ge=1, le=10, strict=True)
    generate: bool = True
    conversation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class QuizInput(BaseModel):
    kind: Literal['single','multiple','judge','short','essay'] = 'single'
    count: int = Field(default=5, ge=1, le=10, strict=True)


class Submission(BaseModel):
    selected: StrictInt | list[StrictInt] | StrictStr


def create_app(directory=None, model=None):
    store = Store(directory or os.getenv('DATA_DIR', str(Path(__file__).resolve().parent.parent / 'data' / 'v2')))
    model = model or Ollama()
    app = FastAPI(title='智学学习知识系统', version='0.3.0')
    app.state.store = store
    jobs = Jobs(store)
    app.state.jobs = jobs
    limiter = defaultdict(list)
    limit_lock = threading.Lock()
    secure_cookie = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'

    @app.middleware('http')
    async def guard(request: Request, call_next):
        if request.method in {'POST', 'PUT', 'DELETE'}:
            origin = request.headers.get('origin')
            configured = os.getenv('PUBLIC_ORIGIN', '')
            if origin and urlsplit(origin).netloc != request.headers.get('host') and origin != configured:
                return JSONResponse({'detail': '不允许跨站请求'}, status_code=403)
            length = request.headers.get('content-length')
            if length is not None:
                try:
                    if int(length) < 0 or int(length) > MAX_FILE + 65536:
                        return JSONResponse({'detail': '请求超过大小限制'}, status_code=413)
                except ValueError:
                    return JSONResponse({'detail': '无效请求长度'}, status_code=400)
            elif request.method == 'POST':
                return JSONResponse({'detail': '请求必须包含 Content-Length'}, status_code=411)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=400)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        logging.exception('request failed')
        return JSONResponse({'detail': '服务处理失败，请检查服务日志'}, status_code=500)

    def user(request: Request):
        found = store.user(request.cookies.get('session'))
        if not found: raise HTTPException(401, '请先登录')
        return found

    def engine(base_id: str, current=Depends(user)):
        if not re.fullmatch(r'[0-9a-f]{32}', base_id) or not store.owns(current['id'], base_id):
            raise HTTPException(404, '知识库不存在')
        return Engine(store.directory / 'bases' / (base_id + '.db'))

    def auth_limit(request):
        ip = request.client.host if request.client else 'local'
        now = time.time()
        with limit_lock:
            # Bound memory and reject large bursts; reverse proxy adds stronger production limits.
            if len(limiter) > 10000: limiter.clear()
            limiter[ip] = [t for t in limiter[ip] if t > now - 60]
            if len(limiter[ip]) >= 20: raise HTTPException(429, '请求过于频繁，请一分钟后重试')
            limiter[ip].append(now)

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'version': '0.3.0', 'chat_model_configured': bool(model.model), 'embedding_model_configured': bool(model.embedding_model)}

    @app.post('/api/auth/register', status_code=201)
    def register(body: Credentials, request: Request):
        auth_limit(request)
        if os.getenv('ALLOW_REGISTRATION', 'true').lower() != 'true': raise HTTPException(403, '注册已关闭')
        try: store.register(body.username, body.password)
        except sqlite3.IntegrityError: raise HTTPException(409, '用户名已存在') from None
        return {'registered': True}

    @app.post('/api/auth/login')
    def login(body: Credentials, request: Request, response: Response):
        auth_limit(request)
        token = store.login(body.username, body.password)
        if not token: raise HTTPException(401, '用户名或密码错误')
        response.set_cookie('session', token, max_age=86400, httponly=True, secure=secure_cookie, samesite='strict', path='/')
        return {'username': body.username}

    @app.post('/api/auth/logout')
    def logout(request: Request, response: Response):
        store.logout(request.cookies.get('session'))
        response.delete_cookie('session', path='/')
        return {'logged_out': True}

    @app.get('/api/auth/me')
    def me(current=Depends(user)): return current

    @app.get('/api/bases')
    def list_bases(current=Depends(user)): return store.bases(current['id'])

    @app.post('/api/bases', status_code=201)
    def new_base(body: BaseInput, current=Depends(user)): return store.new_base(current['id'], body.name)

    @app.get('/api/bases/{base_id}/documents')
    def documents(index=Depends(engine)): return index.documents()

    @app.post('/api/bases/{base_id}/documents', status_code=201)
    def upload(file: UploadFile, index=Depends(engine)):
        try:
            data = file.file.read(MAX_FILE + 1)
            return index.ingest(file.filename or '', data)
        finally: file.file.close()

    @app.delete('/api/bases/{base_id}/documents/{doc_id}')
    def delete_document(base_id: str, doc_id: str, index=Depends(engine)):
        if not index.delete(doc_id): raise HTTPException(404, '资料不存在')
        # Quizzes/history can carry deleted sources: clear dependent exercises and history.
        with store.db() as db:
            db.execute('DELETE FROM quizzes WHERE base_id=? AND source LIKE ?', (base_id, doc_id + ':%'))
            db.execute('DELETE FROM history WHERE base_id=?', (base_id,))
        return {'deleted': True}

    @app.get('/api/bases/{base_id}/graph')
    def graph(index=Depends(engine)): return index.graph()

    @app.post('/api/bases/{base_id}/index')
    def index_vectors(index=Depends(engine)):
        try: return reindex(index, model)
        except Exception: raise HTTPException(503, '语义索引失败，请检查 Ollama、模型名称和内存') from None

    @app.get('/api/bases/{base_id}/jobs')
    def list_jobs(base_id: str, index=Depends(engine)): return jobs.list(base_id)

    @app.post('/api/bases/{base_id}/jobs/{kind}', status_code=202)
    def start_job(base_id: str, kind: Literal['index','relations'], index=Depends(engine)):
        if kind == 'index' and not model.embedding_model: raise ValueError('未配置向量模型')
        if kind == 'relations' and not model.model: raise ValueError('未配置生成模型')
        return jobs.start(base_id, kind, lambda: reindex(index,model) if kind == 'index' else extract_relations(index,model))

    @app.post('/api/bases/{base_id}/ask')
    def ask(base_id: str, body: Question, index=Depends(engine)):
        conversation_id = store.conversation(base_id, body.conversation_id)
        turns = store.turns(base_id, conversation_id)
        # Follow-up pronouns need prior questions to locate evidence, with a hard bound.
        followup = any(word in body.question for word in ('它','这个','上述','继续','为什么','举例','再解释'))
        query = (turns[-1]['question'][:500] + '\n' + body.question[:499]) if turns and followup else body.question
        result = retrieve(index, model, query, body.mode, body.k)
        result['conversation_id'] = conversation_id
        result['retrieval_query'] = query
        result['answer_kind'] = 'extractive'
        result['answer'] = '\n\n'.join(f'[{i}] {s["text"]}' for i,s in enumerate(result['sources'],1)) if result['sources'] else '资料中没有找到足够相关的证据，请补充资料或更具体地提问。'
        if body.generate and model.model and result['sources']:
            try:
                result['answer'] = model.generate(body.question, result['sources'], history=turns) if turns else model.generate(body.question, result['sources'])
                result['answer_kind'] = 'generated'
                result['warning'] = '引用编号已校验，回答事实仍需对照原文核实'
            except Exception:
                result['warning'] = '生成模型不可用或引用无效，已降级为原文摘录'
        store.history(base_id, body.question, result)
        return result

    @app.get('/api/bases/{base_id}/history')
    def history(base_id: str, index=Depends(engine)): return store.history(base_id)

    @app.post('/api/bases/{base_id}/quizzes')
    def quizzes(base_id: str, body: QuizInput, index=Depends(engine)): return generate_quiz(store, index, base_id, body.count, body.kind)

    @app.post('/api/bases/{base_id}/quizzes/{quiz_id}/submit')
    def grade(base_id: str, quiz_id: str, body: Submission, index=Depends(engine)):
        try: return submit(store, base_id, quiz_id, body.selected)
        except LookupError: raise HTTPException(404, '题目不存在') from None

    @app.get('/api/bases/{base_id}/progress')
    def learning_progress(base_id: str, index=Depends(engine)): return progress(store, index, base_id)

    return app


app = create_app()
