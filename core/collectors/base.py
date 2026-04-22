"""
Career Engine - 岗位采集器基类

定义统一的采集器接口，支持:
- 多平台适配 (BOSS/智联/前程无忧/本地)
- 反爬策略 (请求间隔随机化、User-Agent 轮换)
- 数据标准化 (统一字段格式)
- 增量采集 (避免重复)
"""

import json
import os
import sys
import time
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_DIR)
from core.database.models import get_connection, add_job


# ─────────────────────────────────────────────
# 反爬策略
# ─────────────────────────────────────────────

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
]


class AntiScrapeConfig:
    """反爬配置"""
    def __init__(self, 
                 min_delay: float = 2.0,
                 max_delay: float = 5.0,
                 max_retries: int = 3,
                 retry_delay: float = 10.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def random_delay(self):
        """随机延迟"""
        time.sleep(random.uniform(self.min_delay, self.max_delay))
    
    def get_headers(self) -> Dict[str, str]:
        """获取随机请求头"""
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }


# ─────────────────────────────────────────────
# 标准化岗位数据
# ─────────────────────────────────────────────

def normalize_job_data(raw: Dict, source: str) -> Dict:
    """
    将不同平台的原始数据标准化为统一格式
    
    标准字段:
    - source, source_url, source_job_id
    - company, title, department
    - location, remote_type, employment_type
    - salary_min, salary_max, salary_currency, salary_period
    - experience_required, education_required
    - jd_text, jd_keywords, required_skills, preferred_skills
    - archetype, seniority
    """
    from core.scoring.engine import extract_keywords, detect_archetype, detect_seniority
    
    normalized = {
        'source': source,
        'source_url': raw.get('url', ''),
        'source_job_id': raw.get('job_id', ''),
        'company': raw.get('company', ''),
        'title': raw.get('title', ''),
        'department': raw.get('department', ''),
        'location': raw.get('location', ''),
        'remote_type': raw.get('remote_type', 'not_specified'),
        'employment_type': raw.get('employment_type', 'full_time'),
        'salary_min': raw.get('salary_min'),
        'salary_max': raw.get('salary_max'),
        'salary_currency': raw.get('salary_currency', 'CNY'),
        'salary_period': raw.get('salary_period', 'monthly'),
        'experience_required': raw.get('experience_required', ''),
        'education_required': raw.get('education_required', ''),
        'jd_text': raw.get('jd_text', ''),
        'required_skills': raw.get('required_skills', []),
        'preferred_skills': raw.get('preferred_skills', []),
        'tags': raw.get('tags', []),
    }
    
    # 自动提取关键词
    if normalized['jd_text']:
        normalized['jd_keywords'] = extract_keywords(normalized['jd_text'])
        normalized['archetype'] = detect_archetype(normalized['jd_text'])
        normalized['seniority'] = detect_seniority(normalized['jd_text'], normalized['title'])
    
    return normalized


# ─────────────────────────────────────────────
# 采集器基类
# ─────────────────────────────────────────────

class BaseCollector(ABC):
    """岗位采集器基类"""
    
    def __init__(self, platform: str, db_path: str = None, 
                 anti_scrape: AntiScrapeConfig = None):
        self.platform = platform
        self.db_path = db_path or os.path.join(SKILL_DIR, "data", "career_engine.db")
        self.anti_scrape = anti_scrape or AntiScrapeConfig()
        self.stats = {
            'total_found': 0,
            'new_added': 0,
            'duplicates': 0,
            'errors': 0,
        }
    
    @abstractmethod
    async def search_jobs(self, query: str, **kwargs) -> List[Dict]:
        """搜索岗位 (子类实现)"""
        pass
    
    def save_jobs(self, raw_jobs: List[Dict]) -> int:
        """保存岗位到数据库 (去重)"""
        new_count = 0
        conn = get_connection(self.db_path)
        
        try:
            for raw in raw_jobs:
                normalized = normalize_job_data(raw, self.platform)
                
                # 去重检查 (source + source_job_id)
                if normalized['source_job_id']:
                    existing = conn.execute(
                        "SELECT id FROM jobs WHERE source = ? AND source_job_id = ?",
                        (self.platform, normalized['source_job_id'])
                    ).fetchone()
                    if existing:
                        self.stats['duplicates'] += 1
                        continue
                
                # 插入
                data = normalized.copy()
                
                # 序列化 JSON 字段
                json_fields = ['jd_keywords', 'required_skills', 'preferred_skills', 'tags']
                for field in json_fields:
                    if field in data and isinstance(data[field], list):
                        data[field] = json.dumps(data[field], ensure_ascii=False)
                
                # 移除不在表中的字段
                valid_fields = {
                    'source', 'source_url', 'source_job_id', 'company', 'title',
                    'department', 'location', 'remote_type', 'employment_type',
                    'salary_min', 'salary_max', 'salary_currency', 'salary_period',
                    'experience_required', 'education_required', 'jd_text',
                    'jd_keywords', 'required_skills', 'preferred_skills',
                    'archetype', 'seniority', 'tags',
                }
                data = {k: v for k, v in data.items() if k in valid_fields}
                data['scraped_at'] = datetime.now().isoformat()
                
                try:
                    add_job(data, self.db_path)
                    new_count += 1
                    self.anti_scrape.random_delay()
                except Exception as e:
                    self.stats['errors'] += 1
                    print(f"⚠️ 保存失败: {e}")
            
            self.stats['new_added'] += new_count
        finally:
            conn.close()
        
        return new_count
    
    def get_stats(self) -> Dict:
        """获取采集统计"""
        return self.stats.copy()
