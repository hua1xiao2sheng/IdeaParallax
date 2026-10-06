# 用一个 Codex 账号驱动 IdeaParallax

## 结构：谁负责什么

```text
浏览器控制面板（仅本机）
        ↓
IdeaParallax Python 服务（任务、并发、检查点、结果汇总）
        ↓
多个独立的 codex exec（同一个登录账号，不复用之前会话）
        ↓
不同策略的候选 → 可选文献元数据 → 两路独立上下文评审
        ↓
同一网页查看进度、候选、实验计划、风险与下载报告
```

六套策略不需要六个账号，也不需要 Claude、Gemini 或 API Key。
它们的模型能力都来自你的 Codex；方法不同，但仍可能共享模型偏差。
本功能默认运行 `strategy_port`，不是已部署并完整执行六个上游系统。

## 第一次使用（Windows PowerShell）

在你电脑上的终端检查：

```powershell
python --version
codex --version
codex login status
```

需要 Python 3.11+。Codex 命令不存在时，需要安装官方 Codex CLI；
仅浏览器登录或仅安装 IDE 插件，不自动保证 `codex` 在本终端的 PATH 中可运行。
官方安装说明：<https://developers.openai.com/codex/cli>。
通过 npm 安装 CLI 时需要 Node.js；本项目的网页本身没有 Node/npm 构建步骤。

```powershell
# 仅在尚未安装 CLI，且已安装 Node.js/npm 时执行
npm install -g @openai/codex

# 仅在未使用 ChatGPT 登录时执行；在官方浏览器流程中授权
codex login
codex login status
```

请不要把密码、API Key、auth.json 或浏览器 Cookie 发给项目或其他人。
CLI 只读取 `login status` 的分类，不把原始账户信息返回网页。
登录被组织策略限制时，按官方登录流程处理，不绕过策略。

已有项目：在 IdeaParallax 根目录运行 `git pull --ff-only`。
没有项目时：

```powershell
git clone https://github.com/hua1xiao2sheng/IdeaParallax.git
cd IdeaParallax
```

启动网页（不需要先 pip 安装）：

```powershell
python -m idea_parallax web --open
```

浏览器自动打开本机地址。终端必须保持运行。
也可以在仓库根目录双击 `scripts/start-web.cmd`，或从 PowerShell 运行它。
若你的 Python 需要 `py -3` 启动，可用 `py -3 -m idea_parallax web --open`。

## 网页里怎么操作

1. 先看“Codex 连接”。没有确认 ChatGPT 登录时不能启动真实任务，但可看离线演示。
2. 填写研究问题、已有工作和约束。可导入 .txt/.md 笔记；不支持直接解析 PDF。
   种子论文可填 title/url/excerpt JSON；论文链接不会自动被打开。
3. 第一次选 2 个策略、并发 1–2、每分支 1 个候选，关闭评审。模型先留空。
4. 确认会发送研究内容并消耗账号额度后，点击“开始真实构思”。
5. 右侧显示排队、运行、已完成、失败等阶段状态。每个分支返回后可以先看候选，
   不必等所有分支完成。这里不是模型逐 token 输出或完整内部执行轨迹。
6. 全部完成后按来源或关键词筛选，展开最小实验和评审；可下载 MD/JSON/HTML。

默认完整模式：六条策略，共 11 个候选的上限（五路各 2 个，IdeaSpark 1 个），
并发 2，无自动重试，另加两次评审。候选数量是上限，不要求凑数。
只允许一个总任务运行，但任务内部可并发 1–6 路；它们共用同一账号配额。

## 登录、额度与模型

真实网页模式设置 `subscription_only=true`：启动前检查 `codex login status`，
运行时再次检查，使用 `model_provider="openai"`，不继承 `OPENAI_API_KEY` 或 `CODEX_API_KEY`。
不会修改你的登录文件或自动登出。只有登录检查能确认 ChatGPT 登录时才开始。
组织配置、模型访问权、账号限额和服务故障仍然可能阻止执行。

模型留空沿用本机 Codex 的模型配置。网页不会把“ARIS”等项目名误当模型名，
也不承诺某个新模型一定对你的账号开放。没有额外账号不等于不限量。

账户剩余额度请在 Codex 自己的界面查看。网页显示的是**本任务外层调用槽**，
不是订阅余额或美元费用。一个 `codex exec` 内可能产生多次工具/模型调用。
默认禁用自动重试，避免遇到限额后连续重复发送。

官方参考（2026-10-06 核对）：
- 登录：<https://developers.openai.com/codex/auth>
- 脚本执行复用本地认证：<https://developers.openai.com/codex/noninteractive>
- 账号与限额：<https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan>

## 停止、续跑和历史记录

关闭浏览器标签不停止任务；点“停止当前任务”取消当前任务及其本地子进程，
并保留已经成功的阶段。已经消耗的调用槽和服务端消耗不会撤销。
Windows 下终止本次子进程树，不终止其他终端里的 Codex 会话。

预算未用完且存在 manifest 时可续跑，输入、策略、模型与配置不变。
已成功且校验一致的阶段不会重复发送。中断阶段的调用槽不返还；预算耗尽时
需要新建任务，而不是静默追加预算。新建任务会重新调用所有选中的分支。
强制关机可能留下 `.lock`；必须先确认旧进程结束，不能由网页擅自删除锁。

任务保存在 `runs/webui/<任务ID>/job.json` 和 `run/`。
重启同一个数据目录后可查看历史任务。换目录启动不会自动扫描你其他磁盘。
网页只显示由本控制面板管理的任务，不自动导入此前命令行的 runs/my-topic。

## 常见问题

| 问题 | 处理 |
|---|---|
| codex 不存在 | 在同一个终端安装 CLI 或确认 PATH，再启动网页；可用 `where.exe codex` 查看路径。 |
| npm 包装脚本无法运行 | 已处理官方 Windows npm `.cmd` → 固定 Node/JS 入口；非标准包装请指定真实可执行文件。 |
| 桌面/IDE 能用，网页检测未登录 | 在启动网页的同一环境执行 `codex login status`；Windows 与 WSL 的环境和登录目录可能不同。 |
| 出现模型不支持或限额错误 | 使用本账号已有模型、降低并发或等待额度恢复；网页不会自动购买或切换计费通道。 |
| 首次 Windows sandbox 设置阻塞 | 先在同一终端运行一次交互式 `codex`，按官方指引完成 sandbox 配置，不使用 --yolo。 |
| 端口已被占用 | `python -m idea_parallax web --port 8766 --open` |
| 手动打开地址提示未授权 | 用终端打印的完整带 `#token=` 地址打开；`--open` 会自动处理。重启后令牌会变化。 |
| 需要指定 Codex 路径 | `python -m idea_parallax web --open --codex-binary "C:\path\to\codex.exe"` |
| 程序只生成提案、不真正查新 | 这是当前边界；提供论文原文片段并人工核验。Crossref 仅取元数据，不保证新颖性。 |

## 安全范围

这是单人、本机工具，不是部署到公网的账号代理服务。只绑定 127.0.0.1；
每次启动随机令牌、所有数据接口验证令牌/Host/Origin；没有网页登录表单、
任意 shell 命令输入、任意文件读取接口或公网监听选项。
不要把它接到公开隧道、GitHub Pages、共享反向代理或陌生网页。
只读 sandbox 不是完全隔离，Codex 的本机全局设置与工具仍可能共享。
只有你信任的本机环境和研究材料才适合这样运行。
