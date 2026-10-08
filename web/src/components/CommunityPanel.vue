<script setup>
import { computed, ref } from 'vue';
const props = defineProps({ data: Object, busy: Boolean, enabled: Boolean });
const emit = defineEmits(['build']);
const extract = ref(true), level = ref(0);
const communities = computed(() => (props.data?.communities || []).filter(c => c.level === Number(level.value)));
</script>

<template>
  <article class="panel communities-panel">
    <div class="section-heading">
      <div><h3>GraphRAG 知识社区</h3><p class="hint">把知识点组织成社区，用社区报告回答跨资料的问题。</p></div>
      <button :disabled="busy || !enabled" @click="emit('build', { extract })">构建 GraphRAG</button>
    </div>
    <div class="community-controls">
      <label class="check"><input v-model="extract" type="checkbox" />先自动提取关系</label>
      <span class="pill">{{ data?.status?.ready ? '索引已就绪' : '需要构建或更新' }}</span>
      <span>{{ data?.status?.entities || 0 }} 个实体 · {{ data?.status?.communities || 0 }} 个社区</span>
    </div>
    <p v-if="!data?.status?.ready" class="hint">上传或删除资料、更新关系、更换模型后需要重新构建。构建在后台进行，可查看任务进度或停止。</p>
    <template v-else>
      <label class="level-label">社区层级
        <select v-model="level" aria-label="社区层级"><option v-for="n in data.status.levels" :key="n" :value="n">{{ n }} · {{ n === 0 ? '全局主题' : '细分主题' }}</option></select>
      </label>
      <div class="community-grid">
        <details v-for="c in communities" :key="c.id" class="community-card">
          <summary><strong>{{ c.report.title }}</strong><small>{{ c.entity_ids.length }} 个实体 · {{ c.chunk_ids.length }} 个原文片段</small></summary>
          <p class="pre">{{ c.report.summary }}</p>
          <p v-if="c.report.extractive_batches" class="hint">部分报告使用原文摘录，请核对。</p>
          <blockquote v-for="(f, i) in c.report.findings" :key="i"><p>{{ f.text }}</p><small>原文：{{ f.quote }}</small><small>片段 {{ f.chunk_id }}</small></blockquote>
          <small v-if="c.parent_id">上级社区 {{ c.parent_id }}</small>
        </details>
      </div>
    </template>
  </article>
</template>

<style scoped>
.communities-panel { margin-top: 20px; }
.community-controls { display: flex; align-items: center; flex-wrap: wrap; gap: 16px; margin: 18px 0; font-size: 12px; }
.community-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); gap: 14px; margin-top: 16px; }
.community-card { background: #f7f8fa; border: 1px solid #e1e5ea; padding: 16px; border-radius: 12px; min-width: 0; overflow-wrap: anywhere; }
.community-card summary { cursor: pointer; }
.community-card small { display: block; margin-top: 8px; color: #64748b; font-size: 11px; }
.community-card p { font-size: 13px; line-height: 1.8; }
blockquote { margin: 14px 0; border-left: 3px solid #35a393; padding-left: 12px; }
.level-label { display: flex; align-items: center; gap: 12px; max-width: 280px; font-size: 12px; }
.section-heading { flex-wrap: wrap; }
</style>
