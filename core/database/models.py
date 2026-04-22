"""
Career Engine - 核心数据模型
分级分层 SQLite 数据库，支持多用户、多档案版本、完整求职生命周期

数据层级:
  L1 - profiles (用户基础档案)
  L2 - experiences / projects / skills (能力层)
  L3 - jobs / companies (机会层)
  L4 - applications / match_reports (交互层)
  L5 - interview_prep / salary_benchmarks (决策层)
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
DB_PATH = os.path.join(DB_DIR, "career_engine.db")


# ─────────────────────────────────────────────
# 连接管理
# ─────────────────────────────────────────────

def get_connection(path: Optional[str] = None) -> sqlite3.Connection:
    db = path or DB_PATH
    os.makedirs(os.path.dirname(db), exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-2000")  # 2MB cache
    return conn


# ─────────────────────────────────────────────
# 表结构定义 (DDL)
# ─────────────────────────────────────────────

DDL_STATEMENTS = [
    # === L1: 用户基础档案 ===
    """
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT DEFAULT 'default',
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        wechat TEXT,
        github TEXT,
        linkedin TEXT,
        portfolio TEXT,
        personal_website TEXT,
        
        -- 求职目标
        target_roles TEXT,          -- JSON array: ["高级后端工程师", "AI 架构师"]
        target_industries TEXT,     -- JSON array: ["AI", "SaaS", "金融科技"]
        target_companies TEXT,      -- JSON array: 目标公司白名单
        target_cities TEXT,         -- JSON array: ["北京", "上海", "远程"]
        
        -- 薪资期望
        min_salary REAL,            -- 最低接受薪资 (k/月)
        expected_salary REAL,       -- 期望薪资 (k/月)
        salary_currency TEXT DEFAULT 'CNY',
        salary_period TEXT DEFAULT 'monthly',
        
        -- 偏好
        remote_preference TEXT CHECK(remote_preference IN ('fully_remote', 'hybrid', 'onsite', 'no_preference')),
        min_company_size INTEGER,   -- 最小公司规模 (人数)
        max_commute_minutes INTEGER, -- 最大通勤时间
        
        -- 底线 (Deal Breakers)
        deal_breakers TEXT,         -- JSON array: ["996", "外包", "单休"]
        core_strengths TEXT,        -- JSON array: 3 个核心优势
        career_summary TEXT,        -- 一句话职业定位
        
        metadata TEXT,              -- JSON: 扩展字段
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # === L2: 工作经历 (STAR+R 结构) ===
    """
    CREATE TABLE IF NOT EXISTS experiences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        
        -- 基本信息
        company TEXT NOT NULL,
        company_size TEXT,          -- "100-500人", "1000人以上"
        company_industry TEXT,
        role TEXT NOT NULL,
        level TEXT,                 -- "P6", "Senior", "Staff", "Director"
        start_date TEXT NOT NULL,   -- YYYY-MM
        end_date TEXT,              -- YYYY-MM 或 NULL (至今)
        is_current BOOLEAN DEFAULT 0,
        employment_type TEXT DEFAULT 'full_time',
        
        -- STAR 结构
        situation TEXT,             -- S: 背景/挑战
        task TEXT,                  -- T: 任务/目标
        action TEXT,                -- A: 采取的行动
        result TEXT,                -- R: 可量化结果
        reflection TEXT,            -- R+: 反思/成长
        
        -- 详细信息
        responsibilities TEXT,      -- JSON array: 主要职责
        achievements TEXT,          -- JSON array: 关键成就
        tech_stack TEXT,            -- JSON array: 使用的技术
        skills_demonstrated TEXT,   -- JSON array: 展现的技能
        team_size INTEGER,          -- 团队规模
        budget_responsibility TEXT, -- 负责的预算规模
        
        -- 证明点 (用于简历)
        quantifiable_metrics TEXT,  -- JSON: {"performance_improvement": "300%", "cost_saving": "50万/年"}
        references_available BOOLEAN DEFAULT 0,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    )
    """,
    
    # === L2: 项目经历 ===
    """
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        experience_id INTEGER,      -- 关联到哪段工作经历
        
        name TEXT NOT NULL,
        role TEXT,
        url TEXT,
        github_url TEXT,
        start_date TEXT,
        end_date TEXT,
        is_ongoing BOOLEAN DEFAULT 0,
        
        -- STAR 结构
        situation TEXT,
        task TEXT,
        action TEXT,
        result TEXT,
        reflection TEXT,
        
        -- 项目详情
        description TEXT,
        tech_stack TEXT,            -- JSON array
        impact_metrics TEXT,        -- JSON: {users: 10000, revenue: 500000, latency_ms: 50}
        category TEXT,              -- "product", "infrastructure", "ai_ml", "open_source"
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
        FOREIGN KEY (experience_id) REFERENCES experiences(id) ON DELETE SET NULL
    )
    """,
    
    # === L2: 技能栈 (分级管理) ===
    """
    CREATE TABLE IF NOT EXISTS skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        
        name TEXT NOT NULL,
        category TEXT CHECK(category IN (
            'programming_language', 'framework', 'database', 'cloud_infra',
            'devops', 'ai_ml', 'mobile', 'frontend', 'backend',
            'architecture', 'tool', 'soft_skill', 'domain_knowledge', 'other'
        )),
        
        -- 熟练度 (1-5 分级)
        proficiency INTEGER CHECK(proficiency BETWEEN 1 AND 5),
        -- 1: 了解 (Awareness) - 知道概念，能简单使用
        -- 2: 入门 (Beginner) - 能完成基本任务
        -- 3: 熟练 (Competent) - 独立完成复杂任务
        -- 4: 精通 (Proficient) - 能指导他人，解决疑难
        -- 5: 专家 (Expert) - 行业级认可，能设计架构
        
        years_experience REAL,
        last_used TEXT,             -- ISO date
        certification TEXT,         -- 相关认证
        
        -- 证明
        proof_projects TEXT,        -- JSON array: 使用此技能的项目
        proof_results TEXT,         -- JSON array: 用此技能达成的结果
        
        -- ATS 关键词变体
        aliases TEXT,               -- JSON array: ["Python", "Python3", "Py"]
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
        UNIQUE(profile_id, name)
    )
    """,
    
    # === L3: 公司档案 ===
    """
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        
        name TEXT NOT NULL,
        industry TEXT,
        size TEXT,                  -- "50-200人", "1000人以上"
        stage TEXT,                 -- "天使轮", "A轮", "B轮", "C轮", "D轮+", "已上市"
        funding_total TEXT,         -- 融资总额
        last_funding_date TEXT,
        
        headquarters TEXT,
        locations TEXT,             -- JSON array: 办公地点
        
        -- 评价信息
        glassdoor_rating REAL,
        maimai_rating REAL,         -- 脉脉评分
        work_culture TEXT,          -- 文化描述
        known_for TEXT,             -- JSON array: 公司知名产品/技术
        
        -- 技术栈
        tech_stack TEXT,            -- JSON array: 公司使用的技术
        engineering_blog TEXT,
        github_org TEXT,
        
        -- 招聘相关
        careers_url TEXT,
        ats_platform TEXT,          -- "boss", "zhilian", "51job", "lagou", "custom"
        
        -- 用户评价
        user_notes TEXT,
        user_interest_score INTEGER CHECK(user_interest_score BETWEEN 1 AND 5),
        
        scraped_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(name)
    )
    """,
    
    # === L3: 岗位库 ===
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        
        -- 来源
        source TEXT NOT NULL,       -- "boss", "zhilian", "51job", "lagou", "liepin", "manual"
        source_url TEXT,
        source_job_id TEXT,         -- 平台原始 ID
        
        -- 岗位信息
        company TEXT NOT NULL,
        title TEXT NOT NULL,
        department TEXT,
        
        -- 地点与类型
        location TEXT,
        districts TEXT,             -- JSON array: 多个工作地点
        remote_type TEXT CHECK(remote_type IN ('fully_remote', 'hybrid', 'onsite', 'not_specified')),
        employment_type TEXT DEFAULT 'full_time',
        
        -- 薪资
        salary_min REAL,
        salary_max REAL,
        salary_negotiable BOOLEAN DEFAULT 1,
        salary_currency TEXT DEFAULT 'CNY',
        salary_period TEXT DEFAULT 'monthly',
        benefits TEXT,              -- JSON array: 福利
        
        -- 要求
        experience_required TEXT,   -- "1-3年", "3-5年", "5-10年"
        education_required TEXT,    -- "本科", "硕士", "不限"
        required_skills TEXT,       -- JSON array
        preferred_skills TEXT,      -- JSON array
        jd_text TEXT,               -- 完整 JD
        jd_keywords TEXT,           -- JSON array: 提取的关键词
        
        -- 分类
        archetype TEXT,             -- 岗位类型: "backend", "frontend", "fullstack", "ai_ml", "devops", "pm", "data"
        seniority TEXT,             -- "junior", "mid", "senior", "staff", "principal", "director"
        tags TEXT,                  -- JSON array
        
        -- 状态
        is_active BOOLEAN DEFAULT 1,
        is_bookmarked BOOLEAN DEFAULT 0,
        priority INTEGER DEFAULT 0, -- 用户手动置顶
        
        scraped_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
    )
    """,
    
    # === L4: 投递记录 ===
    """
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        profile_id INTEGER NOT NULL,
        resume_version TEXT,        -- "v1.0", "ats-optimized-2024-01"
        resume_path TEXT,           -- 生成的简历文件路径
        
        -- 状态机
        status TEXT CHECK(status IN (
            'not_applied',          -- 未投递
            'researching',          -- 调研中
            'prepared',             -- 材料已准备
            'applied',              -- 已投递
            'screening',            -- 简历筛选中
            'phone_screen',         -- 电话面
            'interview_1',          -- 一面
            'interview_2',          -- 二面
            'interview_final',      -- 终面/HR面
            'offer_received',       -- 收到Offer
            'offer_negotiating',    -- Offer谈判中
            'offer_accepted',       -- 接受Offer
            'rejected',             -- 被拒
            'withdrawn',            -- 主动撤回
            'ghosted'               -- 无回复
        )) DEFAULT 'not_applied',
        
        -- 时间线
        applied_at TIMESTAMP,
        next_step_date TIMESTAMP,   -- 下一步预计日期
        follow_up_date TIMESTAMP,   -- 跟进提醒日期
        
        -- 联系人
        recruiter_name TEXT,
        recruiter_contact TEXT,
        hiring_manager TEXT,
        
        -- 薪资
        offered_salary REAL,
        negotiated_salary REAL,
        
        -- 备注
        notes TEXT,
        rejection_reason TEXT,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (job_id) REFERENCES jobs(id),
        FOREIGN KEY (profile_id) REFERENCES profiles(id)
    )
    """,
    
    # === L4: 匹配评估报告 ===
    """
    CREATE TABLE IF NOT EXISTS match_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        profile_id INTEGER NOT NULL,
        application_id INTEGER,
        
        -- 总体评分
        overall_score REAL CHECK(overall_score BETWEEN 0 AND 100),
        grade TEXT CHECK(grade IN ('A+', 'A', 'A-', 'B+', 'B', 'B-', 'C', 'D', 'F')),
        grade_label TEXT,           -- "Dream Job", "Strong Match", etc.
        
        -- 8 维度评分 (0-100)
        match_score REAL,           -- 25% 技能与经验匹配
        impact_score REAL,          -- 20% 业务影响力
        growth_score REAL,          -- 15% 成长空间
        comp_score REAL,            -- 15% 薪酬竞争力
        culture_score REAL,         -- 10% 文化匹配
        tech_stack_score REAL,      -- 5%  技术栈先进性
        stability_score REAL,       -- 5%  公司稳定性
        wlb_score REAL,             -- 5%  工作生活平衡
        
        -- 分析结果
        pros TEXT,                  -- JSON array: 优势
        cons TEXT,                  -- JSON array: 劣势
        risks TEXT,                 -- JSON array: 风险提示
        red_flags TEXT,             -- JSON array: 红旗警告
        
        -- 建议
        recommendations TEXT,       -- JSON: {resume_changes, interview_prep, negotiation_tips, questions_to_ask}
        suggested_star_stories TEXT,-- JSON array: 推荐使用的 STAR 故事
        keywords_to_add TEXT,       -- JSON array: 简历需补充的关键词
        skills_gap TEXT,            -- JSON array: 技能缺口
        
        -- 薪酬分析
        market_salary_min REAL,
        market_salary_max REAL,
        market_salary_median REAL,
        salary_percentile REAL,     -- 该岗位薪资在市场中的百分位
        
        -- 岗位类型
        job_archetype TEXT,         -- "backend", "ai_ml", "fullstack" 等
        
        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (job_id) REFERENCES jobs(id),
        FOREIGN KEY (profile_id) REFERENCES profiles(id),
        FOREIGN KEY (application_id) REFERENCES applications(id)
    )
    """,
    
    # === L5: 面试准备 ===
    """
    CREATE TABLE IF NOT EXISTS interview_prep (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        profile_id INTEGER NOT NULL,
        application_id INTEGER,
        
        -- STAR 故事库
        star_stories TEXT,          -- JSON array: {id, title, situation, task, action, result, reflection, tags[]}
        
        -- 技术面准备
        technical_topics TEXT,      -- JSON array: 需要复习的技术点
        coding_challenges TEXT,     -- JSON array: 可能的算法题方向
        system_design_topics TEXT,  -- JSON array: 系统设计话题
        
        -- 行为面准备
        behavioral_questions TEXT,  -- JSON array: {question, suggested_answer, related_story_id}
        
        -- 反问环节
        questions_to_ask TEXT,      -- JSON array: 向面试官提的问题
        
        -- 公司信息
        company_research TEXT,      -- JSON: 公司调研笔记
        interviewer_info TEXT,      -- JSON: 面试官信息 (如有)
        
        -- 笔记
        mock_interview_notes TEXT,
        post_interview_reflection TEXT,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (job_id) REFERENCES jobs(id),
        FOREIGN KEY (profile_id) REFERENCES profiles(id),
        FOREIGN KEY (application_id) REFERENCES applications(id)
    )
    """,
    
    # === L5: 薪酬基准 ===
    """
    CREATE TABLE IF NOT EXISTS salary_benchmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        
        role TEXT NOT NULL,
        city TEXT NOT NULL,
        experience_level TEXT,      -- "junior", "mid", "senior", "staff"
        
        -- 市场数据
        p25 REAL,                   -- 25 分位
        p50 REAL,                   -- 中位数
        p75 REAL,                   -- 75 分位
        p90 REAL,                   -- 90 分位
        average REAL,
        
        -- 数据来源
        source TEXT,                -- "manual", "zhipin", "maimai", "offershow"
        sample_size INTEGER,
        
        currency TEXT DEFAULT 'CNY',
        period TEXT DEFAULT 'monthly',
        
        data_date TEXT,             -- 数据日期
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # === 索引优化 ===
    """CREATE INDEX IF NOT EXISTS idx_experiences_profile ON experiences(profile_id)""",
    """CREATE INDEX IF NOT EXISTS idx_projects_profile ON projects(profile_id)""",
    """CREATE INDEX IF NOT EXISTS idx_skills_profile ON skills(profile_id)""",
    """CREATE INDEX IF NOT EXISTS idx_skills_proficiency ON skills(proficiency DESC)""",
    """CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)""",
    """CREATE INDEX IF NOT EXISTS idx_jobs_archetype ON jobs(archetype)""",
    """CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs(location)""",
    """CREATE INDEX IF NOT EXISTS idx_jobs_salary ON jobs(salary_min, salary_max)""",
    """CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status)""",
    """CREATE INDEX IF NOT EXISTS idx_applications_profile ON applications(profile_id)""",
    """CREATE INDEX IF NOT EXISTS idx_match_reports_grade ON match_reports(grade)""",
    """CREATE INDEX IF NOT EXISTS idx_match_reports_score ON match_reports(overall_score DESC)""",
    
    # === L6: 面试辅导 ===
    """
    CREATE TABLE IF NOT EXISTS interview_coaching (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER,
        job_id INTEGER,
        profile_id INTEGER NOT NULL,
        
        -- 面试类型
        interview_type TEXT CHECK(interview_type IN (
            'hr_screening',
            'technical',
            'system_design',
            'behavioral',
            'manager',
            'cross_functional',
            'final'
        )),
        round_number INTEGER,     -- 第几轮面试
        
        -- 面试官画像
        interviewer_role TEXT,    -- HR / Tech Lead / CTO / 总监
        interviewer_background TEXT, -- JSON: 面试官背景信息
        
        -- 话术库
        opening_scripts TEXT,     -- JSON array: 开场白话术
        self_introduction TEXT,   -- 自我介绍 (针对不同轮次优化)
        key_talking_points TEXT,  -- JSON array: 核心表达要点
        salary_negotiation TEXT,  -- JSON: 薪资谈判话术
        questions_to_ask TEXT,    -- JSON array: 反问环节问题库
        
        -- 专业面试辅助
        predicted_topics TEXT,    -- JSON array: 预测面试话题
        technical_deep_dives TEXT,-- JSON array: 技术深挖方向
        weak_areas_prep TEXT,     -- JSON array: 薄弱环节准备建议
        star_stories_matched TEXT,-- JSON array: 匹配的 STAR 故事
        
        -- 模拟面试
        mock_questions TEXT,      -- JSON array: 模拟面试题
        mock_answers TEXT,        -- JSON array: 参考答案要点
        mock_feedback TEXT,       -- 模拟面试反馈
        
        -- 实战记录
        actual_questions TEXT,    -- JSON array: 实际面试问题
        self_assessment TEXT,     -- JSON: 自我评估
        post_interview_notes TEXT,-- 面试后复盘笔记
        improvement_points TEXT,  -- JSON array: 改进点
        
        -- 效果追踪
        effectiveness_score INTEGER CHECK(effectiveness_score BETWEEN 1 AND 10),
        lessons_learned TEXT,     -- JSON array: 经验教训
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE SET NULL,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL,
        FOREIGN KEY (profile_id) REFERENCES profiles(id)
    )
    """,
    
    # === L6: 简历检索分析 ===
    """
    CREATE TABLE IF NOT EXISTS resume_analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        
        -- 简历版本追踪
        version TEXT NOT NULL,
        generated_at TIMESTAMP,
        target_job_id INTEGER,
        
        -- 分析指标
        ats_score REAL,           -- ATS 解析得分
        keyword_density REAL,     -- 关键词密度
        readability_score REAL,   -- 可读性评分
        impact_words_count INTEGER,-- 影响力词汇数量
        quantified_achievements INTEGER, -- 量化成就数量
        
        -- 优化建议
        suggestions TEXT,         -- JSON array: 优化建议
        missing_keywords TEXT,    -- JSON array: 缺失关键词
        weak_sections TEXT,       -- JSON array: 薄弱板块
        
        -- 版本对比
        changes_from_previous TEXT, -- JSON: 与上一版本的差异
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (profile_id) REFERENCES profiles(id),
        FOREIGN KEY (target_job_id) REFERENCES jobs(id)
    )
    """,
    
    # === 视图: 求职看板 ===
    """
    CREATE VIEW IF NOT EXISTS vw_pipeline_dashboard AS
    SELECT
        a.id,
        j.company,
        j.title,
        j.location,
        j.salary_min,
        j.salary_max,
        a.status,
        mr.grade,
        mr.overall_score,
        a.applied_at,
        a.next_step_date,
        j.source_url
    FROM applications a
    JOIN jobs j ON a.job_id = j.id
    LEFT JOIN match_reports mr ON a.id = mr.application_id
    ORDER BY mr.overall_score DESC NULLS LAST
    """,
]


# ─────────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────────

def init_db(path: Optional[str] = None) -> str:
    """初始化数据库，返回数据库路径"""
    conn = get_connection(path)
    try:
        for ddl in DDL_STATEMENTS:
            conn.execute(ddl)
        conn.commit()
    finally:
        conn.close()
    return path or DB_PATH


# ─────────────────────────────────────────────
# CRUD 操作 (Profile)
# ─────────────────────────────────────────────

def create_profile(data: Dict[str, Any], path: Optional[str] = None) -> int:
    """创建用户档案，返回 profile_id"""
    conn = get_connection(path)
    try:
        # JSON 字段序列化
        json_fields = [
            'target_roles', 'target_industries', 'target_companies', 'target_cities',
            'deal_breakers', 'core_strengths'
        ]
        for field in json_fields:
            if field in data and isinstance(data[field], list):
                data[field] = json.dumps(data[field], ensure_ascii=False)
        
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        values = [data[k] for k in data.keys()]
        
        cursor = conn.execute(
            f"INSERT INTO profiles ({columns}) VALUES ({placeholders})",
            values
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_profile(profile_id: int, path: Optional[str] = None) -> Optional[Dict]:
    """获取用户档案"""
    conn = get_connection(path)
    try:
        row = conn.execute(
            "SELECT * FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        # 反序列化 JSON 字段
        json_fields = [
            'target_roles', 'target_industries', 'target_companies', 'target_cities',
            'deal_breakers', 'core_strengths', 'metadata'
        ]
        for field in json_fields:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return result
    finally:
        conn.close()


def get_profile_skills(profile_id: int, path: Optional[str] = None) -> List[Dict]:
    """获取用户技能列表 (按熟练度排序)"""
    conn = get_connection(path)
    try:
        rows = conn.execute(
            "SELECT * FROM skills WHERE profile_id = ? ORDER BY proficiency DESC, years_experience DESC",
            (profile_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_profile_experiences(profile_id: int, path: Optional[str] = None) -> List[Dict]:
    """获取工作经历 (按时间倒序)"""
    conn = get_connection(path)
    try:
        rows = conn.execute(
            "SELECT * FROM experiences WHERE profile_id = ? ORDER BY start_date DESC",
            (profile_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─────────────────────────────────────────────
# CRUD 操作 (Jobs & Applications)
# ─────────────────────────────────────────────

def add_job(data: Dict[str, Any], path: Optional[str] = None) -> int:
    """添加岗位"""
    conn = get_connection(path)
    try:
        json_fields = ['districts', 'required_skills', 'preferred_skills', 'jd_keywords', 'tags', 'benefits']
        for field in json_fields:
            if field in data and isinstance(data[field], list):
                data[field] = json.dumps(data[field], ensure_ascii=False)
        
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        values = [data[k] for k in data.keys()]
        
        cursor = conn.execute(f"INSERT INTO jobs ({columns}) VALUES ({placeholders})", values)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def create_application(job_id: int, profile_id: int, path: Optional[str] = None) -> int:
    """创建投递记录"""
    conn = get_connection(path)
    try:
        cursor = conn.execute(
            "INSERT INTO applications (job_id, profile_id) VALUES (?, ?)",
            (job_id, profile_id)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_application_status(app_id: int, status: str, path: Optional[str] = None):
    """更新投递状态"""
    conn = get_connection(path)
    try:
        now = datetime.now().isoformat()
        updates = {"status": status, "updated_at": now}
        if status == 'applied':
            updates["applied_at"] = now
        
        conn.execute(
            "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, app_id)
        )
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────
# 查询
# ─────────────────────────────────────────────

def get_pipeline(profile_id: Optional[int] = None, path: Optional[str] = None) -> List[Dict]:
    """获取求职看板"""
    conn = get_connection(path)
    try:
        query = """
            SELECT
                a.id, j.company, j.title, j.location,
                j.salary_min, j.salary_max, a.status,
                mr.grade, mr.overall_score,
                a.applied_at, a.next_step_date, j.source_url
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            LEFT JOIN match_reports mr ON a.id = mr.application_id
        """
        params = []
        if profile_id:
            query += " WHERE a.profile_id = ?"
            params.append(profile_id)
        query += " ORDER BY mr.overall_score DESC NULLS LAST, a.updated_at DESC"
        
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_job_stats(profile_id: Optional[int] = None, path: Optional[str] = None) -> Dict:
    """获取求职统计"""
    conn = get_connection(path)
    try:
        where = f"WHERE a.profile_id = {profile_id}" if profile_id else ""
        
        total = conn.execute(
            f"SELECT COUNT(*) as cnt FROM applications a {where}"
        ).fetchone()["cnt"]
        
        by_status = {}
        for row in conn.execute(
            f"SELECT status, COUNT(*) as cnt FROM applications a {where} GROUP BY status"
        ).fetchall():
            by_status[row["status"]] = row["cnt"]
        
        avg_score = conn.execute(
            f"SELECT AVG(mr.overall_score) as avg FROM applications a JOIN match_reports mr ON a.id = mr.application_id {where}"
        ).fetchone()["avg"] or 0
        
        return {
            "total_applications": total,
            "by_status": by_status,
            "average_score": round(avg_score, 1),
        }
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = init_db()
    print(f"✅ Career Engine DB 初始化成功: {db_path}")
    print(f"📊 数据表: 10 个 (profiles/experiences/projects/skills/companies/jobs/applications/match_reports/interview_prep/salary_benchmarks)")
    print(f"📈 视图: 1 个 (vw_pipeline_dashboard)")
    print(f"🔗 索引: 12 个")
