import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ai-service'))
from api import create_app
from agents import run as run_agents
from engine import Engine
from graphrag import build, query, reports, status, snapshot
from jobs import Jobs
from models import Ollama
from store import Store
from test_api import account


class Model:
    model = 'test-chat'
    embedding_model = 'test-embed'
    def __init__(self):
        self.maps = []
        self.plans = []
        self.reviews = 0
    def embed(self,texts): return [[1.,0.] for text in texts]
    def relations(self,text): return []
    def graph_report(self,entities,sources):
        return {'title':entities[0],'summary':'课程社区',
                'findings':[{'text':s['text'],'chunk_id':s['chunk_id'],'quote':s['text']} for s in sources[:4]]}
    def graph_map(self,question,report):
        self.maps.append(report['title'])
        return {'points':[{'text':f['text'],'finding':i,'score':90} for i,f in enumerate(report['findings'][:4],1)]}
    def generate(self,question,sources,history=None): return sources[0]['text']+' [1]'
    def agent_plan(self,goal,observations,feedback,available):
        self.plans.append((observations,feedback,available))
        if observations and observations[-1].get('review')=='accepted':
            return {'worker':'finish','mode':'hybrid','query':''}
        return {'worker':'researcher','mode':'hybrid','query':'正则化' if feedback else '梯度下降'}
    def agent_review(self,goal,answer,sources):
        self.reviews += 1
        return {'accepted':True,'issues':[],'queries':[],
                'support':[{'claim':'课程概念','chunk_id':sources[0]['chunk_id'],'quote':sources[0]['text']}]}


def corpus(tmp_path):
    index = Engine(tmp_path/'knowledge.db')
    index.ingest('optimization.txt','关系：梯度下降|依赖|学习率\n学习率控制更新步长。'.encode())
    index.ingest('regularization.txt','关系：正则化|减少|过拟合\n正则化控制模型复杂度。'.encode())
    index.ingest('orphan.txt','验证集用于模型选择。'.encode())
    return index


def wait(jobs,base,job):
    for _ in range(300):
        state = jobs.get(base,job['id'])
        if state['status'] not in ('queued','running'): return state
        time.sleep(.01)
    raise AssertionError('Job did not complete')


def test_community_coverage_global_map_and_local_sources(tmp_path):
    index,model = corpus(tmp_path),Model()
    result = build(index,model,extract=False)
    assert result['chunks']==3 and result['communities']>=3
    communities = reports(index,model)['communities']
    covered = {cid for c in communities if c['level']==0 for cid in c['chunk_ids']}
    assert covered=={s['chunk_id'] for s in snapshot(index)[0]}
    answer = query(index,model,'课程有哪些主要主题？','global',10)
    assert answer['graph_context']['communities_scanned']==answer['graph_context']['communities_total']
    assert len(model.maps)==answer['graph_context']['communities_total']
    assert {s['name'] for s in answer['sources']}=={'optimization.txt','regularization.txt','orphan.txt'}
    local = query(index,model,'梯度下降依赖什么？','local')
    assert '梯度下降' in local['graph_context']['entities']
    assert local['sources'][0]['name']=='optimization.txt'


def test_index_invalidates_on_documents_models_and_relations(tmp_path):
    index,model = corpus(tmp_path),Model()
    build(index,model,extract=False)
    assert status(index,model)['ready']
    model.model='new-model'
    assert not status(index,model)['ready']
    model.model='test-chat'
    doc = index.documents()[0]
    index.delete(doc['id'])
    assert reports(index,model)['communities']==[]
    with pytest.raises(ValueError,match='索引'): query(index,model,'x','global')
    build(index,model,extract=False)
    index.ingest('new.txt','新课程资料'.encode())
    assert not status(index,model)['ready']


def test_atomic_publication_budget_and_concurrent_edit(tmp_path):
    index,model = corpus(tmp_path),Model()
    build(index,model,extract=False)
    original = reports(index,model)
    with pytest.raises(ValueError,match='预算'): build(index,model,extract=False,max_calls=1)
    assert reports(index,model)==original
    old = model.graph_report
    def edit(entities,sources):
        index.ingest('changed.txt','并发新增资料'.encode())
        return old(entities,sources)
    model.graph_report=edit
    with pytest.raises(ValueError,match='变化'): build(index,model,extract=False)
    assert not status(index,model)['ready']


def test_map_rejects_fabricated_quotes_and_reports_extractive_fallback(tmp_path):
    index,model = corpus(tmp_path),Model()
    model.graph_report=lambda entities,sources:{'title':'主题','summary':'无效发现','findings':[{'text':'编造','chunk_id':sources[0]['chunk_id'],'quote':'原文不存在'}]}
    build(index,model,extract=False)
    assert all(c['report']['extractive_batches'] for c in reports(index,model)['communities'])
    model.graph_map=lambda question,report:{'points':[{'text':'编造','finding':999,'score':100}]}
    result=query(index,model,'主题','global')
    assert result['graph_context']['map_failures']>0
    assert result['sources'] and '编造' not in result['answer']


def test_hierarchy_parents_contain_children(tmp_path,monkeypatch):
    index,model = corpus(tmp_path),Model()
    def partitions(graph,seed):
        nodes=sorted(graph)
        yield [{n} for n in nodes]
        yield [set(nodes)]
    monkeypatch.setattr('graphrag.nx.community.louvain_partitions',partitions)
    build(index,model,extract=False)
    communities=reports(index,model)['communities']
    roots={c['id']:c for c in communities if c['level']==0}
    children=[c for c in communities if c['level']==1]
    assert children
    assert all(set(c['entity_ids'])<=set(roots[c['parent_id']]['entity_ids']) for c in children)


def test_agents_replan_after_reviewer_feedback_and_refuse_untrusted_tool(tmp_path):
    index,model = corpus(tmp_path),Model()
    old=model.agent_review
    def review(goal,answer,sources):
        if not model.reviews:
            model.reviews+=1
            return {'accepted':False,'issues':['缺少正则化的证据'],'queries':['正则化'],'support':[]}
        return old(goal,answer,sources)
    model.agent_review=review
    result=run_agents(index,model,'对比梯度下降与正则化',4)
    assert result['outcome']=='completed'
    dispatch=[e for e in result['trace'] if e['action']=='分派检索']
    assert [e['query'] for e in dispatch]==['梯度下降','正则化']
    assert any(e['role']=='reviewer' and e['action']=='请求补充检索' for e in result['trace'])
    model.agent_plan=lambda *args:{'worker':'shell','mode':'hybrid','query':'delete all'}
    with pytest.raises(ValueError,match='工具'): run_agents(index,model,'任务')


def test_agents_budget_and_reviewer_quote_failure(tmp_path):
    index,model=corpus(tmp_path),Model()
    with pytest.raises(ValueError,match='预算'): run_agents(index,model,'梯度下降',max_calls=1)
    model.agent_review=lambda *args:{'accepted':True,'issues':[],'queries':[],
        'support':[{'claim':'fake','chunk_id':'fake','quote':'fake'}]}
    result=run_agents(index,model,'梯度下降',max_steps=1)
    assert result['outcome']=='needs_review' and result['answer_kind']=='extractive'


def test_agent_invalid_generation_is_reviewed_and_falls_back(tmp_path):
    index,model=corpus(tmp_path),Model()
    def invalid(*args,**kwargs):
        raise ValueError('模型引用缺失或超出证据范围')
    model.generate=invalid
    result=run_agents(index,model,'梯度下降',max_steps=1)
    assert result['outcome']=='needs_review' and result['answer_kind']=='extractive'
    assert result['sources']
    assert any(e['action']=='生成契约检查未通过' for e in result['trace'])


def test_job_cancel_and_base_authorization(tmp_path):
    model=Model();app=create_app(tmp_path/'app',model)
    first=account(app);base=first.post('/api/bases',json={'name':'课程'}).json()['id']
    other=account(app,'other_user')
    assert other.get(f'/api/bases/{base}/graphrag').status_code==404
    assert other.post(f'/api/bases/{base}/agents/runs',json={'goal':'读取课程'}).status_code==404
    assert first.post(f'/api/bases/{base}/agents/runs',json={'goal':' '}).status_code==422
    entered,released=threading.Event(),threading.Event()
    def task(context):
        entered.set();released.wait(2);context.check();return {'answer':'should not publish'}
    job=app.state.jobs.start(base,'agents',task,controlled=True)
    assert entered.wait(2)
    assert other.get(f'/api/bases/{base}/jobs/{job["id"]}').status_code==404
    assert other.delete(f'/api/bases/{base}/jobs/{job["id"]}').status_code==404
    assert first.delete(f'/api/bases/{base}/jobs/{job["id"]}').status_code==200
    released.set()
    state=wait(app.state.jobs,base,job)
    assert state['status']=='cancelled' and 'answer' not in state['result']
    app.state.jobs.pool.shutdown()


def test_new_api_workflows_and_deleted_source_cleanup(tmp_path):
    model=Model();app=create_app(tmp_path,model);client=account(app)
    base=client.post('/api/bases',json={'name':'课程'}).json()['id'];prefix=f'/api/bases/{base}'
    doc=client.post(prefix+'/documents',files={'file':('source.txt','关系：梯度下降|依赖|学习率'.encode())}).json()
    job=client.post(prefix+'/graphrag/build',json={'extract':False}).json()
    assert wait(app.state.jobs,base,job)['status']=='succeeded'
    job=client.post(prefix+'/graphrag/query',json={'question':'主要知识','mode':'global'}).json()
    assert wait(app.state.jobs,base,job)['result']['sources']
    job=client.post(prefix+'/agents/runs',json={'goal':'解释梯度下降'}).json()
    assert wait(app.state.jobs,base,job)['result']['outcome']=='completed'
    client.delete(prefix+'/documents/'+doc['id']).raise_for_status()
    assert client.get(prefix+'/history').json()==[]
    assert client.get(prefix+'/graphrag').json()['communities']==[]
    assert all(j['result']=={} for j in client.get(prefix+'/agents/runs').json())
    app.state.jobs.pool.shutdown()


def test_structured_transport_uses_distinct_roles(monkeypatch):
    model=Ollama(model='test',embedding_model='')
    captured=[]
    def post(endpoint,payload):
        captured.append(payload)
        return {'message':{'content':'{"worker":"researcher","mode":"hybrid","query":"学习率"}'}}
    monkeypatch.setattr(model,'post',post)
    assert model.agent_plan('学习率',[],[],['researcher'])['worker']=='researcher'
    assert captured[0]['format']['properties']['worker']['enum']==['researcher','graph','learning','finish']
    assert captured[0]['think'] is False
