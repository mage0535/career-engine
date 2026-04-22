"""
Career Engine - 投递辅助模块

功能:
1. 投递状态追踪 (状态机管理)
2. Follow-up 提醒生成
3. 投递记录分析 (转化率、瓶颈检测)
4. 半自动投递辅助 (话术模板 + 平台适配)
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_DIR)
from core.database.models import get_connection


# ─────────────────────────────────────────────
# 状态机定义
# ─────────────────────────────────────────────

STATUS_TRANSITIONS = {
    'not_applied': ['researching', 'prepared'],
    'researching': ['prepared', 'not_applied'],
    'prepared': ['applied', 'researching'],
    'applied': ['screening', 'rejected', 'ghosted'],
    'screening': ['phone_screen', 'interview_1', 'rejected', 'ghosted'],
    'phone_screen': ['interview_1', 'rejected', 'ghosted'],
    'interview_1': ['interview_2', 'rejected', 'ghosted'],
    'interview_2': ['interview_final', 'rejected', 'ghosted'],
    'interview_final': ['offer_received', 'rejected', 'ghosted'],
    'offer_received': ['offer_negotiating', 'offer_accepted', 'rejected'],
    'offer_negotiating': ['offer_accepted', 'rejected', 'withdrawn'],
    'offer_accepted': [],  # 终态
    'rejected': [],        # 终态
    'withdrawn': [],       # 终态
    'ghosted': [],         # 终态
}

STATUS_LABELS = {
    'not_applied': '未投递',
    'researching': '调研中',
    'prepared': '材料已准备',
    'applied': '已投递',
    'screening': '简历筛选中',
    'phone_screen': '电话面',
    'interview_1': '一面',
    'interview_2': '二面',
    'interview_final': '终面/HR面',
    'offer_received': '收到Offer',
    'offer_negotiating': 'Offer谈判中',
    'offer_accepted': '接受Offer',
    'rejected': '被拒',
    'withdrawn': '主动撤回',
    'ghosted': '无回复',
}

# 跟进间隔 (天数)
FOLLOW_UP_SCHEDULE = {
    'applied': 7,          # 投递后 7 天跟进
    'screening': 5,        # 筛选中 5 天跟进
    'phone_screen': 3,     # 电话面后 3 天
    'interview_1': 5,      # 一面后 5 天
    'interview_2': 5,      # 二面后 5 天
    'interview_final': 3,  # 终面后 3 天
    'offer_received': 2,   # 收到 Offer 后 2 天
}


class DeliveryTracker:
    """投递状态追踪器"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path
    
    def update_status(self, app_id: int, new_status: str, notes: str = '') -> Dict:
        """更新投递状态"""
        if new_status not in STATUS_TRANSITIONS:
            return {'error': f'Invalid status: {new_status}'}
        
        conn = get_connection(self.db_path)
        try:
            # 获取当前状态
            row = conn.execute(
                "SELECT status FROM applications WHERE id = ?", (app_id,)
            ).fetchone()
            
            if not row:
                return {'error': f'Application {app_id} not found'}
            
            current_status = row['status']
            
            # 验证状态转换合法性
            if new_status not in STATUS_TRANSITIONS.get(current_status, []):
                allowed = STATUS_TRANSITIONS.get(current_status, [])
                return {
                    'error': f'Cannot transition from "{current_status}" to "{new_status}"',
                    'allowed': allowed
                }
            
            now = datetime.now().isoformat()
            updates = {
                'status': new_status,
                'updated_at': now,
            }
            
            if new_status == 'applied':
                updates['applied_at'] = now
            if new_status in FOLLOW_UP_SCHEDULE:
                days = FOLLOW_UP_SCHEDULE[new_status]
                updates['follow_up_date'] = (datetime.now() + timedelta(days=days)).isoformat()
            
            if notes:
                updates['notes'] = notes
            
            conn.execute(
                "UPDATE applications SET status = ?, updated_at = ?, follow_up_date = COALESCE(?, follow_up_date), notes = COALESCE(?, notes) WHERE id = ?",
                (new_status, now, updates.get('follow_up_date'), notes, app_id)
            )
            conn.commit()
            
            return {
                'status': 'ok',
                'app_id': app_id,
                'from_status': current_status,
                'to_status': new_status,
                'follow_up_date': updates.get('follow_up_date'),
            }
        finally:
            conn.close()
    
    def get_follow_ups(self, days_ahead: int = 3) -> List[Dict]:
        """获取需要跟进的投递"""
        conn = get_connection(self.db_path)
        try:
            threshold = (datetime.now() + timedelta(days=days_ahead)).isoformat()
            rows = conn.execute("""
                SELECT a.id, j.company, j.title, a.status, a.follow_up_date,
                       a.applied_at, a.notes
                FROM applications a
                JOIN jobs j ON a.job_id = j.id
                WHERE a.follow_up_date IS NOT NULL 
                  AND a.follow_up_date <= ?
                  AND a.status NOT IN ('rejected', 'withdrawn', 'ghosted', 'offer_accepted')
                ORDER BY a.follow_up_date ASC
            """, (threshold,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    
    def get_conversion_stats(self, profile_id: int = None) -> Dict:
        """获取转化率统计"""
        conn = get_connection(self.db_path)
        try:
            where = ""
            params = []
            if profile_id:
                where = "WHERE a.profile_id = ?"
                params.append(profile_id)
            
            # 漏斗分析
            funnel = {
                'total': 0,
                'applied': 0,
                'screening': 0,
                'interview': 0,
                'offer': 0,
                'accepted': 0,
            }
            
            for row in conn.execute(f"""
                SELECT status, COUNT(*) as cnt FROM applications a {where} GROUP BY status
            """, params).fetchall():
                status = row['status']
                cnt = row['cnt']
                funnel['total'] += cnt
                
                if status in ('applied', 'screening', 'phone_screen'):
                    funnel['applied'] += cnt
                if status in ('screening', 'phone_screen'):
                    funnel['screening'] += cnt
                if status.startswith('interview'):
                    funnel['interview'] += cnt
                if status.startswith('offer'):
                    funnel['offer'] += cnt
                if status == 'offer_accepted':
                    funnel['accepted'] += cnt
            
            # 计算转化率
            conversions = {}
            if funnel['total'] > 0:
                conversions['application_rate'] = funnel['applied'] / funnel['total']
            if funnel['applied'] > 0:
                conversions['screening_rate'] = funnel['screening'] / funnel['applied']
            if funnel['screening'] > 0:
                conversions['interview_rate'] = funnel['interview'] / funnel['screening']
            if funnel['interview'] > 0:
                conversions['offer_rate'] = funnel['offer'] / funnel['interview']
            
            # 瓶颈检测
            bottlenecks = []
            if conversions.get('screening_rate', 1) < 0.3:
                bottlenecks.append('简历筛选通过率低 (建议优化简历/ATS 关键词)')
            if conversions.get('interview_rate', 1) < 0.3:
                bottlenecks.append('面试转化率低 (建议加强面试准备)')
            if conversions.get('offer_rate', 1) < 0.3:
                bottlenecks.append('Offer 转化率低 (建议加强谈判技巧/降低期望)')
            
            return {
                'funnel': funnel,
                'conversions': {k: round(v, 3) for k, v in conversions.items()},
                'bottlenecks': bottlenecks,
            }
        finally:
            conn.close()


# ─────────────────────────────────────────────
# CLI 测试
# ─────────────────────────────────────────────

if __name__ == "__main__":
    db_path = os.path.join(SKILL_DIR, "data", "career_engine.db")
    tracker = DeliveryTracker(db_path)
    
    # 测试状态转换
    print("📊 投递状态机:")
    for status, allowed in STATUS_TRANSITIONS.items():
        print(f"   {STATUS_LABELS[status]} → {', '.join(STATUS_LABELS.get(s, s) for s in allowed[:3])}...")
    
    # 测试统计 (如果有数据)
    if os.path.exists(db_path):
        stats = tracker.get_conversion_stats()
        print(f"\n📈 转化漏斗:")
        for k, v in stats['funnel'].items():
            print(f"   {k}: {v}")
        if stats['bottlenecks']:
            print(f"\n⚠️ 瓶颈: {stats['bottlenecks']}")
