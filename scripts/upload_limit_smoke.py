"""Verify the exact 100 MiB limit through Nginx, Java and FastAPI."""
import argparse
import io
import time
import zipfile

import httpx
from docx import Document


def run(url):
    document=Document();document.add_paragraph('Learning rate controls the gradient descent step size.')
    buffer=io.BytesIO();document.save(buffer)
    name='padding.bin';limit=100*1024*1024
    padding=limit-len(buffer.getvalue())-(30+len(name)+46+len(name))
    with zipfile.ZipFile(buffer,'a',compression=zipfile.ZIP_STORED) as archive: archive.writestr(name,b'x'*padding)
    payload=buffer.getvalue();assert len(payload)==limit
    with httpx.Client(base_url=url,timeout=120,trust_env=False) as client:
        credentials={'username':f'upload_{int(time.time()*1000)}','password':'upload-limit-password-123'}
        client.post('/api/auth/register',json=credentials).raise_for_status()
        client.post('/api/auth/login',json=credentials).raise_for_status()
        response=client.post('/api/bases',json={'name':'Upload limit verification'});response.raise_for_status();prefix='/api/bases/'+response.json()['id']
        response=client.post(prefix+'/documents',files={'file':('hundred-mib.docx',payload)})
        response.raise_for_status();document_id=response.json()['id']
        try:
            assert response.json()['chunks']>0
            response=client.post(prefix+'/documents',files={'file':('too-large.docx',payload+b'x')})
            assert response.status_code in (400,413),response.text
            print('PASS exact 100 MiB DOCX accepted; 100 MiB + 1 byte rejected through full stack',flush=True)
        finally:
            client.delete(prefix+'/documents/'+document_id).raise_for_status()
            client.post('/api/auth/logout',json={}).raise_for_status()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://localhost:8080');run(parser.parse_args().url)
