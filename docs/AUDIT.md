# IdeaParallax — 五轮检查与交付核验

日期：2026-10-05。范围：本次新建的独立项目，未修改此前项目。

这里的“五遍”是五轮**作者自审、针对性补测、修正和实际回归运行**，不是
五位外部审计员认证，也不是五次真实模型科研效果对照。每轮日志保留在本目录。

| 轮次 | 重点 | 发现并修正的问题 | 修正后累计测试 |
|---|---|---|---:|
| 1 | 架构、独立输入、数据合约 | 建立六分支独立构思、来源标签、严格输出与显式演示边界 | 18 |
| 2 | 进程、安全与资源边界 | 大输出子进程回收卡住；路径符号链接检查顺序；凭证环境名单；Git 文本读取限额 | 34 |
| 3 | 断点续跑和并发可靠性 | 损坏预算状态、取消后的阶段状态、并发新建目录竞态；评审改为并发独立执行 | 48 |
| 4 | 科研证据与原生接入 | 不同实验基线被并为同题；空检索词；零候选无理由；评审修改原稿；新增固定 commit 导出边界 | 69 |
| 5 | 接口、安装包与发布 | 重复 JSON 键、原生构思误当评审、负 usage、检索失败状态、发布文件白名单、构建兼容性与移动端报告溢出 | 91 |

## 每轮记录

[第 1 轮](audits/round-1.md) · [测试日志](audits/round-1-tests.txt)
[第 2 轮](audits/round-2.md) · [测试日志](audits/round-2-tests.txt)
[第 3 轮](audits/round-3.md) · [测试日志](audits/round-3-tests.txt)
[第 4 轮](audits/round-4.md) · [测试日志](audits/round-4-tests.txt)
[第 5 轮](audits/round-5.md) · [测试日志](audits/round-5-tests.txt)

第 2 轮修正前的子进程测试实际卡住，由外部测试时限终止；日志是部分输出，
不是完整的失败计数。第 3/4/5 轮分别记录了 4 个断言失败后再修复的结果。
测试总数逐轮增加；91 是最终累计测试数，不是五轮加总后的独立测试数。

## 安装和演示

[构建 wheel](audits/round-5-wheel.txt)、[安装日志](audits/round-5-install.txt)、
[安装后启动与续跑](audits/round-5-smoke.txt)。在源码目录之外启动安装包成功，
六条策略资源正确打包。重构建时下载构建工具遇到 DNS 失败，随后使用已安装
且满足最低版本的 setuptools 82.0.1 离线构建成功，网络失败日志也保留。最终演示明确标记 SYNTHETIC DEMO，包含 6 个合成候选、
2 个合成评审；断点续跑没有重复成功调用。

[浏览器核验](audits/round-5-browser.txt) 还实际检查了报告渲染、筛选、演示标记
和手机宽度布局；修复了运行指纹长文本导致的横向溢出。

复查命令：

```bash
python -m unittest discover -s tests -v
python -m compileall -q idea_parallax scripts tests
python -m idea_parallax demo --out runs/audit-demo
python -m idea_parallax demo --out runs/audit-demo --resume
```

## GitHub 发布状态

**本次尚未发布到 GitHub。** 已连接账户提供的接口只有读取能力；当前运行
环境有 git，但没有 gh、Codex CLI 或可用的已认证发布通道。
[实际发布前置检查日志](audits/github-publication.txt) 记录缺少 gh 导致停止，
没有创建远程仓库，更没有修改旧仓库。

交付附新仓库发布脚本和文件校验清单；脚本默认预览，显式 `--execute` 才会
创建，默认私有，成功后还会读取远程 main 提交以核对推送结果。安装并登录
GitHub CLI 后，从解压得到的项目目录运行：

```bash
gh auth login
python scripts/publish_github.py --owner hua1xiao2sheng --execute
```

仓库已存在时拒绝创建，不覆写；网络中断可能导致新仓库已创建但推送未完成，
此情况脚本会明确报告未确认成功，而不强行覆盖。发布记录是本次交付的历史
快照，之后由用户执行脚本成功不自动改写这份历史记录。

## 不应从这些测试推导出的结论

没有真实模型额度或 Codex 登录，本次未做真实论文 idea 质量测试，未完成六套
上游工程的端到端实跑。原生接入验证了固定版本、目录导出和宿主调用协议，
不是“所有原项目完整运行通过”。默认六条路线是明确标注的策略移植。

本地测试环境为 Linux/Python 3.13.5。仓库包含 Windows/Ubuntu CI 定义，
但远程 GitHub Actions、Windows 兼容性尚未由本次运行验证。

只提供保守结构去重和词法相似提示，不冒充完整语义等价判定。可选检索只获取
元数据，不代表阅读全文或保证世界范围的新颖性。独立上下文不是操作系统隔离；
外层调用上限不是每个上游内部调用和美元支出的严格上限。
