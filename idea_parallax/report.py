from __future__ import annotations
import base64
import hashlib
from html import escape
from pathlib import Path
from .io_utils import write_text

CSS = """
:root{color-scheme:light;--ink:#172435;--muted:#5a6977;--line:#dce4e9;--accent:#0b736b}
*{box-sizing:border-box}body{margin:0;overflow-wrap:anywhere;background:#f4f7f8;color:var(--ink);font:15px/1.75 system-ui,'Segoe UI',sans-serif}
header{background:#152b3c;color:#edf7f6;padding:44px max(24px,calc((100vw - 1120px)/2)) 32px}
.brand{letter-spacing:.17em;color:#88d4c8;font-size:12px;font-weight:750}h1{font-size:34px;line-height:1.25;margin:12px 0}
.sub{color:#c3d2dc;max-width:850px}.wrap{max-width:1168px;padding:26px 24px 60px;margin:auto}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}.stat,.card,.panel{background:white;border:1px solid var(--line);border-radius:12px;padding:20px}.stat b{display:block;font-size:28px;line-height:1.2}.stat span{color:var(--muted);font-size:13px}
.notice{background:#fff5df;border:1px solid #e9d9af;border-radius:10px;padding:15px 18px;margin:16px 0}
.tools{display:flex;gap:12px;margin:24px 0;align-items:center}.tools label{flex-shrink:0;white-space:nowrap}input{width:100%;min-width:0;padding:13px 15px;border:1px solid var(--line);border-radius:8px;font:inherit}input:focus{outline:2px solid var(--accent)}
.card{margin-bottom:18px}.card h2{margin:8px 0 12px;font-size:21px}.tags{display:flex;gap:8px;flex-wrap:wrap}.tag{font-size:12px;background:#e8f5f2;color:#16534d;padding:3px 9px;border-radius:5px}.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}h3{font-size:14px;margin:15px 0 4px}p{margin:4px 0;white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer;font-weight:650;padding:10px 0}table{width:100%;table-layout:fixed;border-collapse:collapse}td,th{padding:9px;text-align:left;border-bottom:1px solid var(--line);overflow-wrap:anywhere}code{font-size:12px;overflow-wrap:anywhere}footer{color:var(--muted);margin-top:25px;font-size:12px}.empty{padding:20px}
@media(max-width:720px){.stats,.grid{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}header{padding:28px 20px}.wrap{padding:18px}h1{font-size:27px}.stat{padding:14px}}
"""
JS = """const input=document.querySelector('#filter');input.addEventListener('input',()=>{const q=input.value.toLocaleLowerCase();let visible=0;document.querySelectorAll('.card').forEach(c=>{const show=c.textContent.toLocaleLowerCase().includes(q);c.hidden=!show;if(show)visible++;});document.querySelector('#shown').textContent=String(visible);});"""

def assessments(report: dict, ident: str) -> list[dict]:
    return [{"role": r["role"], **item} for r in report["reviews"] if r["status"] == "succeeded"
            for item in r["output"]["assessments"] if item["idea_id"] == ident]

def md_text(value: str) -> str:
    # Escape raw HTML; prose is not executable content in a Markdown report.
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def render_reports(root: Path, report: dict):
    synthetic = report["synthetic_demo"]
    lines = ["# IdeaParallax · 并行科研构思报告", "", "**演示数据 / SYNTHETIC DEMO**" if synthetic else "**研究提案，尚未实验验证**",
             "", "## 研究输入", md_text(report["brief"]["topic"]), "",
             f"运行状态：{report['status']}；候选 {len(report['candidates'])} 个；结构组 {report['aggregation']['family_count']} 个。",
             "没有按仓库 Star 或出现次数投票；没有自动删除候选。", "", "## 必须保留的边界"]
    lines += ["- "+md_text(x) for x in report["warnings"]]
    lines += ["", "## 各分支状态"]
    for branch in report["branches"]:
        lines.append(f"- {branch['branch']}: {branch['status']} / {branch['execution_mode']} / {branch['project']}")
        if branch.get("error"):
            lines.append("  "+md_text(branch["error"]))
    lines += ["", "## 候选课题（不是自动选中的课题）"]
    cards = []
    for idea in report["candidates"]:
        lines += ["", "### "+md_text(idea["title"]), f"ID: `{idea['id']}`",
                  f"来源：{idea['provenance']['project']}；{idea['provenance']['execution_mode']}"]
        fields = [("研究问题", "research_question"), ("核心假说", "hypothesis"), ("技术机制", "mechanism"),
                  ("拟议差异（待查新）", "claimed_difference"), ("算力需求", "compute_requirement")]
        for title, key in fields:
            lines += [f"**{title}**："+md_text(idea[key])]
        lines += ["**最小实验**："]+[f"- {k}: {md_text(v)}" for k,v in idea["experiment"].items()]
        lines += ["**风险**："+md_text("；".join(idea["risks"])), "**查新检索式**："+md_text("；".join(idea["search_queries"]))]
        reviews = assessments(report, idea["id"])
        for rev in reviews:
            lines += [f"**{rev['role']} 评审**：{rev['novelty']} / {rev['feasibility']} / {rev['priority']}",
                      "反方意见："+md_text("；".join(rev["objections"])), "下一步："+md_text("；".join(rev["next_checks"]))]
        blocks = "".join(f"<h3>{escape(title)}</h3><p>{escape(idea[key])}</p>" for title,key in fields[:4])
        exp = "".join(f"<h3>{escape(k)}</h3><p>{escape(v)}</p>" for k,v in idea["experiment"].items())
        revhtml = "".join(f"<h3>{escape(r['role'])} · {escape(r['novelty'])}</h3><p>{escape('；'.join(r['objections']))}</p><p>下一步：{escape('；'.join(r['next_checks']))}</p>" for r in reviews)
        cards.append(f"<article class='card'><div class='tags'><span class='tag'>{escape(idea['provenance']['branch'])}</span><span class='tag'>{escape(idea['contribution_type'])}</span><span class='tag'>{escape(idea['provenance']['execution_mode'])}</span></div><h2>{escape(idea['title'])}</h2><code>{escape(idea['id'])}</code>{blocks}<details><summary>最小实验、风险与查新</summary><div class='grid'><div>{exp}</div><div><h3>风险</h3><p>{escape('；'.join(idea['risks']))}</p><h3>查新检索式</h3><p>{escape('；'.join(idea['search_queries']))}</p><h3>来源</h3><p>{escape(idea['provenance']['project'])}</p></div></div></details><details><summary>独立上下文评审（辅助意见）</summary>{revhtml or '<p>未完成评审</p>'}</details></article>")
    lines += ["", "## 文献证据登记（存在不等于支持主张）"]
    for record in report["evidence"]:
        lines.append(f"- {record['id']}: {md_text(record['title'])} / {record['status']}")
        lines.append("  "+md_text(record["url"]))
    write_text(root / "report.md", "\n".join(lines)+"\n")
    script_hash = base64.b64encode(hashlib.sha256(JS.encode()).digest()).decode()
    rows = "".join(f"<tr><td>{escape(b['branch'])}</td><td>{escape(b['status'])}</td><td>{escape(b['execution_mode'])}</td></tr>" for b in report["branches"])
    n = len(report["candidates"])
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-{script_hash}'; base-uri 'none'; form-action 'none'"><title>IdeaParallax · Research Ideas</title><style>{CSS}</style></head><body><header><div class="brand">IDEAPARALLAX / INDEPENDENT RESEARCH DIRECTIONS</div><h1>不同策略，同一个研究问题。</h1><p class="sub">{escape(report['brief']['topic'])}</p></header><main class="wrap"><section class="stats"><div class="stat"><b>{len(report['branches'])}</b><span>独立分支</span></div><div class="stat"><b>{n}</b><span>原始候选</span></div><div class="stat"><b>{report['aggregation']['family_count']}</b><span>结构去重组 · 原稿保留</span></div><div class="stat"><b>{report['budget']['calls_reserved']}</b><span>已占用调用预算</span></div></section><div class="notice"><strong>{'SYNTHETIC DEMO · 仅供流程演示' if synthetic else '研究提案 · 尚未实验验证'}</strong><p>策略移植不等于运行原项目。检索元数据不等于完成查新。没有自动选题，没有自动实验。</p></div><details class="panel"><summary>分支状态 · {escape(report['status'])}</summary><table><thead><tr><th>分支</th><th>状态</th><th>执行模式</th></tr></thead><tbody>{rows}</tbody></table></details><div class="tools"><label for="filter">筛选</label><input id="filter" placeholder="搜索机制、分支、风险或实验"><span id="shown">{n}</span></div>{''.join(cards) or '<div class="panel empty">没有有效候选。请检查分支状态；系统没有伪造替代输出。</div>'}<footer>运行指纹：{escape(report['run_fingerprint'])}<br>所有分数和评审均不构成论文发表或新颖性保证。完整来源、证据和中间结果见 report.json。</footer></main><script>{JS}</script></body></html>"""
    write_text(root / "report.html", html)
