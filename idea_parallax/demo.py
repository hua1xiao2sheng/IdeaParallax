"""Explicit deterministic test fixture; NOT a live model or a publishable idea generator."""
from __future__ import annotations
import copy

MECHANISMS = {
    "orchestra": ("假设反转", "用反证需求代替查询相似度决定下一步检索"),
    "aris": ("失效边界", "按缺失证据类型划分停止检索的失败模式"),
    "ideaspark": ("核心瓶颈", "用显式证据义务表约束检索动作"),
    "kdense": ("竞争解释", "并行构造两个竞争解释并寻找区分性证据"),
    "evoskills": ("跨域迁移", "把实验设计中的信息增益原则用于证据获取"),
    "scientist-v2": ("对照实验", "固定相同检索预算比较不同缺口选择规则"),
}

def demo_output(kind: str, payload: dict) -> dict:
    if kind == "review":
        return {"assessments": [{"idea_id": x["id"], "novelty": "insufficient_evidence", "feasibility": "unknown",
                 "priority": "needs_work", "strengths": ["演示：结构字段完整"],
                 "objections": ["演示数据，未查询真实文献，未完成实验"],
                 "next_checks": ["用真实模型与已核验文献重跑，然后由研究者判断"], "evidence_ids": []}
                 for x in payload["candidates"]], "notes": "SYNTHETIC DEMO — not an independent scientific review"}
    strategy = payload["strategy_id"]
    label, mechanism = MECHANISMS[strategy]
    idea = {"title": f"[演示] {label}路线", "research_question": payload["brief"]["topic"],
        "hypothesis": "演示假说：区分缺口的检索决策可能比重复相似性检索更节省调用；尚未验证。",
        "mechanism": mechanism, "claimed_difference": "待核验，不声称已超越或区别于任何已有工作。",
        "contribution_type": "diagnostic", "evidence_ids": [],
        "search_queries": ["retrieval augmented generation missing evidence active retrieval"],
        "experiment": {"dataset": "待研究者选择公开数据，演示未验证数据可用性", "baseline": "相同预算的重复检索",
            "metric": "答案支持度与检索调用数", "procedure": "先复现基线，再比较单一策略变量。这里只是演示文字。",
            "falsification": "控制预算后未观察到预先定义的收益，或收益来自泄漏/额外信息。"},
        "compute_requirement": "unknown; demo executes no experiment", "risks": ["未查新", "未验证实验可行性"]}
    return {"candidates": [copy.deepcopy(idea)], "notes": "SYNTHETIC DEMO — deterministic fixture, no API calls"}
