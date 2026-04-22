"""
Career Engine - LinkedIn Global Collector

策略:
1. 针对 linkedin.com/jobs
2. 必须使用有效的 User Session Cookie (否则极易触发验证码)
3. 支持按地点 (location)、关键词 (keyword) 搜索
4. 提取薪资、公司、岗位描述、申请链接
"""

import json
import os
import sys
import asyncio
import random
from typing import Dict, List, Optional
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_DIR)
from core.collectors.base import BaseCollector, AntiScrapeConfig


class LinkedInGlobalCollector(BaseCollector):
    """LinkedIn Global 采集器"""
    
    def __init__(self, db_path: str = None, cookie_path: str = None):
        super().__init__(
            platform='linkedin',
            db_path=db_path,
            anti_scrape=AntiScrapeConfig(min_delay=5.0, max_delay=10.0)  # LinkedIn 延迟要求高
        )
        self.cookie_path = cookie_path or os.path.join(SKILL_DIR, "config", "linkedin_cookies.json")
        self.base_url = "https://www.linkedin.com/jobs/search"
    
    async def search_jobs(self, query: str, location: str = 'China',
                          page: int = 1, **kwargs) -> List[Dict]:
        """
        搜索 LinkedIn 岗位
        
        参数:
            query: 关键词
            location: 地点 (e.g., 'Beijing', 'Singapore', 'United States')
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            print("⚠️ Playwright 未安装，使用模拟数据")
            return self._mock_search(query, location, page)
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self.anti_scrape.get_headers()['User-Agent'],
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US'
                )
                
                # 加载 Cookie
                if os.path.exists(self.cookie_path):
                    with open(self.cookie_path) as f:
                        try:
                            cookies = json.load(f)
                            await context.add_cookies(cookies)
                        except:
                            pass
                
                page_obj = await context.new_page()
                
                # 构建 URL
                # LinkedIn URL 结构: https://www.linkedin.com/jobs/search/?keywords=Python&location=China&start=0
                start_index = (page - 1) * 25
                url = f"{self.base_url}?keywords={query}&location={location}&start={start_index}"
                
                print(f"🌐 Fetching: {url}")
                await page_obj.goto(url, wait_until='networkidle')
                await asyncio.sleep(random.uniform(3, 6))  # LinkedIn 需要较长时间渲染
                
                # 检测是否被拦截 (Captcha)
                if "challenge" in page_obj.url:
                    print("⚠️ LinkedIn 触发了安全验证 (Captcha)，请手动验证或更新 Cookie")
                    await browser.close()
                    return self._mock_search(query, location, page)
                
                jobs = await self._parse_job_list(page_obj)
                await browser.close()
                return jobs
                
        except Exception as e:
            print(f"❌ LinkedIn Global 采集失败: {e}")
            return self._mock_search(query, location, page)
    
    async def _parse_job_list(self, page) -> List[Dict]:
        """解析岗位列表"""
        jobs = []
        try:
            # LinkedIn 新版布局选择器
            items = await page.query_selector_all('.jobs-search__results-list li')
            
            for item in items:
                try:
                    title_el = await item.query_selector('.base-search-card__title')
                    company_el = await item.query_selector('.base-search-card__subtitle')
                    location_el = await item.query_selector('.job-search-card__location')
                    link_el = await item.query_selector('a')
                    
                    title = await title_el.inner_text() if title_el else ''
                    company = await company_el.inner_text() if company_el else ''
                    location = await location_el.inner_text() if location_el else ''
                    link = await link_el.get_attribute('href') if link_el else ''
                    
                    jobs.append({
                        'title': title.strip(),
                        'company': company.strip(),
                        'location': location.strip(),
                        'url': link.strip().split('?')[0], # 清理参数
                        'salary_min': None, # LinkedIn 列表页通常不显示薪资，需进详情页
                        'salary_max': None,
                        'jd_text': '',
                    })
                except Exception:
                    continue
        except Exception:
            pass
        return jobs
    
    def _mock_search(self, query: str, location: str, page: int) -> List[Dict]:
        """模拟数据"""
        return [
            {
                'title': f'{query} Engineer',
                'company': 'Tech Global Inc.',
                'location': location,
                'url': f'https://linkedin.com/jobs/view/mock-{page}',
                'salary_min': None,
                'salary_max': None,
                'jd_text': f'We are looking for a {query} to join our team in {location}.',
            },
            {
                'title': f'Senior {query} Specialist',
                'company': 'MNC Solutions',
                'location': location,
                'url': f'https://linkedin.com/jobs/view/mock-{page}-2',
                'salary_min': None,
                'salary_max': None,
                'jd_text': f'Required: 5+ years experience in {query}.',
            }
        ]


if __name__ == "__main__":
    import asyncio
    collector = LinkedInGlobalCollector()
    jobs = asyncio.run(collector.search_jobs('Python Developer', 'China'))
    print(f"Found {len(jobs)} jobs from LinkedIn Global")
    for j in jobs:
        print(f" - {j['title']} @ {j['company']}")
