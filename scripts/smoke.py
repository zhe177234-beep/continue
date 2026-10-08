"""Exercise an already running full stack; creates an isolated test account/base."""
import argparse
import time
from pathlib import Path
import httpx


def run(url):
    with httpx.Client(base_url=url.rstrip('/'), timeout=60, trust_env=False) as client:
        for attempt in range(60):
            try:
                health=client.get('/api/health');health.raise_for_status()
                if health.json().get('status')=='ok': break
            except httpx.HTTPError:
                if attempt==59: raise
                time.sleep(2)
        credentials={'username':f'smoke_{int(time.time()*1000)}','password':'smoke-password-123'}
        r=client.post('/api/auth/register',json=credentials);r.raise_for_status()
        r=client.post('/api/auth/login',json=credentials);r.raise_for_status()
        r=client.post('/api/bases',json={'name':'部署验证'});r.raise_for_status();base=r.json()['id']
        prefix=f'/api/bases/{base}'
        source=Path(__file__).resolve().parents[1]/'datasets/machine-learning.md'
        r=client.post(prefix+'/documents',files={'file':('sample.md',source.read_bytes())});r.raise_for_status();doc=r.json()['id']
        r=client.post(prefix+'/ask',json={'question':'学习率如何影响梯度下降？','generate':False});r.raise_for_status()
        assert r.json()['sources'] and r.json()['sources'][0]['document_id']==doc
        r=client.post(prefix+'/quizzes',json={'count':3});r.raise_for_status();quiz=r.json()[0]
        r=client.post(prefix+f'/quizzes/{quiz["id"]}/submit',json={'selected':0});r.raise_for_status()
        r=client.get(prefix+'/progress');r.raise_for_status()
        assert sum(t['attempts'] for t in r.json()['mastery'])==1
        r=client.delete(prefix+'/documents/'+doc);r.raise_for_status()
        assert client.get(prefix+'/documents').json()==[]
        client.post('/api/auth/logout',json={}).raise_for_status()
        assert client.get('/api/auth/me').status_code==401
    print('通过：健康检查、注册登录、资料上传、问答引用、出题批改、学习统计、删除与退出')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://localhost:8080');args=parser.parse_args();run(args.url)
