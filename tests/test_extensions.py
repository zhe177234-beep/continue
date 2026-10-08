import sys
import time
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ai-service'))
from api import create_app
from engine import Engine
from jobs import extract_relations, Jobs
from store import Store
from test_api import seeded, account, FakeModel


class ContextModel(FakeModel):
    def generate(self,question,sources,history=None):
        self.seen = history or []
        return '学习率影响梯度下降。[1]'
    def relations(self,text):
        return [{'subject':'学习率','predicate':'影响','object':'梯度下降','quote':'学习率影响梯度下降'},
                {'subject':'不存在的实体','predicate':'影响','object':'梯度下降','quote':'学习率影响梯度下降'}]


def test_conversation_context_and_isolation(tmp_path):
    model=ContextModel();app=create_app(tmp_path,model)
    client,base,_=seeded(app)
    first=client.post(f'/api/bases/{base}/ask',json={'question':'梯度下降的学习率'}).json()
    second=client.post(f'/api/bases/{base}/ask',json={'question':'它为什么重要？','conversation_id':first['conversation_id']}).json()
    assert '梯度下降' in second['retrieval_query']
    assert len(model.seen)==1
    other=client.post('/api/bases',json={'name':'另一门课程'}).json()['id']
    assert client.post(f'/api/bases/{other}/ask',json={'question':'继续','conversation_id':first['conversation_id']}).status_code==400
    fresh=client.post(f'/api/bases/{base}/ask',json={'question':'它为什么重要？'}).json()
    assert fresh['conversation_id']!=first['conversation_id']
    assert fresh['retrieval_query']=='它为什么重要？'


def test_grounded_graph_and_two_hop(tmp_path):
    index=Engine(tmp_path/'index.db');index.ingest('a.txt','学习率影响梯度下降'.encode())
    result=extract_relations(index,ContextModel())
    assert result['added']==1 and result['rejected']==1
    assert extract_relations(index,ContextModel())['added']==0
    index.ingest('b.txt','关系：梯度下降|优化|损失函数'.encode())
    sources=index.search('学习率的关系','graph',10)['sources']
    assert {s['name'] for s in sources}=={'a.txt','b.txt'}
    doc = next(d for d in index.documents() if d['name']=='a.txt')
    index.delete(doc['id'])
    assert not any(e['chunk_id'].startswith(doc['id']) for e in index.graph())


def test_all_quiz_types_and_exact_short_grading(tmp_path):
    client,base,_=seeded(create_app(tmp_path,FakeModel()))
    app=client.app
    for kind in ['single','multiple','judge','short','essay']:
        response=client.post(f'/api/bases/{base}/quizzes',json={'count':2,'kind':kind})
        assert response.status_code==200,response.text
        q=response.json()[0]
        with app.state.store.db() as db:
            row=db.execute('SELECT answer FROM quizzes WHERE id=?',(q['id'],)).fetchone()
        import json
        answer=json.loads(row[0]) if kind in ('multiple','essay') else row[0]
        if kind=='essay': answer='；'.join(answer)
        result=client.post(f'/api/bases/{base}/quizzes/{q["id"]}/submit',json={'selected':answer})
        assert result.status_code==200,result.text
        assert result.json()['correct']
        assert client.post(f'/api/bases/{base}/quizzes/{q["id"]}/submit',json={'selected':answer}).status_code==400
    assert sum(x['attempts'] for x in client.get(f'/api/bases/{base}/progress').json()['mastery'])==5


def test_jobs_authorization_completion_and_restart(tmp_path):
    model=ContextModel();app=create_app(tmp_path,model);client,base,_=seeded(app)
    other=account(app,'other_student')
    assert other.get(f'/api/bases/{base}/jobs').status_code==404
    result=client.post(f'/api/bases/{base}/jobs/index',json={})
    assert result.status_code==202
    for _ in range(100):
        jobs=client.get(f'/api/bases/{base}/jobs').json()
        if jobs[0]['status'] not in ('queued','running'):break
        time.sleep(.01)
    assert jobs[0]['status']=='succeeded'
    with app.state.store.db() as db:
        db.execute("INSERT INTO jobs(id,base_id,kind,status,result,created) VALUES('interrupted',?,'index','running','{}',9999999999)",(base,))
    restarted=Jobs(app.state.store)
    assert restarted.list(base)[0]['status']=='failed'
    restarted.pool.shutdown()


def test_scanned_pdf_ocr(monkeypatch):
    import io, shutil
    if not shutil.which('pdftoppm') or not shutil.which('tesseract'): pytest.skip('OCR tools unavailable')
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from engine import parse_document
    monkeypatch.setenv('ENABLE_OCR','true');monkeypatch.setenv('OCR_LANG','eng')
    image=Image.new('RGB',(700,140),'white')
    try: font=ImageFont.truetype('DejaVuSans.ttf',40)
    except OSError: font=ImageFont.load_default(size=40)
    ImageDraw.Draw(image).text((20,30),'Gradient descent',font=font,fill='black')
    buffer=io.BytesIO();pdf=canvas.Canvas(buffer,pagesize=(700,180));pdf.drawImage(ImageReader(image),0,20,width=700,height=140);pdf.save()
    pages=parse_document('scan.pdf',buffer.getvalue())
    assert pages[0][0]==1 and 'gradient' in pages[0][1].lower()


def test_prerequisite_order_and_cycle(tmp_path):
    from learning import progress
    store=Store(tmp_path/'store');store.register('student','safe-password')
    user=store.user(store.login('student','safe-password'));base=store.new_base(user['id'],'课程')['id']
    index=Engine(tmp_path/'index.db')
    index.ingest('a.txt','关系：高级概念|依赖|基础概念\n关系：基础概念|描述|例子'.encode())
    result=progress(store,index,base)
    assert [x['topic'] for x in result['path']]==['基础概念','高级概念']
    assert not result['prerequisite_cycle']
    index.ingest('b.txt','关系：基础概念|依赖|高级概念'.encode())
    assert progress(store,index,base)['prerequisite_cycle']
