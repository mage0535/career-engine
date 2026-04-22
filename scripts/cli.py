"""
Career Engine - CLI 主入口 (完整版)

统一命令行接口，支持:
  - 初始化数据库
  - 交互式简历构建
  - JD 评估 (A-F 评分)
  - 简历分析 (ATS 评分 + 优化建议)
  - 面试辅导 (话术生成 + 模拟面试)
  - 投递追踪 (状态管理 + 转化分析)
  - 档案导出
  - 管道看板
"""

import sys
import os
import json
import argparse
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from core.database.models import (
    init_db, get_connection, get_profile, get_profile_skills,
    get_pipeline, get_job_stats, add_job, create_application
)
from core.scoring.engine import evaluate_job, save_report
from core.renderers.ats_optimizer import generate_ats_resume, generate_html_resume
from core.delivery.tracker import DeliveryTracker, STATUS_LABELS
from core.delivery.scripts_generator import ScriptGenerator, save_scripts_to_db
from core.optimizer.interview_coach import InterviewCoach
from core.optimizer.resume_analyzer import ResumeAnalyzer


DB_PATH = os.path.join(SKILL_DIR, "data", "career_engine.db")


def _pretty_print(data):
    """格式化输出 JSON"""
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def cmd_init():
    """初始化数据库"""
    init_db(DB_PATH)
    print(json.dumps({"status": "ok", "db_path": DB_PATH}, ensure_ascii=False))


def cmd_evaluate(jd_text, profile_id=1, save=True):
    """评估 JD 匹配度"""
    profile = get_profile(profile_id, DB_PATH)
    if not profile:
        print(json.dumps({"error": f"Profile {profile_id} not found. Run 'build' first."}, ensure_ascii=False))
        sys.exit(1)
    
    skills = get_profile_skills(profile_id, DB_PATH)
    skill_names = [s['name'] for s in skills]
    
    import re
    salary_match = re.search(r'(\d+)[\-\~](\d+)k', jd_text)
    salary_min = float(salary_match.group(1)) if salary_match else None
    salary_max = float(salary_match.group(2)) if salary_match else None
    
    report = evaluate_job(
        jd_text=jd_text,
        profile_skills=skill_names,
        profile_data=profile,
        salary_min=salary_min,
        salary_max=salary_max,
    )
    
    if save:
        job_id = add_job({
            'source': 'cli',
            'title': report.get('archetype', 'unknown'),
            'company': report.get('company', 'Unknown'),
            'jd_text': jd_text[:5000],
            'jd_keywords': json.dumps(report.get('keywords_found', []), ensure_ascii=False),
            'salary_min': salary_min,
            'salary_max': salary_max,
            'archetype': report.get('archetype', 'other'),
        }, DB_PATH)
        
        report_id = save_report(report, job_id, profile_id, db_path=DB_PATH)
        report['job_id'] = job_id
        report['report_id'] = report_id
    
    report['status'] = 'ok'
    _pretty_print(report)


def cmd_analyze(profile_id=1, jd_text=''):
    """简历分析"""
    analyzer = ResumeAnalyzer(DB_PATH)
    analysis = analyzer.analyze_resume(profile_id, jd_text)
    
    if 'error' in analysis:
        print(json.dumps(analysis, ensure_ascii=False))
        return
    
    # 保存分析
    record_id = analyzer.save_analysis(profile_id, analysis, version='auto')
    analysis['record_id'] = record_id
    analysis['status'] = 'ok'
    
    _pretty_print(analysis)


def cmd_interview_coach(profile_id=1, job_id=None, jd_text='', interview_type='technical'):
    """面试辅导"""
    coach = InterviewCoach(DB_PATH)
    generator = ScriptGenerator(DB_PATH)
    
    result = {}
    
    # 1. 面试话题预测
    if jd_text:
        result['topic_prediction'] = coach.predict_interview_topics(profile_id, jd_text, interview_type)
    
    # 2. 模拟面试
    if jd_text:
        result['mock_interview'] = coach.generate_mock_interview(profile_id, jd_text, interview_type)
    
    # 3. 话术生成
    if interview_type == 'hr_screening':
        result['scripts'] = generator.generate_hr_scripts(profile_id, job_id)
    elif interview_type == 'technical':
        result['scripts'] = generator.generate_technical_scripts(profile_id, jd_text)
    elif interview_type == 'manager':
        result['scripts'] = generator.generate_manager_scripts(profile_id, job_id)
    
    # 4. 反问问题
    result['questions_to_ask'] = generator.get_questions_to_ask(
        'tech_lead' if interview_type == 'technical' else 'manager' if interview_type == 'manager' else 'hr'
    )
    
    # 保存话术到数据库
    if result.get('scripts'):
        save_scripts_to_db(profile_id, job_id, interview_type=interview_type, 
                          scripts=result['scripts'], db_path=DB_PATH)
    
    result['status'] = 'ok'
    _pretty_print(result)


def cmd_resume(profile_id=1, jd_text='', output_format='text'):
    """生成简历"""
    if output_format == 'text':
        resume = generate_ats_resume(profile_id, jd_text, db_path=DB_PATH)
        print(resume)
    elif output_format == 'html':
        html = generate_html_resume(profile_id, jd_text, db_path=DB_PATH)
        output_path = os.path.join(SKILL_DIR, "data", f"resume_{profile_id}_{datetime.now().strftime('%Y%m%d')}.html")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(json.dumps({
            "status": "ok",
            "output_path": output_path,
        }, ensure_ascii=False))


def cmd_tracker(action='stats', profile_id=1, app_id=None, status=None):
    """投递追踪"""
    tracker = DeliveryTracker(DB_PATH)
    
    if action == 'stats':
        stats = tracker.get_conversion_stats(profile_id)
        _pretty_print(stats)
    elif action == 'followup':
        followups = tracker.get_follow_ups()
        _pretty_print(followups)
    elif action == 'update' and app_id and status:
        result = tracker.update_status(app_id, status)
        _pretty_print(result)
    else:
        print(json.dumps({"error": "Invalid action. Use: stats, followup, update"}, ensure_ascii=False))


def cmd_export(profile_id=1):
    """导出用户档案"""
    profile = get_profile(profile_id, DB_PATH)
    if not profile:
        print(json.dumps({"error": "Profile not found"}, ensure_ascii=False))
        return
    
    skills = get_profile_skills(profile_id, DB_PATH)
    
    conn = get_connection(DB_PATH)
    try:
        experiences = [dict(r) for r in conn.execute(
            "SELECT * FROM experiences WHERE profile_id = ?", (profile_id,)
        ).fetchall()]
    finally:
        conn.close()
    
    output = {
        "profile": profile,
        "skills": skills,
        "experiences": experiences,
        "exported_at": datetime.now().isoformat(),
    }
    _pretty_print(output)


def cmd_pipeline(profile_id=1):
    """查看求职看板"""
    pipeline = get_pipeline(profile_id, DB_PATH)
    stats = get_job_stats(profile_id, DB_PATH)
    
    print(f"\n{'='*60}")
    print(f"📊 求职管道看板")
    print(f"{'='*60}")
    print(f"   总投递: {stats['total_applications']}")
    print(f"   平均分: {stats['average_score']}")
    print(f"   状态分布: {json.dumps(stats['by_status'], ensure_ascii=False)}")
    
    if pipeline:
        print(f"\n{'─'*60}")
        print(f"{'#':<4} {'公司':<15} {'岗位':<20} {'评分':<8} {'评级':<6} {'状态'}")
        print(f"{'─'*60}")
        for i, item in enumerate(pipeline, 1):
            print(f"{i:<4} {item['company']:<15} {item['title']:<20} "
                  f"{item.get('overall_score', 'N/A'):<8} {item.get('grade', 'N/A'):<6} {item['status']}")
    else:
        print(f"\n   (暂无投递记录)")
    
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description='🎯 Career Engine CLI - 求职作战系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python cli.py init                                    # 初始化
  python cli.py evaluate "JD文本..."                    # 评估岗位
  python cli.py analyze --jd "JD文本..."                # 简历分析
  python cli.py interview --jd "JD文本..." --type hr    # 面试辅导
  python cli.py resume --format html                    # 生成简历
  python cli.py tracker stats                           # 投递统计
  python cli.py pipeline                                # 求职看板
  python cli.py export                                  # 导出档案
        """
    )
    subparsers = parser.add_subparsers(dest='command', help='子命令')
    
    # init
    subparsers.add_parser('init', help='初始化数据库')
    
    # evaluate
    eval_p = subparsers.add_parser('evaluate', help='评估 JD 匹配度')
    eval_p.add_argument('jd_text', help='JD 文本内容')
    eval_p.add_argument('--profile-id', type=int, default=1)
    eval_p.add_argument('--no-save', action='store_true')
    
    # analyze
    ana_p = subparsers.add_parser('analyze', help='简历分析 (ATS 评分 + 优化建议)')
    ana_p.add_argument('--profile-id', type=int, default=1)
    ana_p.add_argument('--jd', default='', help='JD 文本 (用于关键词分析)')
    
    # interview
    int_p = subparsers.add_parser('interview', help='面试辅导')
    int_p.add_argument('--profile-id', type=int, default=1)
    int_p.add_argument('--job-id', type=int, default=None)
    int_p.add_argument('--jd', default='', help='JD 文本')
    int_p.add_argument('--type', default='technical', 
                       choices=['hr_screening', 'technical', 'manager', 'behavioral'])
    
    # resume
    res_p = subparsers.add_parser('resume', help='生成简历')
    res_p.add_argument('--profile-id', type=int, default=1)
    res_p.add_argument('--jd', default='', help='JD 文本 (用于关键词优化)')
    res_p.add_argument('--format', choices=['text', 'html'], default='text')
    
    # tracker
    track_p = subparsers.add_parser('tracker', help='投递追踪')
    track_p.add_argument('action', choices=['stats', 'followup', 'update'])
    track_p.add_argument('--profile-id', type=int, default=1)
    track_p.add_argument('--app-id', type=int, default=None)
    track_p.add_argument('--status', default=None)
    
    # export
    subparsers.add_parser('export', help='导出用户档案').add_argument('--profile-id', type=int, default=1)
    
    # pipeline
    subparsers.add_parser('pipeline', help='查看求职管道看板').add_argument('--profile-id', type=int, default=1)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    if args.command == 'init':
        cmd_init()
    elif args.command == 'evaluate':
        cmd_evaluate(args.jd_text, args.profile_id, save=not args.no_save)
    elif args.command == 'analyze':
        cmd_analyze(args.profile_id, args.jd)
    elif args.command == 'interview':
        cmd_interview_coach(args.profile_id, args.job_id, args.jd, args.type)
    elif args.command == 'resume':
        cmd_resume(args.profile_id, args.jd, args.format)
    elif args.command == 'tracker':
        cmd_tracker(args.action, args.profile_id, args.app_id, args.status)
    elif args.command == 'export':
        cmd_export(args.profile_id)
    elif args.command == 'pipeline':
        cmd_pipeline(args.profile_id)


if __name__ == "__main__":
    main()
