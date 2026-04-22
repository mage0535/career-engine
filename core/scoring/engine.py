"""
Career Engine - A-F 多维评分引擎

基于 career-ops 方法论的 8 维度加权评分系统
适配中国招聘市场 (BOSS 直聘/智联/前程无忧)

评分维度:
  Match (25%)       - 技能与经验匹配度
  Impact (20%)      - 业务影响力与核心程度
  Growth (15%)      - 技术成长与职业前景
  Comp (15%)        - 薪资与市场水平对比
  Culture (10%)     - 团队氛围与远程政策
  Tech Stack (5%)   - 技术栈先进性与通用性
  Stability (5%)    - 公司融资状况与裁员风险
  WLB (5%)          - 加班强度与工作生活平衡
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.database.models import get_connection

# ─────────────────────────────────────────────
# 权重配置
# ─────────────────────────────────────────────

SCORING_WEIGHTS = {
    'match': 0.25,
    'impact': 0.20,
    'growth': 0.15,
    'comp': 0.15,
    'culture': 0.10,
    'tech_stack': 0.05,
    'stability': 0.05,
    'wlb': 0.05,
}

# 评级体系 (扩展为 + / -)
GRADE_THRESHOLDS = [
    (95, 'A+', 'Dream Job - 完美匹配，全力争取'),
    (90, 'A',  'Excellent - 极佳匹配，优先投递'),
    (85, 'A-', 'Great - 高度匹配，值得投入'),
    (80, 'B+', 'Strong - 较好匹配，推荐投递'),
    (75, 'B',  'Good - 基本匹配，可以投递'),
    (70, 'B-', 'Fair - 勉强匹配，作为备选'),
    (60, 'C',  'Pass - 匹配度一般，谨慎考虑'),
    (50, 'D',  'Weak - 匹配度低，建议跳过'),
    (0,  'F',  'Avoid - 明显不匹配或存在红旗'),
]


# ─────────────────────────────────────────────
# 岗位类型分类 (Archetype Detection)
# ─────────────────────────────────────────────

ARCHETYPE_PATTERNS = {
    'backend': ['后端', '服务端', 'java', 'python', 'go', 'golang', 'c\+\+', '微服务', 'api开发', '业务开发'],
    'frontend': ['前端', 'web前端', 'html', 'css', 'vue', 'react', 'angular', '小程序'],
    'fullstack': ['全栈', 'fullstack', 'full-stack', '前后端'],
    'ai_ml': ['ai', 'ml', '机器学习', '深度学习', '大模型', 'llm', 'nlp', 'cv', '计算机视觉', '算法工程师', '推荐算法', '搜索算法'],
    'devops': ['devops', '运维', 'sre', '基础设施', 'k8s', 'kubernetes', 'docker', 'ci/cd', '部署'],
    'data': ['数据', 'data', '数据仓库', 'etl', '数据分析', '数据工程', 'bi'],
    'mobile': ['移动', 'ios', 'android', 'flutter', 'react native', '移动端'],
    'pm': ['产品', 'pm', 'product', '产品经理'],
    'security': ['安全', 'security', '网络安全', '渗透测试', '安全工程师'],
    'qa': ['测试', 'qa', 'quality', '自动化测试', '测试开发'],
}


def detect_archetype(jd_text: str) -> str:
    """检测岗位类型"""
    jd_lower = jd_text.lower()
    scores = {}
    for archetype, patterns in ARCHETYPE_PATTERNS.items():
        score = sum(1 for p in patterns if p in jd_lower)
        if score > 0:
            scores[archetype] = score
    
    if not scores:
        return 'other'
    return max(scores, key=scores.get)


def detect_seniority(jd_text: str, title: str = '') -> str:
    """检测岗位级别"""
    combined = (jd_text + ' ' + title).lower()
    
    seniority_indicators = {
        'principal': ['首席', 'principal', '架构师'],
        'staff': ['staff', '技术专家', '资深专家'],
        'director': ['总监', 'director', '负责人', 'leader'],
        'senior': ['高级', 'senior', '5-10年', '5年以上', '8年以上'],
        'mid': ['中级', '3-5年', '2-5年'],
        'junior': ['初级', 'junior', '应届', '1-3年', '实习生'],
    }
    
    for level, indicators in sorted(seniority_indicators.items(), key=lambda x: -len(x[0])):
        if any(i in combined for i in indicators):
            return level
    return 'mid'


# ─────────────────────────────────────────────
# 关键词提取
# ─────────────────────────────────────────────

TECH_KEYWORDS = [
    'python', 'java', 'go', 'golang', 'rust', 'c\+\+', 'c#', 'javascript', 'typescript',
    'react', 'vue', 'angular', 'svelte', 'node.js', 'next.js', 'django', 'flask', 'fastapi', 'spring', 'gin', 'echo',
    'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'sqlite', 'oracle',
    'docker', 'kubernetes', 'k8s', 'helm', 'terraform', 'ansible', 'jenkins', 'gitlab ci',
    'aws', '阿里云', '腾讯云', 'gcp', 'azure', '华为云',
    'kafka', 'rabbitmq', 'redis', 'zeromq', 'grpc', 'thrift', 'rest api', 'graphql',
    'nginx', 'haproxy', 'traefik', 'istio', 'consul',
    'linux', 'macos', 'windows server',
    'git', 'svn',
    'machine learning', 'deep learning', 'llm', 'transformer', 'pytorch', 'tensorflow', 'paddlepaddle',
    'spark', 'hadoop', 'flink', 'hive', 'airflow',
    '微服务', '分布式', '高并发', '高可用', '性能优化',
    'ci/cd', 'devops', 'sre', 'agile', 'scrum',
]


def extract_keywords(jd_text: str) -> List[str]:
    """从 JD 中提取技术关键词"""
    jd_lower = jd_text.lower()
    found = []
    for kw in TECH_KEYWORDS:
        if kw.lower() in jd_lower:
            found.append(kw)
    return found


# ─────────────────────────────────────────────
# 评分计算
# ─────────────────────────────────────────────

def calculate_match_score(profile_skills: List[str], jd_keywords: List[str], 
                          required_skills: Optional[List[str]] = None) -> float:
    """
    计算技能匹配度 (0-100)
    
    策略:
    - 核心技能匹配权重更高
    - 完全匹配 > 部分匹配 (模糊匹配)
    """
    if not jd_keywords and not required_skills:
        return 50
    
    profile_lower = set(s.lower().strip() for s in profile_skills)
    required = set()
    
    if required_skills:
        required = set(s.lower().strip() for s in required_skills)
    if jd_keywords:
        required.update(s.lower().strip() for s in jd_keywords)
    
    if not required:
        return 50
    
    # 精确匹配
    exact_match = profile_lower & required
    # 模糊匹配 (包含关系)
    fuzzy_match = set()
    for p in profile_lower:
        for r in required:
            if p in r or r in p:
                fuzzy_match.add(r)
    
    all_matched = exact_match | fuzzy_match
    score = (len(all_matched) / len(required)) * 100
    
    # 精确匹配额外加分
    exact_ratio = len(exact_match) / max(len(required), 1)
    score = score * 0.7 + exact_ratio * 100 * 0.3
    
    return min(100, max(0, score))


def calculate_comp_score(salary_min: Optional[float], salary_max: Optional[float],
                         expected_salary: Optional[float], archetype: str = '',
                         city: str = '') -> float:
    """
    计算薪酬竞争力评分
    
    基准参考 (2024年中国一二线城市，月薪 k):
    - junior: 8-15
    - mid: 15-25
    - senior: 25-45
    - staff: 45-70
    - principal: 70-100+
    """
    if not salary_min or not expected_salary:
        return 60  # 无数据时中性
    
    # 简化的市场基准
    benchmarks = {
        'junior': {'low': 8, 'mid': 12, 'high': 18},
        'mid': {'low': 15, 'mid': 20, 'high': 30},
        'senior': {'low': 25, 'mid': 35, 'high': 50},
        'staff': {'low': 45, 'mid': 55, 'high': 75},
        'principal': {'low': 70, 'mid': 85, 'high': 120},
    }
    
    mid_salary = (salary_min + salary_max) / 2 if salary_max else salary_min
    
    # 相对于用户期望的匹配度
    if mid_salary >= expected_salary:
        score = min(100, 70 + (mid_salary - expected_salary) / expected_salary * 30)
    else:
        score = max(20, (mid_salary / expected_salary) * 70)
    
    return min(100, max(0, score))


def calculate_grade(score: float) -> tuple:
    """根据总分计算评级"""
    for threshold, grade, desc in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade, desc
    return 'F', 'Avoid'


# ─────────────────────────────────────────────
# 主评估函数
# ─────────────────────────────────────────────

def evaluate_job(
    jd_text: str,
    profile_skills: List[str],
    profile_data: Optional[Dict] = None,
    job_title: str = '',
    job_company: str = '',
    salary_min: Optional[float] = None,
    salary_max: Optional[float] = None,
    location: str = '',
    source: str = 'manual',
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    评估一个岗位，返回完整评分报告
    
    Args:
        jd_text: 完整 JD 文本
        profile_skills: 用户技能列表
        profile_data: 用户档案数据
        job_title: 岗位名称
        job_company: 公司名称
        salary_min/max: 薪资范围
        location: 工作地点
        source: 来源平台
        db_path: 数据库路径
    
    Returns:
        评估报告字典
    """
    profile_data = profile_data or {}
    
    # 1. 提取关键词
    keywords = extract_keywords(jd_text)
    archetype = detect_archetype(jd_text)
    seniority = detect_seniority(jd_text, job_title)
    
    # 2. 解析 JD 中的技能要求
    required_skills = keywords  # 从关键词中提取
    
    # 3. 计算各维度分数
    scores = {}
    
    # Match (25%)
    scores['match'] = calculate_match_score(profile_skills, keywords, required_skills)
    
    # Impact (20%) - 基于岗位级别和业务描述
    impact_score = 50
    if seniority in ('staff', 'principal', 'director'):
        impact_score = 85
    elif seniority == 'senior':
        impact_score = 75
    elif seniority == 'mid':
        impact_score = 60
    elif seniority == 'junior':
        impact_score = 40
    
    # 检查是否有"核心"、"关键"等词
    if any(k in jd_text for k in ['核心', '关键', '主负责', 'owner', 'lead']):
        impact_score = min(100, impact_score + 10)
    scores['impact'] = impact_score
    
    # Growth (15%)
    growth_score = 60
    growth_keywords = ['成长', '培训', '晋升', 'mentorship', 'learning', '发展']
    if any(k in jd_text for k in growth_keywords):
        growth_score = 75
    if any(k in jd_text for k in ['ai', '大模型', 'llm', '前沿', '新技术']):
        growth_score = min(100, growth_score + 10)
    scores['growth'] = growth_score
    
    # Comp (15%)
    expected = profile_data.get('expected_salary')
    scores['comp'] = calculate_comp_score(salary_min, salary_max, expected, archetype, location)
    
    # Culture (10%) - 默认中性，根据 JD 描述调整
    culture_score = 60
    if any(k in jd_text for k in ['弹性', '灵活', '远程', '不打卡', '扁平']):
        culture_score = 80
    if any(k in jd_text for k in ['狼性', '奋斗', '拼搏', '抗压']):
        culture_score = max(20, culture_score - 20)
    scores['culture'] = culture_score
    
    # Tech Stack (5%)
    tech_score = 50
    modern_tech = ['k8s', 'kubernetes', 'go', 'golang', 'rust', 'react', 'vue', 'python', 'fastapi', '微服务', 'llm', 'ai']
    if any(k in jd_text.lower() for k in modern_tech):
        tech_score = 75
    if any(k in jd_text.lower() for k in ['ie6', 'jsp', 'struts', 'jquery 1.x', 'flash']):
        tech_score = max(20, tech_score - 20)
    scores['tech_stack'] = tech_score
    
    # Stability (5%)
    stability_score = 65
    if any(k in jd_text for k in ['上市', 'd轮+', 'c轮', '国企', '央企', '事业单位']):
        stability_score = 85
    elif any(k in jd_text for k in ['创业', '天使', 'a轮', '初创']):
        stability_score = 45
    scores['stability'] = stability_score
    
    # WLB (5%)
    wlb_score = 50
    if any(k in jd_text for k in ['双休', '弹性', '不加班', '965', '远程']):
        wlb_score = 85
    if any(k in jd_text for k in ['大小周', '996', '加班', '单休', '奋斗']):
        wlb_score = max(15, wlb_score - 30)
    scores['wlb'] = wlb_score
    
    # 4. 加权总分
    total = sum(scores[k] * w for k, w in SCORING_WEIGHTS.items())
    grade, grade_desc = calculate_grade(total)
    
    # 5. 红旗检测
    red_flags = []
    if any(k in jd_text for k in ['996', '大小周', '单休']):
        red_flags.append('加班强度大')
    if any(k in jd_text for k in ['外包', '派遣', '驻场']):
        red_flags.append('外包/派遣性质')
    if salary_min and salary_max and (salary_max - salary_min) / salary_min > 1.0:
        red_flags.append('薪资范围跨度大 (可能存在薪资压榨)')
    if any(k in jd_text for k in ['接受应届', '不限经验']) and seniority in ('senior', 'staff'):
        red_flags.append('岗位级别与要求不匹配')
    
    # 6. 技能缺口分析
    profile_lower = set(s.lower().strip() for s in profile_skills)
    jd_required = set(k.lower() for k in keywords)
    skills_gap = list(jd_required - profile_lower)
    
    # 7. 生成报告
    report = {
        'grade': grade,
        'grade_desc': grade_desc,
        'overall_score': round(total, 1),
        'scores': {k: round(v, 1) for k, v in scores.items()},
        'archetype': archetype,
        'seniority': seniority,
        'keywords_found': keywords,
        'red_flags': red_flags,
        'skills_gap': skills_gap,
        'pros': [],
        'cons': [],
        'recommendations': {
            'resume_changes': [],
            'interview_prep': [],
            'negotiation_tips': [],
        },
        'timestamp': datetime.now().isoformat(),
    }
    
    # 补充 pros/cons
    if scores['match'] >= 70:
        report['pros'].append('技能匹配度高')
    if scores['comp'] >= 70:
        report['pros'].append('薪资竞争力强')
    if scores['growth'] >= 70:
        report['pros'].append('成长空间大')
    if scores['wlb'] < 40:
        report['cons'].append('工作生活平衡差')
    if scores['stability'] < 50:
        report['cons'].append('公司稳定性存疑')
    
    return report


def save_report(report: Dict, job_id: int, profile_id: int, 
                application_id: Optional[int] = None, 
                db_path: Optional[str] = None) -> int:
    """保存评估报告到数据库"""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("""
            INSERT INTO match_reports (
                job_id, profile_id, application_id,
                overall_score, grade, grade_label,
                match_score, impact_score, growth_score, comp_score,
                culture_score, tech_stack_score, stability_score, wlb_score,
                pros, cons, risks, red_flags,
                recommendations, keywords_to_add, skills_gap, job_archetype
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id, profile_id, application_id,
            report['overall_score'], report['grade'], report['grade_desc'],
            report['scores']['match'], report['scores']['impact'],
            report['scores']['growth'], report['scores']['comp'],
            report['scores']['culture'], report['scores']['tech_stack'],
            report['scores']['stability'], report['scores']['wlb'],
            json.dumps(report.get('pros', []), ensure_ascii=False),
            json.dumps(report.get('cons', []), ensure_ascii=False),
            json.dumps(report.get('red_flags', []), ensure_ascii=False),
            json.dumps(report.get('red_flags', []), ensure_ascii=False),
            json.dumps(report.get('recommendations', {}), ensure_ascii=False),
            json.dumps(report.get('keywords_found', []), ensure_ascii=False),
            json.dumps(report.get('skills_gap', []), ensure_ascii=False),
            report.get('archetype', 'other'),
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


# ─────────────────────────────────────────────
# CLI 测试
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # 测试用例
    test_jd = """
    高级后端工程师 - AI 平台
    薪资: 30-50k·16薪
    地点: 北京·海淀区
    
    职位描述:
    - 负责 AI 大模型平台的后端服务开发
    - 使用 Python/Go 构建高并发微服务架构
    - 负责模型服务的部署与性能优化
    - 与算法团队协作，推动 AI 能力落地
    
    任职要求:
    - 5 年以上后端开发经验
    - 精通 Python 或 Go，熟悉微服务架构
    - 熟悉 Docker, Kubernetes, Redis, MySQL
    - 有大模型/AI 项目经验者优先
    - 弹性工作，双休，扁平化管理
    """
    
    test_skills = [
        'Python', 'Go', 'Docker', 'Kubernetes', 'MySQL', 'Redis',
        '微服务', 'gRPC', 'FastAPI', 'Linux', 'CI/CD',
    ]
    
    test_profile = {
        'expected_salary': 35,
        'target_roles': ['后端工程师', 'AI 工程师'],
    }
    
    result = evaluate_job(
        jd_text=test_jd,
        profile_skills=test_skills,
        profile_data=test_profile,
        job_title='高级后端工程师',
        job_company='某 AI 公司',
        salary_min=30,
        salary_max=50,
        location='北京',
    )
    
    print(f"\n{'='*60}")
    print(f"🎯 评级: {result['grade']} - {result['grade_desc']}")
    print(f"📊 总分: {result['overall_score']}")
    print(f"🏷️ 岗位类型: {result['archetype']} | 级别: {result['seniority']}")
    print(f"\n📈 维度评分:")
    weights_display = {'match': '25%', 'impact': '20%', 'growth': '15%', 'comp': '15%',
                       'culture': '10%', 'tech_stack': '5%', 'stability': '5%', 'wlb': '5%'}
    for k, v in result['scores'].items():
        bar = '█' * int(v / 5) + '░' * (20 - int(v / 5))
        print(f"   {k:<12} ({weights_display[k]:>3}): [{bar}] {v}")
    
    if result['red_flags']:
        print(f"\n🚩 红旗警告: {', '.join(result['red_flags'])}")
    if result['skills_gap']:
        print(f"\n📚 技能缺口: {', '.join(result['skills_gap'][:5])}")
    if result['pros']:
        print(f"\n✅ 优势: {', '.join(result['pros'])}")
    if result['cons']:
        print(f"\n⚠️ 劣势: {', '.join(result['cons'])}")
    print(f"{'='*60}")
