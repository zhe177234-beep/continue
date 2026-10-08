"""Hierarchical community GraphRAG with atomic indexes and source-grounded queries.

This is the application's own GraphRAG implementation, not Microsoft's package.
Louvain creates a nested hierarchy; global search maps every top-level report.
"""
import hashlib
import json
import math
import re
import unicodedata
from collections import defaultdict

import networkx as nx

from engine import tokens


def normalize(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', value)).strip().casefold()


def stable_id(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def snapshot(index):
    with index.connect() as db:
        db.execute('BEGIN')
        return snapshot_db(db)


def snapshot_db(db):
    sources = [dict(r) for r in db.execute('SELECT c.id AS chunk_id,c.document_id,c.page,c.text,d.name FROM chunks c JOIN documents d ON d.id=c.document_id ORDER BY c.id')]
    edges = [dict(r) for r in db.execute('SELECT DISTINCT * FROM relations ORDER BY chunk_id,subject,predicate,object')]
    fingerprint = hashlib.sha256(json.dumps([sources,edges],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return sources, edges, fingerprint


def signature(model):
    return json.dumps({'schema':1,'chat':model.model,'embedding':model.embedding_model},sort_keys=True)


def status(index, model):
    with index.connect() as db:
        db.execute('BEGIN')
        sources, edges, revision = snapshot_db(db)
        meta = {r['key']:r['value'] for r in db.execute('SELECT * FROM graph_meta')}
        entities = db.execute('SELECT COUNT(*) FROM graph_entities').fetchone()[0]
        communities = db.execute('SELECT COUNT(*) FROM graph_communities').fetchone()[0]
    ready = meta.get('revision') == revision and meta.get('signature') == signature(model)
    return {'ready':ready,'stale':bool(meta) and not ready,'chunks':len(sources),'relations':len(edges),
            'entities':entities,'communities':communities,'revision':revision,
            'levels':json.loads(meta.get('levels','[]')),'report_calls':int(meta.get('report_calls','0'))}


def checked_findings(items, sources, limit=4):
    if not isinstance(items,list) or len(items)>limit: raise ValueError('社区报告发现格式无效')
    lookup = {s['chunk_id']:s for s in sources}
    findings = []
    for item in items:
        if not isinstance(item,dict): continue
        text, quote, chunk = (item.get(k) for k in ('text','quote','chunk_id'))
        if (isinstance(text,str) and 0<len(text.strip())<=1000 and isinstance(quote,str)
                and 0<len(quote.strip())<=600 and chunk in lookup and quote.strip() in lookup[chunk]['text']):
            findings.append({'text':text.strip(),'quote':quote.strip(),'chunk_id':chunk})
    return findings


def build(index, model, context=None, extract=True, max_calls=256):
    if not model.model: raise ValueError('GraphRAG 社区报告需要生成模型')
    if extract:
        from jobs import extract_relations
        extraction = extract_relations(index,model,context)
    else:
        extraction = {'added':0,'processed':0}
    sources, edges, revision = snapshot(index)
    if not sources: raise ValueError('请先上传资料')
    source_by_id = {s['chunk_id']:s for s in sources}
    entities, graph = {}, nx.Graph()
    by_chunk = defaultdict(set)
    for edge in edges:
        pair = []
        for key in ('subject','object'):
            name = edge[key]
            entity_id = stable_id('entity:'+normalize(name))
            entity = entities.setdefault(entity_id,{'id':entity_id,'name':name,'aliases':set(),'chunks':set(),'description':[]})
            entity['aliases'].add(name)
            entity['chunks'].add(edge['chunk_id'])
            by_chunk[edge['chunk_id']].add(entity_id)
            pair.append(entity_id)
            graph.add_node(entity_id)
        if pair[0] != pair[1]:
            old = graph.get_edge_data(*pair,default={}).get('weight',0)
            graph.add_edge(*pair,weight=old+1)
    # Chunks without extracted relations still belong to document communities.
    for source in sources:
        if not by_chunk[source['chunk_id']]:
            eid = stable_id('document:'+source['document_id'])
            entity = entities.setdefault(eid,{'id':eid,'name':source['name'],'aliases':{source['name']},'chunks':set(),'description':[]})
            entity['chunks'].add(source['chunk_id'])
            by_chunk[source['chunk_id']].add(eid)
            graph.add_node(eid)
    for entity in entities.values():
        entity['description'] = '\n'.join(source_by_id[c]['text'] for c in sorted(entity['chunks']))[:1200]
    partitions = list(nx.community.louvain_partitions(graph,seed=42)) if graph.number_of_edges() else [[{n} for n in sorted(graph)]]
    partitions.reverse()  # Coarsest level is zero, children have higher levels.
    communities, previous = [], []
    for level, partition in enumerate(partitions):
        current = []
        for members in sorted(partition,key=lambda group:tuple(sorted(group))):
            nodes = sorted(members)
            chunks = sorted(set().union(*(entities[e]['chunks'] for e in nodes)))
            parent = next((p['id'] for p in previous if set(nodes)<=set(p['entity_ids'])),None)
            community = {'id':stable_id(f'{level}:'+','.join(nodes)),'level':level,'parent_id':parent,
                         'entity_ids':nodes,'chunk_ids':chunks}
            current.append(community)
        communities.extend(current)
        previous = current
    calls = sum(math.ceil(len(c['chunk_ids'])/8) for c in communities)
    if calls>max_calls: raise ValueError(f'社区报告需要 {calls} 次模型调用，超过预算 {max_calls}，请拆分知识库')
    done = 0
    for community in communities:
        findings, titles, summaries, fallbacks = [], [], [], 0
        for offset in range(0,len(community['chunk_ids']),8):
            if context: context.update(stage='社区报告',completed=done,total=calls,communities=len(communities),entities=len(entities))
            batch = [source_by_id[c] for c in community['chunk_ids'][offset:offset+8]]
            report = model.graph_report([entities[e]['name'] for e in community['entity_ids']],batch)
            valid = checked_findings(report.get('findings'),batch)
            if not valid:
                # Preserve all original evidence if a small model fails its format contract.
                valid = [{'text':s['text'],'quote':s['text'],'chunk_id':s['chunk_id']} for s in batch]
                fallbacks += 1
            findings.extend(valid)
            titles.append(str(report.get('title',''))[:120])
            summaries.append(str(report.get('summary',''))[:1500])
            done += 1
        community['report'] = {'title':next((t for t in titles if t.strip()),'知识社区'),
            'summary':'\n'.join(summaries)[:6000],'findings':findings,'extractive_batches':fallbacks}
    vectors = {}
    if model.embedding_model:
        rows = sorted(entities.values(),key=lambda e:e['id'])
        for offset in range(0,len(rows),16):
            if context: context.update(stage='实体向量',completed=offset,total=len(rows))
            batch = rows[offset:offset+16]
            data = model.embed([e['name']+'\n'+e['description'][:600] for e in batch])
            if len(data)!=len(batch): raise ValueError('实体向量数量无效')
            vectors.update({e['id']:v for e,v in zip(batch,data)})
    if context: context.check()
    with index.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        # Serialize publication against upload/delete/extraction; no stale index is published.
        if snapshot_db(db)[2]!=revision: raise ValueError('构建期间资料或关系已变化，请重新构建 GraphRAG')
        index.invalidate_graph(db)
        db.executemany('INSERT INTO graph_entities VALUES(?,?,?,?,?,?)',[
            (e['id'],e['name'],json.dumps(sorted(e['aliases']),ensure_ascii=False),json.dumps(sorted(e['chunks'])),
             e['description'],json.dumps(vectors[e['id']]) if e['id'] in vectors else None) for e in entities.values()])
        db.executemany('INSERT INTO graph_communities VALUES(?,?,?,?,?,?)',[
            (c['id'],c['level'],c['parent_id'],json.dumps(c['entity_ids']),json.dumps(c['chunk_ids']),json.dumps(c['report'],ensure_ascii=False)) for c in communities])
        meta = {'revision':revision,'signature':signature(model),'levels':json.dumps(sorted({c['level'] for c in communities})),
                'report_calls':str(calls)}
        db.executemany('INSERT INTO graph_meta VALUES(?,?)',list(meta.items()))
    return {'entities':len(entities),'communities':len(communities),'report_calls':calls,
            'levels':len(partitions),'chunks':len(sources),'extraction':extraction,'revision':revision}


def load(index, model):
    with index.connect() as db:
        db.execute('BEGIN')
        revision = snapshot_db(db)[2]
        meta = {r['key']:r['value'] for r in db.execute('SELECT * FROM graph_meta')}
        if meta.get('revision')!=revision or meta.get('signature')!=signature(model):
            raise ValueError('GraphRAG 索引未建立或已过期，请在知识关系页重新构建')
        entities = [dict(r) for r in db.execute('SELECT * FROM graph_entities ORDER BY id')]
        communities = [dict(r) for r in db.execute('SELECT * FROM graph_communities ORDER BY level,id')]
    for entity in entities:
        entity['aliases'] = json.loads(entity['aliases'])
        entity['chunk_ids'] = json.loads(entity['chunk_ids'])
        entity['vector'] = json.loads(entity['vector']) if entity['vector'] else None
    for community in communities:
        for key in ('entity_ids','chunk_ids','report'): community[key] = json.loads(community[key])
    return entities,communities,revision


def reports(index, model):
    ready = status(index,model)
    if not ready['ready']: return {'status':ready,'communities':[]}
    _, communities, _ = load(index,model)
    return {'status':ready,'communities':communities}


def cosine(a,b):
    if len(a)!=len(b): return 0
    return sum(x*y for x,y in zip(a,b))/(math.sqrt(sum(x*x for x in a))*math.sqrt(sum(y*y for y in b)) or 1)


def grounded_answer(model, question, result, generate, history=None, context=''):
    result['answer_kind'] = 'extractive'
    result['answer'] = '\n\n'.join(f'[{i}] {s["text"]}' for i,s in enumerate(result['sources'],1)) or '资料中没有找到足够相关的证据。'
    if generate and model.model and result['sources']:
        try:
            prompt = question + ('\n检索背景（仅辅助组织答案，事实必须以原文证据为准）：\n'+context[:8000] if context else '')
            prompt += '\n直接回答问题。每个主要结论后必须标注所给原文的引用编号，例如 [1]；不要只描述检索过程。'
            text = model.generate(prompt,result['sources'],history=history) if history else model.generate(prompt,result['sources'])
            citations = [int(x) for x in re.findall(r'\[(\d+)\]',text)]
            if not citations or any(i<1 or i>len(result['sources']) for i in citations): raise ValueError('引用无效')
            result.update(answer=text,answer_kind='generated')
        except Exception:
            result['warning'] = '生成失败或引用无效，已返回原文证据'
    return result


def query(index, model, question, mode, k=5, generate=True, history=None, context=None, level=0):
    entities, communities, indexed_revision = load(index,model)
    sources, edges, revision = snapshot(index)
    if revision!=indexed_revision: raise ValueError('资料已变化，请重新构建 GraphRAG')
    lookup = {s['chunk_id']:dict(s,score=0.0) for s in sources}
    if mode=='local':
        seeds = {e['id'] for e in entities if any(normalize(alias) in normalize(question) for alias in e['aliases'])}
        if model.embedding_model and any(e['vector'] for e in entities):
            if context: context.check()
            vector = model.embed([question])[0]
            ranked = sorted(((cosine(vector,e['vector']),e['id']) for e in entities if e['vector']),reverse=True)
            seeds.update(eid for score,eid in ranked[:5] if score>=.35)
        selected, frontier = set(seeds),set(seeds)
        adjacency = defaultdict(set)
        for edge in edges:
            a,b = (stable_id('entity:'+normalize(edge[key])) for key in ('subject','object'))
            adjacency[a].add(b);adjacency[b].add(a)
        for _ in range(2):
            frontier = set().union(*(adjacency[e] for e in frontier))-selected if frontier else set()
            selected.update(frontier)
        candidates = index.search(question,'hybrid',10)['sources']
        scores = {s['chunk_id']:s['score'] for s in candidates}
        for entity in entities:
            if entity['id'] in selected:
                for cid in entity['chunk_ids']: scores[cid] = scores.get(cid,0)+(.2 if entity['id'] in seeds else .1)
        chosen = sorted(scores,key=lambda cid:(-scores[cid],cid))[:k]
        community_context = [c for c in communities if c['level']==0 and selected.intersection(c['entity_ids'])]
        result = {'mode':'graphrag-local','sources':[dict(lookup[cid],score=scores[cid]) for cid in chosen],
                  'graph_context':{'entities':[e['name'] for e in entities if e['id'] in selected],
                                   'community_ids':[c['id'] for c in community_context]}}
        background = '\n'.join(c['report']['summary'] for c in community_context)
    elif mode=='global':
        roots = [c for c in communities if c['level']==level]
        if not roots: raise ValueError('选定的社区层级不存在')
        points, failures = [],0
        for position,community in enumerate(roots):
            if context: context.update(stage='全局社区检索',completed=position,total=len(roots))
            report = community['report']
            candidates = report['findings']
            if generate and model.model:
                # Large reports are mapped in batches, so every finding is considered.
                candidates = []
                for offset in range(0,len(report['findings']),8):
                    if context: context.check()
                    batch = dict(report,findings=report['findings'][offset:offset+8],summary=report['summary'][:1500])
                    try:
                        mapped = model.graph_map(question,batch).get('points')
                        if not isinstance(mapped,list) or len(mapped)>4: raise ValueError('Map 结果无效')
                        for item in mapped:
                            if not isinstance(item,dict): raise ValueError('Map 要点无效')
                            finding,score,text = (item.get(key) for key in ('finding','score','text'))
                            if type(finding) is not int or not 1<=finding<=len(batch['findings']): raise ValueError('Map 发现编号无效')
                            if type(score) is not int or not 0<=score<=100 or not isinstance(text,str) or not 0<len(text)<=1000: raise ValueError('Map 要点格式无效')
                            if score>0:
                                # Source identifiers and quotations come from the server,
                                # never from the model's transcription of long hashes.
                                original = batch['findings'][finding-1]
                                candidates.append(dict(original,text=text,score=score))
                    except Exception:
                        failures += 1
                        candidates.extend(dict(f,score=1) for f in batch['findings'])
            for item in candidates:
                points.append(dict(item,community_id=community['id'],score=item.get('score',1)))
        points.sort(key=lambda p:(-p['score'],p['community_id'],p['chunk_id']))
        chosen = []
        for point in points:
            if point['chunk_id'] not in chosen: chosen.append(point['chunk_id'])
            if len(chosen)>=k: break
        result = {'mode':'graphrag-global','sources':[dict(lookup[cid],score=max(p['score'] for p in points if p['chunk_id']==cid)) for cid in chosen],
                  'graph_context':{'communities_scanned':len(roots),'communities_total':len(roots),
                                   'map_failures':failures,'points':len(points),'community_ids':[c['id'] for c in roots]}}
        background = '\n'.join(p['text'] for p in points if p['chunk_id'] in chosen)[:8000]
        if failures: result['warning']='部分社区 Map 失败，已使用带原文的报告发现'
    else:
        raise ValueError('无效 GraphRAG 检索模式')
    if context: context.check()
    result = grounded_answer(model,question,result,generate,history,background)
    if snapshot(index)[2]!=revision: raise ValueError('检索期间资料已变化，请重新提问')
    return result
