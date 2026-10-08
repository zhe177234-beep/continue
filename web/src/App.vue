<script setup>
import {
  ref,
  computed,
  defineAsyncComponent,
  onMounted,
  onUnmounted,
} from "vue";
import Icon from "./components/Icon.vue";
const PageDesigner = defineAsyncComponent(
  () => import("./components/PageDesigner.vue"),
);
const navigation = [
  { name: "问答", icon: "chat", subtitle: "从资料中找到答案" },
  { name: "知识关系", icon: "graph", subtitle: "连接课程中的知识点" },
  { name: "练习", icon: "check", subtitle: "用练习检查理解" },
  { name: "学习记录", icon: "chart", subtitle: "找到下一步的方向" },
  { name: "学习卡片", icon: "layout", subtitle: "自由排版你的学习页面" },
];
const sidebarOpen = ref(false);
const user = ref(null),
  username = ref(""),
  password = ref(""),
  registering = ref(false),
  bases = ref([]),
  active = ref(""),
  newName = ref(""),
  documents = ref([]),
  graph = ref([]),
  history = ref([]),
  progress = ref({ mastery: [], mistakes: [], path: [] }),
  quizzes = ref([]),
  results = ref({}),
  selections = ref({}),
  file = ref(null),
  question = ref(""),
  mode = ref("auto"),
  generate = ref(true),
  answer = ref(null),
  tab = ref("问答"),
  status = ref(""),
  busy = ref(false),
  health = ref({});
const activeName = computed(
  () => bases.value.find((b) => b.id === active.value)?.name || "我的学习空间",
);
const currentSection = computed(() =>
  navigation.find((item) => item.name === tab.value),
);
const completedCount = computed(() =>
  progress.value.mastery.reduce((total, item) => total + item.attempts, 0),
);
const graphFilter = ref("");
const filteredGraph = computed(() =>
  graph.value.filter((e) =>
    (e.subject + e.predicate + e.object).includes(graphFilter.value.trim()),
  ),
);
function jobMessage(j) {
  if (j.result.error) return j.result.error;
  if (j.status === "queued") return "等待执行";
  if (j.status === "running") return "正在处理资料，可继续使用其他页面";
  return j.kind === "index"
    ? `完成 ${j.result.indexed || 0} 个片段的语义索引`
    : `新增 ${j.result.added || 0} 条关系，请核对原文`;
}
function chooseFile(event) {
  file.value =
    event.dataTransfer?.files?.[0] || event.target.files?.[0] || null;
}
function usePrompt(text) {
  question.value = text;
}
let generation = 0;
const conversation = ref(null),
  jobs = ref([]),
  quizKind = ref("single");
function answerLabel(kind, options, a) {
  return kind === "essay"
    ? a.join("、")
    : kind === "short"
      ? a
      : kind === "multiple"
        ? a.map((i) => options[i]).join("、")
        : options[a];
}
let poller;
async function api(path, body, method) {
  const opt = {
    method: method || (body === undefined ? "GET" : "POST"),
    credentials: "same-origin",
    headers: {},
  };
  if (body instanceof FormData) opt.body = body;
  else if (body !== undefined) {
    opt.body = JSON.stringify(body);
    opt.headers["Content-Type"] = "application/json";
  }
  const r = await fetch(path, opt),
    d = await r.json();
  if (!r.ok) {
    if (r.status === 401) user.value = null;
    throw new Error(
      typeof d.detail === "string" ? d.detail : "请求参数无效，请检查输入",
    );
  }
  return d;
}
async function task(fn) {
  if (busy.value) return;
  busy.value = true;
  status.value = "正在处理…";
  try {
    await fn();
  } catch (e) {
    status.value = e.message;
  } finally {
    busy.value = false;
  }
}
const path = () => `/api/bases/${active.value}`;
async function refresh() {
  if (!active.value) return;
  const id = active.value,
    v = ++generation;
  const [d, g, h, p] = await Promise.all([
    api(path() + "/documents"),
    api(path() + "/graph"),
    api(path() + "/history"),
    api(path() + "/progress"),
  ]);
  if (id !== active.value || v !== generation) return;
  documents.value = d;
  graph.value = g;
  history.value = h;
  progress.value = p;
}
async function selectBase() {
  conversation.value = null;
  jobs.value = [];
  answer.value = null;
  quizzes.value = [];
  results.value = {};
  selections.value = {};
  await refresh();
  status.value = "知识库已加载";
}
async function load() {
  bases.value = await api("/api/bases");
  if (!bases.value.some((b) => b.id === active.value))
    active.value = bases.value[0]?.id || "";
  await refresh();
}
async function login() {
  await task(async () => {
    if (registering.value)
      await api("/api/auth/register", {
        username: username.value,
        password: password.value,
      });
    await api("/api/auth/login", {
      username: username.value,
      password: password.value,
    });
    password.value = "";
    user.value = await api("/api/auth/me");
    await load();
    status.value = "先建立知识库，再上传资料";
  });
}
async function logout() {
  await task(async () => {
    await api("/api/auth/logout", {});
    user.value = null;
    conversation.value = null;
    jobs.value = [];
    registering.value = false;
    password.value = "";
    active.value = "";
    bases.value = [];
    documents.value = [];
    graph.value = [];
    history.value = [];
    answer.value = null;
    quizzes.value = [];
    results.value = {};
    selections.value = {};
    progress.value = { mastery: [], mistakes: [], path: [] };
    status.value = "已退出";
  });
}
async function createBase() {
  await task(async () => {
    const b = await api("/api/bases", { name: newName.value });
    newName.value = "";
    active.value = b.id;
    await load();
    await selectBase();
  });
}
async function upload() {
  await task(async () => {
    if (!file.value) throw new Error("请先选择资料");
    if (file.value.size > 3 * 1024 * 1024)
      throw new Error("文件不能超过 3 MiB");
    const body = new FormData();
    body.append("file", file.value);
    const r = await api(path() + "/documents", body);
    await refresh();
    status.value = r.duplicate
      ? "资料已经存在"
      : `入库完成：${r.chunks} 个片段`;
  });
}
async function removeDocument(d) {
  if (!confirm(`删除“${d.name}”？相关练习和问答历史也会清理。`)) return;
  await task(async () => {
    await api(path() + "/documents/" + d.id, undefined, "DELETE");
    answer.value = null;
    quizzes.value = [];
    results.value = {};
    await refresh();
    status.value = "资料及相关记录已清理";
  });
}
async function runJob(kind) {
  await task(async () => {
    await api(path() + "/jobs/" + kind, {});
    await pollJobs();
    status.value = "任务已排队，可在下方查看进度";
  });
}
async function indexVectors() {
  await runJob("index");
}
async function pollJobs() {
  if (!user.value || !active.value) return;
  const id = active.value;
  const previous = jobs.value;
  const next = await api(path() + "/jobs");
  if (id !== active.value) return;
  jobs.value = next;
  if (
    previous.some((j) => ["queued", "running"].includes(j.status)) &&
    !next.some((j) => ["queued", "running"].includes(j.status))
  ) {
    await refresh();
    status.value = "后台任务已结束，请查看任务结果";
  }
}
function newConversation() {
  conversation.value = null;
  answer.value = null;
  question.value = "";
  status.value = "已开始新对话";
}
async function ask() {
  await task(async () => {
    answer.value = await api(path() + "/ask", {
      question: question.value,
      mode: mode.value,
      generate: generate.value,
      conversation_id: conversation.value,
    });
    conversation.value = answer.value.conversation_id;
    await refresh();
    status.value =
      answer.value.warning || `找到 ${answer.value.sources.length} 条证据`;
  });
}
async function quiz() {
  await task(async () => {
    quizzes.value = await api(path() + "/quizzes", {
      count: 5,
      kind: quizKind.value,
    });
    results.value = {};
    selections.value = Object.fromEntries(
      quizzes.value.filter((q) => q.kind === "multiple").map((q) => [q.id, []]),
    );
    status.value = `已生成 ${quizzes.value.length} 道练习`;
  });
}
async function grade(q) {
  await task(async () => {
    if (selections.value[q.id] === undefined) throw new Error("请先选择答案");
    results.value[q.id] = await api(path() + "/quizzes/" + q.id + "/submit", {
      selected: ["short", "multiple", "essay"].includes(q.kind)
        ? selections.value[q.id]
        : Number(selections.value[q.id]),
    });
    await refresh();
    status.value = "批改完成";
  });
}
onUnmounted(() => clearInterval(poller));
onMounted(async () => {
  poller = setInterval(() => pollJobs().catch(() => {}), 3000);
  try {
    health.value = await api("/api/health");
    user.value = await api("/api/auth/me");
    await load();
  } catch (e) {
    status.value = e.message;
  }
});
</script>
<template>
  <a class="skip-link" href="#main-content">跳到学习内容</a>
  <header class="app-header">
    <div class="brand">
      <span class="logo"><Icon name="book" :size="24" /></span>
      <div>
        <h1>智学<span class="brand-dot">.</span></h1>
        <p>个人学习工作台</p>
      </div>
    </div>
    <div class="header-middle">
      <span class="header-divider"></span><span>让知识，成为你的能力</span>
    </div>
    <div class="right">
      <span class="pill model-state"
        ><span class="state-dot"></span
        >{{
          health.chat_model_configured ? "模型已配置" : "离线证据模式"
        }}</span
      ><button
        v-if="user"
        class="secondary account-button"
        :disabled="busy"
        @click="logout"
      >
        <span class="avatar">{{ user.username.slice(0, 1).toUpperCase() }}</span
        ><span>{{ user.username }} · 退出</span
        ><Icon name="logout" :size="16" />
      </button>
    </div>
  </header>
  <main v-if="!user" id="main-content" class="login">
    <section class="login-story">
      <span class="eyebrow"
        ><span class="state-dot"></span> 学习，从连接知识开始</span
      >
      <h2>每一份资料，<br />都能成为<span>成长的线索。</span></h2>
      <p class="muted">
        把课程资料、问题与练习放在一起。<br />有据可查，有处复习，也有下一步的方向。
      </p>
      <div class="learning-preview" aria-label="学习路线示意">
        <div class="preview-top">
          <Icon name="layers" /><span>你的知识，逐步成形</span
          ><span class="pill">学习路线示意</span>
        </div>
        <div class="preview-route">
          <div>
            <span class="route-mark">01</span><strong>课程资料</strong
            ><small>整理学习的起点</small>
          </div>
          <Icon name="arrow" />
          <div>
            <span class="route-mark">02</span><strong>理解与提问</strong
            ><small>用原文核对答案</small>
          </div>
          <Icon name="arrow" />
          <div>
            <span class="route-mark">03</span><strong>练习与复盘</strong
            ><small>从薄弱点再出发</small>
          </div>
        </div>
      </div>
      <div class="login-trust">
        <Icon name="shield" :size="17" /><span
          >资料按账号隔离 · 模型可在本机运行</span
        >
      </div>
    </section>
    <form class="panel login-form" @submit.prevent="login">
      <span class="eyebrow">WELCOME TO ZHIXUE</span>
      <h3>{{ registering ? "建立学习账号" : "进入学习空间" }}</h3>
      <p class="muted">
        {{
          registering
            ? "创建账号，开始整理你的课程资料。"
            : "欢迎回来，接着上一次的思考。"
        }}
      </p>
      <label
        >用户名<input
          v-model="username"
          required
          minlength="3"
          maxlength="32"
          pattern="[a-zA-Z0-9_]+"
          autocomplete="username"
          placeholder="3–32 位字母、数字或下划线" /></label
      ><label
        >密码<input
          v-model="password"
          type="password"
          required
          minlength="10"
          maxlength="128"
          :autocomplete="registering ? 'new-password' : 'current-password'"
          placeholder="至少 10 个字符" /></label
      ><button class="full primary-login" :disabled="busy">
        {{ registering ? "注册并登录" : "登录"
        }}<Icon name="arrow" :size="18" /></button
      ><button
        class="link full"
        type="button"
        :disabled="busy"
        @click="registering = !registering"
      >
        {{ registering ? "返回登录" : "首次使用？创建账号" }}
      </button>
      <p class="status" role="status">{{ status }}</p>
      <div class="login-form-note">一个空间，串起资料、理解与复习。</div>
    </form>
  </main>
  <main
    v-else
    class="workspace"
    :class="{ 'designer-workspace': tab === '学习卡片' }"
  >
    <aside class="resource-sidebar" :class="{ expanded: sidebarOpen }">
      <div class="sidebar-heading">
        <span class="eyebrow">YOUR LIBRARY</span
        ><button
          class="link sidebar-toggle"
          :aria-expanded="sidebarOpen"
          @click="sidebarOpen = !sidebarOpen"
        >
          {{ sidebarOpen ? "收起资料面板" : "展开资料面板" }}
        </button>
      </div>
      <h3><Icon name="layers" />我的知识库</h3>
      <select
        v-model="active"
        aria-label="当前知识库"
        :disabled="busy"
        @change="() => task(selectBase)"
      >
        <option value="" disabled>请选择知识库</option>
        <option v-for="b in bases" :key="b.id" :value="b.id">
          {{ b.name }}
        </option>
      </select>
      <div class="sidebar-body">
        <form class="create" @submit.prevent="createBase">
          <input
            v-model="newName"
            required
            maxlength="80"
            placeholder="新建课程知识库"
          /><button :disabled="busy" aria-label="新建知识库">＋</button>
        </form>
        <template v-if="active"
          ><div class="sidebar-section-title">
            <h3>学习资料</h3>
            <span class="count">{{ documents.length }}</span>
          </div>
          <label
            class="upload-zone"
            @dragover.prevent
            @drop.prevent="chooseFile"
            ><span class="upload-icon"><Icon name="upload" :size="24" /></span
            ><strong>{{ file ? file.name : "选择或拖入学习资料" }}</strong
            ><small>PDF · 文档 · 图片 · 文本</small
            ><input
              type="file"
              class="visually-hidden"
              aria-label="选择学习资料"
              accept=".txt,.md,.pdf,.docx,.pptx,.png,.jpg,.jpeg"
              :disabled="busy"
              @change="chooseFile"
          /></label>
          <p class="hint upload-hint">每份最多 3 MiB；图片需启用 OCR。</p>
          <button class="full" :disabled="busy" @click="upload">
            <Icon name="plus" :size="16" />上传并建立索引</button
          ><button
            class="secondary full"
            :disabled="busy || !health.embedding_model_configured"
            @click="indexVectors"
          >
            更新语义索引
          </button>
          <p v-if="!health.embedding_model_configured" class="hint">
            配置向量模型后可使用语义索引。
          </p>
          <ul class="document-list">
            <li v-for="d in documents" :key="d.id">
              <span class="document-icon"><Icon name="file" :size="18" /></span>
              <div>
                <strong>{{ d.name }}</strong
                ><small>{{ d.chunks }} 个片段</small>
              </div>
              <button
                class="link"
                :disabled="busy"
                @click="removeDocument(d)"
                :aria-label="`删除 ${d.name}`"
              >
                删除
              </button>
            </li>
          </ul>
          <details v-if="jobs.length" class="job-list">
            <summary>
              后台任务<span class="count">{{ jobs.length }}</span>
            </summary>
            <div
              v-for="j in jobs"
              :key="j.id"
              class="job-row"
              :class="j.status"
            >
              <strong
                >{{ j.kind === "index" ? "语义索引" : "关系提取" }} ·
                {{
                  {
                    queued: "排队中",
                    running: "执行中",
                    succeeded: "完成",
                    failed: "失败",
                  }[j.status]
                }}</strong
              >
              <p class="hint">{{ jobMessage(j) }}</p>
            </div>
          </details>
          <div v-if="!documents.length" class="sidebar-empty">
            <Icon name="file" :size="26" />
            <p>资料库还是空的</p>
            <small>可先上传 datasets 中的示例资料。</small>
          </div></template
        >
      </div>
      <div class="sidebar-bottom">
        <Icon name="shield" :size="16" /><span>当前账号的独立学习空间</span>
      </div>
    </aside>
    <section id="main-content" class="content-area">
      <div class="workspace-title">
        <div>
          <div class="breadcrumb">
            学习工作台<Icon name="chevron" :size="13" /><span>{{
              activeName
            }}</span>
          </div>
          <h2>
            {{ currentSection.name
            }}<span class="heading-description">{{
              currentSection.subtitle
            }}</span>
          </h2>
        </div>
        <div class="workspace-count">
          <Icon name="book" /><strong>{{ documents.length }}</strong
          ><span>份课程资料</span>
        </div>
      </div>
      <nav class="workspace-nav" aria-label="学习功能">
        <button
          v-for="item in navigation"
          :key="item.name"
          :class="{ selected: tab === item.name }"
          :aria-current="tab === item.name ? 'page' : undefined"
          @click="tab = item.name"
        >
          <Icon :name="item.icon" :size="18" />{{ item.name
          }}<span v-if="item.name === '学习卡片'" class="new-tag">NEW</span>
        </button>
      </nav>
      <p
        class="status workspace-status"
        role="status"
        aria-live="polite"
        :class="{ processing: busy }"
      >
        <span class="status-dot"></span>{{ status || "学习空间已就绪" }}
      </p>
      <div v-if="!active" class="panel empty">
        <span class="empty-icon"><Icon name="book" :size="32" /></span>
        <h3>从第一门课程开始</h3>
        <p>在资料面板中建立知识库，再上传课程资料。</p>
      </div>
      <template v-else-if="tab === '问答'"
        ><div class="question-layout">
          <div class="question-main">
            <form class="panel question-panel" @submit.prevent="ask">
              <div class="section-heading">
                <span class="section-icon"><Icon name="chat" /></span>
                <div>
                  <h3>带着问题，回到资料</h3>
                  <p class="hint">
                    {{ conversation ? "当前对话支持追问" : "新对话" }}
                  </p>
                </div>
                <button
                  type="button"
                  class="link"
                  :disabled="busy"
                  @click="newConversation"
                >
                  <Icon name="plus" :size="16" />新建对话
                </button>
              </div>
              <label class="question-label"
                >你想了解什么？<textarea
                  v-model="question"
                  required
                  maxlength="1000"
                  placeholder="例如：学习率如何影响梯度下降？"
                ></textarea>
              </label>
              <div class="prompt-list">
                <button
                  type="button"
                  class="prompt"
                  :disabled="busy"
                  @click="usePrompt('请解释资料中的核心概念')"
                >
                  解释核心概念<Icon name="arrow" :size="13" /></button
                ><button
                  type="button"
                  class="prompt"
                  :disabled="busy"
                  @click="usePrompt('哪些知识点具有前置依赖关系？')"
                >
                  梳理知识关系<Icon name="arrow" :size="13" />
                </button>
              </div>
              <div class="question-options">
                <label
                  >检索方式<select v-model="mode" aria-label="检索方式">
                    <option value="auto">自动路由</option>
                    <option value="hybrid">混合检索</option>
                    <option value="bm25">BM25 关键词</option>
                    <option value="cosine">词频余弦</option>
                    <option value="graph">关系增强</option>
                    <option value="semantic">语义向量</option>
                  </select></label
                ><label class="check"
                  ><input
                    v-model="generate"
                    type="checkbox"
                  />模型生成（需配置）</label
                ><button :disabled="busy">
                  <Icon name="search" :size="16" />检索并回答
                </button>
              </div>
            </form>
            <article v-if="answer" class="panel answer-panel">
              <div class="section-heading">
                <span class="section-icon"><Icon name="spark" /></span>
                <h3>
                  {{
                    answer.answer_kind === "generated"
                      ? "学习助手的回答"
                      : "资料中的原文证据"
                  }}
                </h3>
                <span class="pill">{{ answer.mode }}</span>
              </div>
              <p class="pre">{{ answer.answer }}</p>
              <div class="answer-note">
                <Icon name="shield" :size="16" />
                <p>引用编号可帮助核对来源，回答仍需对照原文确认。</p>
              </div>
            </article>
            <div v-else class="question-empty">
              <Icon name="chat" :size="30" />
              <p>好的理解，从一个具体的问题开始。</p>
              <small>上传课程资料后，答案会附上可查阅的原文出处。</small>
            </div>
            <details
              v-for="(s, i) in answer?.sources || []"
              :key="s.chunk_id"
              class="panel source"
              open
            >
              <summary>
                <span class="source-number">{{ i + 1 }}</span
                ><span
                  >{{ s.name }}<small>第 {{ s.page }} 页</small></span
                ><span class="source-label">原文出处</span>
              </summary>
              <p class="pre">{{ s.text }}</p>
              <small
                >片段 {{ s.chunk_id }} · 分数
                {{ Number(s.score).toFixed(4) }}</small
              >
            </details>
          </div>
          <aside class="question-guide">
            <span class="guide-symbol"><Icon name="spark" :size="22" /></span>
            <h3>让提问更有方向</h3>
            <p>先说清你想理解的概念，再补充遇到的疑惑。</p>
            <ol>
              <li>
                <span>01</span>
                <div>
                  <strong>具体一点</strong>
                  <p>用课程中的术语描述问题。</p>
                </div>
              </li>
              <li>
                <span>02</span>
                <div>
                  <strong>核对出处</strong>
                  <p>展开资料片段，看看依据。</p>
                </div>
              </li>
              <li>
                <span>03</span>
                <div>
                  <strong>继续追问</strong>
                  <p>对同一个概念深入一步。</p>
                </div>
              </li>
            </ol>
            <div class="guide-foot">
              <Icon name="file" :size="16" />{{
                documents.length
              }}
              份资料可供检索
            </div>
          </aside>
        </div></template
      >
      <template v-else-if="tab === '知识关系'"
        ><article class="panel graph-panel">
          <div class="section-heading">
            <span class="section-icon"><Icon name="graph" /></span>
            <div>
              <h3>知识关系与出处</h3>
              <p class="hint">
                连接
                {{
                  new Set(graph.flatMap((e) => [e.subject, e.object])).size
                }}
                个实体 · {{ graph.length }} 条关系
              </p>
            </div>
            <button
              :disabled="busy || !health.chat_model_configured"
              @click="runJob('relations')"
            >
              <Icon name="spark" :size="16" />自动提取知识关系
            </button>
          </div>
          <p class="hint">模型提取的关系需核对原文；关系检索最多扩展两跳。</p>
          <label class="graph-search"
            ><Icon name="search" :size="17" /><input
              v-model="graphFilter"
              aria-label="筛选知识关系"
              placeholder="搜索实体或关系名称"
          /></label>
          <div class="edge-grid">
            <div v-for="(e, i) in filteredGraph" :key="i" class="edge">
              <div class="edge-nodes">
                <strong>{{ e.subject }}</strong
                ><span>{{ e.predicate }}<Icon name="arrow" :size="20" /></span
                ><strong>{{ e.object }}</strong>
              </div>
              <small>依据片段：{{ e.chunk_id }}</small>
            </div>
          </div>
          <div v-if="!filteredGraph.length" class="empty">
            <Icon name="graph" :size="32" />
            <p>
              {{
                graph.length
                  ? "没有匹配的知识关系"
                  : "上传含知识关系的资料，或使用模型自动提取。"
              }}
            </p>
          </div>
        </article></template
      >
      <template v-else-if="tab === '练习'"
        ><article class="panel practice-setup">
          <div class="section-heading">
            <span class="section-icon"><Icon name="check" /></span>
            <div>
              <h3>从资料出发，检查掌握程度</h3>
              <p class="hint">
                {{ completedCount }} 次已完成练习 ·
                {{ progress.mistakes.length }} 条错题记录
              </p>
            </div>
          </div>
          <div class="practice-controls">
            <label
              >选择题型<select v-model="quizKind" aria-label="练习题型">
                <option value="single">单选题</option>
                <option value="multiple">多选题</option>
                <option value="judge">判断题</option>
                <option value="short">对象填空</option>
                <option value="essay">简答（关键词评分）</option>
              </select></label
            ><button :disabled="busy" @click="quiz">
              <Icon name="plus" :size="16" />生成 5 道练习
            </button>
          </div>
          <p class="hint">
            填空按名称匹配，简答按关键词覆盖评分，不判断推理正确性。每题首次提交计入统计。
          </p>
        </article>
        <div v-if="!quizzes.length" class="panel empty">
          <Icon name="check" :size="32" />
          <h3>把理解，变成一次练习</h3>
          <p>选择题型，开始检查资料中的知识关系。</p>
        </div>
        <article v-for="(q, i) in quizzes" :key="q.id" class="panel quiz-panel">
          <div class="quiz-meta">
            <span class="pill">练习 {{ String(i + 1).padStart(2, "0") }}</span
            ><span>{{ q.topic }}</span
            ><span v-if="results[q.id]" class="graded-label">已批改</span>
          </div>
          <h3>{{ q.stem }}</h3>
          <textarea
            v-if="['short', 'essay'].includes(q.kind)"
            v-model="selections[q.id]"
            maxlength="500"
            :disabled="Boolean(results[q.id])"
            placeholder="填写你的答案"
            :aria-label="`练习 ${i + 1} 的答案`"
          ></textarea
          ><label
            v-for="(o, j) in q.options"
            :key="j"
            class="option"
            :class="{
              chosen: Array.isArray(selections[q.id])
                ? selections[q.id].includes(j)
                : selections[q.id] === j,
            }"
            ><input
              v-model="selections[q.id]"
              :type="q.kind === 'multiple' ? 'checkbox' : 'radio'"
              :name="q.id"
              :value="j"
              :disabled="Boolean(results[q.id])"
            /><span class="option-letter">{{
              String.fromCharCode(65 + j)
            }}</span
            >{{ o }}</label
          ><button :disabled="busy || Boolean(results[q.id])" @click="grade(q)">
            提交答案<Icon name="arrow" :size="16" />
          </button>
          <div
            v-if="results[q.id]"
            class="feedback"
            :class="{ incorrect: !results[q.id].correct }"
          >
            <strong
              >{{ results[q.id].correct ? "回答正确" : "需要再复习" }} ·
              正确答案
              {{ answerLabel(q.kind, q.options, results[q.id].answer) }}</strong
            >
            <p>{{ results[q.id].explanation }}</p>
            <p v-if="q.kind === 'essay'">
              关键词得分：{{ Math.round(results[q.id].score * 100) }}% ·
              {{ results[q.id].grading_method }}
            </p>
            <small>依据片段：{{ results[q.id].source }}</small>
          </div>
        </article></template
      >
      <PageDesigner
        v-else-if="tab === '学习卡片'"
        :key="user.id + active"
        :user-id="user.id"
        :base-id="active"
        :base-name="activeName"
        :sources="answer?.sources || []"
        :mastery="progress.mastery"
      />
      <template v-else
        ><div class="stats">
          <article class="panel">
            <span class="stat-icon"><Icon name="graph" /></span
            ><small>知识点</small><strong>{{ progress.mastery.length }}</strong>
            <p>在资料关系中逐步连接</p>
          </article>
          <article class="panel">
            <span class="stat-icon amber"><Icon name="check" /></span
            ><small>错题记录</small
            ><strong>{{ progress.mistakes.length }}</strong>
            <p>每次复习的具体起点</p>
          </article>
          <article class="panel">
            <span class="stat-icon blue"><Icon name="chat" /></span
            ><small>问答记录</small><strong>{{ history.length }}</strong>
            <p>保留最近的提问与依据</p>
          </article>
        </div>
        <article class="panel">
          <div class="section-heading">
            <span class="section-icon"><Icon name="layers" /></span>
            <h3>建议复习顺序</h3>
            <span class="pill">已完成 {{ completedCount }} 次练习</span>
          </div>
          <p class="hint">
            已识别的前置知识优先安排；掌握度由练习估计，少量结果仅供参考。
          </p>
          <p v-if="progress.prerequisite_cycle" class="hint">
            检测到前置关系循环，循环部分按掌握度排列，请核对资料关系。
          </p>
          <div
            v-for="(item, i) in progress.path"
            :key="item.topic"
            class="path"
          >
            <span class="path-number">{{
              String(i + 1).padStart(2, "0")
            }}</span>
            <div>
              <strong>{{ item.topic }}</strong>
              <p>
                {{ item.reason }} · {{ item.attempts }} 次练习<span
                  v-if="item.prerequisites?.length"
                >
                  · 前置：{{ item.prerequisites.join("、") }}</span
                >
              </p>
            </div>
            <div class="mastery-indicator">
              <span>{{ Math.round(item.mastery * 100) }}%</span
              ><meter
                min="0"
                max="1"
                :value="item.mastery"
                :aria-label="`${item.topic} 掌握度`"
              ></meter>
            </div>
          </div>
          <div v-if="!progress.path.length" class="empty">
            <Icon name="layers" :size="28" />
            <p>上传资料并完成练习后，在这里查看复习顺序。</p>
          </div>
        </article>
        <div class="review-columns">
          <article class="panel">
            <div class="section-heading">
              <span class="section-icon"><Icon name="check" /></span>
              <h3>错题本</h3>
              <span class="count">{{ progress.mistakes.length }}</span>
            </div>
            <details
              v-for="q in progress.mistakes"
              :key="q.id"
              class="review-item"
            >
              <summary>{{ q.stem }}</summary>
              <p>正确答案：{{ answerLabel(q.kind, q.options, q.answer) }}</p>
              <p>{{ q.explanation }}</p>
            </details>
            <p v-if="!progress.mistakes.length" class="hint">
              这里会记录需要再复习的题目。
            </p>
          </article>
          <article class="panel">
            <div class="section-heading">
              <span class="section-icon"><Icon name="clock" /></span>
              <h3>问答历史</h3>
              <span class="count">{{ history.length }}</span>
            </div>
            <details v-for="h in history" :key="h.id" class="review-item">
              <summary>{{ h.question }}</summary>
              <p class="pre">{{ h.result.answer }}</p>
              <small>{{ new Date(h.created * 1000).toLocaleString() }}</small>
            </details>
            <p v-if="!history.length" class="hint">
              开始提问后，回答与依据会保存在这里。
            </p>
          </article>
        </div></template
      >
    </section>
  </main>
  <footer>
    <span>智学 · 学习有依据，成长有方向</span
    ><span>课程资料由用户提供 · 本地模型可选</span>
  </footer>
</template>
