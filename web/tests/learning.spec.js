import { test, expect } from "@playwright/test";
import path from "node:path";
test("register, upload, ask, practice and review", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByRole("button", { name: "首次使用？创建账号" }).click();
  await page.getByLabel("用户名").fill(`test_${Date.now()}`);
  await page.getByLabel("密码", { exact: true }).fill("safe-password-123");
  await page.getByRole("button", { name: "注册并登录" }).click();
  await expect(page.getByRole("heading", { name: "我的知识库" })).toBeVisible();
  await page.getByPlaceholder("新建课程知识库").fill("机器学习");
  await page.getByRole("button", { name: "新建知识库", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "上传并建立索引" }),
  ).toBeVisible();
  await page
    .locator("input[type=file]")
    .setInputFiles(path.resolve("../datasets/machine-learning.md"));
  await page.getByRole("button", { name: "上传并建立索引" }).click();
  await expect(page.getByRole("status")).toContainText("入库完成");
  await page
    .getByPlaceholder("例如：学习率如何影响梯度下降？")
    .fill("学习率如何影响梯度下降？");
  await page.getByLabel('模型生成（需配置）').uncheck();
  await page.getByRole("button", { name: "检索并回答" }).click();
  await expect(
    page.getByRole("heading", { name: "资料中的原文证据" }),
  ).toBeVisible();
  await expect(page.locator(".source").first()).toContainText(
    "machine-learning.md",
  );
  await page
    .getByPlaceholder("例如：学习率如何影响梯度下降？")
    .fill("它为什么重要？");
  await page.getByRole("button", { name: "检索并回答" }).click();
  await expect(page.getByText("当前对话支持追问")).toBeVisible();
  await page.getByRole("button", { name: "新建对话" }).click();
  await expect(page.getByText("新对话", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "练习", exact: true }).click();
  await page.getByRole("button", { name: "生成 5 道练习" }).click();
  await expect(page.getByRole("button", { name: "提交答案" })).toHaveCount(5);
  await page.getByRole("radio").first().check();
  await page.getByRole("button", { name: "提交答案" }).first().click();
  await expect(page.locator(".feedback")).toContainText("正确答案");
  for (const kind of ["multiple", "judge", "short", "essay"]) {
    await page.getByLabel("练习题型").selectOption(kind);
    await page.getByRole("button", { name: "生成 5 道练习" }).click();
    if (kind === "multiple") await page.getByRole("checkbox").first().check();
    else if (kind === "judge") await page.getByRole("radio").first().check();
    else await page.locator("textarea").first().fill("梯度下降依赖学习率");
    await page.getByRole("button", { name: "提交答案" }).first().click();
    await expect(page.locator(".feedback")).toContainText("正确答案");
  }
  await page.getByRole("button", { name: "学习记录", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "建议复习顺序" }),
  ).toBeVisible();
  await expect(page.locator(".path")).not.toHaveCount(0);
  await page.locator(".workspace-title").click();
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({ path: "test-results/workspace.png", fullPage: true });
  await page.getByRole("button", { name: /退出/ }).click();
  await expect(
    page.getByRole("heading", { name: "进入学习空间" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
