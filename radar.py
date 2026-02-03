import os
import requests
from datetime import datetime, timedelta

# --- 1. 鱼塘配置：精准定义你的监控范围 ---
MONITOR_TARGETS = [
    "deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-Coder", # 顶级大厂
    "QwenLM/Qwen2.5", "THUDM/ChatGLM",                      # 国产之光
    "vllm-project/vllm", "tgi-project/text-generation-inference", # 推理框架
    "unslothai/unsloth", "meta-llama/llama3"                # 训练与微调
]

# --- 2. 猎头雷达权重配置 ---
FOLLOWER_THRESHOLD = 30    # 粉丝门槛
LOCATION_FOCUS = ["Beijing", "Shanghai", "Shenzhen", "Hangzhou", "China", "北京", "上海", "深圳", "杭州"]
KEY_TAGS = ["Expert", "Lead", "Staff", "Founder", "PhD", "Principal", "Researcher"]
TARGET_COMPANIES = ["Google", "Meta", "OpenAI", "Anthropic", "ByteDance", "Tencent", "Alibaba", "Baidu", "DeepSeek"]

GH_TOKEN = os.getenv("GH_TOKEN")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3.star+json"}

def analyze_talent(user_data):
    """人才画像打分与识别逻辑"""
    bio = (user_data.get('bio') or "").lower()
    company = (user_data.get('company') or "").lower()
    loc = (user_data.get('location') or "").lower()
    followers = user_data.get('followers', 0)
    
    tags = []
    # 地区识别
    if any(city.lower() in loc for city in LOCATION_FOCUS):
        tags.append("📍 目标地区")
    # 背景识别
    if any(comp.lower() in company or comp.lower() in bio for comp in TARGET_COMPANIES):
        tags.append("🏢 顶尖大厂")
    # 职位识别
    if any(tag.lower() in bio for tag in KEY_TAGS):
        tags.append("👨‍💻 资深/专家")
    # 影响力识别
    if followers > 200:
        tags.append("🌟 业内KOL")
    elif followers > 50:
        tags.append("📈 潜力股")

    return tags

def get_recent_stars(repo):
    url = f"https://api.github.com/repos/{repo}/stargazers"
    response = requests.get(url, headers=headers)
    if response.status_code != 200: return []

    talents = []
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    for entry in response.json()[-30:]: # 检查最近的30个点星者
        starred_at = datetime.strptime(entry['starred_at'], '%Y-%m-%dT%H:%M:%SZ')
        if starred_at > one_hour_ago:
            u_url = entry['user']['url']
            u_data = requests.get(u_url, headers=headers).json()
            tags = analyze_talent(u_data)
            
            if tags: # 只要命中了任何一个标签，就判定为价值人才
                talents.append({
                    "name": u_data.get('name') or u_data.get('login'),
                    "company": u_data.get('company', '个人开发者'),
                    "loc": u_data.get('location', '未知'),
                    "tags": " | ".join(tags),
                    "url": u_data.get('html_url')
                })
    return talents

def send_feishu_card(repo_name, talents):
    if not talents: return
    elements = [{"tag": "div", "text": {"tag": "lark_md", "content": f"⚡ **{repo_name}** 刚刚吸引了以下人才："}}]
    
    for t in talents:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**[{t['name']}]({t['url']})**\n{t['tags']}\n🏢 {t['company']} · 📍 {t['loc']}"}
        })
    
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "🎯 顶级 AI 猎头传感器"}, "template": "orange"},
            "elements": elements
        }
    }
    requests.post(FEISHU_WEBHOOK, json=card)

if __name__ == "__main__":
    for repo in MONITOR_TARGETS:
        found = get_recent_stars(repo)
        if found: send_feishu_card(repo, found)
