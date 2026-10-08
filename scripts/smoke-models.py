"""Verify a deployed Ollama integration using an isolated test account."""
import argparse
import time

import httpx


def run(url):
    with httpx.Client(base_url=url.rstrip('/'), timeout=180, trust_env=False) as client:
        def post(path, **kwargs):
            response = client.post(path, **kwargs)
            response.raise_for_status()
            return response.json()

        health = client.get('/api/health')
        health.raise_for_status()
        assert health.json()['chat_model_configured']
        assert health.json()['embedding_model_configured']
        credentials = {'username': f'model_check_{int(time.time()*1000)}', 'password': 'model-check-password-123'}
        post('/api/auth/register', json=credentials)
        post('/api/auth/login', json=credentials)
        base = post('/api/bases', json={'name': 'Local model verification'})['id']
        prefix = f'/api/bases/{base}'
        content = '学习率影响梯度下降。学习率过大会导致梯度下降震荡，学习率过小会导致收敛缓慢。'
        doc = post(prefix+'/documents', files={'file': ('model-check.txt', content.encode())})['id']
        try:
            index = post(prefix+'/index', json={})
            assert index['indexed'] > 0 and index['dimensions'] > 0, index
            print('PASS embedding index:', index, flush=True)
            answer = post(prefix+'/ask', json={'question': '学习率过大会导致什么？', 'mode': 'semantic', 'generate': True})
            assert answer['sources'] and answer['answer_kind'] == 'generated', answer
            print('PASS semantic retrieval and generated citations:', answer['answer'], flush=True)
            job = post(prefix+'/jobs/relations', json={})
            deadline = time.monotonic()+240
            while time.monotonic() < deadline:
                response = client.get(prefix+'/jobs')
                response.raise_for_status()
                state = next(item for item in response.json() if item['id'] == job['id'])
                if state['status'] not in ('queued', 'running'):
                    assert state['status'] == 'succeeded', state
                    print('PASS relation extraction:', state['result'], flush=True)
                    break
                time.sleep(1)
            else:
                raise TimeoutError('Relation extraction did not complete within 240 seconds')
        finally:
            client.delete(prefix+'/documents/'+doc).raise_for_status()
            client.post('/api/auth/logout', json={}).raise_for_status()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://localhost:8080')
    run(parser.parse_args().url)
