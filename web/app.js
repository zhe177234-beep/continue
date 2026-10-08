const $ = id => document.getElementById(id);
const status = message => { $('status').textContent = message; };
async function api(path, body) {
  const headers = {Authorization: `Bearer ${$('token').value}`};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {method: body === undefined ? 'GET' : 'POST', headers, body: body === undefined ? undefined : JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '请求失败');
  return result;
}
function element(tag, text, className) {
  const node = document.createElement(tag); node.textContent = text;
  if (className) node.className = className;
  return node;
}
async function refresh() {
  const [documents, graph] = await Promise.all([api('/api/documents'), api('/api/graph')]);
  $('documents').replaceChildren(); $('graph').replaceChildren();
  if (!documents.length) $('documents').append(element('li', '还没有资料，先上传 datasets 中的示例。', 'hint'));
  documents.forEach(doc => {
    const li = element('li', `${doc.name} · ${doc.chunks} 个片段`);
    const button = element('button', '删除', 'quiet');
    button.onclick = async () => {
      if (!confirm(`确认删除资料“${doc.name}”及其索引？`)) return;
      try { await api('/api/documents/delete', {id: doc.id}); await refresh(); $('answer').replaceChildren(); $('sources').replaceChildren(); status('资料已删除'); }
      catch(error) { status(error.message); }
    };
    li.append(button); $('documents').append(li);
  });
  graph.forEach(edge => $('graph').append(element('li', `${edge.subject} → ${edge.predicate} → ${edge.object}`)));
  if (!graph.length) $('graph').append(element('li', '暂无显式关系', 'hint'));
}
$('connect').onclick = () => refresh().then(() => status('已连接')).catch(e => status(e.message));
$('upload').onclick = async () => {
  const file = $('file').files[0];
  if (!file) return status('请先选择文件');
  if (file.size > 3 * 1024 * 1024) return status('文件超过 3 MiB');
  $('upload').disabled = true; status('正在建立索引…');
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = ''; for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
    const result = await api('/api/documents', {name: file.name, data: btoa(binary)});
    await refresh(); status(result.duplicate ? '这份资料已存在，无需重复上传' : `索引完成：${result.chunks} 个片段`);
  } catch(error) { status(error.message); }
  finally { $('upload').disabled = false; }
};
$('ask').onsubmit = async event => {
  event.preventDefault(); $('submit').disabled = true; status('正在检索…');
  $('answer').replaceChildren(); $('sources').replaceChildren();
  try {
    const result = await api('/api/ask', {question: $('question').value, mode: $('mode').value});
    $('answer').append(element('h2', '资料中的证据'), element('p', result.answer, 'answer-text'));
    result.sources.forEach((source, i) => {
      const card = element('article', '', 'source');
      card.append(element('h3', `[${i + 1}] ${source.name} · 第 ${source.page} 页`), element('p', source.text), element('small', `片段 ${source.chunk_id} · 排序分数 ${source.score}`));
      $('sources').append(card);
    });
    status(`检索方式：${result.mode} · ${result.sources.length} 条证据（相关性排序不等于事实验证）`);
  } catch(error) { status(error.message); }
  finally { $('submit').disabled = false; }
};
refresh().catch(e => status(e.message));
