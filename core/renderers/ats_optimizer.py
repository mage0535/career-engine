"""
Career Engine - ATS 简历优化器

功能:
1. 基于 JD 关键词注入优化简历
2. 生成 ATS 友好的纯文本简历
3. 生成 HTML 美化简历 (可转 PDF)
4. STAR+R 故事推荐
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_DIR)
from core.database.models import get_connection, get_profile, get_profile_skills, get_profile_experiences


# ─────────────────────────────────────────────
# ATS 纯文本简历生成
# ─────────────────────────────────────────────

def generate_ats_resume(profile_id: int, jd_text: str = '',
                        jd_keywords: List[str] = None,
                        db_path: str = None) -> str:
    """
    生成 ATS 优化的纯文本简历
    
    ATS (Applicant Tracking System) 偏好:
    - 无表格/图片/特殊格式
    - 标准章节标题
    - 关键词密度适当
    - 倒序时间排列
    """
    profile = get_profile(profile_id, db_path)
    skills = get_profile_skills(profile_id, db_path)
    experiences = get_profile_experiences(profile_id, db_path)
    
    if not profile:
        return "Error: Profile not found"
    
    jd_keywords = jd_keywords or []
    
    # 重新排序技能 (JD 相关的优先)
    if jd_keywords:
        jd_lower = set(k.lower() for k in jd_keywords)
        def skill_sort_key(s):
            is_relevant = s['name'].lower() in jd_lower
            return (-int(is_relevant), -s['proficiency'])
        skills.sort(key=skill_sort_key)
    
    lines = []
    
    # 头部
    lines.append(profile['name'])
    if profile.get('email'):
        lines.append(profile['email'])
    if profile.get('phone'):
        lines.append(profile['phone'])
    links = []
    if profile.get('github'):
        links.append(profile['github'])
    if profile.get('linkedin'):
        links.append(profile['linkedin'])
    if profile.get('portfolio'):
        links.append(profile['portfolio'])
    if links:
        lines.append(' | '.join(links))
    lines.append('')
    
    # 职业概要
    if profile.get('career_summary'):
        lines.append('PROFESSIONAL SUMMARY')
        lines.append(profile['career_summary'])
        lines.append('')
    
    # 核心技能
    lines.append('CORE SKILLS')
    skill_lines = []
    for s in skills:
        prof_map = {5: 'Expert', 4: 'Advanced', 3: 'Proficient', 2: 'Intermediate', 1: 'Familiar'}
        skill_lines.append(f"{s['name']} ({prof_map.get(s['proficiency'], 'Unknown')})")
    lines.append(', '.join(skill_lines))
    lines.append('')
    
    # 工作经历
    lines.append('PROFESSIONAL EXPERIENCE')
    for exp in experiences:
        company = exp['company']
        role = exp['role']
        start = exp['start_date']
        end = exp['end_date'] or 'Present'
        
        lines.append(f'{role} | {company} | {start} - {end}')
        
        # 职责
        if exp.get('responsibilities'):
            try:
                resp = json.loads(exp['responsibilities'])
                for r in resp:
                    lines.append(f'  - {r}')
            except (json.JSONDecodeError, TypeError):
                pass
        
        # 成就
        if exp.get('achievements'):
            try:
                ach = json.loads(exp['achievements'])
                for a in ach:
                    lines.append(f'  * {a}')
            except (json.JSONDecodeError, TypeError):
                pass
        
        # STAR 摘要
        if exp.get('result'):
            lines.append(f'  Result: {exp["result"]}')
        
        lines.append('')
    
    # 项目经历 (可选)
    conn = get_connection(db_path)
    try:
        projects = [dict(r) for r in conn.execute(
            "SELECT * FROM projects WHERE profile_id = ? ORDER BY start_date DESC",
            (profile_id,)
        ).fetchall()]
    finally:
        conn.close()
    
    if projects:
        lines.append('KEY PROJECTS')
        for proj in projects:
            lines.append(f"{proj['name']} - {proj.get('role', '')}")
            if proj.get('description'):
                lines.append(f"  {proj['description']}")
            if proj.get('tech_stack'):
                try:
                    tech = json.loads(proj['tech_stack'])
                    lines.append(f"  Tech: {', '.join(tech)}")
                except:
                    pass
            lines.append('')
    
    # 教育背景 (如果有)
    lines.append('EDUCATION')
    lines.append('[添加你的教育背景]')
    
    return '\n'.join(lines)


# ─────────────────────────────────────────────
# HTML 简历生成
# ─────────────────────────────────────────────

def generate_html_resume(profile_id: int, jd_text: str = '',
                         template: str = 'modern',
                         db_path: str = None) -> str:
    """生成 HTML 格式简历"""
    profile = get_profile(profile_id, db_path)
    skills = get_profile_skills(profile_id, db_path)
    experiences = get_profile_experiences(profile_id, db_path)
    
    if not profile:
        return "<h1>Profile not found</h1>"
    
    # 技能熟练度标签颜色
    def prof_color(p):
        colors = {5: '#10b981', 4: '#3b82f6', 3: '#6366f1', 2: '#f59e0b', 1: '#94a3b8'}
        return colors.get(p, '#94a3b8')
    
    prof_labels = {5: '专家', 4: '精通', 3: '熟练', 2: '入门', 1: '了解'}
    
    # 生成技能条 HTML
    skills_html = ''
    for s in sorted(skills, key=lambda x: -x['proficiency'])[:15]:
        color = prof_color(s['proficiency'])
        label = prof_labels.get(s['proficiency'], '')
        width = s['proficiency'] * 20
        skills_html += f"""
        <div class="skill-item">
            <span class="skill-name">{s['name']}</span>
            <span class="skill-level" style="color: {color}">{label}</span>
            <div class="skill-bar"><div class="skill-fill" style="width: {width}%; background: {color}"></div></div>
        </div>"""
    
    # 生成经历 HTML
    exp_html = ''
    for exp in experiences:
        end = exp['end_date'] or '至今'
        exp_html += f"""
        <div class="experience-item">
            <div class="exp-header">
                <h3>{exp['role']}</h3>
                <span class="exp-company">{exp['company']}</span>
                <span class="exp-period">{exp['start_date']} — {end}</span>
            </div>"""
        
        if exp.get('result'):
            exp_html += f'<div class="exp-result">📊 成果: {exp["result"]}</div>'
        if exp.get('tech_stack'):
            try:
                tech = json.loads(exp['tech_stack'])
                exp_html += f'<div class="exp-tech">技术栈: {", ".join(tech[:6])}</div>'
            except:
                pass
        exp_html += '</div>'
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{profile['name']} - 简历</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'PingFang SC', 'Microsoft YaHei', -apple-system, sans-serif; 
               background: #f8fafc; color: #1e293b; line-height: 1.7; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 40px 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   color: white; padding: 40px; border-radius: 16px; margin-bottom: 30px; }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header .contact {{ opacity: 0.9; font-size: 0.95em; }}
        .section {{ background: white; padding: 30px; border-radius: 12px; 
                    margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .section h2 {{ color: #667eea; font-size: 1.4em; margin-bottom: 20px; 
                       padding-bottom: 10px; border-bottom: 2px solid #e2e8f0; }}
        .skill-item {{ display: flex; align-items: center; margin-bottom: 8px; }}
        .skill-name {{ width: 120px; font-weight: 500; }}
        .skill-level {{ width: 60px; font-size: 0.8em; }}
        .skill-bar {{ flex: 1; height: 6px; background: #e2e8f0; border-radius: 3px; margin-left: 10px; }}
        .skill-fill {{ height: 100%; border-radius: 3px; transition: width 0.3s; }}
        .experience-item {{ padding: 15px 0; border-bottom: 1px solid #f1f5f9; }}
        .experience-item:last-child {{ border-bottom: none; }}
        .exp-header h3 {{ color: #1e293b; margin-bottom: 5px; }}
        .exp-company {{ color: #667eea; font-weight: 500; }}
        .exp-period {{ color: #94a3b8; font-size: 0.9em; margin-left: 15px; }}
        .exp-result {{ background: #f0fdf4; color: #166534; padding: 8px 12px; 
                       border-radius: 6px; margin-top: 8px; font-size: 0.9em; }}
        .exp-tech {{ color: #64748b; font-size: 0.85em; margin-top: 5px; }}
        .summary {{ font-size: 1.1em; color: #475569; }}
        @media print {{
            body {{ background: white; }}
            .container {{ padding: 0; }}
            .section {{ box-shadow: none; border: 1px solid #e2e8f0; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{profile['name']}</h1>
            <div class="contact">
                {profile.get('email', '')}
                {' | ' + profile['phone'] if profile.get('phone') else ''}
                {' | ' + profile.get('github', '') if profile.get('github') else ''}
            </div>
        </div>
        
        <div class="section">
            <h2>📋 职业概要</h2>
            <p class="summary">{profile.get('career_summary', '')}</p>
        </div>
        
        <div class="section">
            <h2>🛠️ 核心技能</h2>
            {skills_html}
        </div>
        
        <div class="section">
            <h2>💼 工作经历</h2>
            {exp_html}
        </div>
    </div>
</body>
</html>"""
    
    return html


# ─────────────────────────────────────────────
# CLI 测试
# ─────────────────────────────────────────────

if __name__ == "__main__":
    db_path = os.path.join(SKILL_DIR, "data", "career_engine.db")
    
    # 测试生成 ATS 简历
    if os.path.exists(db_path):
        resume = generate_ats_resume(1, db_path=db_path)
        print(resume[:1000])
        print("\n...\n")
        
        # 生成 HTML
        html_path = os.path.join(SKILL_DIR, "data", "sample_resume.html")
        html = generate_html_resume(1, db_path=db_path)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ HTML 简历已生成: {html_path}")
    else:
        print("⚠️ 数据库不存在，请先运行 interactive_builder.py 构建简历")
