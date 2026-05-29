<script setup>
import { computed, onMounted, ref } from "vue";
import {
  BarChart3,
  Building2,
  CalendarRange,
  CheckCircle2,
  ClipboardList,
  Eye,
  FileText,
  GripVertical,
  Layers3,
  LogOut,
  Plus,
  QrCode,
  RefreshCw,
  Save,
  ShieldCheck,
  Target,
  Trash2,
  UserRound,
  Users,
} from "@lucide/vue";
import { api, apiUrl, getToken, setToken } from "./api";

const defaultOptions = () => [
  { label: "满意", score_weight: 100 },
  { label: "基本满意", score_weight: 60 },
  { label: "不满意", score_weight: 0 },
];

const defaultSections = () => [
  {
    title: "政治建设",
    items: [
      { title: "学习贯彻习近平新时代中国特色社会主义思想" },
      { title: "贯彻落实习近平总书记关于石油工业和中国石油重要指示批示精神情况" },
      { title: "贯彻党的路线方针政策情况、落实公司党委重大部署情况" },
    ],
  },
];

const loading = ref(false);
const message = ref("");
const error = ref("");
const user = ref(null);
const active = ref("dashboard");
const route = ref(window.location.hash || "#/");

const units = ref([]);
const levels = ref([]);
const groups = ref([]);
const periods = ref([]);
const forms = ref([]);
const overview = ref([]);
const tasks = ref([]);
const selectedStats = ref(null);
const selectedStatsFormId = ref("");
const linksByForm = ref({});
const newLinkTargets = ref({});
const draggedLevelId = ref(null);

const loginForm = ref({ username: "root", password: "root123" });
const unitForm = ref({ name: "" });
const levelForm = ref({ name: "", description: "" });
const groupForm = ref({
  name: "",
  username: "",
  password: "",
  enabled: true,
});
const periodForm = ref({
  name: "",
  year: new Date().getFullYear(),
  half: "上半年",
  starts_on: `${new Date().getFullYear()}-01-01`,
  ends_on: `${new Date().getFullYear()}-06-30`,
});

const emptyFormBuilder = () => ({
  title: "",
  description: "",
  unit_id: "",
  group_id: "",
  period_id: "",
  options: defaultOptions(),
  sections: defaultSections(),
});
const formBuilder = ref(emptyFormBuilder());

const survey = ref(null);
const surveyAnswers = ref({});
const surveySubmitted = ref(false);

const isSurveyRoute = computed(() => route.value.startsWith("#/survey/"));
const surveyToken = computed(() => route.value.replace("#/survey/", ""));
const isRoot = computed(() => user.value?.role === "root");

const navItems = computed(() => {
  if (isRoot.value) {
    return [
      { key: "dashboard", label: "工作台", icon: BarChart3 },
      { key: "units", label: "单位管理", icon: Building2 },
      { key: "levels", label: "测评人员层级管理", icon: Layers3 },
      { key: "groups", label: "巡察组管理", icon: Users },
      { key: "periods", label: "时间任务", icon: CalendarRange },
      { key: "forms", label: "测评表单", icon: ClipboardList },
      { key: "stats", label: "统计分析", icon: CheckCircle2 },
    ];
  }
  return [
    { key: "tasks", label: "我的任务", icon: ClipboardList },
    { key: "links", label: "二维码与进度", icon: QrCode },
    { key: "stats", label: "填报数据", icon: BarChart3 },
  ];
});

const summary = computed(() => [
  { label: "单位", value: units.value.length, tone: "green" },
  { label: "巡察组", value: groups.value.length, tone: "orange" },
  { label: "测评表", value: forms.value.length, tone: "blue" },
  {
    label: "已提交/目标",
    value: `${overview.value.reduce((sum, item) => sum + item.progress.response_count, 0)}/${overview.value.reduce((sum, item) => sum + item.progress.target_count, 0)}`,
    tone: "gray",
  },
]);

const publicSurveyUrl = (token) => `${window.location.origin}/#/survey/${token}`;
const qrUrl = (token) =>
  apiUrl(
    `/public/links/${token}/qr?origin=${encodeURIComponent(
      window.location.origin,
    )}`,
  );

function showMessage(text) {
  message.value = text;
  error.value = "";
  window.setTimeout(() => {
    if (message.value === text) message.value = "";
  }, 2600);
}

function showError(err) {
  error.value = err?.message || "操作失败";
  message.value = "";
}

async function run(action, successText = "") {
  loading.value = true;
  try {
    const result = await action();
    if (successText) showMessage(successText);
    return result;
  } catch (err) {
    showError(err);
    return null;
  } finally {
    loading.value = false;
  }
}

function storeUser(nextUser) {
  user.value = nextUser;
  if (nextUser) {
    localStorage.setItem("mzcp_user", JSON.stringify(nextUser));
  } else {
    localStorage.removeItem("mzcp_user");
  }
}

async function login() {
  await run(async () => {
    error.value = "";
    message.value = "";
    const result = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify(loginForm.value),
    });
    setToken(result.token);
    storeUser(result.user);
    active.value = result.user.role === "root" ? "dashboard" : "tasks";
    await loadData();
  }, "登录成功");
}

function logout() {
  setToken("");
  storeUser(null);
  selectedStats.value = null;
  message.value = "";
  error.value = "";
}

async function loadData() {
  if (!user.value) return;
  if (isRoot.value) {
    const [unitData, levelData, groupData, periodData, formData, statData, taskData] =
      await Promise.all([
        api("/units"),
        api("/levels"),
        api("/groups"),
        api("/periods"),
        api("/forms"),
        api("/stats/overview"),
        api("/tasks/progress"),
      ]);
    units.value = unitData.items;
    levels.value = levelData.items;
    groups.value = groupData.items;
    periods.value = periodData.items;
    forms.value = formData.items;
    overview.value = statData.items;
    tasks.value = taskData.items;
  } else {
    const [levelData, periodData, formData, statData, taskData] = await Promise.all([
      api("/levels"),
      api("/periods"),
      api("/forms"),
      api("/stats/overview"),
      api("/tasks/progress"),
    ]);
    levels.value = levelData.items;
    periods.value = periodData.items;
    forms.value = formData.items;
    overview.value = statData.items;
    tasks.value = taskData.items;
    await Promise.all(forms.value.map((form) => loadLinks(form.id)));
  }
}

async function createUnit() {
  await run(async () => {
    await api("/units", { method: "POST", body: JSON.stringify(unitForm.value) });
    unitForm.value.name = "";
    await loadData();
  }, "单位已创建");
}

async function createLevel() {
  await run(async () => {
    await api("/levels", { method: "POST", body: JSON.stringify(levelForm.value) });
    levelForm.value = { name: "", description: "" };
    await loadData();
  }, "层级已创建");
}

async function reorderLevels(targetId) {
  const sourceId = draggedLevelId.value;
  draggedLevelId.value = null;
  if (!sourceId || sourceId === targetId) return;
  const next = [...levels.value];
  const from = next.findIndex((item) => item.id === sourceId);
  const to = next.findIndex((item) => item.id === targetId);
  if (from < 0 || to < 0) return;
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  levels.value = next;
  await run(async () => {
    const result = await api("/levels/reorder", {
      method: "PUT",
      body: JSON.stringify({ ids: next.map((item) => item.id) }),
    });
    levels.value = result.items;
  }, "层级顺序已更新");
}

async function createGroup() {
  await run(async () => {
    await api("/groups", { method: "POST", body: JSON.stringify(groupForm.value) });
    groupForm.value = { name: "", username: "", password: "", enabled: true };
    await loadData();
  }, "巡察组账号已创建");
}

async function updateGroup(group) {
  await run(async () => {
    await api(`/groups/${group.id}`, {
      method: "PUT",
      body: JSON.stringify(group),
    });
    await loadData();
  }, "巡察组账号已更新");
}

async function createPeriod() {
  await run(async () => {
    await api("/periods", { method: "POST", body: JSON.stringify(periodForm.value) });
    periodForm.value.name = "";
    await loadData();
  }, "时间任务已创建");
}

function addOption() {
  formBuilder.value.options.push({ label: "", score_weight: 0 });
}

function removeOption(index) {
  if (formBuilder.value.options.length <= 2) return;
  formBuilder.value.options.splice(index, 1);
}

function addSection() {
  formBuilder.value.sections.push({ title: "", items: [{ title: "" }] });
}

function removeSection(index) {
  if (formBuilder.value.sections.length <= 1) return;
  formBuilder.value.sections.splice(index, 1);
}

function addSectionItem(section) {
  section.items.push({ title: "" });
}

function removeSectionItem(section, index) {
  if (section.items.length <= 1) return;
  section.items.splice(index, 1);
}

async function createEvaluationForm() {
  await run(async () => {
    await api("/forms", {
      method: "POST",
      body: JSON.stringify(formBuilder.value),
    });
    formBuilder.value = emptyFormBuilder();
    await loadData();
  }, "测评表已创建并分配");
}

async function deleteItem(resource, id, successText) {
  await run(async () => {
    await api(`/${resource}/${id}`, { method: "DELETE" });
    await loadData();
  }, successText);
}

async function loadLinks(formId) {
  const data = await api(`/forms/${formId}/links`);
  linksByForm.value = { ...linksByForm.value, [formId]: data.items };
}

function linkTargetKey(formId, levelId) {
  return `${formId}-${levelId}`;
}

async function generateLink(formId, levelId) {
  const key = linkTargetKey(formId, levelId);
  await run(async () => {
    await api(`/forms/${formId}/links`, {
      method: "POST",
      body: JSON.stringify({
        level_id: levelId,
        target_count: Number(newLinkTargets.value[key] || 0),
      }),
    });
    newLinkTargets.value[key] = "";
    await loadLinks(formId);
    await loadData();
  }, "二维码链接已生成");
}

async function updateLink(link) {
  await run(async () => {
    await api(`/links/${link.id}`, {
      method: "PUT",
      body: JSON.stringify(link),
    });
    await loadLinks(link.form_id);
    await loadData();
  }, "目标人数已更新");
}

async function selectStats(formId) {
  selectedStatsFormId.value = formId;
  if (!formId) {
    selectedStats.value = null;
    return;
  }
  await run(async () => {
    selectedStats.value = await api(`/stats/forms/${formId}`);
  });
}

async function viewStats(formId) {
  active.value = "stats";
  await selectStats(formId);
}

async function loadPublicSurvey() {
  await run(async () => {
    survey.value = await api(`/public/surveys/${surveyToken.value}`);
    surveyAnswers.value = {};
    surveySubmitted.value = false;
  });
}

function setSurveyAnswer(itemId, optionId) {
  surveyAnswers.value = { ...surveyAnswers.value, [itemId]: optionId };
}

const surveyComplete = computed(() => {
  if (!survey.value) return false;
  return survey.value.items.every((item) => surveyAnswers.value[item.id]);
});

async function submitSurvey() {
  await run(async () => {
    await api(`/public/surveys/${surveyToken.value}/responses`, {
      method: "POST",
      body: JSON.stringify({ answers: surveyAnswers.value }),
    });
    surveySubmitted.value = true;
  }, "提交成功");
}

window.addEventListener("hashchange", async () => {
  route.value = window.location.hash || "#/";
  if (isSurveyRoute.value) await loadPublicSurvey();
});

onMounted(async () => {
  if (isSurveyRoute.value) {
    await loadPublicSurvey();
    return;
  }
  const savedUser = localStorage.getItem("mzcp_user");
  if (getToken() && savedUser) {
    storeUser(JSON.parse(savedUser));
    loading.value = true;
    try {
      const result = await api("/auth/me");
      storeUser(result.user);
      active.value = result.user.role === "root" ? "dashboard" : "tasks";
      await loadData();
    } catch {
      logout();
      error.value = "登录已失效，请重新登录";
    } finally {
      loading.value = false;
    }
  }
});
</script>

<template>
  <main v-if="isSurveyRoute" class="survey-shell">
    <section class="public-panel">
      <div class="brand-line">
        <ShieldCheck :size="24" />
        <span>民主测评</span>
      </div>

      <div v-if="survey && !surveySubmitted" class="survey-content">
        <p class="eyebrow">{{ survey.unit.name }} · {{ survey.level.name }}</p>
        <h1>{{ survey.title }}</h1>
        <p class="muted">{{ survey.period.name }}</p>

        <div v-if="!survey.is_open" class="notice warning">当前测评表不在填报时间内。</div>

        <form v-else class="survey-form" @submit.prevent="submitSurvey">
          <section v-for="section in survey.sections" :key="section.id" class="survey-section">
            <h2>{{ section.title }}</h2>
            <div v-for="item in section.items" :key="item.id" class="survey-item">
              <div class="item-title">{{ item.sort_order }}. {{ item.title }}</div>
              <div class="score-row">
                <button
                  v-for="option in survey.options"
                  :key="option.id"
                  type="button"
                  class="score-button"
                  :class="{ selected: surveyAnswers[item.id] === option.id }"
                  @click="setSurveyAnswer(item.id, option.id)"
                >
                  {{ option.label }}
                </button>
              </div>
            </div>
          </section>
          <button class="primary wide" type="submit" :disabled="!surveyComplete">
            <Save :size="18" />
            提交测评
          </button>
        </form>
      </div>

      <div v-else-if="surveySubmitted" class="done-state">
        <CheckCircle2 :size="54" />
        <h1>提交成功</h1>
        <p>感谢参与本次民主测评。</p>
      </div>

      <div v-else class="loading-state">正在加载测评表...</div>
    </section>
  </main>

  <main v-else-if="!user" class="login-shell">
    <section class="login-panel">
      <div class="system-mark">
        <ShieldCheck :size="30" />
      </div>
      <h1>民主测评管理系统</h1>
      <p>root 管理测评任务，巡察组生成二维码并组织填报。</p>
      <div v-if="message" class="notice success login-notice">{{ message }}</div>
      <div v-if="error" class="notice error login-notice">{{ error }}</div>
      <form class="stack" @submit.prevent="login">
        <label>
          账号
          <input v-model="loginForm.username" autocomplete="username" />
        </label>
        <label>
          密码
          <input v-model="loginForm.password" autocomplete="current-password" type="password" />
        </label>
        <button class="primary wide" type="submit" :disabled="loading">
          <UserRound :size="18" />
          登录
        </button>
      </form>
    </section>
  </main>

  <main v-else class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <ShieldCheck :size="26" />
        <div>
          <strong>民主测评</strong>
          <span>{{ user.name }}</span>
        </div>
      </div>
      <nav>
        <button
          v-for="item in navItems"
          :key="item.key"
          type="button"
          :class="{ active: active === item.key }"
          @click="active = item.key"
        >
          <component :is="item.icon" :size="18" />
          {{ item.label }}
        </button>
      </nav>
    </aside>

    <section class="workspace">
      <header class="topbar">
        <div>
          <p class="eyebrow">{{ user.role === "root" ? "系统管理员" : "巡察组" }}</p>
          <h1>{{ navItems.find((item) => item.key === active)?.label }}</h1>
        </div>
        <div class="actions">
          <button class="ghost icon-text" type="button" title="刷新" @click="loadData">
            <RefreshCw :size="17" />
            刷新
          </button>
          <button class="ghost icon-text" type="button" title="退出" @click="logout">
            <LogOut :size="17" />
            退出
          </button>
        </div>
      </header>

      <div v-if="message" class="notice success">{{ message }}</div>
      <div v-if="error" class="notice error">{{ error }}</div>

      <section v-if="active === 'dashboard'" class="page-grid">
        <div v-for="item in summary" :key="item.label" class="metric" :class="item.tone">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
        <section class="panel full">
          <div class="panel-head">
            <h2>发布任务完成情况</h2>
          </div>
          <table>
            <thead>
              <tr>
                <th>测评表</th>
                <th>单位</th>
                <th>巡察组</th>
                <th>进度</th>
                <th>满意度</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in overview" :key="item.id">
                <td>{{ item.title }}</td>
                <td>{{ item.unit.name }}</td>
                <td>{{ item.group.name }}</td>
                <td>
                  {{ item.progress.response_count }}/{{ item.progress.target_count }}
                  <span class="muted">({{ item.progress.completion_percent }}%)</span>
                </td>
                <td>{{ item.satisfaction_percent }}%</td>
                <td>
                  <button class="ghost icon-text" type="button" @click="viewStats(item.id)">
                    <Eye :size="17" />
                    查看
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </section>

      <section v-if="active === 'units'" class="management-grid">
        <section class="panel">
          <div class="panel-head">
            <h2>新增单位</h2>
          </div>
          <form class="inline-form" @submit.prevent="createUnit">
            <input v-model="unitForm.name" placeholder="单位名称" />
            <button class="primary" type="submit">
              <Plus :size="18" />
              新增
            </button>
          </form>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>单位列表</h2>
          </div>
          <div class="record-list">
            <div v-for="item in units" :key="item.id" class="record-row">
              <span>{{ item.name }}</span>
              <small>挂载测评表 {{ item.form_count }} 张</small>
              <button
                class="icon danger"
                title="删除"
                type="button"
                :disabled="item.form_count > 0"
                @click="deleteItem('units', item.id, '单位已删除')"
              >
                <Trash2 :size="17" />
              </button>
            </div>
          </div>
        </section>
      </section>

      <section v-if="active === 'levels'" class="management-grid">
        <section class="panel">
          <div class="panel-head">
            <h2>新增测评人员层级</h2>
          </div>
          <form class="stack" @submit.prevent="createLevel">
            <label>
              层级名称
              <input v-model="levelForm.name" placeholder="A层级" />
            </label>
            <label>
              说明
              <input v-model="levelForm.description" placeholder="可选" />
            </label>
            <button class="primary" type="submit">
              <Plus :size="18" />
              新增
            </button>
          </form>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>拖动调整顺序</h2>
          </div>
          <div class="record-list">
            <div
              v-for="item in levels"
              :key="item.id"
              class="record-row draggable"
              draggable="true"
              @dragstart="draggedLevelId = item.id"
              @dragover.prevent
              @drop="reorderLevels(item.id)"
            >
              <GripVertical :size="18" />
              <span>{{ item.name }}</span>
              <small>{{ item.description || "未填写说明" }}</small>
              <button
                class="icon danger"
                title="删除"
                type="button"
                :disabled="item.link_count > 0"
                @click="deleteItem('levels', item.id, '层级已删除')"
              >
                <Trash2 :size="17" />
              </button>
            </div>
          </div>
        </section>
      </section>

      <section v-if="active === 'groups'" class="management-grid wide-left">
        <section class="panel">
          <div class="panel-head">
            <h2>新增巡察组账号</h2>
          </div>
          <form class="stack" @submit.prevent="createGroup">
            <label>
              巡察组名称
              <input v-model="groupForm.name" placeholder="第一巡察组" />
            </label>
            <label>
              登录账号
              <input v-model="groupForm.username" placeholder="group1" />
            </label>
            <label>
              登录密码
              <input v-model="groupForm.password" />
            </label>
            <label class="checkline">
              <input v-model="groupForm.enabled" type="checkbox" />
              启用账号
            </label>
            <button class="primary" type="submit">
              <Plus :size="18" />
              新增
            </button>
          </form>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>巡察组列表</h2>
          </div>
          <div class="editable-list">
            <div v-for="item in groups" :key="item.id" class="editable-row">
              <label>
                巡察组名称
                <input v-model="item.name" aria-label="巡察组名称" />
              </label>
              <label>
                登录账号
                <input v-model="item.username" aria-label="账号" />
              </label>
              <label>
                登录密码
                <input v-model="item.password" aria-label="密码" />
              </label>
              <label class="checkline compact">
                <input v-model="item.enabled" type="checkbox" />
                启用
              </label>
              <small>任务 {{ item.form_count }} 个</small>
              <button class="ghost icon-text" type="button" @click="updateGroup(item)">
                <Save :size="17" />
                保存
              </button>
              <button
                class="icon danger"
                title="删除"
                type="button"
                :disabled="item.form_count > 0"
                @click="deleteItem('groups', item.id, '巡察组已删除')"
              >
                <Trash2 :size="17" />
              </button>
            </div>
          </div>
        </section>
      </section>

      <section v-if="active === 'periods'" class="management-grid">
        <section class="panel">
          <div class="panel-head">
            <h2>新增时间任务</h2>
          </div>
          <form class="stack" @submit.prevent="createPeriod">
            <label>
              名称
              <input v-model="periodForm.name" placeholder="2026年上半年" />
            </label>
            <div class="two-cols">
              <label>
                年份
                <input v-model.number="periodForm.year" type="number" />
              </label>
              <label>
                半年
                <select v-model="periodForm.half">
                  <option>上半年</option>
                  <option>下半年</option>
                </select>
              </label>
            </div>
            <div class="two-cols">
              <label>
                开始日期
                <input v-model="periodForm.starts_on" type="date" />
              </label>
              <label>
                结束日期
                <input v-model="periodForm.ends_on" type="date" />
              </label>
            </div>
            <button class="primary" type="submit">
              <Plus :size="18" />
              新增
            </button>
          </form>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>时间任务列表</h2>
          </div>
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>周期</th>
                <th>填报时间</th>
                <th>测评表</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in periods" :key="item.id">
                <td>{{ item.name }}</td>
                <td>{{ item.year }} · {{ item.half }}</td>
                <td>{{ item.starts_on }} 至 {{ item.ends_on }}</td>
                <td>{{ item.form_count }}</td>
                <td>
                  <button
                    class="icon danger"
                    title="删除"
                    type="button"
                    :disabled="item.form_count > 0"
                    @click="deleteItem('periods', item.id, '时间任务已删除')"
                  >
                    <Trash2 :size="17" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </section>

      <section v-if="active === 'forms'" class="management-grid wide-left">
        <section class="panel">
          <div class="panel-head">
            <h2>创建测评表</h2>
          </div>
          <form class="stack" @submit.prevent="createEvaluationForm">
            <label>
              表单名称
              <input v-model="formBuilder.title" placeholder="民主测评表" />
            </label>
            <label>
              说明
              <textarea v-model="formBuilder.description" rows="3" />
            </label>
            <div class="three-cols">
              <label>
                单位
                <select v-model="formBuilder.unit_id">
                  <option disabled value="">选择单位</option>
                  <option v-for="item in units" :key="item.id" :value="item.id">
                    {{ item.name }}
                  </option>
                </select>
              </label>
              <label>
                巡察组
                <select v-model="formBuilder.group_id">
                  <option disabled value="">选择巡察组</option>
                  <option v-for="item in groups" :key="item.id" :value="item.id">
                    {{ item.name }}
                  </option>
                </select>
              </label>
              <label>
                时间任务
                <select v-model="formBuilder.period_id">
                  <option disabled value="">选择时间任务</option>
                  <option v-for="item in periods" :key="item.id" :value="item.id">
                    {{ item.name }}
                  </option>
                </select>
              </label>
            </div>

            <div class="subpanel">
              <div class="panel-head compact-head">
                <h2>测评选项</h2>
                <button class="ghost icon-text" type="button" @click="addOption">
                  <Plus :size="17" />
                  添加选项
                </button>
              </div>
              <div class="option-editor">
                <div v-for="(option, index) in formBuilder.options" :key="index" class="option-row">
                  <input v-model="option.label" placeholder="选项名称" />
                  <input v-model.number="option.score_weight" type="number" placeholder="权重" />
                  <button class="icon" type="button" title="删除选项" @click="removeOption(index)">
                    <Trash2 :size="17" />
                  </button>
                </div>
              </div>
            </div>

            <div class="subpanel">
              <div class="panel-head compact-head">
                <h2>测评维度与测评项</h2>
                <button class="ghost icon-text" type="button" @click="addSection">
                  <Plus :size="17" />
                  添加维度
                </button>
              </div>
              <div class="section-editor">
                <section
                  v-for="(section, sectionIndex) in formBuilder.sections"
                  :key="sectionIndex"
                  class="section-block"
                >
                  <div class="section-title-row">
                    <FileText :size="18" />
                    <input v-model="section.title" placeholder="例如：政治建设" />
                    <button class="icon" type="button" title="删除维度" @click="removeSection(sectionIndex)">
                      <Trash2 :size="17" />
                    </button>
                  </div>
                  <div
                    v-for="(item, itemIndex) in section.items"
                    :key="itemIndex"
                    class="item-edit-row"
                  >
                    <span class="merged-cell-label" v-if="itemIndex === 0">
                      {{ section.title || "测评维度" }}
                    </span>
                    <span class="merged-cell-label ghost-cell" v-else></span>
                    <input v-model="item.title" :placeholder="`测评项 ${itemIndex + 1}`" />
                    <button
                      class="icon"
                      type="button"
                      title="删除测评项"
                      @click="removeSectionItem(section, itemIndex)"
                    >
                      <Trash2 :size="17" />
                    </button>
                  </div>
                  <button class="ghost icon-text" type="button" @click="addSectionItem(section)">
                    <Plus :size="17" />
                    添加测评项
                  </button>
                </section>
              </div>
            </div>

            <button class="primary" type="submit">
              <Save :size="18" />
              保存并分配
            </button>
          </form>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>测评表列表</h2>
          </div>
          <div class="record-list">
            <div v-for="item in forms" :key="item.id" class="form-record">
              <strong>{{ item.title }}</strong>
              <span>{{ item.unit.name }} · {{ item.group.name }}</span>
              <small>
                进度 {{ item.progress.response_count }}/{{ item.progress.target_count }}
              </small>
              <div class="record-actions">
                <button class="ghost icon-text" type="button" @click="viewStats(item.id)">
                  <Eye :size="17" />
                  数据
                </button>
                <button
                  class="icon danger"
                  title="删除"
                  type="button"
                  :disabled="item.progress.response_count > 0"
                  @click="deleteItem('forms', item.id, '测评表已删除')"
                >
                  <Trash2 :size="17" />
                </button>
              </div>
            </div>
          </div>
        </section>
      </section>

      <section v-if="active === 'tasks'" class="panel">
        <div class="panel-head">
          <h2>我的任务完成进度</h2>
        </div>
        <table>
          <thead>
            <tr>
              <th>测评表</th>
              <th>单位</th>
              <th>周期</th>
              <th>进度</th>
              <th>满意度</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in overview" :key="item.id">
              <td>{{ item.title }}</td>
              <td>{{ item.unit.name }}</td>
              <td>{{ item.period.name }}</td>
              <td>{{ item.progress.response_count }}/{{ item.progress.target_count }} · {{ item.progress.completion_percent }}%</td>
              <td>{{ item.satisfaction_percent }}%</td>
              <td>
                <button class="ghost icon-text" type="button" @click="viewStats(item.id)">
                  <Eye :size="17" />
                  数据
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-if="active === 'links'" class="links-grid">
        <section v-for="form in forms" :key="form.id" class="panel">
          <div class="panel-head">
            <div>
              <h2>{{ form.title }}</h2>
              <p>{{ form.unit.name }} · {{ form.period.name }}</p>
            </div>
          </div>
          <div class="level-actions">
            <div v-for="level in levels" :key="level.id" class="target-create">
              <span>{{ level.name }}</span>
              <input
                v-model.number="newLinkTargets[linkTargetKey(form.id, level.id)]"
                type="number"
                min="0"
                placeholder="目标人数"
              />
              <button class="ghost icon-text" type="button" @click="generateLink(form.id, level.id)">
                <QrCode :size="17" />
                生成
              </button>
            </div>
          </div>
          <div class="qr-list">
            <div v-for="link in linksByForm[form.id] || []" :key="link.id" class="qr-item">
              <img :src="qrUrl(link.token)" :alt="`${link.level.name}二维码`" />
              <div>
                <strong>{{ link.level.name }}</strong>
                <a :href="publicSurveyUrl(link.token)" target="_blank">
                  {{ publicSurveyUrl(link.token) }}
                </a>
                <div class="target-edit">
                  <Target :size="16" />
                  <input v-model.number="link.target_count" type="number" min="0" />
                  <span>已提交 {{ link.response_count }} 份 · {{ link.completion_percent }}%</span>
                  <button class="ghost icon-text" type="button" @click="updateLink(link)">
                    <Save :size="16" />
                    保存
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>
      </section>

      <section v-if="active === 'stats'" class="panel">
        <div class="panel-head">
          <h2>{{ isRoot ? "统计分析" : "填报数据情况" }}</h2>
          <select v-model="selectedStatsFormId" @change="selectStats(selectedStatsFormId)">
            <option value="">选择测评表</option>
            <option v-for="item in forms" :key="item.id" :value="item.id">
              {{ item.title }} · {{ item.unit.name }}
            </option>
          </select>
        </div>

        <div v-if="selectedStats" class="stats-layout">
          <div class="stat-summary">
            <span>整体满意度</span>
            <strong>{{ selectedStats.overall.satisfaction_percent }}%</strong>
            <small>
              已提交 {{ selectedStats.progress.response_count }} / 目标 {{ selectedStats.progress.target_count }}
            </small>
          </div>
          <div class="stats-table">
            <section class="stat-row section-stat">
              <div>
                <strong>全表汇总</strong>
                <span>有效选择 {{ selectedStats.overall.total }} 项次</span>
              </div>
              <div class="bar-track">
                <div
                  class="bar-fill"
                  :style="{ width: `${selectedStats.overall.satisfaction_percent}%` }"
                />
              </div>
              <div class="count-grid dynamic">
                <span v-for="option in selectedStats.overall.options" :key="option.option_id">
                  {{ option.label }} {{ option.count }}
                </span>
              </div>
            </section>

            <section v-for="section in selectedStats.sections" :key="section.section_id" class="section-stat-block">
              <div class="section-stat-title">
                <strong>{{ section.title }}</strong>
                <span>维度满意度 {{ section.summary.satisfaction_percent }}%</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${section.summary.satisfaction_percent}%` }" />
              </div>
              <div class="count-grid dynamic">
                <span v-for="option in section.summary.options" :key="option.option_id">
                  {{ option.label }} {{ option.count }}
                </span>
              </div>

              <div v-for="item in section.items" :key="item.item_id" class="stat-row item-stat">
                <div>
                  <strong>{{ item.title }}</strong>
                  <span>小项满意度 {{ item.summary.satisfaction_percent }}%</span>
                </div>
                <div class="bar-track">
                  <div class="bar-fill" :style="{ width: `${item.summary.satisfaction_percent}%` }" />
                </div>
                <div class="count-grid dynamic">
                  <span v-for="option in item.summary.options" :key="option.option_id">
                    {{ option.label }} {{ option.count }}
                  </span>
                </div>
              </div>
            </section>

            <section v-if="selectedStats.levels?.length" class="level-stats">
              <div class="section-stat-title">
                <strong>按测评人员层级统计</strong>
                <span>按每个层级二维码分别汇总</span>
              </div>
              <article
                v-for="levelStat in selectedStats.levels"
                :key="levelStat.level.id"
                class="level-stat-card"
              >
                <div class="level-stat-head">
                  <div>
                    <strong>{{ levelStat.level.name }}</strong>
                    <span>
                      进度 {{ levelStat.progress.response_count }}/{{ levelStat.progress.target_count }}
                      · {{ levelStat.progress.completion_percent }}%
                    </span>
                  </div>
                  <strong>{{ levelStat.overall.satisfaction_percent }}%</strong>
                </div>
                <div class="bar-track">
                  <div
                    class="bar-fill"
                    :style="{ width: `${levelStat.overall.satisfaction_percent}%` }"
                  />
                </div>
                <div class="count-grid dynamic">
                  <span v-for="option in levelStat.overall.options" :key="option.option_id">
                    {{ option.label }} {{ option.count }}
                  </span>
                </div>
                <details class="level-detail">
                  <summary>查看维度和小项明细</summary>
                  <section
                    v-for="section in levelStat.sections"
                    :key="section.section_id"
                    class="level-section-detail"
                  >
                    <div class="section-stat-title">
                      <strong>{{ section.title }}</strong>
                      <span>{{ section.summary.satisfaction_percent }}%</span>
                    </div>
                    <div class="count-grid dynamic">
                      <span v-for="option in section.summary.options" :key="option.option_id">
                        {{ option.label }} {{ option.count }}
                      </span>
                    </div>
                    <div v-for="item in section.items" :key="item.item_id" class="level-item-detail">
                      <strong>{{ item.title }}</strong>
                      <span>{{ item.summary.satisfaction_percent }}%</span>
                      <div class="count-grid dynamic">
                        <span v-for="option in item.summary.options" :key="option.option_id">
                          {{ option.label }} {{ option.count }}
                        </span>
                      </div>
                    </div>
                  </section>
                </details>
              </article>
            </section>
          </div>
        </div>
        <div v-else class="empty-state">选择一张测评表查看任务进度、维度汇总和小项明细。</div>
      </section>
    </section>
  </main>
</template>
