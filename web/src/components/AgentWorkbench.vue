<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue';
const props = defineProps({ baseId: String, enabled: Boolean });
const emit = defineEmits(['changed']);
const goal = ref(''), steps = ref(4), runs = ref([]), selected = ref(''), message = ref(''), submitting = ref(false);
const current = computed(() => runs.value.find(r => r.id === selected.value));
const running = computed(() => runs.value.some(r => ['queued', 'running'].includes(r.status)));
const roles = { planner: '规划 Agent', researcher: '资料 Agent', graph: '图谱 Agent', learning: '学习 Agent', tutor: '回答 Agent', reviewer: '审查 Agent', supervisor: '协调器' };
const states = { queued: '排队中', running: '运行中', succeeded: '已结束', failed: '失败', cancelled: '已停止' };
let poller, request = 0, polling = false;
async function api(base, suffix, body, method) {
  const response = await fetch(`/api/bases/${base}/${suffix}`, { method: method || (body ? 'POST' : 'GET'), credentials: 'same-origin', headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '请求失败');
  return data;
}
async function refresh() {
  if (!props.baseId || polling) return;
  polling = true;
  const base = props.baseId, token = request;
  try {
    const next = await api(base, 'agents/runs');
    if (base !== props.baseId || token !== request) return;
    const completed = runs.value.some(old => ['queued','running'].includes(old.status) && next.some(n => n.id === old.id && !['queued','running'].includes(n.status)));
    runs.value = next;
    if (!next.some(r => r.id === selected.value)) selected.value = next[0]?.id || '';
    if (completed) emit('changed');
  } catch (error) { if (base === props.baseId && token === request) message.value = error.message; }
  finally { polling = false; }
}
async function start() {
  if (!goal.value.trim() || submitting.value) return;
  const base = props.baseId, token = request;
  submitting.value = true;
  try {
    const run = await api(base,'agents/runs',{ goal: goal.value.trim(), max_steps: Number(steps.value) });
    if (base !== props.baseId || token !== request) return;
    selected.value = run.id;
    message.value = '任务已启动。Agent 会根据证据审查结果选择下一步，最多运行所选检索轮数。';
    await refresh();
  } catch (error) { if (base === props.baseId && token === request) message.value = error.message; }
  finally { submitting.value = false; }
}
async function stop(id) {
  const base = props.baseId;
  try { await api(base,`jobs/${id}`,undefined,'DELETE'); message.value = '已请求停止，当前模型调用结束后生效。'; await refresh(); }
  catch (error) { if (base === props.baseId) message.value = error.message; }
}
watch(() => props.baseId, () => { request++; runs.value = []; selected.value = ''; message.value = ''; goal.value = ''; refresh(); });
onMounted(() => { refresh(); poller = setInterval(refresh,3000); });
onUnmounted(() => { request++; clearInterval(poller); });
</script>

<template>
  <div class="agent-workbench">
    <article class="panel">
      <h3>自主学习任务</h3>
      <p class="hint">描述你希望完成的目标。规划、资料、图谱、回答和审查 Agent 会协作检索当前知识库，必要时补查资料；你可以随时停止。</p>
      <form @submit.prevent="start">
        <label>任务目标<textarea v-model="goal" aria-label="任务目标" maxlength="1000" rows="4" placeholder="例如：梳理梯度下降、学习率和正则化的关系，说明常见误区，并给出复习顺序。" required /></label>
        <div class="agent-controls"><label>最多检索轮数<select v-model="steps" aria-label="最多检索轮数"><option v-for="n in [2,4,6,8]" :key="n" :value="n">{{ n }} 轮</option></select></label>
          <button :disabled="!enabled || !baseId || running || submitting || !goal.trim()">开始自主任务</button>
        </div>
      </form>
      <p v-if="!enabled" class="hint">先配置本地生成模型。GraphRAG 构建完成后，图谱 Agent 会自动成为可选工具。</p>
      <p class="hint" role="status">{{ message }}</p>
    </article>
    <div class="agent-results">
      <aside class="panel run-list"><h3>任务记录</h3><p v-if="!runs.length" class="hint">你的任务会保存在当前知识库。</p>
        <button v-for="run in runs" :key="run.id" :class="{ active: run.id === selected }" @click="selected = run.id"><strong>{{ run.result.goal || '已清理的任务' }}</strong><small>{{ states[run.status] }}</small></button>
      </aside>
      <article v-if="current" class="panel run-detail">
        <div class="section-heading"><h3>{{ current.result.goal || '任务详情' }}</h3><span class="pill">{{ states[current.status] }}</span><button v-if="['queued','running'].includes(current.status)" class="link" :disabled="!!current.cancel_requested" @click="stop(current.id)">{{ current.cancel_requested ? '停止中…' : '停止任务' }}</button></div>
        <p v-if="current.result.error" class="hint">{{ current.result.error }}</p>
        <p v-if="current.result.stage" class="hint">{{ current.result.stage }} · {{ current.result.model_calls || 0 }} 次模型调用</p>
        <ol class="agent-trace"><li v-for="event in current.result.trace || []" :key="event.step"><strong>{{ roles[event.role] || event.role }}</strong><span>{{ event.action }}</span><p v-if="event.query">{{ event.query }}</p><small v-if="event.sources !== undefined">找到 {{ event.sources }} 条原文证据</small><p v-if="event.issues?.length">{{ event.issues.join('；') }}</p></li></ol>
        <template v-if="current.result.answer"><h4>{{ current.result.outcome === 'completed' ? '协作结果' : '证据与待核对结果' }}</h4><p class="pre">{{ current.result.answer }}</p><p class="hint">{{ current.result.warning }}</p>
          <details v-for="(source,i) in current.result.sources || []" :key="source.chunk_id" class="agent-source"><summary>[{{ i + 1 }}] {{ source.name }} · 第 {{ source.page }} 页</summary><p class="pre">{{ source.text }}</p></details>
        </template>
      </article>
    </div>
  </div>
</template>

<style scoped>
.agent-workbench h3 { margin: 0 0 14px; }
form>label { display: block; font-size: 13px; margin-top: 20px; }
textarea { display: block; width: 100%; margin-top: 10px; resize: vertical; line-height: 1.8; }
.agent-controls { display: flex; align-items: flex-end; flex-wrap: wrap; gap: 20px; margin-top: 16px; }
.agent-controls label { font-size: 12px; }
.agent-controls select { display: block; min-width: 130px; margin-top: 8px; }
.agent-results { display: grid; grid-template-columns: 230px minmax(0,1fr); gap: 20px; margin-top: 20px; align-items: start; }
.run-list button { width: 100%; display: block; text-align: left; background: #f5f7f8; color: #334155; margin-top: 12px; white-space: normal; overflow-wrap: anywhere; }
.run-list button.active { outline: 2px solid #279d8b; }
.run-list small { display: block; margin-top: 6px; }
.run-detail { overflow-wrap: anywhere; }
.run-detail .section-heading { flex-wrap: wrap; }
.agent-trace { list-style: none; padding: 0; border-left: 2px solid #dde7e5; margin: 20px 0; }
.agent-trace li { padding: 10px 0 10px 16px; font-size: 12px; }
.agent-trace strong { display: inline-block; min-width: 98px; color: #267e71; }
.agent-trace p { margin: 8px 0; color: #64748b; }
.agent-source { border-top: 1px solid #e2e8f0; padding: 14px 0; font-size: 12px; }
.agent-source summary { cursor: pointer; }
@media (max-width: 760px) { .agent-results { grid-template-columns: minmax(0,1fr); } }
</style>
