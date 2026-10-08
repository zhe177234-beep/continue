import json
import math


def reindex(engine, model):
    with engine.connect() as db:
        rows = [dict(r) for r in db.execute('SELECT id,text FROM chunks ORDER BY id')]
    if not rows: return {'indexed': 0}
    vectors = []
    for offset in range(0, len(rows), 16):
        vectors.extend(model.embed([r['text'] for r in rows[offset:offset + 16]]))
    if len({len(v) for v in vectors}) > 1: raise ValueError('模型返回向量维度不一致')
    with engine.connect() as db:
        db.executemany('INSERT OR REPLACE INTO embeddings VALUES(?,?,?)', [(r['id'], model.embedding_model, json.dumps(v)) for r, v in zip(rows, vectors)])
    return {'indexed': len(rows), 'model': model.embedding_model, 'dimensions': len(vectors[0])}


def retrieve(engine, model, question, mode, k):
    base = engine.search(question, 'hybrid' if mode == 'semantic' else mode, k=10)
    if not model.embedding_model:
        if mode == 'semantic': raise ValueError('请先配置 EMBEDDING_MODEL 并建立语义索引')
        base['sources'] = base['sources'][:k]
        return base
    with engine.connect() as db:
        rows = [dict(r) for r in db.execute('SELECT c.*,d.name,e.vector FROM embeddings e JOIN chunks c ON e.chunk_id=c.id JOIN documents d ON d.id=c.document_id WHERE e.model=? ORDER BY c.id', (model.embedding_model,))]
        total = db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
    if not rows:
        if mode == 'semantic': raise ValueError('尚未建立语义索引，请点击“更新语义索引”')
        base['sources'] = base['sources'][:k]
        return base
    if mode not in {'semantic', 'hybrid', 'graph', 'auto'}:
        base['sources'] = base['sources'][:k]
        return base
    try:
        q = model.embed([question])[0]
        ranked = []
        for row in rows:
            v = json.loads(row.pop('vector'))
            if len(q) != len(v): raise ValueError('索引维度变化，请重新建立索引')
            score = sum(a*b for a,b in zip(q,v)) / (math.sqrt(sum(a*a for a in q))*math.sqrt(sum(a*a for a in v)) or 1)
            if score >= .25:
                ranked.append({'chunk_id': row['id'], 'document_id': row['document_id'], 'name': row['name'], 'page': row['page'], 'text': row['text'], 'score': score})
        ranked.sort(key=lambda r: (-r['score'], r['chunk_id']))
        if mode == 'semantic':
            sources = ranked[:k]
            base['mode'] = 'semantic'
        else:
            merged = {}
            for items in [base['sources'], ranked[:10]]:
                for rank, item in enumerate(items, 1):
                    key = item['chunk_id']
                    if key not in merged: merged[key] = dict(item, score=0)
                    merged[key]['score'] += 1 / (60 + rank)
            sources = sorted(merged.values(), key=lambda r: (-r['score'],r['chunk_id']))[:k]
            base['mode'] += '+semantic'
        base['sources'] = sources
        if len(rows) < total: base['warning'] = '部分资料未建立语义索引，请更新索引'
    except Exception:
        if mode == 'semantic': raise ValueError('语义检索失败，请检查模型服务并更新索引') from None
        base['sources'] = base['sources'][:k]
        base['warning'] = '语义模型不可用，已降级为离线检索'
    return base
