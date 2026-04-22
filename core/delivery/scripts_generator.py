"""
Career Engine - 话术生成器

功能:
1. HR 初筛话术 (自我介绍、动机阐述、薪资期望)
2. 技术面试话术 (技术亮点、项目深度讲解)
3. 经理面试话术 (业务理解、团队协作、管理能力)
4. 薪资谈判话术 (锚定策略、竞品 Offer 杠杆)
5. 反问环节问题库 (展示思考深度的高质量问题)
"""

import json
import os
import sys
from typing import Dict, List, Optional, Any
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_DIR)
from core.database.models import get_connection, get_profile, get_profile_skills, get_profile_experiences


# ─────────────────────────────────────────────
# 话术模板库
# ─────────────────────────────────────────────

SCRIPT_TEMPLATES = {
    'hr_screening': {
        'self_introduction': """
面试官您好，我是{name}。

我目前是一名{current_role}，拥有{years}年{domain}领域经验。

在我的职业生涯中，我主要专注于{core_strengths}。最近一段在{recent_company}的经历中，我负责{key_responsibility}，取得了{key_result}。

我对贵公司的{company_highlight}方向非常感兴趣，认为我的{relevant_skill}经验能够为团队带来价值。

希望今天能有机会深入交流，谢谢！""",
        
        'motivation': """
我关注贵公司很久了，特别认可{company_culture}。

从职业发展角度，我希望在{career_goal}方向深耕，而贵公司在{specific_area}的实践正是我希望参与的方向。

此外，我了解到团队在{tech_challenge}方面正在突破，这与我的{skill_match}经验高度匹配。""",
        
        'salary_expectation': """
根据我的经验和市场行情，我的期望薪资是{expected_range}。

当然，我更看重的是{non_salary_priority}，薪资方面有一定的弹性空间。

想了解一下贵公司对这个岗位的预算范围是？""",
    },
    
    'technical': {
        'project_deep_dive': """
让我用 STAR 结构来介绍这个项目：

**背景**: {situation}
**挑战**: 当时面临{challenge}
**我的方案**: 我采用了{solution}，主要考虑{reasoning}
**技术细节**: {tech_details}
**结果**: 最终实现了{result}
**反思**: 如果重来，我会在{improvement}方面做得不同""",
        
        'strength_highlight': """
我的核心优势是{strength}，体现在：

1. **深度**: 在{area}方面，我有{years}年实战经验，主导过{project_count}个项目
2. **广度**: 除了{primary_skill}，我还熟悉{secondary_skills}
3. **实战**: 最近用{skill}解决了{problem}，提升了{metric}""",
    },
    
    'manager': {
        'business_understanding': """
我理解这个岗位的核心目标是{business_goal}。

从业务角度，当前面临的挑战可能是{business_challenge}。我的解决思路是：

1. **短期**: {short_term_action}
2. **中期**: {mid_term_action}
3. **长期**: {long_term_vision}

在之前的{similar_experience}经历中，我采用类似方法实现了{result}。""",
        
        'team_collaboration': """
我习惯的协作方式是：

- **沟通**: 定期 1:1 + 透明的进度同步
- **决策**: 数据驱动 + 充分讨论后快速执行
- **冲突**: 先理解对方立场，找到共同目标再讨论方案

在{team_size}人的团队中，我通过{collaboration_method}提升了团队效率{improvement}。""",
    },
    
    'salary_negotiation': {
        'anchor_high': """
感谢您提供的 Offer。基于我的{years}年经验、{key_achievement}的成果，以及目前市场上类似岗位的薪资水平，我的期望是{target_salary}。

这个数字考虑了{justification}，我相信这个薪资与我能带来的价值是匹配的。""",
        
        'competing_offer': """
我目前也在和其他公司沟通中，收到了{competing_salary}的 Offer。

但我更倾向于加入贵公司，因为{reason_prefer}。如果在薪资上能够接近{target_range}，我可以尽快做出决定。""",
        
        'non_salary_leverage': """
薪资之外，我还关注：

- **期权/股票**: 是否有长期激励机制？
- **弹性工作**: 远程/混合办公政策
- **成长预算**: 培训、会议、考证支持
- **设备**: 电脑、显示器等办公配置

如果薪资空间有限，这些方面的灵活性也会影响我的决策。""",
    },
}


# ─────────────────────────────────────────────
# 反问环节问题库
# ─────────────────────────────────────────────

QUESTIONS_BY_INTERVIEWER = {
    'hr': [
        "这个岗位是新设的还是替补？团队目前的规模是？",
        "公司的晋升机制是怎样的？通常的晋升周期是？",
        "团队的文化氛围如何？您在这里工作最大的感受是什么？",
        "这个岗位的绩效考核标准是什么？",
        "公司的培训和发展机会有哪些？",
        "这个岗位的前任离职原因是什么？（如果是替补）",
    ],
    'tech_lead': [
        "团队目前最大的技术挑战是什么？",
        "技术栈的决策流程是怎样的？有技术委员会吗？",
        "团队的代码审查和 CI/CD 流程是怎样的？",
        "您希望这个岗位入职后 3 个月内解决什么问题？",
        "团队的技术分享和知识沉淀机制是怎样的？",
        "目前系统的架构是怎样的？有哪些技术债务？",
    ],
    'manager': [
        "团队目前的业务目标是什么？这个岗位如何支撑？",
        "您对这个岗位 1 年后的期望是什么？",
        "团队的人员结构和分工是怎样的？",
        "您最看重候选人的什么特质？",
        "团队的协作方式是怎样的？跨部门沟通多吗？",
        "公司/部门未来的战略方向是什么？",
    ],
    'cto': [
        "公司的技术愿景是什么？",
        "技术团队在公司中的话语权和定位如何？",
        "公司在技术投入上的规划和预算是怎样的？",
        "您认为优秀的工程师应该具备什么特质？",
        "公司如何平衡业务需求和技术债务？",
        "技术团队的招聘标准和培养体系是怎样的？",
    ],
}


# ─────────────────────────────────────────────
# 话术生成器
# ─────────────────────────────────────────────

class ScriptGenerator:
    """话术生成器"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path
    
    def generate_hr_scripts(self, profile_id: int, job_id: int = None) -> Dict:
        """生成 HR 面试话术"""
        profile = get_profile(profile_id, self.db_path)
        if not profile:
            return {'error': 'Profile not found'}
        
        experiences = get_profile_experiences(profile_id, self.db_path)
        recent = experiences[0] if experiences else {}
        
        # 计算工作年限
        start_date = recent.get('start_date', '2020-01')
        years = max(1, (2026 - int(start_date.split('-')[0])))
        
        # HR 自我介绍
        self_intro = SCRIPT_TEMPLATES['hr_screening']['self_introduction'].format(
            name=profile['name'],
            current_role=profile.get('target_roles', ['工程师'])[0] if isinstance(profile.get('target_roles'), list) else '工程师',
            years=years,
            domain='技术',
            core_strengths=profile.get('core_strengths', '技术开发'),
            recent_company=recent.get('company', '上一家公司'),
            key_responsibility=recent.get('task', '核心项目开发'),
            key_result=recent.get('result', '显著的业务成果'),
            company_highlight='技术和产品',
            relevant_skill='技术',
        )
        
        # 动机阐述
        motivation = SCRIPT_TEMPLATES['hr_screening']['motivation'].format(
            company_culture='技术和产品',
            career_goal=profile.get('target_roles', ['技术'])[0] if isinstance(profile.get('target_roles'), list) else '技术',
            specific_area='业务创新',
            tech_challenge='技术架构',
            skill_match='技术',
        )
        
        # 薪资期望
        salary_exp = SCRIPT_TEMPLATES['hr_screening']['salary_expectation'].format(
            expected_range=f"{profile.get('expected_salary', 30)}k-{int(profile.get('expected_salary', 30) * 1.3)}k",
            non_salary_priority='个人成长和团队氛围',
        )
        
        return {
            'self_introduction': self_intro,
            'motivation': motivation,
            'salary_expectation': salary_exp,
            'opening_tips': [
                "保持微笑，语气自信",
                "控制时长在 2-3 分钟",
                "重点突出与岗位匹配的经历",
            ]
        }
    
    def generate_technical_scripts(self, profile_id: int, jd_text: str = '') -> Dict:
        """生成技术面试话术"""
        experiences = get_profile_experiences(profile_id, self.db_path)
        skills = get_profile_skills(profile_id, self.db_path)
        
        if not experiences:
            return {'error': 'No experiences found'}
        
        # 项目深度讲解 (基于最近经历)
        recent = experiences[0]
        project_script = SCRIPT_TEMPLATES['technical']['project_deep_dive'].format(
            situation=recent.get('situation', '业务发展需要'),
            challenge=recent.get('task', '技术难题'),
            solution=recent.get('action', '优化方案'),
            reasoning='性能和可维护性',
            tech_details=recent.get('tech_stack', '主流技术栈'),
            result=recent.get('result', '显著提升'),
            improvement='架构设计',
        )
        
        # 技术亮点
        top_skills = sorted(skills, key=lambda x: -x.get('proficiency', 0))[:5]
        strength_script = SCRIPT_TEMPLATES['technical']['strength_highlight'].format(
            strength=top_skills[0]['name'] if top_skills else '技术能力',
            area=top_skills[0]['name'] if top_skills else '技术',
            years=top_skills[0].get('years_experience', 3) if top_skills else 3,
            project_count=len(experiences),
            primary_skill=top_skills[0]['name'] if top_skills else '核心技术',
            secondary_skills=', '.join([s['name'] for s in top_skills[1:3]]) if len(top_skills) > 1 else '相关技术',
            skill=top_skills[0]['name'] if top_skills else '技术',
            problem='业务痛点',
            metric='效率',
        )
        
        # 预测技术话题
        predicted_topics = []
        for skill in top_skills[:5]:
            if skill['proficiency'] >= 4:
                predicted_topics.append(f"{skill['name']} 深度原理")
                predicted_topics.append(f"{skill['name']} 实战场景")
            if skill['proficiency'] >= 3:
                predicted_topics.append(f"{skill['name']} 常见问题")
        
        return {
            'project_deep_dive': project_script,
            'strength_highlight': strength_script,
            'predicted_topics': predicted_topics,
            'tips': [
                "用 STAR 结构回答问题",
                "技术深度 > 技术广度",
                "诚实承认知识盲区，展示学习意愿",
                "主动展示项目中的技术决策思考过程",
            ]
        }
    
    def generate_manager_scripts(self, profile_id: int, job_id: int = None) -> Dict:
        """生成经理面试话术"""
        profile = get_profile(profile_id, self.db_path)
        experiences = get_profile_experiences(profile_id, self.db_path)
        
        recent = experiences[0] if experiences else {}
        
        business_script = SCRIPT_TEMPLATES['manager']['business_understanding'].format(
            business_goal='业务增长',
            business_challenge='技术支撑',
            short_term_action='快速理解业务，建立技术信任',
            mid_term_action='优化架构，提升交付效率',
            long_term_vision='打造技术壁垒，支撑业务创新',
            similar_experience=recent.get('company', '上一家公司'),
            result=recent.get('result', '显著成果'),
        )
        
        collaboration_script = SCRIPT_TEMPLATES['manager']['team_collaboration'].format(
            team_size=recent.get('team_size', 5),
            collaboration_method='敏捷开发 + 定期技术分享',
            improvement='30%',
        )
        
        return {
            'business_understanding': business_script,
            'team_collaboration': collaboration_script,
            'questions_for_manager': QUESTIONS_BY_INTERVIEWER['manager'],
            'tips': [
                "展示业务思维，不只是技术思维",
                "强调团队协作和沟通能力",
                "准备 1-2 个跨部门协作的案例",
                "展现领导潜力和主人翁意识",
            ]
        }
    
    def generate_salary_negotiation(self, profile_id: int, offer_salary: float = None) -> Dict:
        """生成薪资谈判话术"""
        profile = get_profile(profile_id, self.db_path)
        if not profile:
            return {'error': 'Profile not found'}
        
        expected = profile.get('expected_salary', 30)
        min_accept = profile.get('min_salary', expected * 0.8)
        
        anchor_script = SCRIPT_TEMPLATES['salary_negotiation']['anchor_high'].format(
            years=5,
            key_achievement='核心项目交付',
            target_salary=f"{expected}k",
            justification='市场行情和我的经验',
        )
        
        non_salary_script = SCRIPT_TEMPLATES['salary_negotiation']['non_salary_leverage']
        
        return {
            'anchor_high': anchor_script,
            'target_range': f"{expected}k-{int(expected * 1.2)}k",
            'min_accept': f"{min_accept}k",
            'non_salary_leverage': non_salary_script,
            'negotiation_tips': [
                "先让对方出价，不要先暴露底线",
                "用数据支撑你的期望 (市场价、竞品 Offer)",
                "表现出对岗位的兴趣，但不要被拿捏",
                "谈判是合作，不是对抗",
                "如果薪资无法达到预期，争取其他福利补偿",
            ]
        }
    
    def get_questions_to_ask(self, interviewer_type: str = 'tech_lead') -> List[str]:
        """获取反问环节问题"""
        return QUESTIONS_BY_INTERVIEWER.get(interviewer_type, QUESTIONS_BY_INTERVIEWER['tech_lead'])


# ─────────────────────────────────────────────
# 保存到数据库
# ─────────────────────────────────────────────

def save_scripts_to_db(
    profile_id: int,
    job_id: int = None,
    application_id: int = None,
    interview_type: str = 'technical',
    scripts: Dict = None,
    db_path: str = None
) -> int:
    """保存话术到 interview_coaching 表"""
    if not scripts:
        return 0
    
    conn = get_connection(db_path)
    try:
        # 序列化 JSON 字段
        json_fields = [
            'opening_scripts', 'key_talking_points', 'salary_negotiation',
            'questions_to_ask', 'predicted_topics', 'technical_deep_dives',
            'weak_areas_prep', 'star_stories_matched', 'mock_questions',
            'mock_answers', 'improvement_points', 'lessons_learned'
        ]
        
        insert_data = {
            'profile_id': profile_id,
            'job_id': job_id,
            'application_id': application_id,
            'interview_type': interview_type,
            'round_number': 1,
        }
        
        for field in json_fields:
            if field in scripts:
                insert_data[field] = json.dumps(scripts[field], ensure_ascii=False)
        
        # 文本字段
        text_fields = ['self_introduction', 'mock_feedback', 'post_interview_notes']
        for field in text_fields:
            if field in scripts:
                insert_data[field] = scripts[field]
        
        columns = ', '.join(insert_data.keys())
        placeholders = ', '.join(['?' for _ in insert_data])
        values = [insert_data[k] for k in insert_data.keys()]
        
        cursor = conn.execute(
            f"INSERT INTO interview_coaching ({columns}) VALUES ({placeholders})",
            values
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


# ─────────────────────────────────────────────
# CLI 测试
# ─────────────────────────────────────────────

if __name__ == "__main__":
    db_path = os.path.join(SKILL_DIR, "data", "career_engine.db")
    generator = ScriptGenerator(db_path)
    
    if os.path.exists(db_path):
        print("🎤 HR 面试话术:")
        hr_scripts = generator.generate_hr_scripts(1)
        print(hr_scripts.get('self_introduction', '')[:300])
        print("...")
        
        print("\n🔧 技术面试话术:")
        tech_scripts = generator.generate_technical_scripts(1)
        print(f"预测话题: {tech_scripts.get('predicted_topics', [])}")
        
        print("\n💼 经理面试话术:")
        mgr_scripts = generator.generate_manager_scripts(1)
        print("业务理解要点:", mgr_scripts.get('business_understanding', '')[:200])
        print("...")
        
        print("\n💰 薪资谈判:")
        salary_scripts = generator.generate_salary_negotiation(1)
        print(f"期望范围: {salary_scripts.get('target_range', '')}")
        print(f"底线: {salary_scripts.get('min_accept', '')}")
    else:
        print("⚠️ 数据库不存在")
