# Career Engine - 集成指南

## 适用于任何 AI 助理

本系统采用**纯 Python + SQLite** 架构，零外部依赖（仅需 Python 3.7+），可被任何 AI 助理直接加载使用。

---

## 快速集成

### 方式 1: 复制 Skill 目录

```bash
# 将整个 career-engine 目录复制到目标 AI 助理的 skills 目录
cp -r ~/.hermes/skills/career-engine /path/to/ai-assistant/skills/
```

### 方式 2: 作为 Git 子模块

```bash
git submodule add https://github.com/YOUR-REPO/career-engine.git skills/career-engine
```

### 方式 3: 直接导入 (AI 助理支持 Python 执行时)

```python
import sys
sys.path.insert(0, '/path/to/career-engine')
from core.database.models import init_db, get_profile
from core.scoring.engine import evaluate_job
from core.renderers.ats_optimizer import generate_ats_resume
```

---

## 核心 API

### 初始化
```python
from core.database.models import init_db
db_path = init_db()  # 创建数据库，返回路径
```

### 创建档案
```python
from core.database.models import create_profile

profile_id = create_profile({
    'name': '张三',
    'email': 'zhangsan@example.com',
    'target_roles': '["后端工程师", "AI 工程师"]',  # JSON 字符串
    'expected_salary': 35,
    # ... 其他字段
})
```

### 评估岗位
```python
from core.scoring.engine import evaluate_job

report = evaluate_job(
    jd_text="完整 JD 文本...",
    profile_skills=['Python', 'Go', 'Docker'],
    profile_data={'expected_salary': 35},
    salary_min=30,
    salary_max=50,
)

print(f"评级: {report['grade']} - {report['grade_desc']}")
print(f"总分: {report['overall_score']}")
```

### 生成简历
```python
from core.renderers.ats_optimizer import generate_ats_resume, generate_html_resume

# ATS 纯文本
ats_resume = generate_ats_resume(profile_id=1, jd_text="JD文本", db_path="path/to/db")

# HTML 美化
html_resume = generate_html_resume(profile_id=1, db_path="path/to/db")
```

### CLI 调用
```bash
python scripts/cli.py init
python scripts/cli.py evaluate "JD文本..."
python scripts/cli.py export --profile-id 1
python scripts/cli.py pipeline
```

---

## 数据库结构

| 表名 | 用途 | 核心字段 |
|------|------|---------|
| profiles | 用户基础档案 | name, email, target_roles, expected_salary |
| experiences | 工作经历 | company, role, STAR fields, tech_stack |
| projects | 项目经历 | name, description, impact_metrics |
| skills | 技能栈 | name, category, proficiency (1-5) |
| companies | 公司档案 | name, industry, size, funding |
| jobs | 岗位库 | title, company, salary, jd_text, archetype |
| applications | 投递记录 | status (状态机), applied_at |
| match_reports | 评估报告 | grade, overall_score, 8维度分数 |
| interview_prep | 面试准备 | star_stories, technical_topics |
| salary_benchmarks | 薪酬基准 | p25, p50, p75, p90 |

---

## 为其他 AI 助理适配

### Claude Code
```bash
# 在 CLAUDE.md 或 AGENTS.md 中添加:
# 使用 Career Engine 进行求职评估:
# cd ~/.hermes/skills/career-engine
# python scripts/cli.py evaluate "$JD_TEXT"
```

### OpenCode
```json
// 在 skills 配置中添加
{
  "name": "career-engine",
  "path": "~/.hermes/skills/career-engine",
  "commands": ["python scripts/cli.py evaluate"]
}
```

### Codex
```python
# 直接在对话中引导 Codex 执行:
# "使用 career-engine 评估这个岗位: python scripts/cli.py evaluate '...'"
```

### Cursor
```json
// .cursor/rules/career-engine.json
{
  "alwaysApply": false,
  "description": "Use Career Engine for job evaluation and resume generation",
  "instructions": "Run: python ~/.hermes/skills/career-engine/scripts/cli.py evaluate 'JD...'"
}
```

---

## 架构设计原则

1. **零外部依赖**: 仅使用 Python 标准库 + sqlite3
2. **数据本地化**: 所有数据存储在 SQLite，不上传第三方
3. **API 稳定**: 核心接口向后兼容
4. **模块化**: 每个模块可独立使用
5. **可分享**: 整个 skill 目录可直接复制到其他环境

---

## 扩展指南

### 添加新的招聘平台采集器

在 `core/collectors/` 下创建新文件，继承 `base.py` 中的 `BaseCollector`:

```python
from core.collectors.base import BaseCollector

class NewPlatformCollector(BaseCollector):
    def __init__(self):
        super().__init__(platform='new_platform')
    
    async def search_jobs(self, query: str, **kwargs) -> List[Dict]:
        # 实现搜索逻辑
        pass
```

### 自定义评分权重

编辑 `core/scoring/engine.py` 中的 `SCORING_WEIGHTS`:

```python
SCORING_WEIGHTS = {
    'match': 0.30,    # 提高匹配权重
    'comp': 0.20,     # 提高薪资权重
    # ... 其他维度
}
```

### 添加新的简历模板

在 `templates/html/` 下创建新的 HTML 模板文件，然后在 `ats_optimizer.py` 中添加引用。
