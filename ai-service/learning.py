import json
import random
import time
import uuid


def generate_quiz(store, engine, base_id, count, kind="single"):
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
            if len(options) < 2 and kind in ('single','multiple'): continue
            random.SystemRandom().shuffle(options)
            quiz_id = uuid.uuid4().hex
            stem = f'根据资料，“{r["subject"]}”的“{r["predicate"]}”对象是什么？'
            answer = options.index(r['object'])
            if kind == 'multiple':
                options = sorted(valid)[:6] + distractors[:2]
                random.SystemRandom().shuffle(options)
                answer = json.dumps([i for i,o in enumerate(options) if o in valid])
                stem = f'根据资料，“{r["subject"]}”的“{r["predicate"]}”对象有哪些？从下列选项中选择全部正确项。'
            elif kind == 'judge':
                negate = random.SystemRandom().choice([True,False])
                stem = f'判断：资料{ "未指出" if negate else "指出" }“{r["subject"]} — {r["predicate"]} — {r["object"]}”。'
                options,answer = ['错误','正确'], int(not negate)
            elif kind == 'essay':
                options,answer = [], json.dumps(sorted(set([r['subject'],r['predicate'],r['object']])),ensure_ascii=False)
                stem = f'请用自己的话说明“{r["subject"]}”与“{r["object"]}”的“{r["predicate"]}”关系。'
            elif kind == 'short':
                options,answer = [], r['object']
                stem += ' 请填写资料中的对象名称。'
            db.execute('INSERT INTO quizzes(id,base_id,topic,stem,options,answer,explanation,source,created,kind) VALUES(?,?,?,?,?,?,?,?,?,?)', (quiz_id, base_id, r['subject'], stem, json.dumps(options, ensure_ascii=False), answer, f'资料明确记录：{r["subject"]} — {r["predicate"]} — {r["object"]}。', r['chunk_id'], time.time(), kind))
            rows.append({'id': quiz_id, 'topic': r['subject'], 'stem': stem, 'options': options, 'kind':kind})
            if len(rows) >= count: break
    if not rows: raise ValueError('至少需要两个不同关系对象来构建选项')
    return rows


def submit(store, base_id, quiz_id, selected):
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        q = db.execute('SELECT * FROM quizzes WHERE id=? AND base_id=?', (quiz_id, base_id)).fetchone()
        if not q: raise LookupError('题目不存在')
        kind = q['kind']
        options = json.loads(q['options'])
        answer = q['answer']
        if kind in ('single','judge'):
            if type(selected) is not int or not 0 <= selected < len(options): raise ValueError('选项索引无效')
            correct = selected == answer
        elif kind == 'multiple':
            if not isinstance(selected,list) or not selected or any(type(i) is not int or not 0 <= i < len(options) for i in selected) or len(set(selected)) != len(selected): raise ValueError('多选答案格式无效')
            answer = json.loads(answer)
            correct = set(selected) == set(answer)
        elif kind == 'essay':
            if not isinstance(selected,str) or not selected.strip() or len(selected)>500: raise ValueError('简答内容须为 1–500 字符')
            answer = json.loads(answer)
            hits = sum(word.casefold() in selected.casefold() for word in answer)
            score = round(hits / len(answer),3)
            correct = hits == len(answer)
        else:
            if not isinstance(selected,str) or not selected.strip() or len(selected)>500: raise ValueError('填空答案须为 1–500 字符')
            correct = selected.strip().casefold() == str(answer).strip().casefold()
        stored = json.dumps(selected,ensure_ascii=False) if kind in ('multiple','short','essay') else selected
        if db.execute('SELECT 1 FROM attempts WHERE quiz_id=?', (quiz_id,)).fetchone():
            raise ValueError('题目已经提交，重复提交不会更新掌握度')
        db.execute('INSERT INTO attempts VALUES(?,?,?,?,?)', (uuid.uuid4().hex, quiz_id, stored, int(correct), time.time()))
        return {'correct': correct, 'answer': answer, 'kind':kind, 'score':score if kind=='essay' else int(correct), 'grading_method':'关键词覆盖，不判断推理正确性' if kind=='essay' else '标准答案匹配', 'explanation': q['explanation'], 'source': q['source']}


def progress(store, engine, base_id):
    with store.db() as db:
        rows = [dict(r) for r in db.execute('SELECT q.topic,COUNT(a.id) AS attempts,COALESCE(SUM(a.correct),0) AS correct FROM quizzes q JOIN attempts a ON a.quiz_id=q.id WHERE q.base_id=? GROUP BY q.topic', (base_id,))]
        mistakes = [dict(r) for r in db.execute('SELECT q.id,q.stem,q.topic,q.kind,q.options,q.answer,q.explanation,q.source,a.selected FROM quizzes q JOIN attempts a ON a.quiz_id=q.id WHERE q.base_id=? AND a.correct=0 ORDER BY a.created DESC LIMIT 100', (base_id,))]
    topics = {r['subject'] for r in engine.graph()}
    stats = {r['topic']: r for r in rows}
    mastery = []
    for topic in sorted(topics | set(stats)):
        row = stats.get(topic, {'attempts': 0, 'correct': 0})
        value = (row['correct'] + 1) / (row['attempts'] + 2)
        mastery.append({'topic': topic, 'attempts': row['attempts'], 'correct': row['correct'], 'mastery': round(value, 3)})
    priority = sorted(mastery, key=lambda r: (r['mastery'], -r['attempts'], r['topic']))
    prerequisites = {topic:set() for topic in topics}
    for edge in engine.graph():
        if edge['predicate'] in ('依赖','前置','先修','需要先掌握') and edge['object'] in topics and edge['object'] != edge['subject']:
            prerequisites.setdefault(edge['subject'],set()).add(edge['object'])
    ordered, remaining, covered = [], list(priority), set()
    cycle = False
    while remaining:
        ready = next((r for r in remaining if prerequisites.get(r['topic'],set()) <= covered),None)
        if ready is None:
            cycle = True
            ordered.extend(remaining)
            break
        remaining.remove(ready);ordered.append(ready);covered.add(ready['topic'])
    priority = ordered
    for r in priority: r['prerequisites'] = sorted(prerequisites.get(r['topic'],set()))
    for r in mistakes:
        r['options'] = json.loads(r['options'])
        if r['kind'] in ('multiple','essay'): r['answer'] = json.loads(r['answer'])
    return {'mastery': mastery, 'mistakes': mistakes, 'path': [dict(r, reason='先复习错题与引用原文' if r['attempts'] else '尚未练习，建议先阅读资料') for r in priority], 'prerequisite_cycle':cycle, 'method': 'Beta(1,1) 平滑正确率；小样本启发式，不是经过验证的认知诊断模型'}
