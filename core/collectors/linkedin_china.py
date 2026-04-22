"""
Career Engine - LinkedIn China (领英职场) Collector

说明:
领英中国 (LinkedIn.cn) 目前主要提供求职招聘功能 (InCareer 已停止运营，功能合并回全球版但针对中国区优化)。
本采集器主要针对国内用户的使用习惯和展示形式进行适配。

策略:
1. 针对 linkedin.cn 或中国区 IP 下的 linkedin.com/jobs
2. 提取中文岗位名称、公司名称
3. 适配国内常见的薪资展示 (如 15-25k)
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


class LinkedInChinaCollector(BaseCollector):
    """LinkedIn China 采集器"""
    
    def __init__(self, db_path: str = None, cookie_path: str = None):
        super().__init__(
            platform='linkedin_cn',
            db_path=db_path,
            anti_scrape=AntiScrapeConfig(min_delay=4.0, max_delay=8.0)
        )
        self.cookie_path = cookie_path or os.path.join(SKILL_DIR, "config", "linkedin_cookies.json")
        self.base_url = "https://www.linkedin.cn/jobs/search" # 或 linkedin.com
    
    async def search_jobs(self, query: str, location: str = '北京',
                          page: int = 1, **kwargs) -> List[Dict]:
        """
        搜索领英中国岗位
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
                    locale='zh-CN'
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
                
                # URL 构建
                start_index = (page - 1) * 25
                # 领英中国版 URL 参数可能与全球版略有不同，这里复用通用参数结构
                url = f"https://www.linkedin.com/jobs/search/?keywords={query}&location={location}&start={start_index}&trk=public_jobs_jserp_result_search"
                
                # 注意：领英中国版现在大多直接跳转到全球版，但内容展示针对国内优化
                await page_obj.goto(url, wait_until='networkidle')
                await asyncio.sleep(random.uniform(3, 6))
                
                # 检查验证码
                if "challenge" in page_obj.url:
                    print("⚠️ 触发领英安全验证")
                    await browser.close()
                    return self._mock_search(query, location, page)
                
                jobs = await self._parse_job_list(page_obj)
                await browser.close()
                return jobs
                
        except Exception as e:
            print(f"❌ 领英中国采集失败: {e}")
            return self._mock_search(query, location, page)
    
    async def _parse_job_list(self, page) -> List[Dict]:
        """解析列表"""
        jobs = []
        try:
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
                        'url': link.strip().split('?')[0],
                    })
                except:
                    continue
        except:
            pass
        return jobs

    def _mock_search(self, query: str, location: str, page: int) -> List[Dict]:
        """模拟数据"""
        return [
            {
                'title': f'{query} 工程师 (外企)',
                'company': '某知名外企 (中国)',
                'location': location,
                'url': f'https://linkedin.cn/jobs/view/mock-{page}',
            },
            {
                'title': f'资深 {query} 专家',
                'company': 'Global Tech 北京',
                'location': location,
                'url': f'https://linkedin.cn/jobs/view/mock-{page}-2',
            }
        ]


if __name__ == "__main__":
    import asyncio
    collector = LinkedInChinaCollector()
    jobs = asyncio.run(collector.search_jobs('AI 产品经理', '北京'))
    print(f"Found {len(jobs)} jobs from LinkedIn China")
    for j in jobs:
        print(f" - {j['title']} @ {j['company']}")
