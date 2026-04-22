"""
Career Engine - 智联招聘采集器

策略:
1. 使用公开搜索接口 (webapi.zhaopin.com)
2. 代理池轮换 (可选)
3. 请求间隔 2-5 秒
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


class ZhilianCollector(BaseCollector):
    """智联招聘采集器"""
    
    def __init__(self, db_path: str = None):
        super().__init__(
            platform='zhilian',
            db_path=db_path,
            anti_scrape=AntiScrapeConfig(min_delay=2.0, max_delay=5.0)
        )
        self.api_base = "https://webapi.zhaopin.com"
    
    async def search_jobs(self, query: str, city: str = '北京',
                          page: int = 1, **kwargs) -> List[Dict]:
        """搜索智联招聘岗位"""
        try:
            import httpx
        except ImportError:
            print("⚠️ httpx 未安装，使用模拟数据")
            return self._mock_search(query, city, page)
        
        city_id = self._get_city_id(city)
        url = f"{self.api_base}/job/search"
        params = {
            'start': (page - 1) * 60,
            'pageSize': 60,
            'cityId': city_id,
            'keyword': query,
            'workExperience': '-1',
            'degree': '-1',
            'household': '-1',
            'jobType': '-1',
            'companySize': '-1',
            'salary': '4001,6000,8001,10001,15001,20001,30001,40001,50001,60001',
        }
        
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params, headers=self.anti_scrape.get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    return self._parse_response(data)
                else:
                    print(f"⚠️ 请求失败: {resp.status_code}")
                    return self._mock_search(query, city, page)
        except Exception as e:
            print(f"❌ 智联招聘采集失败: {e}")
            return self._mock_search(query, city, page)
    
    def _parse_response(self, data: Dict) -> List[Dict]:
        """解析 API 响应"""
        jobs = []
        results = data.get('data', {}).get('results', [])
        
        for item in results:
            company = item.get('company', {})
            job_info = item.get('jobInfo', {})
            
            jobs.append({
                'title': item.get('jobName', ''),
                'company': company.get('name', ''),
                'location': item.get('city', {}).get('display', ''),
                'salary_min': item.get('salary', {}).get('min'),
                'salary_max': item.get('salary', {}).get('max'),
                'jd_text': job_info.get('detail', ''),
                'experience_required': item.get('workingExp', {}).get('name', ''),
                'education_required': item.get('eduLevel', {}).get('name', ''),
            })
        
        return jobs
    
    def _get_city_id(self, city: str) -> int:
        """获取城市 ID"""
        city_ids = {
            '北京': 530, '上海': 538, '广州': 763, '深圳': 765,
            '杭州': 653, '成都': 801, '武汉': 736, '南京': 658,
            '西安': 854, '重庆': 551,
        }
        return city_ids.get(city, 530)
    
    def _mock_search(self, query: str, city: str, page: int) -> List[Dict]:
        """模拟数据"""
        return [
            {
                'title': f'{query}开发',
                'company': f'{city}智联科技公司',
                'location': city,
                'salary_min': 15, 'salary_max': 25,
                'jd_text': f'负责{query}开发，3 年以上经验',
                'experience_required': '3-5年',
                'education_required': '本科',
            },
            {
                'title': f'资深{query}工程师',
                'company': f'{city}智联数据公司',
                'location': city,
                'salary_min': 25, 'salary_max': 40,
                'jd_text': f'主导{query}架构，5 年以上经验',
                'experience_required': '5-10年',
                'education_required': '本科',
            },
        ]


# ─────────────────────────────────────────────
# 前程无忧采集器
# ─────────────────────────────────────────────

class Job51Collector(BaseCollector):
    """前程无忧采集器"""
    
    def __init__(self, db_path: str = None):
        super().__init__(
            platform='51job',
            db_path=db_path,
            anti_scrape=AntiScrapeConfig(min_delay=3.0, max_delay=6.0)
        )
        self.search_url = "https://search.51job.com/list/"
    
    async def search_jobs(self, query: str, city: str = '北京',
                          page: int = 1, **kwargs) -> List[Dict]:
        """搜索前程无忧岗位"""
        # 前程无忧搜索 URL 格式
        city_param = self._get_city_param(city)
        url = f"{self.search_url}{city_param},000000,0000,00,9,99,{query},2,{page}.html"
        
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page_obj = await browser.new_page()
                await page_obj.goto(url, wait_until='domcontentloaded')
                await asyncio.sleep(random.uniform(2, 4))
                
                jobs = await self._parse_page(page_obj)
                await browser.close()
                return jobs
        except Exception as e:
            print(f"❌ 前程无忧采集失败: {e}")
            return self._mock_search(query, city, page)
    
    async def _parse_page(self, page) -> List[Dict]:
        """解析页面"""
        jobs = []
        try:
            items = await page.query_selector_all('.el')
            for item in items[1:]:  # 跳过表头
                try:
                    title = await item.query_selector('.t1 a')
                    company = await item.query_selector('.t2 a')
                    location = await item.query_selector('.t3')
                    salary = await item.query_selector('.t4')
                    
                    jobs.append({
                        'title': await title.inner_text() if title else '',
                        'company': await company.inner_text() if company else '',
                        'location': await location.inner_text() if location else '',
                        'salary_raw': await salary.inner_text() if salary else '',
                    })
                except:
                    continue
        except:
            pass
        return jobs
    
    def _get_city_param(self, city: str) -> str:
        city_params = {
            '北京': '010000', '上海': '020000', '广州': '030200',
            '深圳': '040000', '杭州': '080200', '成都': '090200',
        }
        return city_params.get(city, '010000')
    
    def _mock_search(self, query: str, city: str, page: int) -> List[Dict]:
        return [
            {
                'title': f'{query}工程师',
                'company': f'{city}前程公司',
                'location': city,
                'salary_min': 12, 'salary_max': 20,
                'jd_text': f'{query}相关开发',
            },
        ]
