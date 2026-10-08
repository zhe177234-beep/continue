"""Persisted, bounded model jobs. Interrupted jobs are reported after a restart."""
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor


class Cancelled(Exception):
    pass


class JobContext:
    def __init__(self, jobs, job_id, seconds):
        self.jobs, self.id = jobs, job_id
        self.deadline = time.monotonic() + seconds

    def check(self):
        with self.jobs.store.db() as db:
            row = db.execute('SELECT cancel_requested FROM jobs WHERE id=?', (self.id,)).fetchone()
        if not row or row[0]: raise Cancelled('任务已停止')
        if time.monotonic() >= self.deadline: raise ValueError('任务超过时间预算，请缩小知识库或减少步骤后重试')

    def update(self, **values):
        self.check()
        with self.jobs.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT result,cancel_requested FROM jobs WHERE id=?', (self.id,)).fetchone()
            if row['cancel_requested']: raise Cancelled('任务已停止')
            payload = json.loads(row[0])
            payload.update(values)
            db.execute('UPDATE jobs SET result=? WHERE id=?', (json.dumps(payload,ensure_ascii=False),self.id))


class Jobs:
    def __init__(self, store):
        self.store = store
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='knowledge-job')
        self.lock = threading.Lock()
        with store.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,base_id TEXT,kind TEXT,status TEXT,result TEXT,created REAL)')
            if 'cancel_requested' not in {r[1] for r in db.execute('PRAGMA table_info(jobs)')}:
                db.execute('ALTER TABLE jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0')
            db.execute("UPDATE jobs SET status='failed',result=? WHERE status IN ('queued','running')", (json.dumps({'error':'服务重启中断任务，请重新执行'},ensure_ascii=False),))

    def list(self, base_id):
        with self.store.db() as db:
            return [dict(r, result=json.loads(r['result'])) for r in db.execute('SELECT * FROM jobs WHERE base_id=? ORDER BY created DESC LIMIT 20', (base_id,))]

    def get(self, base_id, job_id):
        with self.store.db() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=? AND base_id=?',(job_id,base_id)).fetchone()
            if not row: raise LookupError('任务不存在')
            return dict(row,result=json.loads(row['result']))

    def start(self, base_id, kind, fn, controlled=False, initial=None, seconds=1200):
        with self.lock, self.store.db() as db:
            if db.execute("SELECT 1 FROM jobs WHERE base_id=? AND status IN ('queued','running')", (base_id,)).fetchone():
                raise ValueError('当前知识库已有任务，请等待完成')
            if db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0] >= 8:
                raise ValueError('任务队列已满，请稍后重试')
            job_id = uuid.uuid4().hex
            db.execute('INSERT INTO jobs(id,base_id,kind,status,result,created) VALUES(?,?,?,?,?,?)',
                       (job_id,base_id,kind,'queued',json.dumps(initial or {},ensure_ascii=False),time.time()))
        self.pool.submit(self.run, job_id, fn, controlled, seconds)
        return {'id':job_id,'status':'queued','kind':kind}

    def cancel(self, base_id, job_id):
        with self.store.db() as db:
            found = db.execute('SELECT status FROM jobs WHERE id=? AND base_id=?',(job_id,base_id)).fetchone()
            if not found: raise LookupError('任务不存在')
            if found[0] in ('queued','running'):
                db.execute('UPDATE jobs SET cancel_requested=1 WHERE id=?',(job_id,))
        return {'id':job_id,'stop_requested':found[0] in ('queued','running')}

    def run(self, job_id, fn, controlled=False, seconds=1200):
        context = JobContext(self,job_id,seconds)
        with self.store.db() as db: db.execute("UPDATE jobs SET status='running' WHERE id=?",(job_id,))
        try:
            context.check()
            result, status = fn(context) if controlled else fn(), 'succeeded'
            context.check()
        except Cancelled:
            result, status = {'error':'任务已停止'}, 'cancelled'
        except ValueError as exc:
            result, status = {'error':str(exc)}, 'failed'
        except Exception:
            result, status = {'error':'任务失败，请检查模型服务、模型名称和内存后重试'}, 'failed'
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT result,cancel_requested FROM jobs WHERE id=?',(job_id,)).fetchone()
            if row['cancel_requested']:
                result,status = {'error':'任务已停止'},'cancelled'
            previous = json.loads(row['result'])
            previous.update(result)
            db.execute('UPDATE jobs SET status=?,result=? WHERE id=?',(status,json.dumps(previous,ensure_ascii=False),job_id))


def extract_relations(index, model, context=None):
    if not model.model: raise ValueError('未配置生成模型')
    with index.connect() as db:
        rows = list(db.execute('SELECT id,text FROM chunks ORDER BY id'))
    accepted, rejected = [], 0
    for position,row in enumerate(rows):
        if context: context.update(stage='关系提取',completed=position,total=len(rows))
        candidates = model.relations(row['text'])
        if not isinstance(candidates,list) or len(candidates)>8: raise ValueError('模型关系格式无效')
        for edge in candidates:
            if not isinstance(edge,dict): rejected += 1; continue
            values = [edge.get(k) for k in ('subject','predicate','object','quote')]
            if any(not isinstance(v,str) or not v.strip() for v in values): rejected += 1; continue
            subject,predicate,obj,quote = (v.strip() for v in values)
            if len(subject)>60 or len(predicate)>30 or len(obj)>60 or len(quote)>600 or quote not in row['text'] or subject not in quote or obj not in quote:
                rejected += 1; continue
            accepted.append((row['id'],subject,predicate,obj))
    # Atomic publication; failures never leave half a graph. Explicit relations stay.
    with index.connect() as db:
        if context: context.check()
        db.execute('BEGIN IMMEDIATE')
        current = list(db.execute('SELECT id,text FROM chunks ORDER BY id'))
        if [(r['id'],r['text']) for r in current] != [(r['id'],r['text']) for r in rows]:
            raise ValueError('关系提取期间资料已变化，请重新执行')
        added = 0
        for edge in accepted:
            if db.execute('SELECT 1 FROM chunks WHERE id=?',(edge[0],)).fetchone() and not db.execute('SELECT 1 FROM relations WHERE chunk_id=? AND subject=? AND predicate=? AND object=?',edge).fetchone():
                db.execute('INSERT INTO relations VALUES(?,?,?,?)',edge)
                added += 1
        if added: index.invalidate_graph(db)
    return {'added':added,'rejected':rejected,'processed':len(rows),'warning':'实体和摘录已核验，关系语义仍需人工复核'}
