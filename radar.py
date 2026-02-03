import os
import requests
from datetime import datetime, timedelta, timezone

# --- [定向狙击鱼塘配置] ---
MONITOR_CONFIG = {
    "ARCH": [
        "vllm-project/vllm", "tikv/tikv", "pytorch/pytorch", 
        "deepseek-ai/DeepSeek-V3", "NVIDIA/FasterTransformer",
        "ggml-org/llama.cpp", "flashinfer-ai/flashinfer"
    ],
    "WEB3": [
        "paradigmxyz/reth", "succinctlabs/sp1", 
        "ethereum/consensus-specs", "solana-labs/solana",
        "hyperledger/fabric"
    ]
}
MONITOR_TARGETS = [repo for repos in MONITOR_CONFIG.values() for repo in repos]

# --- [人才画像权重] ---
LOCATION_FOCUS = ["Beijing", "Shanghai", "Shenzhen", "Hangzhou", "China", "北京", "上海", "深圳", "杭州"]
KEY_TAGS = ["Expert", "Lead", "Staff", "PhD", "Principal", "Architect", "Kernel", "Infra", "CUDA", "Cryptography"]
TARGET_COMPANIES = ["DeepSeek", "OpenAI", "Google", "Meta", "ByteDance", "Tencent", "Alibaba", "Binance", "Paradigm"]

GH_TOKEN = os.getenv("GH_TOKEN")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3.star+json"}

# 时区处理：北京时间 UTC+8
SHA_TZ = timezone(timedelta(hours=8))

def analyze_talent(u_data, repo):
    bio = (u_data.get('bio') or "").lower()
    company = (u_data.get('company') or "").lower()
    loc = (u_data.get('location') or "").lower()
    
    tags = []
    # 识别底层架构背景
    is_arch_expert = any(k.lower() in bio or k.lower() in company for k in ["kernel", "distributed", "cuda", "infra", "architect"])
    
    # 交叉狙击：架构大牛出现在 Web3 项目
    if repo in MONITOR_CONFIG["WEB3"] and is_arch_expert:
        tags.append("🔥 CROSS_OVER (架构师入场Web3)")
    
    if any(c.lower() in loc for c in LOCATION_FOCUS): tags.append("📍 目标地区")
    if any(com.lower() in company or com.lower() in bio for com in TARGET_COMPANIES): tags.append("🏢 顶尖背景")
    if u_data.get('followers', 0) > 100: tags.append("🌟 KOL")
    
    return tags

def get_recent_stars(repo):
    url = f"https://api.github.com/repos/{repo}/stargazers"
    response = requests.get(url, headers=headers)
    if response.status_code != 200: return []

    talents = []
    # 判定过去 1 小时（UTC对比）
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    
    for entry in response.json()[-30:]:
        starred_at = datetime.strptime(entry['starred_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        if starred_at > one_hour_ago:
            u_data = requests.get(entry['user']['url'], headers=headers).json()
            tags = analyze_talent(u_data, repo)
            if tags:
                talents.append({
                    "name": u_data.get('name') or u_data.get('login'),
                    "tag_str": " | ".join(tags),
                    "is_cross": "CROSS_OVER" in "".join(tags),
                    "company": u_data.get('company', '未知'),
                    "url": u_data.get('html_url')
                })
    return talents

def send_feishu(repo, talents):
    has_cross = any(t['is_cross'] for t in talents)
    template = "red" if has_cross else ("blue" if repo in MONITOR_CONFIG["ARCH"] else "purple")
    
    elements = [{"tag": "div", "text": {"tag": "lark_md", "content": f"**项目:** `{repo}`\n---"}}]
    for t in talents:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"👤 **[{t['name']}]({t['url']})**\n标签: `{t['tag_str']}`\n公司: {t['company']}"}})

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": f"{'🚨 交叉情报' if has_cross else '🎯 定向狙击'} | {repo.split('/')[-1]}"}, "template": template},
            "elements": elements
        }
    }
    requests.post(FEISHU_WEBHOOK, json=card)

if __name__ == "__main__":
    now_bj = datetime.now(SHA_TZ).strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"\n### 📡 运行记录: {now_bj} (北京时间)\n"
    found_any = False
    
    for repo in MONITOR_TARGETS:
        talents = get_recent_stars(repo)
        if talents:
            found_any = True
            send_feishu(repo, talents)
            log_entry += f"- ✅ 发现 {len(talents)} 位高质量人才于 `{repo}`\n"
    
    if not found_any: log_entry += "- 😴 本次运行未发现高价值人才异动。\n"
    
    with open("run_log.txt", "w", encoding="utf-8") as f:
        f.write(log_entry)
