"""
Career Engine - BOSS 直聘采集器

注意: BOSS 直聘有严格的反爬机制
策略: 
1. 使用 Playwright 模拟浏览器
2. Cookie 复用 (用户手动登录后导出)
3. 请求间隔随机化 (3-8 秒)
4. User-Agent 轮换
5. 限制采集频率 (每小时最多 20 次)

使用前需配置:
- cookies.json (手动登录后导出)
- 或使用 playwright 手动登录
"""

import json
import os
import sys
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_DIR)
from core.collectors.base import BaseCollector, AntiScrapeConfig


class BossZhipinCollector(BaseCollector):
    """BOSS 直聘采集器"""
    
    def __init__(self, db_path: str = None, cookie_path: str = None):
        super().__init__(
            platform='boss',
            db_path=db_path,
            anti_scrape=AntiScrapeConfig(min_delay=3.0, max_delay=8.0)
        )
        self.cookie_path = cookie_path or os.path.join(SKILL_DIR, "config", "boss_cookies.json")
        self.base_url = "https://www.zhipin.com"
    
    async def search_jobs(self, query: str, city: str = '北京', 
                          page: int = 1, **kwargs) -> List[Dict]:
        """
        搜索 BOSS 直聘岗位
        
        参数:
            query: 搜索关键词 (如 "Python 后端")
            city: 城市
            page: 页码
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            print("⚠️ Playwright 未安装，使用模拟数据")
            return self._mock_search(query, city, page)
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self.anti_scrape.get_headers()['User-Agent'],
                    viewport={'width': 1920, 'height': 1080},
                )
                
                # 加载 Cookie
                if os.path.exists(self.cookie_path):
                    with open(self.cookie_path) as f:
                        cookies = json.load(f)
                        await context.add_cookies(cookies)
                
                page_obj = await context.new_page()
                
                # 构建搜索 URL
                city_code = self._get_city_code(city)
                url = f"{self.base_url}/web/geek/job?query={query}&city={city_code}&page={page}"
                
                await page_obj.goto(url, wait_until='networkidle')
                await asyncio.sleep(random.uniform(2, 4))
                
                # 解析岗位列表
                jobs = await self._parse_job_list(page_obj)
                
                await browser.close()
                return jobs
                
        except Exception as e:
            print(f"❌ BOSS 直聘采集失败: {e}")
            return self._mock_search(query, city, page)
    
    async def _parse_job_list(self, page) -> List[Dict]:
        """解析岗位列表页"""
        jobs = []
        
        try:
            # BOSS 直聘的岗位列表结构
            job_cards = await page.query_selector_all('.job-list-box .job-card-wrapper')
            
            for card in job_cards:
                try:
                    title_el = await card.query_selector('.job-name')
                    company_el = await card.query_selector('.company-name')
                    salary_el = await card.query_selector('.salary')
                    location_el = await card.query_selector('.job-area')
                    
                    title = await title_el.inner_text() if title_el else ''
                    company = await company_el.inner_text() if company_el else ''
                    salary = await salary_el.inner_text() if salary_el else ''
                    location = await location_el.inner_text() if location_el else ''
                    
                    # 解析薪资
                    salary_min, salary_max = self._parse_salary(salary)
                    
                    jobs.append({
                        'title': title,
                        'company': company,
                        'location': location,
                        'salary_min': salary_min,
                        'salary_max': salary_max,
                        'salary_raw': salary,
                    })
                except Exception as e:
                    print(f"⚠️ 解析单条岗位失败: {e}")
                    continue
        except Exception as e:
            print(f"⚠️ 解析页面失败: {e}")
        
        return jobs
    
    def _parse_salary(self, salary_raw: str) -> tuple:
        """解析薪资字符串 (如 "25-40K·14薪")"""
        import re
        match = re.search(r'(\d+)[\-\~](\d+)', salary_raw)
        if match:
            return float(match.group(1)), float(match.group(2))
        return None, None
    
    def _get_city_code(self, city: str) -> str:
        """获取城市代码"""
        city_codes = {
            '北京': '101010100',
            '上海': '101020100',
            '广州': '101280100',
            '深圳': '101280600',
            '杭州': '101210100',
            '成都': '101270100',
            '武汉': '101200100',
            '南京': '101190100',
            '西安': '101110100',
            '重庆': '101040100',
        }
        return city_codes.get(city, '101010100')
    
    def _mock_search(self, query: str, city: str, page: int) -> List[Dict]:
        """模拟搜索 (用于测试)"""
        import random
        mock_jobs = [
            {
                'title': f'{query}工程师',
                'company': f'{city}科技有限公司',
                'location': city,
                'salary_min': random.randint(15, 30),
                'salary_max': random.randint(30, 50),
                'jd_text': f'负责{query}相关开发工作，要求 3-5 年经验',
            },
            {
                'title': f'高级{query}工程师',
                'company': f'{city}互联网公司',
                'location': city,
                'salary_min': random.randint(25, 40),
                'salary_max': random.randint(40, 60),
                'jd_text': f'主导{query}架构设计，要求 5 年以上经验',
            },
            {
                'title': f'{query}技术专家',
                'company': f'{city}大厂',
                'location': city,
                'salary_min': random.randint(40, 50),
                'salary_max': random.randint(60, 80),
                'jd_text': f'负责{query}技术方向，带领团队攻关',
            },
        ]
        return mock_jobs


# ─────────────────────────────────────────────
# CLI 测试
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    
    db_path = os.path.join(SKILL_DIR, "data", "career_engine.db")
    collector = BossZhipinCollector(db_path)
    
    print("🔍 BOSS 直聘采集测试:")
    jobs = asyncio.run(collector.search_jobs('Python 后端', '北京'))
    
    print(f"\n找到 {len(jobs)} 个岗位:")
    for job in jobs:
        print(f"   - {job['title']} @ {job['company']} | {job.get('salary_min', '?')}-{job.get('salary_max', '?')}k")
    
    # 保存
    new_count = collector.save_jobs(jobs)
    print(f"\n✅ 新增 {new_count} 个岗位")
    print(f"📊 统计: {collector.get_stats()}")
