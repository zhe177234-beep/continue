import base64
import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ai-service'))
from engine import Engine, parse_document
from app import handler_for


class SystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = Engine(Path(self.temp.name) / 'test.db')

    def tearDown(self):
        self.temp.cleanup()

    def seed(self):
        return self.engine.ingest('ml.md', (ROOT / 'datasets/machine-learning.md').read_bytes())

    def test_persistence_duplicate_and_cascade(self):
        result = self.seed()
        self.assertTrue(self.seed()['duplicate'])
        new = Engine(self.engine.path)
        self.assertEqual(len(new.documents()), 1)
        self.assertTrue(new.graph())
        self.assertTrue(new.delete(result['id']))
        self.assertEqual(new.graph(), [])
        self.assertEqual(new.search('梯度下降')['sources'], [])

    def test_citations_and_modes(self):
        self.seed()
        for mode in ['bm25', 'cosine', 'hybrid', 'graph', 'auto']:
            result = self.engine.answer('梯度下降和学习率的关系', mode)
            self.assertTrue(result['sources'])
            self.assertIn('梯度下降', result['sources'][0]['text'])
            self.assertEqual(result['sources'][0]['page'], 1)
            self.assertEqual(result['answer_kind'], 'extractive')
        self.assertEqual(self.engine.answer('学习率的依赖关系')['mode'], 'graph')
        self.assertEqual(self.engine.answer('火星移民的交通费')['sources'], [])

    def test_input_validation(self):
        for name, data in [('bad.exe', b'hello'), ('a.txt', b'\xff'), ('a.txt', b''), ('a.txt', b' '), ('a.pdf', b'not pdf')]:
            with self.assertRaises(ValueError):
                self.engine.ingest(name, data)
        for question, mode, k in [('', 'auto', 5), (None, 'auto', 5), ('x', 'oops', 5), ('x', 'auto', True), ('x', 'auto', 11)]:
            with self.assertRaises(ValueError):
                self.engine.search(question, mode, k)
        self.assertEqual(self.engine.documents(), [])

    def test_pdf_page_provenance(self):
        try:
            from pypdf import PdfWriter
        except ImportError:
            self.skipTest('optional PDF dependency unavailable')
        writer = PdfWriter(); writer.add_blank_page(width=200, height=200)
        buffer = io.BytesIO(); writer.write(buffer)
        with self.assertRaisesRegex(ValueError, '未提取到文本'):
            parse_document('scan.pdf', buffer.getvalue())

    def test_http_flow_and_auth(self):
        original = os.environ.get('APP_TOKEN')
        os.environ['APP_TOKEN'] = 'test-secret-123456'
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.engine))
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        base = f'http://127.0.0.1:{server.server_port}'
        def call(path, body=None, token=True):
            headers = {'Content-Type': 'application/json'}
            if token: headers['Authorization'] = 'Bearer test-secret-123456'
            req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=5) as r: return json.load(r)
        try:
            with self.assertRaises(urllib.error.HTTPError) as error:
                call('/api/documents', token=False)
            self.assertEqual(error.exception.code, 401)
            with urllib.request.urlopen(base + '/') as response:
                self.assertIn('智学'.encode(), response.read())
            self.assertEqual(call('/api/health')['status'], 'ok')
            result = call('/api/documents', {'name': 'ml.md', 'data': base64.b64encode((ROOT / 'datasets/machine-learning.md').read_bytes()).decode()})
            answer = call('/api/ask', {'question': '学习率如何影响梯度下降？'})
            self.assertTrue(answer['sources'])
            self.assertEqual(answer['sources'][0]['document_id'], result['id'])
            with self.assertRaises(urllib.error.HTTPError) as error:
                call('/api/documents', {'name': 'x.txt', 'data': 'bad base64'})
            self.assertEqual(error.exception.code, 400)
            self.assertTrue(call('/api/documents/delete', {'id': result['id']})['deleted'])
            self.assertEqual(call('/api/documents'), [])
        finally:
            server.shutdown(); server.server_close(); worker.join()
            if original is None: os.environ.pop('APP_TOKEN', None)
            else: os.environ['APP_TOKEN'] = original


if __name__ == '__main__':
    unittest.main()
