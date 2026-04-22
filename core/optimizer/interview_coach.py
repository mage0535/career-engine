"""
Career Engine - 专业面试辅导模块

功能:
1. 面试方向预测 (基于 JD 和用户简历)
2. 技术深挖准备 (针对用户薄弱点)
3. 模拟面试 (生成题目 + 参考答案)
4. 面试复盘 (记录实际问题 + 改进建议)
5. 效果追踪 (评估面试准备的有效性)
"""

import json
import os
import sys
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_DIR)
from core.database.models import get_connection, get_profile, get_profile_skills, get_profile_experiences
from core.scoring.engine import extract_keywords, detect_archetype


# ─────────────────────────────────────────────
# 技术面试题库 (按方向分类)
# ─────────────────────────────────────────────

TECH_QUESTION_BANK = {
    'python': {
        'basic': [
            "Python 中的 GIL 是什么？如何规避？",
            "Python 的内存管理机制？垃圾回收原理？",
            "装饰器的原理和应用场景？",
            "生成器和迭代器的区别？",
            "Python 中的深浅拷贝？",
        ],
        'advanced': [
            "asyncio 的事件循环机制？",
            "Python 的元类和装饰器元类？",
            "Python 的性能优化手段？",
            "GIL 对多线程的影响及解决方案？",
            "Python 的类型提示和静态检查？",
        ],
        'framework': [
            "Django/Flask/FastAPI 的架构差异？",
            "WSGI 和 ASGI 的区别？",
            "ORM 的 N+1 问题如何解决？",
            "如何设计一个高并发的 API 服务？",
        ],
    },
    'go': {
        'basic': [
            "Goroutine 和线程的区别？",
            "Channel 的底层实现？",
            "Go 的垃圾回收机制？",
            "defer 的执行顺序？",
            "interface 的底层结构？",
        ],
        'advanced': [
            "GMP 调度模型详解？",
            "Go 的内存分配器 (tcmalloc 变种)？",
            "逃逸分析的原理和应用？",
            "Go 的并发模式 (Worker Pool, Pipeline, Fan-in/out)？",
            "Go 的 GC 三色标记法？",
        ],
        'framework': [
            "Gin 的中间件机制？",
            "gRPC 和 REST 的对比？",
            "Go 微服务框架选型 (Go-Zero, Kratos, Go-Micro)？",
        ],
    },
    'java': {
        'basic': [
            "JVM 内存模型？",
            "HashMap 的底层实现？",
            "多线程的同步机制？",
            "Spring 的 IoC 和 AOP？",
            "Java 的垃圾回收算法？",
        ],
        'advanced': [
            "JVM 调优经验？",
            "Spring Boot 自动装配原理？",
            "分布式锁的实现方案？",
            "消息队列的选型和使用场景？",
            "微服务的分布式事务？",
        ],
    },
    'database': {
        'mysql': [
            "MySQL 的索引原理 (B+ 树)？",
            "事务的隔离级别和实现？",
            "慢查询优化经验？",
            "分库分表的方案？",
            "MySQL 的锁机制？",
        ],
        'redis': [
            "Redis 的数据结构和使用场景？",
            "Redis 的持久化机制 (RDB/AOF)？",
            "缓存穿透/击穿/雪崩的解决方案？",
            "Redis 集群方案 (Sentinel/Cluster)？",
            "Redis 的内存淘汰策略？",
        ],
    },
    'devops': {
        'docker': [
            "Docker 的底层原理 (Namespace, Cgroups, UnionFS)？",
            "Dockerfile 最佳实践？",
            "Docker 的网络模式？",
        ],
        'kubernetes': [
            "K8s 的架构和核心组件？",
            "Pod 的生命周期？",
            "Service 的几种类型？",
            "Deployment 和 StatefulSet 的区别？",
            "K8s 的调度策略？",
        ],
    },
    'system_design': {
        'general': [
            "设计一个短链接生成系统",
            "设计一个分布式 ID 生成器",
            "设计一个限流系统",
            "设计一个消息推送系统",
            "设计一个秒杀系统",
            "设计一个Feed流系统",
        ],
    },
    'ai_ml': {
        'general': [
            "大模型的训练流程？",
            "RAG 架构的原理和实现？",
            "Prompt Engineering 的最佳实践？",
            "如何评估一个 LLM 应用的效果？",
            "模型部署的性能优化？",
        ],
    },
}


# ─────────────────────────────────────────────
# 行为面试题库
# ─────────────────────────────────────────────

BEHAVIORAL_QUESTIONS = [
    ("介绍一个你最自豪的项目", "考察：项目深度、技术能力、主动性"),
    ("描述一次你解决复杂技术问题的经历", "考察：问题解决能力、技术深度"),
    ("描述一次团队冲突及其解决过程", "考察：沟通协作、情商"),
    ("描述一次你失败的经历以及你从中学到了什么", "考察：反思能力、成长思维"),
    ("如何在紧迫的 deadline 下保证质量", "考察：优先级管理、抗压能力"),
    ("描述一次你推动技术改进的经历", "考察：影响力、主动性"),
    ("你如何处理技术债务", "考察：工程思维、权衡能力"),
    ("你如何学习新技术", "考察：学习能力、方法"),
    ("描述一次你指导他人的经历", "考察：领导力、知识分享"),
    ("你为什么想离开现在的公司", "考察：动机、职业规划"),
]


# ─────────────────────────────────────────────
# 面试辅导引擎
# ─────────────────────────────────────────────

class InterviewCoach:
    """专业面试辅导引擎"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path
    
    def predict_interview_topics(
        self, profile_id: int, jd_text: str, interview_type: str = 'technical'
    ) -> Dict:
        """预测面试话题"""
        profile = get_profile(profile_id, self.db_path)
        skills = get_profile_skills(profile_id, self.db_path)
        experiences = get_profile_experiences(profile_id, self.db_path)
        
        if not profile:
            return {'error': 'Profile not found'}
        
        jd_keywords = extract_keywords(jd_text)
        archetype = detect_archetype(jd_text)
        
        # 分析用户技能与 JD 的匹配
        profile_skills_map = {s['name'].lower(): s for s in skills}
        
        matched_skills = []
        gap_skills = []
        
        for kw in jd_keywords:
            kw_lower = kw.lower()
            # 精确匹配
            if kw_lower in profile_skills_map:
                matched_skills.append({
                    'name': kw,
                    'proficiency': profile_skills_map[kw_lower]['proficiency'],
                    'years': profile_skills_map[kw_lower].get('years_experience', 0),
                })
            else:
                # 模糊匹配
                fuzzy_match = False
                for ps in skills:
                    if kw_lower in ps['name'].lower() or ps['name'].lower() in kw_lower:
                        matched_skills.append({
                            'name': kw,
                            'proficiency': ps['proficiency'],
                            'years': ps.get('years_experience', 0),
                            'matched_as': ps['name'],
                        })
                        fuzzy_match = True
                        break
                if not fuzzy_match:
                    gap_skills.append(kw)
        
        # 生成预测话题
        predicted_topics = []
        technical_deep_dives = []
        weak_areas = []
        
        # 匹配到的技能 -> 深挖方向
        for skill in matched_skills:
            prof = skill['proficiency']
            name = skill['name'].lower()
            
            # 在题库中查找
            for tech, questions in TECH_QUESTION_BANK.items():
                if tech in name or name in tech:
                    if prof >= 4:
                        predicted_topics.extend(questions.get('advanced', []))
                    if prof >= 3:
                        predicted_topics.extend(questions.get('basic', []))
                    if 'framework' in questions:
                        predicted_topics.extend(questions['framework'])
        
        # 去重
        predicted_topics = list(dict.fromkeys(predicted_topics))
        
        # 技能缺口 -> 准备建议
        for gap in gap_skills[:5]:
            weak_areas.append({
                'skill': gap,
                'suggestion': f"了解 {gap} 的基本概念，诚实承认经验不足，但展示学习意愿",
                'risk_level': 'high' if gap in ['python', 'go', 'java'] else 'medium',
            })
        
        # 系统设计话题
        if archetype in ('backend', 'fullstack', 'devops'):
            predicted_topics.extend(TECH_QUESTION_BANK['system_design']['general'][:3])
        
        # AI/ML 话题
        if archetype == 'ai_ml':
            predicted_topics.extend(TECH_QUESTION_BANK['ai_ml']['general'])
        
        return {
            'matched_skills': matched_skills,
            'gap_skills': gap_skills,
            'predicted_topics': predicted_topics[:20],  # 限制数量
            'technical_deep_dives': technical_deep_dives,
            'weak_areas': weak_areas,
            'archetype': archetype,
            'jd_keywords': jd_keywords,
        }
    
    def generate_mock_interview(
        self, profile_id: int, jd_text: str,
        interview_type: str = 'technical', round_number: int = 1
    ) -> Dict:
        """生成模拟面试"""
        prediction = self.predict_interview_topics(profile_id, jd_text, interview_type)
        
        if 'error' in prediction:
            return prediction
        
        questions = []
        
        if interview_type == 'technical':
            # 技术面：技术题 + 项目深挖
            tech_questions = prediction['predicted_topics'][:5]
            for q in tech_questions:
                questions.append({
                    'type': 'technical',
                    'question': q,
                    'difficulty': 'hard' if '高级' in q or '底层' in q or '原理' in q else 'medium',
                    'tips': '用 STAR 结构回答，先讲背景，再讲方案，最后讲结果',
                })
            
            # 项目相关
            experiences = get_profile_experiences(profile_id, self.db_path)
            for exp in experiences[:2]:
                if exp.get('action'):
                    questions.append({
                        'type': 'project',
                        'question': f"请详细介绍你在 {exp['company']} 的 {exp['role']} 期间做的一个项目",
                        'context': f"背景: {exp.get('situation', '')}",
                        'expected_focus': '技术决策过程、遇到的挑战、最终成果',
                    })
        
        elif interview_type == 'behavioral':
            # 行为面
            import random
            selected = random.sample(BEHAVIORAL_QUESTIONS, min(5, len(BEHAVIORAL_QUESTIONS)))
            for q,考察 in selected:
                questions.append({
                    'type': 'behavioral',
                    'question': q,
                    '考察点': 考察,
                    'tips': '使用 STAR+R 结构，重点突出 Result 和 Reflection',
                })
        
        elif interview_type == 'hr_screening':
            questions = [
                {'type': 'intro', 'question': '请做一下自我介绍', 'tips': '2-3 分钟，突出与岗位匹配的经历'},
                {'type': 'motivation', 'question': '为什么想加入我们公司？', 'tips': '展示对公司的了解和兴趣'},
                {'type': 'career', 'question': '你的职业规划是什么？', 'tips': '与公司发展方向对齐'},
                {'type': 'salary', 'question': '你的期望薪资是多少？', 'tips': '给出范围，不要给具体数字'},
                {'type': 'availability', 'question': '你多久可以到岗？', 'tips': '如实回答，如有竞业协议提前说明'},
            ]
        
        return {
            'interview_type': interview_type,
            'round_number': round_number,
            'questions': questions,
            'predicted_topics': prediction['predicted_topics'][:10],
            'weak_areas': prediction['weak_areas'],
            'preparation_tips': self._get_preparation_tips(interview_type),
        }
    
    def save_interview_record(
        self, profile_id: int, job_id: int, application_id: int,
        interview_type: str, round_number: int,
        actual_questions: List[str],
        self_assessment: Dict = None,
        notes: str = '',
        effectiveness_score: int = None,
    ) -> int:
        """保存面试实战记录"""
        conn = get_connection(self.db_path)
        try:
            # 检查是否已有记录
            existing = conn.execute("""
                SELECT id FROM interview_coaching 
                WHERE application_id = ? AND interview_type = ? AND round_number = ?
            """, (application_id, interview_type, round_number)).fetchone()
            
            if existing:
                # 更新
                conn.execute("""
                    UPDATE interview_coaching 
                    SET actual_questions = ?, self_assessment = ?, 
                        post_interview_notes = ?, effectiveness_score = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    json.dumps(actual_questions, ensure_ascii=False),
                    json.dumps(self_assessment, ensure_ascii=False) if self_assessment else None,
                    notes,
                    effectiveness_score,
                    existing['id']
                ))
                return existing['id']
            else:
                # 插入
                cursor = conn.execute("""
                    INSERT INTO interview_coaching (
                        profile_id, job_id, application_id,
                        interview_type, round_number,
                        actual_questions, self_assessment,
                        post_interview_notes, effectiveness_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile_id, job_id, application_id,
                    interview_type, round_number,
                    json.dumps(actual_questions, ensure_ascii=False),
                    json.dumps(self_assessment, ensure_ascii=False) if self_assessment else None,
                    notes,
                    effectiveness_score,
                ))
                conn.commit()
                return cursor.lastrowid
        finally:
            conn.close()
    
    def get_interview_history(self, profile_id: int) -> List[Dict]:
        """获取面试历史记录"""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("""
                SELECT ic.*, j.company, j.title
                FROM interview_coaching ic
                LEFT JOIN jobs j ON ic.job_id = j.id
                WHERE ic.profile_id = ?
                ORDER BY ic.created_at DESC
            """, (profile_id,)).fetchall()
            
            result = []
            for row in rows:
                d = dict(row)
                if d.get('actual_questions'):
                    try:
                        d['actual_questions'] = json.loads(d['actual_questions'])
                    except:
                        pass
                if d.get('self_assessment'):
                    try:
                        d['self_assessment'] = json.loads(d['self_assessment'])
                    except:
                        pass
                if d.get('improvement_points'):
                    try:
                        d['improvement_points'] = json.loads(d['improvement_points'])
                    except:
                        pass
                result.append(d)
            
            return result
        finally:
            conn.close()
    
    def _get_preparation_tips(self, interview_type: str) -> List[str]:
        """获取面试准备建议"""
        tips_map = {
            'technical': [
                "复习核心技术的底层原理",
                "准备 2-3 个深度项目案例",
                "练习白板/在线编码",
                "了解公司技术栈和架构",
            ],
            'behavioral': [
                "准备 5-8 个 STAR+R 故事",
                "练习用 2 分钟讲清楚一个项目",
                "准备失败案例和反思",
                "展示成长思维和主动性",
            ],
            'hr_screening': [
                "控制自我介绍在 2-3 分钟",
                "准备动机阐述 (为什么选这家公司)",
                "了解基本薪资行情",
                "准备反问环节的问题",
            ],
            'system_design': [
                "掌握常见系统设计模式",
                "练习从需求分析到架构设计的全流程",
                "关注可扩展性、可用性、性能",
                "学会做技术权衡 (Trade-offs)",
            ],
        }
        return tips_map.get(interview_type, [])


# ─────────────────────────────────────────────
# CLI 测试
# ─────────────────────────────────────────────

if __name__ == "__main__":
    db_path = os.path.join(SKILL_DIR, "data", "career_engine.db")
    coach = InterviewCoach(db_path)
    
    if os.path.exists(db_path):
        test_jd = "高级后端工程师，负责 AI 平台后端开发，使用 Python/Go/K8s"
        
        print("🎯 面试话题预测:")
        prediction = coach.predict_interview_topics(1, test_jd, 'technical')
        print(f"匹配技能: {[s['name'] for s in prediction.get('matched_skills', [])]}")
        print(f"技能缺口: {prediction.get('gap_skills', [])}")
        print(f"预测话题: {prediction.get('predicted_topics', [])[:5]}")
        print(f"薄弱环节: {prediction.get('weak_areas', [])}")
        
        print("\n📝 模拟面试 (技术面):")
        mock = coach.generate_mock_interview(1, test_jd, 'technical')
        for i, q in enumerate(mock.get('questions', [])[:3], 1):
            print(f"  {i}. [{q['type']}] {q['question']}")
    else:
        print("⚠️ 数据库不存在")
