# v0.3 API

Docker 地址 http://localhost:8080；直接开发服务 http://127.0.0.1:8000。FastAPI 的 /docs 提供交互式接口文档。登录后由 HttpOnly session Cookie 鉴权，24 小时过期；POST 使用 JSON（上传除外）。错误一般为 `{"detail":"说明"}`，参数校验可能为 detail 数组。

| 方法 | 路径 | 输入 / 用途 |
| --- | --- | --- |
| GET | /api/health | 服务版本与模型配置状态，无需登录 |
| POST | /api/auth/register | username：3–32 位字母数字下划线，password：10–128 字符 |
| POST | /api/auth/login | 同上，设置会话 Cookie |
| POST | /api/auth/logout | 空 JSON，撤销当前会话 |
| GET | /api/auth/me | 当前用户 |
| GET/POST | /api/bases | 列表；创建时传 name（1–80 非空字符） |
| GET | /api/bases/{id}/documents | 当前库文档列表 |
| POST | /api/bases/{id}/documents | multipart/form-data，字段 file |
| DELETE | /api/bases/{id}/documents/{doc} | 删除资料及相关索引、练习与历史 |
| GET | /api/bases/{id}/graph | 知识关系与 chunk_id |
| POST | /api/bases/{id}/index | 空 JSON，用当前向量模型重新建立索引 |
| GET | /api/bases/{id}/jobs | 最近 20 个后台任务，含状态和结果 |
| POST | /api/bases/{id}/jobs/{kind} | kind 为 index/relations，202 返回任务 ID；页面使用此接口 |
| POST | /api/bases/{id}/ask | question（1–1000 字符）、mode、k（1–10）、generate（布尔）、conversation_id（可选，追问传回上次响应中的 ID） |
| GET | /api/bases/{id}/history | 最近 100 条问答及引用 |
| POST | /api/bases/{id}/quizzes | count（1–10）、kind（single/multiple/judge/short/essay），可能因可用关系不足返回较少题目 |
| POST | /api/bases/{id}/quizzes/{quiz}/submit | selected：单选/判断传整数索引，多选传整数数组，填空/简答传字符串；每题限首次提交 |
| GET | /api/bases/{id}/progress | mastery、mistakes、path（含 prerequisites）、prerequisite_cycle、method |

mode 为 auto/bm25/cosine/hybrid/graph/semantic。默认 auto；generate 默认 true，仅配置模型时调用。未配置语义模型时 semantic 返回 400，其他模式保持离线工作。

问答响应含 mode、answer、answer_kind（extractive/generated）、sources 与可选 warning。sources 包含 chunk_id、document_id、name、page、text、score。score 不是可信度概率；自动路由包含关系/关联/依赖/前置关键词时选择 graph，否则 hybrid。

显式关系可写成资料中的独立行：`关系：梯度下降|依赖|学习率`。返回题目不泄露答案；提交后返回正确选项、解释与原文片段 ID。知识库所有接口都进行账号所有权检查，无权访问返回 404。

常见状态码：400 业务输入问题，401 未登录，403 跨站或禁用注册，404 不存在或无权，409 用户名重复，413 超大请求，422 字段校验，429 登录注册频率限制，502 网关上游故障，503 模型索引故障。


自动提取通过后台 relations 任务调用模型的 JSON Schema 输出，逐条验证实体和摘录属于原文。完成后写入关系表，可用于图检索和出题。不是经过标注评测的高准确率抽取器。

追问的 conversation_id 必须属于当前知识库。模型最多接收最近 4 轮，指代式追问使用上一问题辅助检索；当前证据仍重新检索。未传 ID 就建立新对话。资料删除清空该库历史，避免旧引用继续参与上下文。

任务状态为 queued/running/succeeded/failed；队列最多 8 个待处理任务，每个库同时只允许 1 个；失败或重启中断可重新提交。旧同步 /index 接口保留兼容，长任务推荐 jobs/index。

简答批改返回 score（0–1）和 grading_method；仅按主题、关系和对象关键词覆盖评分，不理解逻辑或同义改写。首次提交使用写事务避免并发重复计分。
