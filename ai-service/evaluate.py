"""Small reproducible smoke evaluation, NOT a thesis benchmark."""
import json
import tempfile
from pathlib import Path
from engine import Engine

CASES = [
    ("学习率如何影响梯度下降", "optimization.txt"),
    ("如何缓解模型过拟合", "regularization.txt"),
    ("测试集为什么不能用于调参", "split.txt"),
]
DOCUMENTS = {
    "optimization.txt": "梯度下降沿梯度的反方向优化参数。学习率控制更新步长，过大可能发散，过小可能收敛缓慢。\n关系：梯度下降|依赖|学习率",
    "regularization.txt": "正则化通过惩罚模型复杂度缓解过拟合。L1正则化可能产生稀疏参数，L2正则化倾向于缩小参数。\n关系：正则化|缓解|过拟合",
    "split.txt": "训练集拟合模型，验证集选择超参数，测试集用于最终评估。测试集不能用于调参，否则结果偏乐观。",
}


def evaluate():
    report = {"dataset": "人工编写的 3 问题冒烟集，不可作为论文性能结论", "queries": len(CASES), "results": []}
    with tempfile.TemporaryDirectory() as tmp:
        engine = Engine(Path(tmp) / "eval.db")
        for name, text in DOCUMENTS.items(): engine.ingest(name, text.encode())
        for mode in ["bm25", "cosine", "hybrid", "graph", "auto"]:
            ranks = []
            for question, gold in CASES:
                names = [s["name"] for s in engine.search(question, mode, 3)["sources"]]
                ranks.append(names.index(gold) + 1 if gold in names else None)
            report["results"].append({"mode": mode, "Recall@3": sum(r is not None for r in ranks) / len(ranks), "MRR@3": sum(1/r if r else 0 for r in ranks) / len(ranks)})
    return report


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
