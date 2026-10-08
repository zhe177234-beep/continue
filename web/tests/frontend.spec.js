import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs/promises";
async function setup(page) {
  await page.goto("/");
  await page.getByRole("button", { name: "首次使用？创建账号" }).click();
  await page
    .getByLabel("用户名")
    .fill(`ui_${Date.now()}_${Math.floor(Math.random() * 999)}`);
  await page.getByLabel("密码", { exact: true }).fill("safe-password-123");
  await page.getByRole("button", { name: "注册并登录" }).click();
  await expect(
    page.getByRole("navigation", { name: "学习功能" }),
  ).toBeVisible();
  if (await page.getByRole("button", { name: "展开资料面板" }).isVisible())
    await page.getByRole("button", { name: "展开资料面板" }).click();
  await page.getByPlaceholder("新建课程知识库").fill("学习页面设计");
  await page.getByRole("button", { name: "新建知识库", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "上传并建立索引" }),
  ).toBeEnabled();
}
test("GrapesJS blocks, draft restore, devices, sources and standalone export", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  // Apply the production CSP to HTML while keeping Vite's development connection available.
  await page.route("**/*", async (route) => {
    if (route.request().resourceType() !== "document") return route.continue();
    const response = await route.fetch();
    await route.fulfill({
      response,
      headers: {
        ...response.headers(),
        "content-security-policy":
          "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; connect-src 'self' ws:",
      },
    });
  });
  await setup(page);
  await page
    .locator("input[type=file]")
    .setInputFiles(path.resolve("../datasets/machine-learning.md"));
  await page.getByRole("button", { name: "上传并建立索引" }).click();
  await expect(page.getByRole("status").first()).toContainText("入库完成");
  await page
    .getByPlaceholder("例如：学习率如何影响梯度下降？")
    .fill("梯度下降学习率");
  await page.getByRole("button", { name: "检索并回答" }).click();
  await expect(page.locator(".source").first()).toBeVisible();
  await page.getByRole("button", { name: "学习卡片" }).click();
  await expect(page.locator(".designer-status")).toContainText("编辑器已就绪");
  const frame = page.frameLocator('iframe[title="学习卡片画布"]');
  await expect(
    frame.getByRole("heading", { name: "学习页面设计 · 学习手记" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "标题", exact: true }).click();
  await expect(
    frame.getByRole("heading", { name: "一个新的知识点" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "撤销", exact: true }).click();
  await expect(
    frame.getByRole("heading", { name: "一个新的知识点" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "重做", exact: true }).click();
  await expect(
    frame.getByRole("heading", { name: "一个新的知识点" }),
  ).toBeVisible();
  const heading = frame.getByRole("heading", { name: "一个新的知识点" });
  await heading.dblclick();
  await heading.fill("我自己的学习标题");
  await page.getByRole("button", { name: "插入问答出处" }).click();
  await expect(frame.getByText("machine-learning.md · 第 1 页")).toBeVisible();
  await page.getByLabel("画布设备").selectOption("手机");
  await expect(page.locator(".gjs-frame-wrapper").first()).toHaveCSS(
    "width",
    "375px",
  );
  await page.getByRole("button", { name: "预览页面", exact: true }).click();
  await expect(page.locator(".designer-blocks")).toBeHidden();
  await page.getByRole("button", { name: "返回编辑", exact: true }).click();
  await page.getByLabel("画布设备").selectOption("桌面");
  await frame.locator("body").evaluate((el) => el.ownerDocument.fonts.ready);
  await expect
    .poll(async () => {
      const canvas = await page.locator(".gjs-cv-canvas").boundingBox();
      const wrapper = await page
        .locator(".gjs-frame-wrapper")
        .first()
        .boundingBox();
      return Math.abs(canvas.width - wrapper.width);
    })
    .toBeLessThan(2);
  const draggable = page.getByRole("button", { name: "文字", exact: true });
  const from = await draggable.boundingBox();
  const target = await frame.locator(".sheet-card").first().boundingBox();
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    target.x + target.width / 2,
    target.y + target.height - 8,
    { steps: 20 },
  );
  await expect(page.locator(".gjs-placeholder").first()).toBeVisible();
  await page.mouse.up();
  await expect(
    frame.getByText("双击编辑，记录你的理解。", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "保存草稿", exact: true }).click();
  await expect(page.locator(".designer-status")).toContainText(
    "草稿已保存在当前浏览器",
  );
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 HTML", exact: true }).click();
  const download = await downloadPromise;
  const html = await fs.readFile(await download.path(), "utf8");
  expect(html).toContain("我自己的学习标题");
  expect(html).toContain("machine-learning.md");
  expect(html).toContain("script-src 'none'");
  expect(html).not.toContain("<script");
  await page.getByRole("button", { name: "问答", exact: true }).click();
  await page.getByRole("button", { name: "学习卡片" }).click();
  await expect(page.locator(".designer-status")).toContainText("已恢复");
  await expect(
    page
      .frameLocator('iframe[title="学习卡片画布"]')
      .getByRole("heading", { name: "我自己的学习标题" }),
  ).toBeVisible();
  await page.locator(".workspace-title").click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page
    .frameLocator('iframe[title="学习卡片画布"]')
    .locator("body")
    .evaluate((el) => el.ownerDocument.fonts.ready);
  await page.screenshot({
    path: "test-results/designer-desktop.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test("mobile layout, keyboard blocks and knowledge filtering", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.screenshot({
    path: "test-results/login-mobile.png",
    fullPage: true,
  });
  await setup(page);
  await page
    .locator("input[type=file]")
    .setInputFiles(path.resolve("../datasets/machine-learning.md"));
  await page.getByRole("button", { name: "上传并建立索引" }).click();
  await expect(page.getByRole("status").first()).toContainText("入库完成");
  await page.getByRole("button", { name: "收起资料面板" }).click();
  await page.getByRole("button", { name: "知识关系", exact: true }).click();
  await page.getByLabel("筛选知识关系").fill("梯度下降");
  await expect(page.locator(".edge")).toHaveCount(2);
  await page.getByRole("button", { name: "学习卡片" }).click();
  await expect(page.locator(".designer-status")).toContainText("编辑器已就绪");
  const block = page.getByRole("button", { name: "知识卡片", exact: true });
  await block.focus();
  await page.keyboard.press("Enter");
  await expect(
    page
      .frameLocator('iframe[title="学习卡片画布"]')
      .getByRole("heading", { name: "核心概念" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/designer-mobile.png",
    fullPage: true,
  });
});
