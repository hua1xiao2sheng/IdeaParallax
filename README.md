# IdeaParallax

[GitHub 仓库](https://github.com/hua1xiao2sheng/IdeaParallax) · [发布核验](docs/PUBLICATION.md) · [五轮检查](docs/AUDIT.md)

**一个研究输入，多种独立策略；先各自构思，再带着证据一起比较。**

IdeaParallax 是一个**全新、独立的科研构思项目**。不修改、不依赖 OpenClaw、DSH、PaperForge 或以前的融合型 Idea Engine。它不会让总控先选方向再要求所有分支附和。

## 已实现的边界

- 六条可并行运行的策略移植：Orchestra、ARIS、IdeaSpark、K-Dense、EvoSkills、AI-Scientist-v2。
- Codex CLI、本地/远程 OpenAI-compatible Chat Completions API，以及显式授权的外部程序接口。
- 每分支独立上下文和临时工作目录；相同研究要求、不同策略；输出来源、提示版本和模型信息可追溯。
- 严格 JSON 合约、全局**调用次数**上限、并发上限、有限重试、成功阶段持久化和输入指纹约束的断点续跑。
- 保守结构去重，保留所有原稿；相似机制只建议复核，不按来源数量投票。
- 隐藏项目来源的独立上下文评审；缺少全文证据时强制标记 `insufficient_evidence`。
- 可选 Crossref 元数据检索，明确不等于全文阅读或全球查新。
- JSON、Markdown、可搜索的独立 HTML 报告；零密钥、零联网的**显式演示模式**。
- 本地 upstream 文本导入：完整 Git commit 固定、文件校验、人工信任开关。
- 原生项目执行接口 `native-codex`：把已审阅的本地仓库按完整 commit 导出到独立目录，让 Codex 按真实入口执行构思；另提供通用 JSON/外部程序接口。必须显式授权，不自动安装依赖，不启用自动实验。

**重要：默认是 `strategy_port`，不是声称完整执行了六个上游科研系统。** 源项目不被悄悄改写为同一个流程；本项目分别实现了六种不同的构思策略，但没有打包或假装执行它们的全部内部检索、裁判、质量门和实验脚本。详情见 [接入说明](docs/ADAPTERS.md)。

## 最快运行

需要 Python **3.11+**。核心程序只使用标准库；安装工具可能需要联网下载 setuptools。

```bash
python -m pip install -e .
python -m idea_parallax doctor
python -m idea_parallax demo --out runs/demo
```

打开 `runs/demo/report.html`。演示使用确定性测试数据，不调用模型，不查询文献，不运行实验；页面显著显示 `SYNTHETIC DEMO`。重新演示请换目录或加 `--resume`。

### 使用已经登录的 Codex

编辑 `examples/research.json`：研究问题、资源约束、已有材料和种子论文。然后：

```bash
python -m idea_parallax run --brief examples/research.json --config configs/codex.json --out runs/my-topic
```

模型字段留空时使用你的 Codex 配置。程序启动独立的 `codex exec` 会话，不复用此前会话；只读 sandbox，不启用绕过审批参数。Codex 必须已在本机安装、登录且对应模型可用。

```bash
python -m idea_parallax run --brief examples/research.json --config configs/codex.json --out runs/my-topic --resume
```

续跑必须保持输入、配置、策略和检索模式不变；已经成功的生成阶段不会再次计费。失败阶段可在剩余调用预算内重试。改变问题、模型或策略后须新建运行目录。

### 使用 API 或本地模型

复制 `configs/api.json` 为 `configs/api.local.json`，填写实际可用模型与 endpoint；密钥只放环境变量，不放配置文件：

```bash
# Bash / Git Bash
export IDEA_LLM_API_KEY='your-key'
python -m idea_parallax run --brief examples/research.json --config configs/api.local.json --out runs/api-topic
```

```powershell
# Windows PowerShell
$env:IDEA_LLM_API_KEY='your-key'
python -m idea_parallax run --brief examples/research.json --config configs/api.local.json --out runs/api-topic
```

接口使用 `/chat/completions`、`response_format: json_object` 和 `max_completion_tokens`。并非所有号称兼容的网关均支持这些字段；不兼容时会报错，不自动降级或改用演示。HTTP 仅允许 localhost/127.0.0.1/::1 的本地 endpoint；其他地址必须 HTTPS。

各 branch 可以单独配置 `provider`，`reviewer` 可配置为不同模型/服务。相同模型的多会话只是上下文独立，不能称为独立科学证据。

### 输入格式

```json
{
  "topic": "你的研究问题",
  "language": "zh-CN",
  "constraints": ["仅公开数据", "不额外标注", "优先低成本验证"],
  "context": "已经做了什么，还不确定什么",
  "seed_papers": [{"title": "实际论文标题", "url": "https://example.org/paper", "excerpt": "你提供的相关原文或笔记"}]
}
```

种子论文标记为用户提供、未独立核验。为避免隐私误外发，不会自动抓取输入中的任意 URL。报告和请求文件包含研究内容，默认仅保存在你指定的本地运行目录。

### 可选检索

```bash
python -m idea_parallax run --brief examples/research.json --config configs/codex.json --out runs/with-metadata --retrieval crossref
```

这会向 Crossref 发送候选检索式。每个候选取第一条检索式、最多 5 条元数据结果，缓存相同查询；不读取全文。空结果/网络失败绝不被转换成“从未有人做过”。

## 运行产物

```text
runs/my-topic/
  manifest.json          # 不变的输入/配置指纹
  state.json             # 调用预算与阶段状态
  stages/
    generate-*/request.json
    generate-*/result.json
    review-scientific/...
    review-feasibility/...
  retrieval/             # 显式启用才会查询
  report.json            # 全部候选、来源、证据与评审
  report.md              # 学生课题讨论稿
  report.html            # 可筛选的本地看板
```

候选数量是上限，不是质量配额。允许有理由的零候选；一个分支失败不会伪造替代结果。阶段成功表示返回内容通过本项目的数据合约，不证明原生项目的每个内部步骤都完成；完整上游流程的逐步证明尚未实现。状态 `partial`/`failed` 返回退出码 2；非法配置返回 1；中断返回 130。

## 安全、预算与研究诚信

独立工作目录**不是操作系统级机密隔离**。Codex 的本机配置、身份、全局能力仍可能共享；第三方程序也可能越过目录边界。对不可信原项目请使用单独容器/虚拟机，不要传入机密数据。详见 [SECURITY.md](SECURITY.md)。

`max_calls` 只硬限制外层 provider 请求次数，重试计入。Codex/原项目内部可能进行多次模型或工具调用；本项目不能承诺精确 token/美元总预算。API/CLI 返回的 usage 会记录，无法得知的费用为 `null`，不是 0。执行超时会终止本地进程，但远程服务已经发生的费用不能撤销。

查新结论、可行性和论文档次不作保证；两名模型评审不等于两位真实专家。没有自动实验、自动投稿、自动联系学生，也不预置“达到某会议水平”的标签。

## 开发与五轮检查

```bash
python -m unittest discover -s tests -v
python -m compileall -q idea_parallax scripts tests
```

五轮自审、修正和回归日志放在 [docs/audits](docs/audits/)，汇总见 [AUDIT.md](docs/AUDIT.md)。这是工程测试，不是六个上游科研系统的真实效果对照，也不是五位外部审计员的认证。

## 发布到一个新 GitHub 仓库

附带 `scripts/publish_github.py`，只从交付清单复制经过校验的文件到新临时 Git 仓库，默认私有，拒绝覆写旧仓库。它需要本机已安装且登录 GitHub CLI (`gh`)。

```bash
python scripts/publish_github.py --owner hua1xiao2sheng
# 上面仅预览；明确执行新建与推送：
python scripts/publish_github.py --owner hua1xiao2sheng --execute
```

本项目已发布到上方 GitHub 仓库。此脚本仅适用于创建一个全新的仓库，不应用于更新已经存在的 IdeaParallax；已有仓库请正常使用 Git 提交与推送。首次发布核验见 [PUBLICATION.md](docs/PUBLICATION.md)。

## 上游依据与许可

每条策略的上游仓库与入口可运行 `python -m idea_parallax catalog` 查看；详细依据见 [SOURCES.md](docs/SOURCES.md)。这些是方法来源，不表示作者背书或原项目运行成功。

IdeaParallax 自有代码使用 MIT 许可。不捆绑第三方代码、原始 skill 文本或模型凭证；后续导入上游文件需要遵循其各自许可。
