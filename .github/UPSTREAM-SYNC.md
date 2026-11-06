# 官方正式版同步

`Sync official stable release` 每 6 小时（北京时间 02:23、08:23、14:23、20:23）
检查 `2dust/v2rayN` 的最新正式 Release；GitHub 调度可能延迟。
也可在 Actions 中手动 Run workflow。只跟踪最新正式版，不追踪每次 master 提交或预发布版。

- 官方版本已经包含在本仓库默认分支：不创建 PR。
- 有新版本：从官方 tag 的固定提交创建 `upstream/stable-*` 分支，再向默认分支创建 PR。
- 有合并冲突：创建 Issue 并 @IntMainJhy；重复运行更新同一个 Issue，避免刷屏。
- 运行失败：创建故障 Issue 并提供日志入口。如果连 Issue 创建也失败，查看 Actions 失败通知。
- 同版本已经有 PR：不会重复创建；关闭 PR 表示跳过该版本。
- 不自动合并、不覆盖 master、不自动发布定制安装包。

合并前检查 UI、构建和运行功能。使用 merge commit 合并同步 PR，保留上游提交历史；
不要使用 squash/rebase 合并同步 PR，否则以后可能无法用提交祖先关系识别已同步版本。
旧版 PR 未处理时，新正式版仍可创建新 PR；优先处理最新版本，旧 PR 可手动关闭。

## 仓库设置

1. Actions 开启（fork 默认可能禁用）。
2. Settings → Actions → General → Workflow permissions：
   勾选 **Allow GitHub Actions to create and approve pull requests**。
   默认 token 可保持只读，本工作流单独声明 contents / pull-requests / issues 写权限。
3. Settings → General → Features：开启 Issues。
4. GitHub 个人通知开启参与或 @提及通知；是否收到邮件取决于个人通知设置。

只使用内置 `GITHUB_TOKEN`，无需个人 PAT。由此 token 创建的 PR 检查可能需要在 PR 页面点击
**Approve workflows to run** 才会运行；请确认检查已运行并通过。本工作流自身不表示构建已通过。
公共仓库 60 天无活动时，GitHub 可能自动停用定时工作流，届时需在 Actions 页面重新开启。

## 本地验证

```sh
python3 -m unittest discover -s .github/scripts -p 'test_*.py'
```

测试使用临时 Git 仓库验证保留 UI 和冲突检测，并验证提醒去重、冲突再次出现和预发布过滤。
