"""Bounded autonomous planner / specialist / tutor / reviewer collaboration.

Roles use separate model messages. The planner chooses tools and changes queries
using reviewer feedback. Tools are server-owned, read-only, and base-scoped.
The event trace exposes actions/results, never hidden model reasoning.
"""
import re
import time

from graphrag import query as graph_query, snapshot, status as graph_status, checked_findings
from retrieval import retrieve


class BudgetModel:
    def __init__(self, model, context, limit):
        self.raw, self.context, self.limit = model, context, limit
        self.calls = 0
        self.model, self.embedding_model = model.model, model.embedding_model

    def __getattr__(self, name):
        fn = getattr(self.raw,name)
        if name not in {'generate','embed','graph_map','agent_plan','agent_review'}: return fn
        def call(*args,**kwargs):
            if self.context: self.context.check()
            if self.calls>=self.limit: raise ValueError('Agent 模型调用预算已用尽')
            self.calls += 1
            return fn(*args,**kwargs)
        return call


def cited(text, sources):
    if not isinstance(text,str) or not text.strip() or len(text)>20000: return False
    citations = [int(x) for x in re.findall(r'\[(\d+)\]',text)]
    return bool(citations) and all(1<=i<=len(sources) for i in citations)


def run(index, model, goal, max_steps=4, context=None, learning=None, history=None, max_calls=64):
    if not model.model: raise ValueError('自主 Agent 需要先配置生成模型')
    model = BudgetModel(model,context,max_calls)
    revision = snapshot(index)[2]
    trace, observations, feedback, pool, used = [],[],[],{},set()
    accepted, answer = False,''
    graph_ready = graph_status(index,model)['ready']
    available = ['researcher','learning']+(['graph'] if graph_ready else [])
    started = time.monotonic()

    def check():
        if context: context.check()
        if snapshot(index)[2]!=revision: raise ValueError('Agent 执行期间资料或关系已变化，请重新启动任务')

    def event(role, action, **details):
        trace.append({'step':len(trace)+1,'role':role,'action':action,**details})
        if context: context.update(stage=action,goal=goal,trace=trace,model_calls=model.calls)

    for step in range(max_steps):
        check()
        plan = model.agent_plan(goal,observations[-4:],feedback,available)
        worker, mode, search = (plan.get(k) for k in ('worker','mode','query'))
        if worker=='finish' and accepted:
            event('planner','完成任务')
            break
        if worker not in available or mode not in ('hybrid','local','global') or not isinstance(search,str) or not search.strip() or len(search)>1000:
            raise ValueError('规划 Agent 返回了无效或不可用的工具，请检查模型或先构建 GraphRAG')
        search = search.strip()
        identity = (worker,mode,search)
        if identity in used:
            # Reviewer queries supply a concrete repair when the planner repeats itself.
            alternatives = [q for q in feedback if isinstance(q,str) and 0<len(q.strip())<=1000 and ('researcher','hybrid',q.strip()) not in used]
            if not alternatives:
                event('planner','停止重复检索')
                break
            worker,mode,search = 'researcher','hybrid',alternatives[0].strip()
            identity = (worker,mode,search)
        used.add(identity)
        event('planner','分派检索',worker=worker,mode=mode,query=search,round=step+1)
        if worker=='graph':
            result = graph_query(index,model,search,mode if mode in ('local','global') else 'local',10,False,context=context)
        elif worker=='learning':
            record = learning() if learning else {'path':[],'mastery':[]}
            topics = [row['topic'] for row in record.get('path',[])[:3]]
            lookup = (' '.join(topics)+' '+search)[:1000]
            result = retrieve(index,model,lookup,'hybrid',10)
            event('learning','读取学习记录',topics=topics,attempts=sum(r['attempts'] for r in record.get('mastery',[])))
        else:
            result = retrieve(index,model,search,'hybrid',10)
        check()
        for source in result['sources']:
            pool.setdefault(source['chunk_id'],source)
        event(worker,'找到原文证据',sources=len(result['sources']),retrieval=result['mode'])
        observations.append({'query':search,'worker':worker,'sources':[{'chunk_id':s['chunk_id'],'text':s['text'][:300]} for s in result['sources'][:6]]})
        if not pool:
            feedback = ['请换一种表述寻找相关原文。']
            event('reviewer','缺少资料依据')
            continue
        # Merge latest specialist results first, then retain earlier complementary evidence.
        ordered = {s['chunk_id']:s for s in result['sources']}
        ordered.update({key:source for key,source in pool.items() if key not in ordered})
        sources = list(ordered.values())[:20]
        prompt = goal+'\n请回答用户的全部目标；缺少证据的部分明确说明，不要补写。'
        if feedback: prompt += '\n上一轮审查需修正：'+'；'.join(feedback)[:1800]
        try:
            answer = model.generate(prompt,sources,history=history) if history else model.generate(prompt,sources)
        except ValueError:
            if model.calls>=model.limit: raise
            accepted = False
            feedback = ['生成结果为空、过长或引用无效，请重新查找证据并用有效编号回答。']
            event('reviewer','生成契约检查未通过')
            continue
        check()
        event('tutor','生成回答',sources=len(sources))
        if not cited(answer,sources):
            accepted = False
            feedback = ['回答必须为每个主要结论使用有效原文引用编号。']
            event('reviewer','引用检查未通过')
            continue
        review = model.agent_review(goal,answer,sources)
        support = checked_findings([{'text':r.get('claim'),'chunk_id':r.get('chunk_id'),'quote':r.get('quote')}
                                   for r in review.get('support',[]) if isinstance(r,dict)],sources,8)
        issues, queries = review.get('issues'),review.get('queries')
        if not isinstance(issues,list) or not isinstance(queries,list): raise ValueError('审查 Agent 输出无效')
        accepted = review.get('accepted') is True and not issues and bool(support) and len(support)==len(review.get('support',[]))
        feedback = [item[:1000] for item in issues+queries if isinstance(item,str)][:7]
        if not accepted and not feedback:
            feedback = ['请核对原文并修正证据引用，回答学习目标中的核心问题。']
        event('reviewer','审查通过' if accepted else '请求补充检索',issues=feedback,supported_claims=len(support),
              declared_claims=len(review.get('support',[])),model_accepted=review.get('accepted') is True)
        if accepted:
            # Planner observes the accepted review and decides whether more work is needed.
            observations.append({'answer':answer[:2000],'review':'accepted'})
            if step==max_steps-1: break
    check()
    if not pool:
        sources = []
        answer = '当前知识库没有足够证据完成目标，请补充资料后再运行。'
        kind, outcome = 'extractive','insufficient_evidence'
    elif accepted:
        kind,outcome = 'generated','completed'
    else:
        sources = list(pool.values())[:20]
        answer = '\n\n'.join(f'[{i}] {s["text"]}' for i,s in enumerate(sources,1))
        kind,outcome = 'extractive','needs_review'
    event('supervisor','任务结束',outcome=outcome)
    return {'goal':goal,'answer':answer,'answer_kind':kind,'mode':'multi-agent','sources':sources,
            'trace':trace,'outcome':outcome,'model_calls':model.calls,'elapsed_seconds':round(time.monotonic()-started,2),
            'warning':'审查是模型判定加逐字证据与引用检查，不能保证事实正确。' if accepted else '未通过完整审查，返回原文证据，请人工核对。'}
