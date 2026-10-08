import { test, expect } from '@playwright/test';

async function setup(page) {
  await page.route('**/api/health', route => route.fulfill({ json: { status: 'ok', version: '0.4.0', chat_model_configured: true, embedding_model_configured: true } }));
  await page.goto('/');
  await page.getByRole('button', { name: '首次使用？创建账号' }).click();
  await page.getByLabel('用户名').fill(`advanced_ui_${Date.now()}_${Math.floor(Math.random()*1000)}`);
  await page.getByLabel('密码', { exact: true }).fill('safe-password-123');
  await page.getByRole('button', { name: '注册并登录' }).click();
  await expect(page.getByRole('navigation', { name: '学习功能' })).toBeVisible();
  if (await page.getByRole('button', { name: '展开资料面板' }).isVisible()) await page.getByRole('button', { name: '展开资料面板' }).click();
  await page.getByPlaceholder('新建课程知识库').fill('新功能验证');
  await page.getByRole('button', { name: '新建知识库', exact: true }).click();
  await expect(page.getByRole('status').first()).toContainText('知识库已加载');
}

const source = { chunk_id: 'test-source:1:0', document_id: 'test-source', name: '学习资料.txt', page: 1, text: '学习率控制参数更新的步长。', score: 1 };

test('community build, reports and asynchronous global answer', async ({ page }) => {
  let building = false, jobReads = 0, querying = false;
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.route(/\/api\/bases\/[^/]+\/graphrag$/, route => {
    const ready = building && jobReads >= 2;
    return route.fulfill({ json: { status: { ready, levels: ready ? [0] : [], entities: ready ? 2 : 0, communities: ready ? 1 : 0 }, communities: ready ? [{ id: 'c1', level: 0, parent_id: null, entity_ids: ['a','b'], chunk_ids: [source.chunk_id], report: { title: '梯度下降社区', summary: '学习率与参数更新', findings: [{ text: source.text, quote: source.text, chunk_id: source.chunk_id }] } }] : [] } });
  });
  await page.route(/\/api\/bases\/[^/]+\/graphrag\/build$/, route => { building = true; return route.fulfill({ status: 202, json: { id: 'graph-build' } }); });
  await page.route(/\/api\/bases\/[^/]+\/graphrag\/query$/, route => { querying = true; return route.fulfill({ status: 202, json: { id: 'global-query' } }); });
  await page.route(/\/api\/bases\/[^/]+\/jobs$/, route => {
    if (building) jobReads++;
    const jobs = building ? [{ id: 'graph-build', kind: 'graphrag', status: jobReads >= 2 ? 'succeeded' : 'running', result: { stage: '社区报告', entities: 2, communities: 1 } }] : [];
    if (querying) jobs.unshift({ id: 'global-query', kind: 'graph-query', status: 'succeeded', result: { answer: '学习率控制参数更新的步长。[1]', answer_kind: 'generated', mode: 'graphrag-global', conversation_id: 'a'.repeat(32), sources: [source], graph_context: { communities_scanned: 1, communities_total: 1 } } });
    return route.fulfill({ json: jobs });
  });
  await setup(page);
  await page.getByRole('button', { name: '知识关系', exact: true }).click();
  await page.getByRole('button', { name: '构建 GraphRAG', exact: true }).click();
  await expect(page.getByText('索引已就绪')).toBeVisible({ timeout: 15000 });
  await page.getByText('梯度下降社区', { exact: true }).click();
  await expect(page.getByText(`片段 ${source.chunk_id}`, { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '问答', exact: true }).click();
  await page.getByLabel('检索方式').selectOption('graphrag-global');
  await page.getByPlaceholder('例如：学习率如何影响梯度下降？').fill('课程的主要主题？');
  await page.getByRole('button', { name: '检索并回答' }).click();
  await expect(page.locator('.answer-panel')).toContainText('学习率控制参数更新');
  await expect(page.locator('.answer-panel')).toContainText('已扫描 1/1');
  expect(errors).toEqual([]);
});

test('agent progress, cancellation, completed evidence and mobile layout', async ({ page }) => {
  let run = null, starts = 0, reads = 0;
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.route(/\/api\/bases\/[^/]+\/agents\/runs$/, async route => {
    if (route.request().method() === 'POST') {
      starts++; reads = 0;
      run = { id: `agent-${starts}`, status: 'running', kind: 'agents', result: { goal: route.request().postDataJSON().goal, trace: [{ step: 1, role: 'planner', action: '分派检索', query: '学习率' }, { step: 2, role: 'researcher', action: '找到原文证据', sources: 1 }] } };
      return route.fulfill({ status: 202, json: { id: run.id } });
    }
    if (run && starts === 2 && ++reads >= 2) run = { ...run, status: 'succeeded', result: { ...run.result, answer: '学习率控制参数更新的步长。[1]', sources: [source], outcome: 'completed', trace: [...run.result.trace.slice(0,2), { step: 3, role: 'reviewer', action: '审查通过' }] } };
    return route.fulfill({ json: run ? [run] : [] });
  });
  await page.route(/\/api\/bases\/[^/]+\/jobs\/agent-1$/, route => { run.status = 'cancelled'; return route.fulfill({ json: { stop_requested: true } }); });
  await setup(page);
  await page.getByRole('button', { name: '自主任务', exact: true }).click();
  await page.getByLabel('任务目标').fill('解释学习率并给出引用');
  await page.getByRole('button', { name: '开始自主任务' }).click();
  await expect(page.locator('.agent-trace')).toContainText('规划 Agent');
  await page.getByRole('button', { name: '停止任务', exact: true }).click();
  await expect(page.locator('.run-detail .pill')).toContainText('已停止');
  await page.getByRole('button', { name: '开始自主任务' }).click();
  await expect(page.locator('.run-detail')).toContainText('协作结果', { timeout: 15000 });
  await expect(page.locator('.agent-source')).toContainText('学习资料.txt');
  await page.screenshot({ path: 'test-results/agents-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByLabel('任务目标')).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: 'test-results/agents-mobile.png', fullPage: true });
  expect(errors).toEqual([]);
});
