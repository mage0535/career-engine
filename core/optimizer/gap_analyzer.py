"""
Career Engine - 岗位调研优化器

功能:
1. JD 缺口分析 (对比用户简历与 JD 要求)
2. 针对性问答 (引导用户补充缺失经历/技能)
3. 简历自动优化 (基于用户回答更新简历)
4. 优化效果评估
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
# 缺口分析引擎
# ─────────────────────────────────────────────

class GapAnalyzer:
    """JD 缺口分析器"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path
    
    def analyze_gap(self, profile_id: int, jd_text: str) -> Dict:
        """
        分析用户简历与 JD 的差距
        
        返回:
        {
            'skill_gaps': [...],      # 技能缺口
            'experience_gaps': [...],  # 经验缺口
            'keyword_gaps': [...],    # 关键词缺口
            'questions': [...],       # 针对性问题
            'optimization_suggestions': [...],  # 优化建议
        }
        """
        profile = get_profile(profile_id, self.db_path)
        skills = get_profile_skills(profile_id, self.db_path)
        experiences = get_profile_experiences(profile_id, self.db_path)
        
        if not profile:
            return {'error': 'Profile not found'}
        
        # 1. 提取 JD 关键词
        jd_keywords = extract_keywords(jd_text)
        jd_lower = set(k.lower() for k in jd_keywords)
        
        # 2. 提取用户技能
        user_skills = set()
        skill_map = {}
        for s in skills:
            user_skills.add(s['name'].lower())
            skill_map[s['name'].lower()] = s
        
        # 3. 分析缺口
        skill_gaps = []
        for kw in jd_keywords:
            kw_lower = kw.lower()
            if kw_lower not in user_skills:
                # 检查模糊匹配
                matched = False
                for us in user_skills:
                    if kw_lower in us or us in kw_lower:
                        matched = True
                        break
                if not matched:
                    skill_gaps.append({
                        'keyword': kw,
                        'severity': 'high' if self._is_core_skill(kw, jd_text) else 'medium',
                        'suggestion': self._get_learning_suggestion(kw),
                    })
        
        # 4. 经验缺口分析
        experience_gaps = self._analyze_experience_gap(jd_text, experiences)
        
        # 5. 关键词缺口
        keyword_gaps = [g['keyword'] for g in skill_gaps if g['severity'] == 'high']
        
        # 6. 生成针对性问题
        questions = self._generate_questions(skill_gaps, experience_gaps, jd_text)
        
        # 7. 优化建议
        optimization_suggestions = self._generate_optimization_suggestions(
            skill_gaps, experience_gaps, keyword_gaps, jd_text
        )
        
        return {
            'skill_gaps': skill_gaps,
            'experience_gaps': experience_gaps,
            'keyword_gaps': keyword_gaps,
            'questions': questions,
            'optimization_suggestions': optimization_suggestions,
            'gap_score': self._calculate_gap_score(skill_gaps, experience_gaps),
        }
    
    def _is_core_skill(self, skill: str, jd_text: str) -> bool:
        """判断是否为核心技能"""
        core_indicators = ['精通', '熟练', '必须', 'required', 'must have', '核心']
        skill_context = jd_text[max(0, jd_text.lower().find(skill.lower()) - 50):
                                jd_text.lower().find(skill.lower()) + len(skill) + 50]
        return any(ind in skill_context for ind in core_indicators)
    
    def _get_learning_suggestion(self, skill: str) -> str:
        """获取学习建议"""
        suggestions = {
            'python': '熟悉 Python 核心语法和常用库',
            'go': '了解 Go 的并发模型和标准库',
            'kubernetes': '学习 K8s 核心概念 (Pod/Service/Deployment)',
            'docker': '掌握 Docker 容器化基础',
            'mysql': '理解 MySQL 索引和事务原理',
            'redis': '了解 Redis 数据结构和缓存策略',
            'ai': '了解 AI/ML 基础概念和应用场景',
            'llm': '学习大模型应用开发 (Prompt/RAG/Fine-tuning)',
        }
        return suggestions.get(skill.lower(), f'了解 {skill} 的基本概念和应用场景')
    
    def _analyze_experience_gap(self, jd_text: str, experiences: List[Dict]) -> List[Dict]:
        """分析经验缺口"""
        gaps = []
        
        # 检查年限要求
        import re
        year_match = re.search(r'(\d+)[\-\~]?(\d+)?年', jd_text)
        if year_match:
            required_years = int(year_match.group(1))
            total_years = 0
            for exp in experiences:
                if exp.get('start_date'):
                    start_year = int(exp['start_date'].split('-')[0])
                    total_years += 2026 - start_year
            
            if total_years < required_years:
                gaps.append({
                    'type': 'years',
                    'required': f'{required_years}年',
                    'actual': f'{total_years}年',
                    'severity': 'high' if required_years - total_years > 2 else 'medium',
                    'suggestion': f'强调项目经验和深度，弥补年限不足',
                })
        
        # 检查经验类型
        experience_types = [
            ('微服务', 'microservices'),
            ('高并发', 'high concurrency'),
            ('分布式', 'distributed'),
            ('大型项目', 'large-scale'),
            ('团队管理', 'team management'),
        ]
        
        for cn, en in experience_types:
            if cn in jd_text or en in jd_text.lower():
                has_exp = any(
                    cn in str(exp.get('tech_stack', '')) or 
                    cn in str(exp.get('action', ''))
                    for exp in experiences
                )
                if not has_exp:
                    gaps.append({
                        'type': 'experience_type',
                        'required': cn,
                        'severity': 'medium',
                        'suggestion': f'准备相关案例或说明可迁移能力',
                    })
        
        return gaps
    
    def _generate_questions(self, skill_gaps: List[Dict], experience_gaps: List[Dict],
                           jd_text: str) -> List[Dict]:
        """生成针对性问答"""
        questions = []
        
        # 针对技能缺口
        for gap in skill_gaps[:5]:
            questions.append({
                'type': 'skill_gap',
                'question': f"JD 要求 {gap['keyword']}，你有相关经验吗？",
                'context': f"如果没有，可以说明: 1) 学习意愿 2) 可迁移技能 3) 快速学习计划",
                'gap': gap,
            })
        
        # 针对经验缺口
        for gap in experience_gaps:
            questions.append({
                'type': 'experience_gap',
                'question': f"JD 要求 {gap.get('required', '')} 经验，你有相关经历吗？",
                'context': gap.get('suggestion', ''),
                'gap': gap,
            })
        
        # 通用问题
        questions.append({
            'type': 'general',
            'question': "这个岗位最吸引你的点是什么？",
            'context': '用于动机阐述，建议结合公司业务方向',
        })
        
        return questions
    
    def _generate_optimization_suggestions(self, skill_gaps: List[Dict],
                                           experience_gaps: List[Dict],
                                           keyword_gaps: List[str],
                                           jd_text: str) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        # 关键词注入
        if keyword_gaps:
            suggestions.append(f"🔑 在简历中补充关键词: {', '.join(keyword_gaps[:5])}")
        
        # 经历重构
        suggestions.append("📝 将最相关的经历放在前面")
        suggestions.append("📊 使用量化数据描述成果 (百分比/金额/用户数)")
        
        # 技能补充
        high_severity = [g for g in skill_gaps if g['severity'] == 'high']
        if high_severity:
            suggestions.append(f"⚠️ 重点准备: {', '.join(g['keyword'] for g in high_severity[:3])}")
        
        return suggestions
    
    def _calculate_gap_score(self, skill_gaps: List[Dict], experience_gaps: List[Dict]) -> float:
        """计算缺口评分 (0-100, 越高越好)"""
        penalty = 0
        
        for gap in skill_gaps:
            if gap['severity'] == 'high':
                penalty += 15
            else:
                penalty += 5
        
        for gap in experience_gaps:
            if gap.get('severity') == 'high':
                penalty += 20
            else:
                penalty += 10
        
        return max(0, 100 - penalty)
    
    def save_gap_analysis(self, profile_id: int, job_id: int, 
                          analysis: Dict) -> int:
        """保存缺口分析到数据库"""
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute("""
                INSERT INTO resume_analytics (
                    profile_id, version, target_job_id, generated_at,
                    ats_score, keyword_density, suggestions, missing_keywords
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile_id, f'gap-v1', job_id, datetime.now().isoformat(),
                analysis.get('gap_score', 0),
                0,
                json.dumps(analysis.get('optimization_suggestions', []), ensure_ascii=False),
                json.dumps(analysis.get('keyword_gaps', []), ensure_ascii=False),
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


# ─────────────────────────────────────────────
# CLI 测试
# ─────────────────────────────────────────────

if __name__ == "__main__":
    db_path = os.path.join(SKILL_DIR, "data", "career_engine.db")
    analyzer = GapAnalyzer(db_path)
    
    test_jd = """
    高级后端工程师 - AI 平台
    要求:
    - 5 年以上 Python/Go 开发经验
    - 精通微服务架构，有 K8s 部署经验
    - 熟悉高并发场景，有性能优化经验
    - 有大模型/AI 项目经验者优先
    - 熟悉 MySQL, Redis, Kafka
    """
    
    if os.path.exists(db_path):
        print("🔍 缺口分析:")
        result = analyzer.analyze_gap(1, test_jd)
        
        print(f"缺口评分: {result['gap_score']}")
        print(f"\n技能缺口: {len(result['skill_gaps'])} 个")
        for g in result['skill_gaps'][:3]:
            print(f"   - {g['keyword']} ({g['severity']})")
        
        print(f"\n经验缺口: {len(result['experience_gaps'])} 个")
        for g in result['experience_gaps']:
            print(f"   - {g.get('required', '')}: {g.get('suggestion', '')}")
        
        print(f"\n💡 针对性问题:")
        for q in result['questions'][:3]:
            print(f"   Q: {q['question']}")
        
        print(f"\n📝 优化建议:")
        for s in result['optimization_suggestions']:
            print(f"   {s}")
    else:
        print("⚠️ 数据库不存在")
