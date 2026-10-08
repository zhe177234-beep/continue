"""Real Ollama integration check; does not claim answer quality benchmarks."""
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ai-service'))
from engine import Engine
from models import Ollama
from retrieval import reindex, retrieve
from jobs import extract_relations

model=Ollama()
assert model.model and model.embedding_model, 'Configure both model names'
with tempfile.TemporaryDirectory() as folder:
    index=Engine(Path(folder)/'index.db')
    index.ingest('optimization.txt','梯度下降依赖学习率。学习率控制参数更新的步长。'.encode())
    index.ingest('cooking.txt','烹饪米饭需要清水和电饭煲。'.encode())
    indexed=reindex(index,model)
    result=retrieve(index,model,'梯度下降需要什么参数控制步长？','semantic',2)
    assert result['sources'] and result['sources'][0]['name']=='optimization.txt',result
    answer=model.generate('根据资料简短回答：学习率控制什么？必须附上引用 [1]。',result['sources'][:1])
    relations=extract_relations(index,model)
    assert relations['added']>=1,relations
    print(json.dumps({'indexed':indexed,'semantic_top1':result['sources'][0]['name'],'answer':answer,'relations':relations,'scope':'真实模型连通性、检索和输出契约检查，不代表领域准确率'},ensure_ascii=False,indent=2))
