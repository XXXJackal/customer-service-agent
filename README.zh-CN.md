# Customer Service Agent · 极简版

**简体中文** | [English](README.md)

[![CI](https://github.com/XXXJackal/customer-service-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/XXXJackal/customer-service-agent/actions/workflows/ci.yml)
[![Eval Gate](https://github.com/XXXJackal/customer-service-agent/actions/workflows/eval.yml/badge.svg)](https://github.com/XXXJackal/customer-service-agent/actions/workflows/eval.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://github.com/astral-sh/ruff)

> 一个用来学习 **Loop Engineering** 与 **Harness Engineering** 两种最新范式的生产级客服 Agent 骨架。
> 全部核心模块手写,不依赖 LangChain / LangGraph / DSPy,代码可直接读懂。

> ⚠️ Before pushing to GitHub: replace every `XXXJackal` in this README, in `pyproject.toml`,
> in `CHANGELOG.md`, and in `.github/ISSUE_TEMPLATE/config.yml` with your GitHub username.

---

## 1. 为什么要学这两个东西

| 范式 | 一句话定义 | 解决什么问题 |
|---|---|---|
| **Loop Engineering** | 不再 prompt 单步任务,而是**设计**一个会自动迭代到目标达成的循环 | Agent 的"过程"——怎么思考、怎么调用工具、什么时候停 |
| **Harness Engineering** | 把 eval 当**生产基础设施**而非一次性脚本:轨迹存储 + 多类评分器 + CI Gate | Agent 的"质量"——上线前怎么知道它没退化 |

本项目把这两件事拆成最薄的两个目录:`src/agent/` 是循环,`src/harness/` 是评估架,任意一个文件单独打开都能读懂。

---

## 2. 项目结构

```
customer-service-agent/
├── src/
│   ├── agent/            # === Loop Engineering 核心 ===
│   │   ├── loop.py       # 内循环(ReAct) + 外循环(Verify-and-Retry)
│   │   ├── tools.py      # 6 个客服工具:FAQ / 订单 / 退款 / 改地址 / 退换货 / 转人工
│   │   ├── prompts.py    # 系统提示词
│   │   └── llm.py        # 一个极薄的 LLM 客户端封装
│   ├── harness/          # === Harness Engineering 核心 ===
│   │   ├── runner.py     # 把 Agent 跑在所有测试用例上
│   │   ├── graders.py    # 三类评分器:Code / LLM-Judge / Trajectory
│   │   ├── trajectory.py # 完整轨迹的数据模型(可重放)
│   │   └── metrics.py    # 聚合 + Pass/Fail 决策
│   └── knowledge/faq.json
├── eval/
│   ├── cases.jsonl       # 测试用例数据集(15 条,覆盖 13 个类别)
│   └── rubrics.json      # LLM-Judge 的评分细则
├── scripts/
│   ├── chat.py           # 交互式对话(看循环跑起来)
│   └── eval.py           # 跑评估架(出报告)
├── tests/
│   ├── test_loop.py      # 循环单元测试(伪 LLM,无需 API key)
│   └── test_tools.py     # 工具直接单元测试
└── .github/workflows/
    ├── ci.yml            # 每次 push:lint + 单测
    └── eval.yml          # PR Gate:跑完整评估架
```

---

## 3. Loop Engineering 在本项目里长什么样

`src/agent/loop.py` 实现了两层循环:

```
┌─────────────────────────────────────────────────────────┐
│  Outer Loop (Verify-and-Retry, 最多 N 次)               │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Inner Loop (ReAct, 最多 K 步)                    │  │
│  │    LLM 推理 → 选工具 → 执行 → 观察 → 再推理 ...   │  │
│  │    停止条件:LLM 输出 final answer                │  │
│  └───────────────────────────────────────────────────┘  │
│  Verifier 评分 → 不通过则把反馈塞回 messages,再跑一轮 │
└─────────────────────────────────────────────────────────┘
```

关键设计点(都写在 `loop.py` 注释里):

1. **Step Budget**:内循环最多 `max_steps` 步,防止无限工具调用
2. **Goal Condition**:外循环用一个轻量的 verifier 模型判断"答得够不够好"
3. **Writer/Reviewer 分离**:Verifier 用更便宜的模型,符合 loop engineering 主流做法
4. **Full Trajectory**:每一次 LLM 调用、工具调用、观察、评分都被记录,可重放、可评估

---

## 4. Harness Engineering 在本项目里长什么样

`src/harness/` 实现了 Anthropic 风格的评估架,核心组件:

| 组件 | 文件 | 作用 |
|---|---|---|
| **Task Runner** | `runner.py` | 把 Agent 跑在 `cases.jsonl` 的每个用例上 |
| **Trajectory Store** | `trajectory.py` | 把每次跑的完整轨迹序列化存盘,可重放 |
| **Grader Suite** | `graders.py` | 三类评分器:<br>· `CodeGrader`——确定性检查(是否调用了正确工具)<br>· `LLMJudgeGrader`——语义质量(基于 rubric)<br>· `TrajectoryGrader`——过程指标(步数、token、延迟) |
| **Aggregator** | `metrics.py` | 计算 pass rate、平均分,做 deploy 决策 |
| **CI Gate** | `.github/workflows/eval.yml` | PR 必须通过阈值才能 merge |

---

## 5. 快速开始

```bash
# 1. 安装
pip install -r requirements.txt
cp .env.example .env   # 填入 OPENAI_API_KEY(或任意兼容供应商的 key)

# 2. 跟 Agent 聊天(看循环跑起来)
python scripts/chat.py

# 3. 跑评估架(出 markdown 报告)
python scripts/eval.py --out report.md
```

`.env` 里的 `OPENAI_BASE_URL` 可以指向任意 OpenAI 兼容端点(DeepSeek / Qwen / Moonshot / 本地 vLLM 等),代码无需改动。

---

## 6. 你最值得逐字读的 3 个文件

如果时间紧,只读这三个就抓住了精髓:

1. `src/agent/loop.py` —— 看清"内循环 + 外循环"怎么写
2. `src/harness/graders.py` —— 看清"三类评分器"怎么写
3. `src/harness/runner.py` —— 看清"评估架"怎么把以上两者粘合起来

---

## License

MIT
