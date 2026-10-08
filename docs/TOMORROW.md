# 明天在电脑上的最短操作

仓库：https://github.com/zhe177234-beep/continue 。系统代码与模型接口已在云端测试；不会自动安装到你的电脑。

## 1. 准备

安装并打开 Docker Desktop；等待引擎运行。安装 Git，或在 GitHub 点击 Code → Download ZIP 后解压。在 PowerShell 进入项目目录。

如果还没有下载：

```powershell
git clone https://github.com/zhe177234-beep/continue.git
cd continue
```

如果已有 Git 克隆，先保存自己的改动，再执行 `git pull --ff-only`；不要用强制重置覆盖自己的文件。

## 2. 一次性启用本地模型并启动

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-models.ps1
```

脚本启动 Ollama，下载已经完成云端实测的聊天与向量模型，备份并写入 `.env`，构建并启动应用，随后打开浏览器。下载失败时会停止并提示；重新执行可复用已下载内容。默认使用 CPU，无需修改代码或申请 API Key。第一次需要下载镜像、依赖和模型，耗时取决于网络与电脑资源。

若明天只想先体验基础流程，可执行 `scripts/start.ps1`，不下载模型；之后再执行上述模型脚本。

## 3. 在网页完成首次准备

1. 打开 http://localhost:8080 ，注册自己的账号；没有预设管理员或默认密码。
2. 建立“机器学习”知识库，上传 `datasets/machine-learning.md` 或自己的课程资料。
3. 点击“更新语义索引”；在后台任务区域等待完成。
4. 在“知识关系”页点击“自动提取知识关系”；等待完成并复核出处。示例中的显式关系上传后已可用。
5. 在“问答”页提问并追问；“新建对话”清除当前追问上下文。
6. 在“知识关系”页构建 GraphRAG，问答可选择局部检索或全局汇总；“自主任务”页可启动多 Agent 学习目标。
7. 在“练习”页选择单选、多选、判断、填空或简答；提交后查看答案、错题和复习顺序。单文件上传已提高至 10 MiB。

上传新资料后再次更新语义索引。模型变化后也要重新建立索引。后台失败会明确显示，不代表资料已经成功建立语义索引。

## 可自行调整的配置

- 端口占用：`.env` 改 `WEB_PORT=8082`，重新运行启动脚本。
- 更换模型：向模型脚本传入 `-ChatModel 模型名 -EmbeddingModel 模型名`；大模型需要更多资源，CPU 推理也会更慢。
- 默认的轻量模型用于跑通功能，回答质量需逐步评测；引用编号不保证事实正确。
- 暂停：`docker compose stop`。再次启动可运行 `scripts/start.ps1`。
- 保留资料：不要执行带 `-v` 的 `docker compose down`，它会删除数据卷。

电脑无法运行或下载失败时，保留错误文本和 `docker compose logs --tail=100` 输出即可排查，无需重写项目。

## 已实现与后续创新边界

v0.4 已加入社区报告 GraphRAG、全局 Map-Reduce 和自主多 Agent 协作。简答仍采用关键词评分，掌握度仍为平滑正确率；数据库为 SQLite。PostgreSQL/pgvector、图表/公式语义和大规模质量评测属于后续开发。使用与边界见 [GraphRAG 与 Agent 指南](GRAPHRAG-AGENTS.md)。
