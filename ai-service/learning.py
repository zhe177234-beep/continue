import json
import random
import time
import uuid


def generate_quiz(store, engine, base_id, count):
    relations = engine.graph()
    if not relations:
        raise ValueError('资料中没有可出题的显式知识关系，请先上传示例或补充关系行')
    # Template questions have actual source evidence, not unvalidated LLM output.
    objects = sorted({r['object'] for r in relations})
    rows = []
    random.SystemRandom().shuffle(relations)
    used = set()
    with store.db() as db:
        for r in relations:
            key = (r['subject'], r['predicate'], r['object'])
            if key in used: continue
            used.add(key)
            valid = {edge['object'] for edge in relations if edge['subject'] == r['subject'] and edge['predicate'] == r['predicate']}
            distractors = [x for x in objects if x not in valid]
            random.SystemRandom().shuffle(distractors)
            options = [r['object']] + distractors[:3]
            if len(options) < 2: continue
            random.SystemRandom().shuffle(options)
            quiz_id = uuid.uuid4().hex
            stem = f'根据资料，“{r["subject"]}”的“{r["predicate"]}”对象是什么？'
            db.execute('INSERT INTO quizzes VALUES(?,?,?,?,?,?,?,?,?)', (quiz_id, base_id, r['subject'], stem, json.dumps(options, ensure_ascii=False), options.index(r['object']), f'资料明确记录：{r["subject"]} — {r["predicate"]} — {r["object"]}。', r['chunk_id'], time.time()))
            rows.append({'id': quiz_id, 'topic': r['subject'], 'stem': stem, 'options': options})
            if len(rows) >= count: break
    if not rows: raise ValueError('至少需要两个不同关系对象来构建选项')
    return rows


def submit(store, base_id, quiz_id, selected):
    with store.db() as db:
        q = db.execute('SELECT * FROM quizzes WHERE id=? AND base_id=?', (quiz_id, base_id)).fetchone()
        if not q: raise LookupError('题目不存在')
        if not 0 <= selected < len(json.loads(q['options'])): raise ValueError('选项索引无效')
        if db.execute('SELECT 1 FROM attempts WHERE quiz_id=?', (quiz_id,)).fetchone():
            raise ValueError('题目已经提交，重复提交不会更新掌握度')
        correct = selected == q['answer']
        db.execute('INSERT INTO attempts VALUES(?,?,?,?,?)', (uuid.uuid4().hex, quiz_id, selected, int(correct), time.time()))
        return {'correct': correct, 'answer': q['answer'], 'explanation': q['explanation'], 'source': q['source']}


def progress(store, engine, base_id):
    with store.db() as db:
        rows = [dict(r) for r in db.execute('SELECT q.topic,COUNT(a.id) AS attempts,COALESCE(SUM(a.correct),0) AS correct FROM quizzes q JOIN attempts a ON a.quiz_id=q.id WHERE q.base_id=? GROUP BY q.topic', (base_id,))]
        mistakes = [dict(r) for r in db.execute('SELECT q.id,q.stem,q.topic,q.options,q.answer,q.explanation,q.source,a.selected FROM quizzes q JOIN attempts a ON a.quiz_id=q.id WHERE q.base_id=? AND a.correct=0 ORDER BY a.created DESC LIMIT 100', (base_id,))]
    topics = {r['subject'] for r in engine.graph()}
    stats = {r['topic']: r for r in rows}
    mastery = []
    for topic in sorted(topics | set(stats)):
        row = stats.get(topic, {'attempts': 0, 'correct': 0})
        value = (row['correct'] + 1) / (row['attempts'] + 2)
        mastery.append({'topic': topic, 'attempts': row['attempts'], 'correct': row['correct'], 'mastery': round(value, 3)})
    priority = sorted(mastery, key=lambda r: (r['mastery'], -r['attempts'], r['topic']))
    for r in mistakes: r['options'] = json.loads(r['options'])
    return {'mastery': mastery, 'mistakes': mistakes, 'path': [dict(r, reason='先复习错题与引用原文' if r['attempts'] else '尚未练习，建议先阅读资料') for r in priority], 'method': 'Beta(1,1) 平滑正确率；小样本启发式，不是经过验证的认知诊断模型'}
