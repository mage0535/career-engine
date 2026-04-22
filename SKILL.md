---
name: career-engine
description: 企业级求职自动化系统 - 基于 career-ops 方法论的 A-F 多维评分模型、智能简历构建、岗位采集与匹配、面试辅导、自动化投递追踪。零外部依赖 (纯 Python + SQLite)，可被任何 AI 助理直接加载。
metadata:
  version: 2.0.0
  category: career
  author: Hermes
  created: 2026-04-21
  updated: 2026-04-22
  shareable: true
  dependencies: []
---

# 🎯 Career Engine - 企业级求职自动化系统

## 系统定位

> Companies use AI to filter candidates. **We give candidates AI to *choose* and *win* companies.**

基于 [career-ops](https://github.com/career-ops/career-ops) 方法论解构重建的**求职决策与执行引擎**——从简历构建、岗位挖掘、智能匹配、面试辅导到投递追踪的全流程自动化。

**设计哲学**:
- **Not spray-and-pray**: 筛选器，帮你从海量 JD 中找到真正值得投入的机会
- **Human-in-the-Loop**: AI 评估+推荐，人工决策+执行
- **Zero dependencies**: 纯 Python + SQLite，任何 AI 助理可直接加载
- **Data-driven**: 所有数据写入 SQLite，持续优化

---

## 架构概览

```
career-engine/
├── SKILL.md                          # 本文档
├── core/
│   ├── database/
│   │   └── models.py                 # SQLite 数据模型 (12 表 + 1 视图 + 12 索引)
│   ├── collectors/
│   │   ├── base.py                   # 采集器基类 (反爬策略 + 数据标准化)
│   │   ├── boss_zhipin.py            # BOSS 直聘采集器 (Playwright)
│   │   └── platform_collectors.py    # 智联/前程无忧采集器
│   ├── scoring/
│   │   └── engine.py                 # A-F 多维评分引擎 ✅
│   ├── renderers/
│   │   └── ats_optimizer.py          # ATS 简历优化器 ✅ (文本 + HTML)
│   ├── optimizer/
│   │   ├── gap_analyzer.py           # JD 缺口分析 + 针对性问答 ✅
│   │   ├── interview_coach.py        # 专业面试辅导引擎 ✅
│   │   └── resume_analyzer.py        # 简历分析 + 优化建议 ✅
│   └── delivery/
│       ├── tracker.py                # 投递状态追踪 + 转化分析 ✅
│       └── scripts_generator.py      # 话术生成器 (HR/技术/经理/谈判) ✅
├── data/
│   └── career_engine.db              # SQLite 数据库 (运行时生成)
├── templates/
│   ├── html/                         # HTML 简历模板
│   ├── pdf/                          # PDF 简历模板
│   └── ats/                          # ATS 纯文本模板
├── scripts/
│   ├── cli.py                        # CLI 主入口 ✅
│   └── interactive_builder.py        # 交互式简历构建器 ✅
├── docs/
│   └── integration_guide.md          # 集成指南 (任何 AI 助理) ✅
└── config/
    ├── platforms.yaml                # 招聘平台配置
    └── scoring_weights.yaml          # 评分权重配置
```

---

## 核心工作流

### 1. 交互式简历构建
```
启动 → Q&A 引导 → STAR+R 经历提取 → 技能栈建模 (1-5 级) → 写入 SQLite
```
**命令**: `python scripts/interactive_builder.py`

### 2. 简历分析与优化
```
加载简历 → ATS 格式检查 → 关键词密度分析 → 量化成就统计 → 生成优化建议 → 保存分析
```
**命令**: `python scripts/cli.py analyze --jd "JD文本"`

### 3. 岗位评估 (A-F 评分)
```
JD 输入 → 关键词提取 → 岗位类型分类 → 8 维度加权评分 → 评级 + 报告
```
**命令**: `python scripts/cli.py evaluate "JD文本"`

### 4. 缺口分析与针对性优化
```
简历 vs JD → 技能缺口检测 → 经验缺口分析 → 生成针对性问题 → 用户回答 → 更新简历
```

### 5. 面试辅导
```
面试类型 → 话题预测 → 模拟面试 → 话术生成 → 实战记录 → 效果追踪 → 数据复盘
```
**命令**: `python scripts/cli.py interview --jd "JD文本" --type technical`

### 6. 投递追踪
```
状态机管理 → Follow-up 提醒 → 转化率分析 → 瓶颈检测 → 数据驱动优化
```
**命令**: `python scripts/cli.py tracker stats`

---

## A-F 评分模型 (8 维度加权)

| 维度 | 权重 | 说明 | 计算策略 |
|------|------|------|---------|
| Match | 25% | 技能与经验匹配度 | 精确匹配 + 模糊匹配 |
| Impact | 20% | 业务影响力与核心程度 | 岗位级别 + 关键词分析 |
| Growth | 15% | 技术成长与职业前景 | JD 描述 + 技术趋势 |
| Comp | 15% | 薪资与市场水平对比 | 分位基准 + 用户期望 |
| Culture | 10% | 团队氛围与远程政策 | JD 描述情感分析 |
| Tech Stack | 5% | 技术栈先进性与通用性 | 现代技术检测 |
| Stability | 5% | 公司融资状况与裁员风险 | 融资阶段 + 行业 |
| WLB | 5% | 加班强度与工作生活平衡 | 关键词检测 (996/双休等) |

**评级体系**:
| 评级 | 分数 | 含义 |
|------|------|------|
| A+ | 95-100 | Dream Job - 完美匹配 |
| A | 90-94 | Excellent - 极佳匹配 |
| A- | 85-89 | Great - 高度匹配 |
| B+ | 80-84 | Strong - 较好匹配 |
| B | 75-79 | Good - 基本匹配 |
| B- | 70-74 | Fair - 勉强匹配 |
| C | 60-69 | Pass - 匹配度一般 |
| D | 50-59 | Weak - 匹配度低 |
| F | <50 | Avoid - 不匹配/红旗 |

---

## 数据模型 (SQLite)

### 分级分层架构

```
L1 - profiles          (用户基础档案)
L2 - experiences       (工作经历 - STAR+R)
   - projects           (项目经历)
   - skills             (技能栈 - 1-5 分级)
L3 - companies         (公司档案)
   - jobs               (岗位库 - 多平台来源)
L4 - applications      (投递记录 - 状态机)
   - match_reports      (匹配评估报告)
L5 - interview_prep    (面试准备 - STAR 故事库)
   - salary_benchmarks  (薪酬基准数据)
L6 - interview_coaching (面试辅导 - 话术/预测/复盘)
   - resume_analytics   (简历分析 - 版本追踪/优化建议)
```

### 状态机 (投递流程)
```
not_applied → researching → prepared → applied → screening
→ phone_screen → interview_1 → interview_2 → interview_final
→ offer_received → offer_negotiating → offer_accepted
→ rejected / withdrawn / ghosted
```

---

## 使用方式

### 通过 Hermes
```
用户: "初始化求职系统"
→ 运行 interactive_builder.py

用户: "评估这个岗位: [JD文本/链接]"
→ 运行 cli.py evaluate

用户: "分析我的简历"
→ 运行 cli.py analyze

用户: "帮我准备技术面试"
→ 运行 cli.py interview --type technical

用户: "查看我的求职管道"
→ 运行 cli.py pipeline
```

### 通过 CLI
```bash
python scripts/cli.py init                          # 初始化
python scripts/cli.py evaluate "JD文本..."          # 评估
python scripts/cli.py analyze --jd "JD文本..."      # 简历分析
python scripts/cli.py interview --jd "JD..." --type technical  # 面试辅导
python scripts/cli.py resume --format html          # 生成简历
python scripts/cli.py tracker stats                 # 投递统计
python scripts/cli.py pipeline                      # 看板
python scripts/cli.py export                        # 导出
python scripts/interactive_builder.py               # 构建简历
```

### 通过 API (其他 AI 助理)
```python
import sys; sys.path.insert(0, '/path/to/career-engine')
from core.database.models import init_db, get_profile
from core.scoring.engine import evaluate_job
from core.optimizer.interview_coach import InterviewCoach
from core.delivery.scripts_generator import ScriptGenerator
from core.optimizer.resume_analyzer import ResumeAnalyzer

init_db()
report = evaluate_job(jd_text="...", profile_skills=["Python", "Go"])
coach = InterviewCoach()
prediction = coach.predict_interview_topics(1, "JD文本", "technical")
```

---

## 与 Career-Ops 的对比

| 特性 | career-ops | Career Engine |
|------|-----------|---------------|
| 核心架构 | Claude Code 专用 prompts | 通用 Python 库 |
| 数据存储 | Markdown + TSV | SQLite (12 表 + 索引) |
| 平台适配 | Greenhouse/Ashby/Lever | BOSS/智联/前程无忧/本地 |
| 评分维度 | 10 维度 (未公开权重) | 8 维度 (公开权重) |
| 依赖 | Claude Code + Playwright | 零依赖 (纯 Python 标准库) |
| 分享性 | 需 Claude Code 环境 | 任何 Python 环境可用 |
| 面试辅导 | ❌ | ✅ 话术 + 预测 + 模拟 + 复盘 |
| 简历分析 | ❌ | ✅ ATS 评分 + 优化建议 |
| 投递追踪 | TSV 文件 | 状态机 + 转化漏斗 |
| Dashboard | Go TUI (Bubble Tea) | CLI + 可扩展 Web |
| STAR+R | ✅ | ✅ |
| ATS PDF | ✅ | ✅ (文本 + HTML) |

---

## 当前状态

| 模块 | 状态 | 进度 |
|------|------|------|
| 数据库模型 | ✅ 完成 | 100% |
| 评分引擎 | ✅ 完成 | 100% |
| 简历优化器 | ✅ 完成 | 100% (文本+HTML) |
| 简历分析器 | ✅ 完成 | 100% |
| CLI 入口 | ✅ 完成 | 100% |
| 交互式构建器 | ✅ 完成 | 100% |
| 面试辅导 | ✅ 完成 | 100% |
| 话术生成器 | ✅ 完成 | 100% |
| 投递追踪器 | ✅ 完成 | 100% |
| 缺口分析器 | ✅ 完成 | 100% |
| 集成文档 | ✅ 完成 | 100% |
| 岗位采集器 | 🚧 基础完成 | 70% (需 Playwright) |
| PDF 渲染 | 🚧 待实现 | 0% |

---

## 当前用户配置
- **用户**: Magic we
- **数据库**: `data/career_engine.db`
- **状态**: 核心引擎全功能就绪
