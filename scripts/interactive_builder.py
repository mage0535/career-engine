"""
Career Engine - 交互式简历构建器

通过结构化 Q&A 引导用户输入：
1. 基础档案 (profiles)
2. 工作经历 (experiences - STAR+R 结构)
3. 项目经历 (projects)
4. 技能栈 (skills - 分级管理)
5. 求职目标与偏好

支持断点续传、智能建议、自动验证。
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# 路径设置
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_DIR)
from core.database.models import (
    init_db, get_connection, create_profile, get_profile,
    get_profile_skills, get_profile_experiences
)

# ─────────────────────────────────────────────
# 输入辅助函数
# ─────────────────────────────────────────────

def _banner(title: str):
    print(f"\n{'═'*60}")
    print(f"  {title}")
    print(f"{'═'*60}")

def _input(prompt: str, default: str = '', required: bool = False,
           multiline: bool = False, choices: List[str] = None) -> str:
    """通用输入函数"""
    while True:
        if choices:
            print(f"\n📋 {prompt}")
            for i, c in enumerate(choices, 1):
                print(f"   [{i}] {c}")
            if default:
                print(f"   [Enter] 默认: {default}")
            raw = input("\n选择 > ").strip()
            if not raw and default:
                return default
            if raw.isdigit() and 1 <= int(raw) <= len(choices):
                return choices[int(raw) - 1]
            # 也支持直接输入文本
            if raw:
                return raw
            print("❌ 请选择有效选项")
            continue
        
        suffix = f" (默认: {default})" if default else ""
        suffix += " (必填)" if required else ""
        
        if multiline:
            print(f"\n📋 {prompt}{suffix}")
            print("   (输入空行结束)")
            lines = []
            while True:
                line = input("   > ")
                if not line and lines:
                    break
                lines.append(line)
            val = '\n'.join(lines).strip()
        else:
            print(f"\n📋 {prompt}{suffix}")
            val = input("   > ").strip()
        
        if not val and default:
            return default
        if required and not val:
            print("   ❌ 此项必填，请重新输入")
            continue
        return val

def _input_list(prompt: str, default: List[str] = None, separator: str = '，') -> List[str]:
    """列表输入 (逗号/顿号分隔)"""
    default_str = ', '.join(default) if default else ''
    raw = _input(prompt, default=default_str)
    if not raw:
        return default or []
    return [x.strip() for x in raw.replace(',', separator).replace('、', separator).split(separator) if x.strip()]

def _input_number(prompt: str, default: float = 0) -> float:
    """数字输入"""
    raw = _input(prompt, default=str(default) if default else '')
    try:
        return float(raw)
    except (ValueError, TypeError):
        return default


# ─────────────────────────────────────────────
# 模块 1: 基础档案
# ─────────────────────────────────────────────

def collect_profile() -> Dict[str, Any]:
    """采集用户基础档案"""
    _banner("📝 模块 1: 基础档案")
    
    profile = {}
    
    # 基本信息
    profile['name'] = _input("姓名/昵称", default="Magic we")
    profile['email'] = _input("联系邮箱", required=True)
    profile['phone'] = _input("联系电话")
    profile['wechat'] = _input("微信号")
    profile['github'] = _input("GitHub 主页 URL")
    profile['linkedin'] = _input("LinkedIn 主页 URL")
    profile['portfolio'] = _input("个人作品集/博客 URL")
    
    _banner("🎯 求职目标")
    profile['target_roles'] = json.dumps(
        _input_list("目标岗位 (逗号分隔)", default=["高级后端工程师", "AI 工程师"])
    )
    profile['target_industries'] = json.dumps(
        _input_list("目标行业 (逗号分隔)", default=["AI", "SaaS", "金融科技"])
    )
    profile['target_cities'] = json.dumps(
        _input_list("期望工作城市 (逗号分隔)", default=["北京", "上海", "远程"])
    )
    profile['target_companies'] = json.dumps(
        _input_list("目标公司 (逗号分隔，可跳过)", default=[])
    )
    
    _banner("💰 薪资期望")
    profile['min_salary'] = _input_number("最低接受薪资 (k/月)", default=20)
    profile['expected_salary'] = _input_number("期望薪资 (k/月)", default=35)
    profile['salary_currency'] = 'CNY'
    profile['salary_period'] = 'monthly'
    
    _banner("⚙️ 工作偏好")
    profile['remote_preference'] = _input(
        "远程偏好",
        choices=["fully_remote (全远程)", "hybrid (混合)", "onsite (坐班)", "no_preference (不限)"],
        default="no_preference (不限)"
    ).split(' ')[0]
    
    profile['deal_breakers'] = json.dumps(
        _input_list("绝对不接受的条件 (逗号分隔)", default=["996", "外包", "单休"])
    )
    profile['core_strengths'] = json.dumps(
        _input_list("你的 3 个核心优势 (逗号分隔)", default=["全栈开发", "AI 工程化", "系统架构"])
    )
    
    profile['career_summary'] = _input(
        "一句话职业定位 (如: 5 年经验的全栈工程师，专注 AI 应用落地)",
        multiline=True
    )
    
    return profile


# ─────────────────────────────────────────────
# 模块 2: 工作经历
# ─────────────────────────────────────────────

def collect_experiences() -> List[Dict[str, Any]]:
    """采集工作经历 (STAR+R 结构)"""
    _banner("📁 模块 2: 工作经历")
    
    experiences = []
    
    while True:
        _banner(f"📝 第 {len(experiences) + 1} 段工作经历")
        
        exp = {}
        exp['company'] = _input("公司名称", required=True)
        exp['company_size'] = _input(
            "公司规模",
            choices=["50人以下", "50-200人", "200-500人", "500-1000人", "1000-5000人", "5000人以上"]
        )
        exp['company_industry'] = _input("公司行业")
        exp['role'] = _input("职位/角色", required=True)
        exp['level'] = _input(
            "级别",
            choices=["初级/Junior", "中级/Mid", "高级/Senior", "专家/Staff", "架构师/Principal", "总监/Director", "其他"]
        )
        exp['start_date'] = _input("开始时间 (YYYY-MM)", required=True)
        exp['end_date'] = _input("结束时间 (YYYY-MM，至今则留空)")
        exp['is_current'] = exp['end_date'] in ('', '至今')
        
        _banner("📝 STAR+R 结构分解")
        print("💡 提示: STAR+R 是面试核心方法论")
        print("   S (Situation): 当时背景/挑战")
        print("   T (Task): 你负责的任务/目标")
        print("   A (Action): 你采取的关键行动")
        print("   R (Result): 可量化的结果")
        print("   R+ (Reflection): 反思与成长")
        
        exp['situation'] = _input(
            "S - 背景/挑战 (团队规模、技术债务、业务压力等)",
            multiline=True
        )
        exp['task'] = _input("T - 你的任务/目标", multiline=True)
        exp['action'] = _input("A - 关键行动 (技术方案、架构决策、团队管理等)", multiline=True)
        exp['result'] = _input("R - 可量化结果 (性能提升X%、节省成本Y万、用户增长Z%)", multiline=True)
        exp['reflection'] = _input("R+ - 反思与成长 (如果重来会做得不同的地方)", multiline=True)
        
        exp['responsibilities'] = json.dumps(
            _input_list("主要职责 (逗号分隔)", multiline=False)
        )
        exp['achievements'] = json.dumps(
            _input_list("关键成就/亮点 (逗号分隔)")
        )
        exp['tech_stack'] = json.dumps(
            _input_list("使用的技术栈 (逗号分隔)", default=["Python", "Go", "Docker"])
        )
        exp['team_size'] = _input_number("团队规模 (人数)", default=5)
        
        experiences.append(exp)
        
        if _input("继续添加下一段经历?", choices=["是", "否"], default="否") == "否":
            break
    
    return experiences


# ─────────────────────────────────────────────
# 模块 3: 技能栈
# ─────────────────────────────────────────────

SKILL_CATEGORIES = [
    'programming_language', 'framework', 'database', 'cloud_infra',
    'devops', 'ai_ml', 'mobile', 'frontend', 'backend',
    'architecture', 'tool', 'soft_skill', 'domain_knowledge', 'other'
]

PROFICIENCY_LEVELS = [
    (1, "了解 - 知道概念，能简单使用"),
    (2, "入门 - 能完成基本任务"),
    (3, "熟练 - 独立完成复杂任务"),
    (4, "精通 - 能指导他人，解决疑难"),
    (5, "专家 - 行业级认可，能设计架构"),
]


def collect_skills() -> List[Dict[str, Any]]:
    """采集技能栈"""
    _banner("🛠️ 模块 3: 技能栈")
    
    skills = []
    
    while True:
        skill = {}
        skill['name'] = _input("技能名称 (如: Python, React, Kubernetes)", required=True)
        
        print("\n技能分类:")
        for i, cat in enumerate(SKILL_CATEGORIES, 1):
            print(f"   [{i}] {cat}")
        cat_choice = input("选择 > ").strip()
        try:
            skill['category'] = SKILL_CATEGORIES[int(cat_choice) - 1]
        except (ValueError, IndexError):
            skill['category'] = 'other'
        
        print("\n熟练度:")
        for level, desc in PROFICIENCY_LEVELS:
            print(f"   [{level}] {desc}")
        prof = _input("选择熟练度 (1-5)", default="3")
        try:
            skill['proficiency'] = int(prof)
        except ValueError:
            skill['proficiency'] = 3
        
        skill['years_experience'] = _input_number("使用年限", default=1)
        
        skills.append(skill)
        
        if _input("继续添加下一个技能?", choices=["是", "否"], default="否") == "否":
            break
    
    return skills


# ─────────────────────────────────────────────
# 保存
# ─────────────────────────────────────────────

def save_all(profile: Dict, experiences: List[Dict], skills: List[Dict],
             db_path: str) -> int:
    """保存所有数据到数据库"""
    profile_id = create_profile(profile, db_path)
    print(f"\n✅ 基础档案已保存 (ID: {profile_id})")
    
    conn = get_connection(db_path)
    try:
        # 保存经历
        for exp in experiences:
            # 序列化 JSON 字段
            for field in ['responsibilities', 'achievements', 'tech_stack']:
                if field in exp and isinstance(exp[field], str):
                    pass  # 已经是 JSON 字符串
                elif field in exp:
                    exp[field] = json.dumps(exp[field], ensure_ascii=False)
            
            conn.execute("""
                INSERT INTO experiences (
                    profile_id, company, company_size, company_industry,
                    role, level, start_date, end_date, is_current,
                    situation, task, action, result, reflection,
                    responsibilities, achievements, tech_stack, team_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile_id, exp['company'], exp.get('company_size'), exp.get('company_industry'),
                exp['role'], exp.get('level'), exp['start_date'], exp.get('end_date'),
                exp.get('is_current', False),
                exp.get('situation'), exp.get('task'), exp.get('action'),
                exp.get('result'), exp.get('reflection'),
                exp.get('responsibilities', '[]'), exp.get('achievements', '[]'),
                exp.get('tech_stack', '[]'), exp.get('team_size'),
            ))
        print(f"✅ 工作经历已保存 ({len(experiences)} 段)")
        
        # 保存技能
        for skill in skills:
            conn.execute("""
                INSERT INTO skills (profile_id, name, category, proficiency, years_experience)
                VALUES (?, ?, ?, ?, ?)
            """, (
                profile_id, skill['name'], skill['category'],
                skill['proficiency'], skill.get('years_experience', 1)
            ))
        print(f"✅ 技能栈已保存 ({len(skills)} 项)")
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 保存失败: {e}")
        raise
    finally:
        conn.close()
    
    return profile_id


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def main(db_path: str = None):
    """交互式简历构建器主流程"""
    if not db_path:
        db_path = os.path.join(SKILL_DIR, "data", "career_engine.db")
    
    # 初始化数据库
    init_db(db_path)
    
    print("""
╔══════════════════════════════════════════════════════╗
║          🎯 Career Engine - 简历构建系统               ║
║          基于 STAR+R 方法论的结构化信息采集              ║
╚══════════════════════════════════════════════════════╝

💡 提示: 本系统将引导你完成简历档案的构建。
   你可以随时按 Ctrl+C 暂停，下次继续。
    """)
    
    try:
        # Step 1: 基础档案
        profile = collect_profile()
        
        # Step 2: 工作经历
        experiences = collect_experiences()
        
        # Step 3: 技能栈
        skills = collect_skills()
        
        # 保存
        profile_id = save_all(profile, experiences, skills, db_path)
        
        # 验证
        print(f"\n{'═'*60}")
        print("🎉 简历档案构建完成!")
        print(f"{'═'*60}")
        
        saved_profile = get_profile(profile_id, db_path)
        saved_skills = get_profile_skills(profile_id, db_path)
        saved_exps = get_profile_experiences(profile_id, db_path)
        
        print(f"\n📊 档案摘要:")
        print(f"   姓名: {saved_profile['name']}")
        print(f"   目标岗位: {', '.join(saved_profile.get('target_roles', []))}")
        print(f"   期望薪资: {saved_profile.get('expected_salary')}k/月")
        print(f"   工作经历: {len(saved_exps)} 段")
        print(f"   技能栈: {len(saved_skills)} 项")
        
        top_skills = [s['name'] for s in sorted(saved_skills, key=lambda x: -x['proficiency'])[:5]]
        print(f"   核心技能: {', '.join(top_skills)}")
        
        print(f"\n📋 下一步:")
        print(f"   1. 发送 JD 文本/链接给我 → A-F 匹配评估")
        print(f"   2. 运行岗位采集器 → 批量发现机会")
        print(f"   3. 生成定制简历 → ATS 优化")
        
    except KeyboardInterrupt:
        print("\n\n⏸️ 已暂停，数据不会丢失。")
        print("下次运行时可以从上次继续。")


if __name__ == "__main__":
    main()
