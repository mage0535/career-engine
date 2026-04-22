"""
Career Engine - 简历分析与优化模块

功能:
1. 简历 ATS 评分 (模拟 ATS 系统解析)
2. 关键词密度分析
3. 薄弱板块识别
4. 优化建议生成
5. 版本对比 (追踪简历迭代效果)
6. 数据写入 resume_analytics 表
"""

import json
import os
import re
import sys
from typing import Dict, List, Optional, Any
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_DIR)
from core.database.models import get_connection, get_profile, get_profile_skills, get_profile_experiences


# ─────────────────────────────────────────────
# ATS 评分规则
# ─────────────────────────────────────────────

# 影响力动词
IMPACT_VERBS = [
    '主导', '设计', '实现', '优化', '重构', '推动', '提升', '降低',
    '构建', '开发', '部署', '维护', '管理', '协调', '带领', '指导',
    'led', 'designed', 'implemented', 'optimized', 'architected',
    'developed', 'deployed', 'managed', 'improved', 'reduced', 'increased',
    'achieved', 'delivered', 'spearheaded', 'orchestrated', 'transformed',
]

# 量化指标模式
QUANTIFY_PATTERNS = [
    r'\d+%', r'\d+\s*万', r'\d+\s*千', r'\d+k', r'\d+M', r'\d+B',
    r'提升.*\d+', r'降低.*\d+', r'减少.*\d+', r'增加.*\d+',
    r'improved.*\d+', r'reduced.*\d+', r'increased.*\d+',
]

# ATS 友好格式检查
ATS_FORMAT_CHECKS = [
    ('has_contact_info', '包含联系方式', ['email', 'phone']),
    ('has_summary', '包含职业概要', ['summary', '概要', '简介']),
    ('has_skills_section', '包含技能板块', ['skill', '技能', '技术栈']),
    ('has_experience', '包含工作经历', ['experience', '经历', '工作']),
    ('reverse_chronological', '倒序排列', []),  # 需要额外检查
]


class ResumeAnalyzer:
    """简历分析器"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path
    
    def analyze_resume(self, profile_id: int, jd_text: str = '') -> Dict:
        """分析简历质量"""
        profile = get_profile(profile_id, self.db_path)
        skills = get_profile_skills(profile_id, self.db_path)
        experiences = get_profile_experiences(profile_id, self.db_path)
        
        if not profile:
            return {'error': 'Profile not found'}
        
        analysis = {}
        
        # 1. ATS 基础检查
        analysis['ats_checks'] = self._check_ats_format(profile, experiences)
        
        # 2. 关键词密度 (针对 JD)
        if jd_text:
            analysis['keyword_analysis'] = self._analyze_keywords(profile, skills, experiences, jd_text)
        else:
            analysis['keyword_analysis'] = {'status': 'no_jd_provided', 'missing_keywords': []}
        
        # 3. 影响力词汇
        analysis['impact_words'] = self._count_impact_words(experiences)
        
        # 4. 量化成就
        analysis['quantified_achievements'] = self._count_quantified(experiences)
        
        # 5. 综合评分
        analysis['overall_score'] = self._calculate_resume_score(analysis, len(experiences), len(skills))
        
        # 6. 优化建议
        analysis['suggestions'] = self._generate_suggestions(analysis, profile, skills, experiences)
        
        return analysis
    
    def _check_ats_format(self, profile: Dict, experiences: List[Dict]) -> Dict:
        """ATS 格式检查"""
        checks = {
            'has_name': bool(profile.get('name')),
            'has_email': bool(profile.get('email')),
            'has_phone': bool(profile.get('phone')),
            'has_links': bool(profile.get('github') or profile.get('linkedin') or profile.get('portfolio')),
            'has_summary': bool(profile.get('career_summary')),
            'has_skills': True,  # 数据库中有技能记录
            'has_experiences': len(experiences) > 0,
            'has_dates': all(exp.get('start_date') for exp in experiences) if experiences else False,
        }
        
        checks['passed'] = sum(1 for v in checks.values() if isinstance(v, bool) and v)
        checks['total'] = sum(1 for v in checks.values() if isinstance(v, bool))
        checks['score'] = checks['passed'] / max(checks['total'], 1) * 100
        
        return checks
    
    def _analyze_keywords(self, profile: Dict, skills: List[Dict], 
                          experiences: List[Dict], jd_text: str) -> Dict:
        """关键词分析"""
        from core.scoring.engine import extract_keywords
        
        jd_keywords = extract_keywords(jd_text)
        profile_keywords = set()
        
        # 从技能中提取
        for s in skills:
            profile_keywords.add(s['name'].lower())
            if s.get('aliases'):
                try:
                    profile_keywords.update(json.loads(s['aliases']))
                except:
                    pass
        
        # 从经历中提取
        for exp in experiences:
            if exp.get('tech_stack'):
                try:
                    profile_keywords.update(json.loads(exp['tech_stack']))
                except:
                    pass
        
        # 匹配分析
        jd_lower = set(k.lower() for k in jd_keywords)
        matched = jd_lower & profile_keywords
        missing = jd_lower - profile_keywords
        
        return {
            'jd_keywords': jd_keywords,
            'profile_keywords': list(profile_keywords),
            'matched_keywords': list(matched),
            'missing_keywords': list(missing),
            'match_rate': len(matched) / max(len(jd_lower), 1) * 100,
            'keyword_density': len(matched) / max(len(profile_keywords), 1) * 100,
        }
    
    def _count_impact_words(self, experiences: List[Dict]) -> Dict:
        """统计影响力词汇"""
        all_text = ' '.join(
            f"{exp.get('action', '')} {exp.get('result', '')} {exp.get('task', '')}"
            for exp in experiences
        )
        
        found_verbs = [v for v in IMPACT_VERBS if v in all_text.lower()]
        
        return {
            'count': len(found_verbs),
            'verbs': found_verbs[:10],
            'score': min(100, len(found_verbs) * 10),
        }
    
    def _count_quantified(self, experiences: List[Dict]) -> Dict:
        """统计量化成就"""
        count = 0
        examples = []
        
        for exp in experiences:
            for field in ['result', 'achievements', 'action']:
                text = exp.get(field, '')
                if not text:
                    continue
                
                matches = []
                for pattern in QUANTIFY_PATTERNS:
                    matches.extend(re.findall(pattern, text, re.IGNORECASE))
                
                if matches:
                    count += len(matches)
                    examples.extend(matches[:3])
        
        return {
            'count': count,
            'examples': examples[:5],
            'score': min(100, count * 15),
        }
    
    def _calculate_resume_score(self, analysis: Dict, exp_count: int, skill_count: int) -> float:
        """计算简历综合评分"""
        scores = []
        
        # ATS 格式分
        ats_score = analysis.get('ats_checks', {}).get('score', 0)
        scores.append(('ATS 格式', ats_score, 0.25))
        
        # 关键词匹配分
        kw_score = analysis.get('keyword_analysis', {}).get('match_rate', 50)
        scores.append(('关键词匹配', kw_score, 0.25))
        
        # 影响力词汇分
        impact_score = analysis.get('impact_words', {}).get('score', 0)
        scores.append(('影响力词汇', impact_score, 0.15))
        
        # 量化成就分
        quant_score = analysis.get('quantified_achievements', {}).get('score', 0)
        scores.append(('量化成就', quant_score, 0.15))
        
        # 经历丰富度分
        exp_score = min(100, exp_count * 25)
        scores.append(('经历丰富度', exp_score, 0.10))
        
        # 技能栈广度分
        skill_score = min(100, skill_count * 10)
        scores.append(('技能栈广度', skill_score, 0.10))
        
        total = sum(score * weight for _, score, weight in scores)
        
        return {
            'total': round(total, 1),
            'breakdown': {name: round(score, 1) for name, score, _ in scores},
            'weights': {name: weight for name, _, weight in scores},
        }
    
    def _generate_suggestions(self, analysis: Dict, profile: Dict,
                              skills: List[Dict], experiences: List[Dict]) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        # ATS 格式建议
        ats = analysis.get('ats_checks', {})
        if not ats.get('has_email'):
            suggestions.append('⚠️ 添加联系邮箱')
        if not ats.get('has_phone'):
            suggestions.append('⚠️ 添加联系电话')
        if not ats.get('has_summary'):
            suggestions.append('💡 添加职业概要 (Professional Summary)')
        if not ats.get('has_links'):
            suggestions.append('💡 添加 GitHub/LinkedIn/作品集链接')
        
        # 关键词建议
        kw = analysis.get('keyword_analysis', {})
        if kw.get('missing_keywords'):
            suggestions.append(f'🔑 建议补充 JD 关键词: {", ".join(kw["missing_keywords"][:5])}')
        
        # 影响力词汇建议
        impact = analysis.get('impact_words', {})
        if impact.get('count', 0) < 5:
            suggestions.append('📝 使用更多影响力动词 (主导/设计/实现/优化/提升等)')
        
        # 量化成就建议
        quant = analysis.get('quantified_achievements', {})
        if quant.get('count', 0) < 3:
            suggestions.append('📊 增加量化成果 (百分比、具体数字、金额等)')
        
        # 经历建议
        if len(experiences) < 2:
            suggestions.append('💼 建议补充更多工作或项目经历')
        
        # 技能建议
        if len(skills) < 5:
            suggestions.append('🛠️ 建议详细列出技能栈 (至少 5 项)')
        
        # 通用建议
        if not suggestions:
            suggestions.append('✅ 简历质量良好，保持更新即可')
        
        return suggestions
    
    def compare_versions(self, profile_id: int, current_analysis: Dict, 
                         target_job_id: int = None) -> Dict:
        """与上一版本对比"""
        conn = get_connection(self.db_path)
        try:
            prev = conn.execute("""
                SELECT * FROM resume_analytics 
                WHERE profile_id = ? 
                ORDER BY created_at DESC LIMIT 1
            """, (profile_id,)).fetchone()
            
            if not prev:
                return {'status': 'first_version', 'changes': {}}
            
            changes = {}
            curr_score = current_analysis.get('overall_score', {}).get('total', 0)
            prev_score = prev['ats_score'] or 0
            
            changes['score_change'] = round(curr_score - prev_score, 1)
            changes['improved'] = curr_score > prev_score
            
            return {
                'status': 'compared',
                'previous_score': prev_score,
                'current_score': curr_score,
                'changes': changes,
            }
        finally:
            conn.close()
    
    def save_analysis(self, profile_id: int, analysis: Dict,
                      target_job_id: int = None, version: str = 'auto') -> int:
        """保存分析结果到数据库"""
        conn = get_connection(self.db_path)
        try:
            if version == 'auto':
                # 自动版本号
                count = conn.execute(
                    "SELECT COUNT(*) FROM resume_analytics WHERE profile_id = ?",
                    (profile_id,)
                ).fetchone()[0]
                version = f"v{count + 1}.0"
            
            overall = analysis.get('overall_score', {})
            kw = analysis.get('keyword_analysis', {})
            impact = analysis.get('impact_words', {})
            quant = analysis.get('quantified_achievements', {})
            
            cursor = conn.execute("""
                INSERT INTO resume_analytics (
                    profile_id, version, target_job_id, generated_at,
                    ats_score, keyword_density, readability_score,
                    impact_words_count, quantified_achievements,
                    suggestions, missing_keywords, weak_sections
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile_id, version, target_job_id, datetime.now().isoformat(),
                overall.get('total', 0),
                kw.get('keyword_density', 0),
                kw.get('match_rate', 0),
                impact.get('count', 0),
                quant.get('count', 0),
                json.dumps(analysis.get('suggestions', []), ensure_ascii=False),
                json.dumps(kw.get('missing_keywords', []), ensure_ascii=False),
                json.dumps([], ensure_ascii=False),  # weak_sections
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
    analyzer = ResumeAnalyzer(db_path)
    
    if os.path.exists(db_path):
        test_jd = "高级后端工程师，Python/Go，K8s，微服务，AI 平台"
        
        print("📊 简历分析:")
        analysis = analyzer.analyze_resume(1, test_jd)
        
        print(f"\n总分: {analysis['overall_score']['total']}")
        print(f"\nATS 检查: {analysis['ats_checks']['passed']}/{analysis['ats_checks']['total']}")
        print(f"关键词匹配: {analysis['keyword_analysis'].get('match_rate', 0):.1f}%")
        print(f"缺失关键词: {analysis['keyword_analysis'].get('missing_keywords', [])}")
        print(f"影响力词汇: {analysis['impact_words']['count']} 个")
        print(f"量化成就: {analysis['quantified_achievements']['count']} 处")
        
        print(f"\n💡 优化建议:")
        for s in analysis['suggestions']:
            print(f"   {s}")
        
        # 保存
        record_id = analyzer.save_analysis(1, analysis, version='v1.0')
        print(f"\n✅ 分析已保存 (ID: {record_id})")
    else:
        print("⚠️ 数据库不存在")
