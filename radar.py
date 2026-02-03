import os
import requests
from datetime import datetime, timedelta

# --- 配置区 ---
# 监控的组织或项目 (格式: "org/repo" 或 "org")
MONITOR_TARGETS = ["deepseek-ai", "QwenLM", "unslothai/unsloth", "vllm-project/vllm"]
# 过滤门槛：Follower 超过多少的人才值得推送到飞书
FOLLOWER_THRESHOLD = 50 
# 重点关注的公司/关键词（不区分大小写）
KEY_COMPANIES = ["OpenAI", "Google", "Meta", "ByteDance", "Tencent", "Alibaba", "Stanford", "Tsinghua"]

GH_TOKEN = os.getenv("GH_TOKEN")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")

headers = {"Authorization": f"token {GH_TOKEN}"}

def get_recent_stars(repo_full_name):
    """获取过去 1 小时内新增的 Star 用户"""
    url = f"https://api.github.com/repos/{repo_full_name}/stargazers"
    # 使用 Accept header 获取点星时间
    headers["Accept"] = "application/vnd.github.v3.star+json"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return []

    talents = []
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    for entry in response.json():
        starred_at = datetime.strptime(entry['starred_at'], '%Y-%m-%dT%H:%M:%SZ')
        if starred_at > one_hour_ago:
            user_url = entry['user']['url']
            user_data = requests.get(user_url, headers=headers).json()
            
            # 人才筛选逻辑
            bio = (user_data.get('bio') or "").lower()
            company = (user_data.get('company') or "").lower()
            followers = user_data.get('followers', 0)
            
            is_key_talent = any(k.lower() in bio or k.lower() in company for k in KEY_COMPANIES)
            if followers > FOLLOWER_THRESHOLD or is_key_talent:
                talents.append({
                    "name": user_data.get('name') or user_data.get('login'),
                    "login": user_data.get('login'),
                    "company": user_data.get('company', 'Unknown'),
                    "followers": followers,
                    "bio": user_data.get('bio', ''),
                    "url": user_data.get('html_url')
                })
    return talents

def send_feishu_card(repo_name, talents):
    """推送飞书富文本卡片"""
    if not talents: return
    
    talent_list_str = ""
    for t in talents:
        talent_list_str += f"👤 **[{t['name']}]({t['url']})**\n🏢 公司: {t['company']}\n👥 粉丝: {t['followers']}\n📝 简介: {t['bio']}\n\n"

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": f"🎯 AI 猎头发现新动向: {repo_name}"}, "template": "blue"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**过去 1 小时，以下优质人才 Star 了该项目：**\n\n{talent_list_str}"}},
                {"tag": "hr"},
                {"tag": "note", "content": {"tag": "plain_text", "content": "自动追踪系统 · 实时监听中"}}
            ]
        }
    }
    requests.post(FEISHU_WEBHOOK, json=card)

if __name__ == "__main__":
    for target in MONITOR_TARGETS:
        # 如果是组织名，可以进一步扩展获取其下所有 Repo，这里简单处理为单个 Repo
        print(f"Checking {target}...")
        talents = get_recent_stars(target)
        if talents:
            send_feishu_card(target, talents)
