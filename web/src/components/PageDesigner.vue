<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import grapesjs from "grapesjs";
import zh from "grapesjs/locale/zh";
import DOMPurify from "dompurify";
import "grapesjs/dist/css/grapes.min.css";
import Icon from "./Icon.vue";
const props = defineProps({
  userId: String,
  baseId: String,
  baseName: String,
  sources: { type: Array, default: () => [] },
  mastery: { type: Array, default: () => [] },
});
const host = ref(null),
  blockHost = ref(null),
  styleHost = ref(null),
  layerHost = ref(null),
  message = ref("正在加载编辑器…"),
  ready = ref(false),
  device = ref("桌面"),
  rightTab = ref("样式"),
  preview = ref(false);
let editor,
  saveTimer,
  disposed = false;
const key = `zhixue:design:v1:${props.userId}:${props.baseId}`;
const escape = (text) =>
  String(text ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const sheetCss = `*{box-sizing:border-box}body{margin:0;font-family:"Noto Sans SC","Microsoft YaHei","PingFang SC",system-ui,sans-serif;color:#2b4234;background:#f4f6ee;line-height:1.8}.learning-sheet{max-width:850px;margin:auto;padding:38px 32px}.sheet-heading{font-size:12px;color:#8aa276;letter-spacing:2px}.sheet-title{font-size:32px;font-weight:600;line-height:1.5;margin:12px 0 22px}.sheet-card{padding:24px;background:#fff;border:1px solid #e0e7d8;border-radius:12px;margin:18px 0}.sheet-card h2{font-size:18px;margin:0 0 14px}.sheet-card p{font-size:14px}.sheet-caption{font-size:11px;color:#91a280}.sheet-divider{border:0;border-top:1px solid #dce5d3;margin:26px 0}.sheet-columns{display:flex;gap:16px}.sheet-columns>div{flex:1;min-width:0}.sheet-callout{background:#eaf1df;border-left:3px solid #8aaa72;padding:20px;margin:18px 0}.sheet-callout p{margin:0}.sheet-footer{font-size:11px;color:#93a183;margin-top:24px}@media(max-width:600px){.learning-sheet{padding:24px 18px}.sheet-title{font-size:26px}.sheet-columns{display:block}}`;
function canvasFonts() {
  return [...document.styleSheets]
    .flatMap((sheet) => {
      try {
        return [...sheet.cssRules]
          .filter((rule) => rule.type === CSSRule.FONT_FACE_RULE)
          .map((rule) =>
            rule.cssText.replace(/url\(([^)]+)\)/g, (_, raw) => {
              const value = raw.trim().replace(/^["']|["']$/g, "");
              return `url("${new URL(value, sheet.href || document.baseURI).href}")`;
            }),
          );
      } catch {
        return [];
      }
    })
    .join("\n");
}
function initialHtml() {
  return `<main class="learning-sheet"><p class="sheet-heading">MY LEARNING NOTES</p><h1 class="sheet-title">${escape(props.baseName)} · 学习手记</h1><section class="sheet-card"><h2>今天，我想理解什么？</h2><p>双击文字，把你的问题与想法记在这里。</p><p class="sheet-caption">从左侧拖入组件，或点击组件将它插入页面。</p></section><section class="sheet-card"><h2>接下来的一步</h2><p>写下一个可以完成的小目标，再回到资料中寻找依据。</p></section><p class="sheet-footer">智学 · 用自己的方式，整理每一次理解。</p></main>`;
}
const blocks = [
  {
    id: "heading",
    label: "标题",
    content: "<h2>一个新的知识点</h2>",
    symbol: "H₂",
  },
  {
    id: "text",
    label: "文字",
    content: "<p>双击编辑，记录你的理解。</p>",
    symbol: "T",
  },
  {
    id: "card",
    label: "知识卡片",
    content:
      '<section class="sheet-card"><h2>核心概念</h2><p>写下定义、例子或你的疑问。</p></section>',
    symbol: "▤",
  },
  {
    id: "columns",
    label: "双栏对照",
    content:
      '<div class="sheet-columns"><div class="sheet-card"><h2>概念 A</h2><p>从定义开始。</p></div><div class="sheet-card"><h2>概念 B</h2><p>找出异同。</p></div></div>',
    symbol: "Ⅱ",
  },
  {
    id: "callout",
    label: "重点提示",
    content: '<aside class="sheet-callout"><p>记住一个关键点。</p></aside>',
    symbol: "!",
  },
  {
    id: "divider",
    label: "分隔线",
    content: '<hr class="sheet-divider">',
    symbol: "—",
  },
];
function addBlock(id) {
  if (!editor || !ready.value) return;
  const block = blocks.find((b) => b.id === id);
  if (!block) return;
  const sheet =
    editor.getWrapper().find(".learning-sheet")[0] || editor.getWrapper();
  const added = sheet.append(block.content);
  editor.select(added[0]);
  message.value = `已插入${block.label}`;
}
function save(silent = false) {
  if (!editor || !ready.value) return;
  try {
    const data = JSON.stringify(editor.getProjectData());
    if (data.length > 1_000_000) throw new Error("large");
    localStorage.setItem(key, data);
    if (!silent) message.value = "草稿已保存在当前浏览器";
  } catch {
    message.value =
      "草稿无法保存：浏览器存储不可用或页面过大，请导出 HTML 保留内容";
  }
}
function run(command) {
  if (editor && ready.value) editor.runCommand(command);
}
function setDevice() {
  if (!editor) return;
  editor.setDevice(device.value);
  const target =
    device.value === "手机" ? 375 : device.value === "平板" ? 768 : 0;
  const available = Math.max(200, host.value.clientWidth - 24);
  editor.Canvas.setZoom(
    target ? Math.min(100, Math.floor((available / target) * 100)) : 100,
  );
}
function togglePreview() {
  preview.value = !preview.value;
  if (preview.value) editor.runCommand("preview");
  else editor.stopCommand("preview");
}
function addSources() {
  if (!props.sources.length) return;
  const sheet =
    editor.getWrapper().find(".learning-sheet")[0] || editor.getWrapper();
  sheet.append(
    props.sources
      .map(
        (s, i) =>
          `<section class="sheet-card"><h2>资料摘录 ${i + 1}</h2><p>${escape(s.text)}</p><p class="sheet-caption">${escape(s.name)} · 第 ${Number(s.page)} 页</p></section>`,
      )
      .join(""),
  );
  message.value = "已插入当前问答的原文摘录";
}
function addReview() {
  const sheet =
    editor.getWrapper().find(".learning-sheet")[0] || editor.getWrapper();
  const rows = props.mastery
    .map(
      (r) =>
        `<li>${escape(r.topic)} · ${Math.round(r.mastery * 100)}% · ${Number(r.attempts)} 次练习</li>`,
    )
    .join("");
  sheet.append(
    `<section class="sheet-card"><h2>我的复习记录</h2><ul>${rows}</ul><p class="sheet-caption">根据已完成练习估计，仅供复习参考；此卡片不会自动更新。</p></section>`,
  );
  message.value = "已插入当前复习记录";
}
function exportHtml() {
  if (!editor) return;
  const clean = DOMPurify.sanitize(editor.getHtml({ cleanId: true }), {
    USE_PROFILES: { html: true },
    FORBID_TAGS: [
      "script",
      "iframe",
      "object",
      "embed",
      "form",
      "link",
      "meta",
      "base",
    ],
    FORBID_ATTR: ["srcdoc"],
  });
  const css = (sheetCss + "\n" + editor.getCss()).replace(/</g, "\\3c ");
  const text = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; script-src 'none'; base-uri 'none'; form-action 'none'"><title>${escape(props.baseName)} · 学习手记</title><style>${css}</style></head><body>${clean}</body></html>`;
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/html;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = "zhixue-learning-page.html";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  message.value = "已导出独立 HTML 页面，可在浏览器打开或打印为 PDF";
}
onMounted(() => {
  try {
    let project;
    const raw = localStorage.getItem(key);
    if (raw) {
      if (raw.length > 1_000_000) throw new Error("large");
      project = JSON.parse(raw);
    }
    editor = grapesjs.init({
      container: host.value,
      height: "620px",
      width: "auto",
      storageManager: false,
      canvasCss:
        canvasFonts() +
        '\nbody{font-family:"Noto Sans SC",system-ui,sans-serif!important}',
      panels: { defaults: [] },
      projectData: project,
      components: project ? undefined : initialHtml(),
      style: project ? undefined : sheetCss,
      jsInHtml: false,
      canvas: { scripts: [], styles: [] },
      parser: {
        optionsHtml: {
          allowScripts: false,
          allowUnsafeAttr: false,
          allowUnsafeAttrValue: false,
        },
      },
      i18n: { locale: "zh", localeFallback: "en", messages: { zh } },
      blockManager: {
        appendTo: blockHost.value,
        blocks: blocks.map((b) => ({
          ...b,
          media: `<span class="block-symbol">${b.symbol}</span>`,
          onClick: () => addBlock(b.id),
        })),
      },
      layerManager: { appendTo: layerHost.value },
      selectorManager: { appendTo: styleHost.value },
      styleManager: {
        appendTo: styleHost.value,
        sectors: [
          {
            name: "尺寸与间距",
            open: true,
            buildProps: ["width", "min-height", "padding", "margin"],
            properties: [
              { property: "width", name: "宽度" },
              { property: "min-height", name: "最小高度" },
              { property: "padding", name: "内边距" },
              { property: "margin", name: "外边距" },
            ],
          },
          {
            name: "文字",
            properties: [
              { property: "font-size", name: "字号" },
              { property: "font-weight", name: "字重" },
              { property: "color", name: "文字颜色" },
              { property: "text-align", name: "对齐" },
              { property: "line-height", name: "行高" },
            ],
            open: false,
            buildProps: [
              "font-size",
              "font-weight",
              "color",
              "text-align",
              "line-height",
            ],
          },
          {
            name: "外观",
            properties: [
              { property: "background-color", name: "背景色" },
              { property: "border", name: "边框" },
              { property: "border-radius", name: "圆角" },
              { property: "box-shadow", name: "阴影" },
            ],
            open: false,
            buildProps: [
              "background-color",
              "border",
              "border-radius",
              "box-shadow",
            ],
          },
        ],
      },
      deviceManager: {
        devices: [
          { name: "桌面", width: "" },
          { name: "平板", width: "768px", widthMedia: "900px" },
          { name: "手机", width: "375px", widthMedia: "600px" },
        ],
      },
    });
    editor.on("load", () => {
      if (disposed) return;
      ready.value = true;
      editor.Canvas.getFrameEl().setAttribute("title", "学习卡片画布");
      message.value = project
        ? "已恢复当前知识库的浏览器草稿"
        : "编辑器已就绪：拖拽或点击组件，双击画布文字进行编辑";
      blockHost.value.querySelectorAll(".gjs-block").forEach((el, i) => {
        el.setAttribute("role", "button");
        el.setAttribute("aria-label", blocks[i].label);
        el.tabIndex = 0;
        el.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            addBlock(blocks[i].id);
          }
        });
      });
    });
    editor.on("update", () => {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => save(true), 700);
    });
  } catch {
    message.value =
      "编辑器初始化失败。可切换到其他学习页面；浏览器草稿未被删除。";
  }
});
onBeforeUnmount(() => {
  disposed = true;
  clearTimeout(saveTimer);
  if (editor) {
    save(true);
    editor.destroy();
  }
});
</script>
<template>
  <div class="designer">
    <div class="designer-intro">
      <div>
        <span class="eyebrow">YOUR LEARNING CANVAS</span>
        <h3>给理解，一个自己的版面</h3>
        <p>拖拽组件、双击文字；草稿保存在当前浏览器，按账号与知识库区分。</p>
      </div>
      <span class="pill"><Icon name="layout" :size="14" />GrapesJS</span>
    </div>
    <div class="designer-toolbar">
      <div class="designer-devices">
        <Icon
          :name="device === '手机' ? 'mobile' : 'desktop'"
          :size="16"
        /><select
          v-model="device"
          aria-label="画布设备"
          :disabled="!ready"
          @change="setDevice"
        >
          <option>桌面</option>
          <option>平板</option>
          <option>手机</option>
        </select>
      </div>
      <button class="secondary" :disabled="!ready" @click="run('core:undo')">
        <Icon name="undo" :size="15" />撤销</button
      ><button class="secondary" :disabled="!ready" @click="run('core:redo')">
        重做</button
      ><button
        class="secondary"
        :disabled="!ready"
        :aria-pressed="preview"
        @click="togglePreview"
      >
        {{ preview ? "返回编辑" : "预览页面" }}</button
      ><span class="toolbar-space"></span
      ><button class="secondary" :disabled="!ready" @click="save(false)">
        <Icon name="save" :size="15" />保存草稿</button
      ><button :disabled="!ready" @click="exportHtml">
        <Icon name="download" :size="15" />导出 HTML
      </button>
    </div>
    <div class="designer-data">
      <button
        class="link"
        :disabled="!ready || !sources.length"
        @click="addSources"
      >
        <Icon name="file" :size="15" />插入问答出处</button
      ><button
        class="link"
        :disabled="!ready || !mastery.length"
        @click="addReview"
      >
        <Icon name="chart" :size="15" />插入复习记录</button
      ><span>导出页面是独立的学习笔记，不会更改应用界面。</span>
    </div>
    <div class="designer-body" :class="{ 'preview-mode': preview }">
      <aside class="designer-blocks">
        <h4>组件块</h4>
        <p>拖入画布，或点击插入</p>
        <div ref="blockHost"></div>
      </aside>
      <div ref="host" class="designer-canvas" aria-label="学习卡片编辑器"></div>
      <aside class="designer-properties">
        <div class="designer-tabs">
          <button
            :class="{ active: rightTab === '样式' }"
            @click="rightTab = '样式'"
          >
            样式</button
          ><button
            :class="{ active: rightTab === '图层' }"
            @click="rightTab = '图层'"
          >
            图层
          </button>
        </div>
        <p>先选中画布中的组件</p>
        <div v-show="rightTab === '样式'" ref="styleHost"></div>
        <div v-show="rightTab === '图层'" ref="layerHost"></div>
      </aside>
    </div>
    <p class="designer-status" role="status">{{ message }}</p>
    <p class="designer-note">
      草稿不会同步到其他设备。离开前可导出 HTML
      留存；清理浏览器数据会删除本地草稿。
    </p>
  </div>
</template>
<style>
.designer {
  --gjs-primary-color: #f5f7f0;
  --gjs-secondary-color: #d6e1cc;
  --gjs-tertiary-color: #709566;
  --gjs-quaternary-color: #72926a;
  --gjs-font-color: #6d805f;
  --gjs-main-color: #f5f7f0;
  --gjs-font-color-active: #315f3e;
  border: 1px solid #dde5d6;
  border-radius: 14px;
  background: #fff;
  overflow: hidden;
}
.designer-intro {
  padding: 24px;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  align-items: start;
  background: linear-gradient(120deg, #f9fbf5, #fff);
}
.designer-intro h3 {
  font-size: 18px;
  margin: 10px 0 7px;
}
.designer-intro p {
  font-size: 10px;
  color: #8a9b7b;
  line-height: 1.9;
  margin: 0;
}
.designer-toolbar {
  padding: 12px 15px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  border-top: 1px solid #e6ebdf;
  border-bottom: 1px solid #e6ebdf;
  background: #fafbf7;
}
.designer-toolbar button {
  font-size: 9px;
  padding: 8px 9px;
}
.designer-devices {
  display: flex;
  gap: 7px;
  align-items: center;
  margin-right: 6px;
  color: #8b9e78;
}
.designer-devices select {
  font-size: 10px;
  padding: 6px;
  width: 76px;
  border-color: #e1e9d8;
}
.toolbar-space {
  flex: 1;
}
.designer-data {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  flex-wrap: wrap;
  border-bottom: 1px solid #e6ebdf;
}
.designer-data .link {
  font-size: 9px;
}
.designer-data > span {
  font-size: 9px;
  color: #98a68b;
  margin-left: auto;
}
.designer-body {
  display: grid;
  grid-template-columns: 128px minmax(0, 1fr) 185px;
  background: #e9eee2;
  min-width: 0;
}
.designer-body > aside {
  min-width: 0;
  background: #f6f8f1;
  overflow: auto;
  max-height: 620px;
}
.designer-blocks {
  border-right: 1px solid #dfe7d5;
  padding: 12px 9px;
}
.designer-blocks h4 {
  font-size: 11px;
  font-weight: 500;
  color: #6d835e;
  margin: 4px 3px;
}
.designer-body aside > p {
  font-size: 8px;
  color: #98a58b;
  padding: 0 4px;
  line-height: 1.7;
}
.designer-canvas {
  min-width: 0;
  overflow: hidden;
}
.designer-properties {
  border-left: 1px solid #dfe7d5;
  padding: 12px 8px;
}
.designer-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
}
.designer-tabs button {
  font-size: 10px;
  padding: 6px 15px;
  background: transparent;
  color: #8e9e7e;
}
.designer-tabs .active {
  background: #e7efdc;
  color: #637e4f;
}
.designer .gjs-blocks-c {
  gap: 6px;
  padding: 4px 0;
}
.designer .gjs-block {
  width: calc(50% - 3px);
  min-width: 0;
  min-height: 77px;
  margin: 0;
  padding: 12px 4px;
  background: #fff;
  border: 1px solid #dde6d1;
  box-shadow: none;
  border-radius: 7px;
  color: #789367;
  font-family: inherit;
  font-size: 9px;
  cursor: grab;
}
.designer .gjs-block:hover {
  border-color: #8daa78;
  background: #f2f7e9;
}
.designer .gjs-block-label {
  font-size: 9px;
  margin-top: 7px;
}
.designer .gjs-block__media {
  margin: 0;
}
.block-symbol {
  font-size: 22px;
  font-family: Georgia, serif;
}
.designer .gjs-cv-canvas {
  width: 100%;
  height: 100%;
  top: 0;
  background: #e6ecdf;
}
.designer .gjs-one-bg {
  background: #f4f7ed;
}
.designer .gjs-two-color {
  color: #728665;
}
.designer .gjs-three-bg {
  background: #82a36d;
}
.designer .gjs-four-color {
  color: #749565;
}
.designer .gjs-sm-sector {
  border: 0;
  border-bottom: 1px solid #e0e7d7;
}
.designer .gjs-sm-sector-title {
  font-size: 10px;
  padding: 12px 6px;
  background: #eef3e5;
}
.designer .gjs-sm-property {
  font-size: 9px;
  padding: 8px 3px;
}
.designer .gjs-field {
  background: #fff;
  border: 1px solid #dfe7d4;
  color: #6a8059;
  border-radius: 4px;
  box-shadow: none;
}
.designer .gjs-field input,
.designer .gjs-field select {
  font-size: 10px;
  color: #698157;
  min-height: 24px;
}
.designer .gjs-sm-label {
  font-size: 9px;
}
.designer .gjs-sm-empty {
  font-size: 10px;
  color: #8a9d79;
  padding: 25px 5px;
}
.designer .gjs-clm-tags {
  padding: 8px;
  font-size: 10px;
}
.designer .gjs-layer {
  font-size: 10px;
  color: #718862;
}
.designer .gjs-layer-title {
  padding: 10px 3px;
}
.designer .gjs-selected {
  outline: 2px solid #85a96f !important;
}
.designer .gjs-toolbar {
  background: #769b64;
  border-radius: 4px;
}
.designer .gjs-toolbar-item {
  padding: 6px;
}
.designer-status {
  font-size: 10px;
  color: #758e65;
  margin: 0;
  padding: 13px 18px;
  border-top: 1px solid #dfe7d5;
  background: #f5f8ef;
}
.designer-note {
  font-size: 9px;
  color: #9ba78d;
  margin: 0;
  padding: 10px 18px;
  border-top: 1px solid #edf1e5;
}
.preview-mode {
  grid-template-columns: minmax(0, 1fr);
}
.preview-mode > .designer-blocks,
.preview-mode > .designer-properties {
  display: none;
}
@media (max-width: 1180px) {
  .designer-body {
    grid-template-columns: 100px minmax(0, 1fr) 155px;
  }
  .designer-data > span {
    width: 100%;
    margin: 0 7px 4px;
  }
  .designer-tabs button {
    padding: 6px 9px;
  }
}
@media (max-width: 650px) {
  .designer-intro {
    padding: 19px;
    gap: 8px;
  }
  .designer-intro > .pill {
    display: none;
  }
  .designer-toolbar {
    padding: 10px;
  }
  .toolbar-space {
    display: none;
  }
  .designer-body {
    grid-template-columns: minmax(0, 1fr);
  }
  .designer-body > .designer-blocks {
    border-right: 0;
    border-bottom: 1px solid #dfe7d5;
    padding: 10px;
  }
  .designer-blocks .gjs-blocks-c {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px;
  }
  .designer .gjs-block {
    width: 100%;
    min-height: 55px;
    padding: 9px 5px;
  }
  .block-symbol {
    font-size: 18px;
  }
  .designer-body > .designer-properties {
    max-height: 300px;
    border-left: 0;
    border-top: 1px solid #dfe7d5;
  }
  .designer-tabs {
    margin-bottom: 4px;
  }
  .designer-canvas {
    height: 620px;
  }
  .preview-mode > .designer-canvas {
    grid-column: 1;
  }
  .designer .gjs-block-label {
    margin-top: 4px;
  }
  .designer-intro h3 {
    font-size: 16px;
  }
  .designer-note {
    font-size: 8px;
  }
}
</style>

<style>
.designer .gjs-editor,
.designer .gjs-blocks-c,
.designer .gjs-block-label,
.designer .gjs-sm-sector,
.designer .gjs-sm-empty,
.designer .gjs-clm-tags,
.designer .gjs-layer,
.designer .gjs-sm-label {
  font-family: "Noto Sans SC", system-ui, sans-serif;
}
</style>
