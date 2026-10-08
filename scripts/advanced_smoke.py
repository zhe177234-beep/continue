"""Exercise deployed community GraphRAG and autonomous agents with real models."""
import argparse
import json
import time

import httpx


def run(url):
    with httpx.Client(base_url=url.rstrip('/'),timeout=210,trust_env=False) as client:
        def post(path,body):
            response=client.post(path,json=body);response.raise_for_status();return response.json()
        def wait(prefix,job):
            deadline=time.monotonic()+1200
            previous=None
            while time.monotonic()<deadline:
                response=client.get(prefix+'/jobs/'+job['id']);response.raise_for_status();state=response.json()
                stage=(state['status'],state['result'].get('stage'),state['result'].get('completed'),len(state['result'].get('trace',[])))
                if stage!=previous:
                    print(json.dumps({'job':state['kind'],'status':stage[0],'stage':stage[1],'completed':stage[2],'events':stage[3]},ensure_ascii=False),flush=True)
                    previous=stage
                if state['status'] not in ('queued','running'):
                    assert state['status']=='succeeded',state
                    return state['result']
                time.sleep(2)
            raise TimeoutError('Advanced workflow timed out')
        credentials={'username':f'advanced_{int(time.time()*1000)}','password':'advanced-smoke-password-123'}
        post('/api/auth/register',credentials);post('/api/auth/login',credentials)
        base=post('/api/bases',{'name':'GraphRAG and Agent verification'})['id'];prefix=f'/api/bases/{base}'
        documents=[]
        try:
            for name,text in [('optimization.txt','梯度下降依赖学习率。学习率控制参数更新的步长。\n关系：梯度下降|依赖|学习率'),
                              ('regularization.txt','正则化减少过拟合，限制模型复杂度。\n关系：正则化|减少|过拟合')]:
                response=client.post(prefix+'/documents',files={'file':(name,text.encode())});response.raise_for_status();documents.append(response.json()['id'])
            indexed=wait(prefix,post(prefix+'/graphrag/build',{'extract':True}))
            assert indexed['entities']>=4 and indexed['communities']>=2,indexed
            print('PASS hierarchical communities and reports:',json.dumps(indexed,ensure_ascii=False),flush=True)
            answer=wait(prefix,post(prefix+'/graphrag/query',{'question':'资料中有哪些主要知识主题？','mode':'global'}))
            assert answer['sources'] and answer['answer_kind']=='generated',answer
            assert answer['graph_context']['communities_scanned']==answer['graph_context']['communities_total']>=2,answer
            print('PASS global map-reduce:',answer['answer'],flush=True)
            local=post(prefix+'/ask',{'question':'学习率控制什么？','mode':'graphrag-local'})
            assert local['sources'] and local['answer_kind']=='generated',local
            print('PASS GraphRAG local:',local['answer'],flush=True)
            result=wait(prefix,post(prefix+'/agents/runs',{'goal':'根据资料说明学习率控制什么，并给出原文引用。','max_steps':4}))
            assert result['sources'] and result['outcome']=='completed',result
            roles={event['role'] for event in result['trace']}
            assert {'planner','tutor','reviewer'}<=roles,result
            print('PASS autonomous agents:',json.dumps({'answer':result['answer'],'roles':sorted(roles),'calls':result['model_calls']},ensure_ascii=False),flush=True)
        finally:
            for document in documents: client.delete(prefix+'/documents/'+document).raise_for_status()
            client.post('/api/auth/logout',json={}).raise_for_status()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://localhost:8080')
    run(parser.parse_args().url)
