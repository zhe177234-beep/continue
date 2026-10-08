"""Persisted, bounded model jobs. Interrupted jobs are reported after a restart."""
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor


class Jobs:
    def __init__(self, store):
        self.store = store
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='knowledge-job')
        self.lock = threading.Lock()
        with store.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,base_id TEXT,kind TEXT,status TEXT,result TEXT,created REAL)')
            db.execute("UPDATE jobs SET status='failed',result=? WHERE status IN ('queued','running')", (json.dumps({'error':'服务重启中断任务，请重新执行'},ensure_ascii=False),))

    def list(self, base_id):
        with self.store.db() as db:
            return [dict(r, result=json.loads(r['result'])) for r in db.execute('SELECT * FROM jobs WHERE base_id=? ORDER BY created DESC LIMIT 20', (base_id,))]

    def start(self, base_id, kind, fn):
        with self.lock, self.store.db() as db:
            if db.execute("SELECT 1 FROM jobs WHERE base_id=? AND status IN ('queued','running')", (base_id,)).fetchone():
                raise ValueError('当前知识库已有任务，请等待完成')
            if db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0] >= 8:
                raise ValueError('任务队列已满，请稍后重试')
            job_id = uuid.uuid4().hex
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?)',(job_id,base_id,kind,'queued','{}',time.time()))
        self.pool.submit(self.run, job_id, fn)
        return {'id':job_id,'status':'queued','kind':kind}

    def run(self, job_id, fn):
        with self.store.db() as db: db.execute("UPDATE jobs SET status='running' WHERE id=?",(job_id,))
        try:
            result, status = fn(), 'succeeded'
        except Exception:
            result, status = {'error':'任务失败，请检查模型服务、模型名称和内存后重试'}, 'failed'
        with self.store.db() as db:
            db.execute('UPDATE jobs SET status=?,result=? WHERE id=?',(status,json.dumps(result,ensure_ascii=False),job_id))


def extract_relations(index, model):
    if not model.model: raise ValueError('未配置生成模型')
    with index.connect() as db:
        rows = list(db.execute('SELECT id,text FROM chunks ORDER BY id LIMIT 101'))
    if len(rows) > 100: raise ValueError('自动关系抽取每次最多处理 100 个片段，请拆分知识库')
    accepted, rejected = [], 0
    for row in rows:
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
        db.execute('BEGIN IMMEDIATE')
        added = 0
        for edge in accepted:
            if db.execute('SELECT 1 FROM chunks WHERE id=?',(edge[0],)).fetchone() and not db.execute('SELECT 1 FROM relations WHERE chunk_id=? AND subject=? AND predicate=? AND object=?',edge).fetchone():
                db.execute('INSERT INTO relations VALUES(?,?,?,?)',edge)
                added += 1
    return {'added':added,'rejected':rejected,'processed':len(rows),'warning':'实体和摘录已核验，关系语义仍需人工复核'}
