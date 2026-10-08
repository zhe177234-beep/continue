# v0.1 API

默认地址 `http://127.0.0.1:8000`。POST 使用 `Content-Type: application/json`。若设置 `APP_TOKEN`，全部 API 请求需带 `Authorization: Bearer <token>`；静态页面允许访问。错误返回 `{"error":"说明"}`，状态码 400/401/403/404/413/415/500。

| 方法 | 路径 | 请求 | 响应 |
| --- | --- | --- | --- |
| GET | /api/health | 无 | status、answer_kind |
| GET | /api/documents | 无 | 文档 id、name、created、chunks 列表 |
| POST | /api/documents | name: 文件名，data: 原始文件的 base64 | id、duplicate、chunks（重复时不返回 chunks） |
| POST | /api/documents/delete | id: 文档 ID | deleted: 布尔值 |
| GET | /api/graph | 无 | subject、predicate、object、chunk_id 列表 |
| POST | /api/ask | question: 1~1000 字符，mode: auto/bm25/cosine/hybrid/graph，k: 1~10 | mode、answer、answer_kind、sources |

sources 每项包含 chunk_id、document_id、name、page、text、score。PDF 页码为原始页码；TXT/MD 页码固定为 1。score 为当前检索模式排序分数，不是可信度概率。

无相关证据仍返回 200 与空 sources，answer 说明资料不足。该版本没有生成式大模型接口。

关系格式（资料内独立行）：

```text
关系：梯度下降|依赖|学习率
```

关系增强以问题中显式出现的实体为种子，召回包含该实体的一跳关系所在片段。auto 使用关系、关联、依赖、前置四个关键词选择 graph，否则使用 hybrid。
