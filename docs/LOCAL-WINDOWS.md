# 本机部署记录

部署日期：2026-10-09（北京时间）。

项目目录：`D:\王爱哲\GitHub\continue`。
访问地址：http://localhost:8080 。首次使用请注册自己的账号。

已安装 qwen3:0.6b（生成）和 qwen3-embedding:0.6b（向量）。
已验证注册登录、资料上传、问答引用、练习批改、学习统计、退出，
以及真实模型生成、1024 维语义索引和自动关系提取。
验证使用独立测试账号，测试资料已删除；测试账号仍保留。

## 下次启动

启动 Docker Desktop，等待引擎运行，然后在 PowerShell 执行：

```powershell
cd 'D:\王爱哲\GitHub\continue'
docker compose --profile models up -d
```

打开 http://localhost:8080 。已有镜像和模型无需重新下载。
上传资料后，点击“更新语义索引”，再进行语义检索。

## 停止和检查

```powershell
docker compose --profile models stop
docker compose ps
docker compose logs --tail 100
```

数据保存在 `continue_knowledge-data`，模型在 `continue_model-data`。
不要执行 `docker compose down -v`，这会删除这些数据卷。

## 本地修复

启动脚本提示改为 ASCII，修复 Windows PowerShell 5 的 UTF-8 中文解析问题。
启动脚本在进程未指定 HTTPS_PROXY 时，读取已启用的 Windows 简单代理地址，
以供 Docker 构建认证使用；不会修改系统代理或 Git 全局配置。
本机下载仓库时使用了现有系统代理 127.0.0.1:10808。
这些修复与模型验证脚本纳入 v0.4 发布。

v0.4 增加社区报告式 GraphRAG 和自主多 Agent。“知识关系”页构建 GraphRAG；“自主任务”页启动协作目标。

本轮本地调整：单文件上传上限为 100 MiB，文字 PDF/PPT 最多 1000 页；按用户选择保留扫描 PDF 最多 OCR 20 页。解析文本最多 1000 万字符、知识库最多 20,000 分块、Office 解压最多 250 MiB。容量调整暂未上传 GitHub。
