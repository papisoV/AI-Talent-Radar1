import os
import requests
from datetime import datetime, timedelta

# --- 狙击目标配置 (支持领域打标) ---
MONITOR_CONFIG = {
    "ARCH": ["vllm-project/vllm", "tikv/tikv", "pytorch/pytorch", "deepseek-ai/DeepSeek-V3", "NVIDIA/FasterTransformer"],
    "WEB3": ["paradigmxyz/reth", "succinctlabs/sp1", "ethereum/consensus-specs", "solana-labs/solana"]
}
MONITOR_TARGETS = [repo for repos in MONITOR_CONFIG.values() for repo in repos]

# --- 猎头权重配置 ---
LOCATION_FOCUS = ["Beijing", "Shanghai", "Shenzhen", "Hangzhou", "China", "北京", "上海", "深圳", "杭州"]
KEY_TAGS = ["Expert", "Lead", "Staff", "PhD", "Principal", "Architect", "Kernel", "Infra"]
TARGET_COMPANIES = ["DeepSeek", "OpenAI", "Google", "Meta", "ByteDance", "Tencent", "Alibaba", "Binance", "Paradigm"]

GH_TOKEN = os.getenv("GH_TOKEN")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3.star+json"}

def analyze_talent(u_data, repo):
    """深度画像识别：判定是否为交叉人才"""
    bio = (u_data.get('bio') or "").lower()
    company = (u_data.get('company') or "").lower()
    loc = (u_data.get('location') or "").lower()
    
    tags = []
    # 基础维度筛选
    is_arch_expert = any(k.lower() in bio or k.lower() in company for k in ["kernel", "distributed", "cuda", "infra", "architect"])
    
    # 交叉狙击判定：底层大牛出现在 Web3 项目中
    if repo in MONITOR_CONFIG["WEB3"] and is_arch_expert:
        tags.append("🔥 CROSS_OVER (架构师看Web3)")
    
    if any(c.lower() in loc for c in LOCATION_FOCUS): tags.append("📍 目标地区")
    if any(com.lower() in company or com.lower() in bio for com in TARGET_COMPANIES): tags.append("🏢 顶尖背景")
    if u_data.get('followers', 0) > 100: tags.append("🌟 KOL")
    
    return tags

def get_recent_stars(repo):
    url = f"https://api.github.com/repos/{repo}/stargazers"
    response = requests.get(url, headers=headers)
    if response.status_code != 200: return []

    talents = []
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    for entry in response.json()[-30:]:
        starred_at = datetime.strptime(entry['starred_at'], '%Y-%m-%dT%H:%M:%SZ')
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
    """大杂烩推送：根据交叉属性动态变色"""
    has_cross = any(t['is_cross'] for t in talents)
    # 交叉情报用红色(red)，架构用蓝色(blue)，Web3用紫色(purple)
    template = "red" if has_cross else ("blue" if repo in MONITOR_CONFIG["ARCH"] else "purple")
    
    elements = [{"tag": "div", "text": {"tag": "lark_md", "content": f"**项目:** `{repo}`\n---"}}]
    for t in talents:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"👤 **[{t['name']}]({t['url']})**\n`{t['tag_str']}`\n🏢 {t['company']}"}})

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": f"{'🚨 交叉情报' if has_cross else '🎯 定向狙击'} | {repo.split('/')[-1]}"}, "template": template},
            "elements": elements
        }
    }
    requests.post(FEISHU_WEBHOOK, json=card)

if __name__ == "__main__":
    log_entry = f"\n### Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    found_any = False
    
    for repo in MONITOR_TARGETS:
        talents = get_recent_stars(repo)
        if talents:
            found_any = True
            send_feishu(repo, talents)
            log_entry += f"- ✅ Found {len(talents)} talents in `{repo}`\n"
    
    if not found_any: log_entry += "- 😴 No high-value movements detected.\n"
    
    # 将结果写入临时文件给 GitHub Actions 使用
    with open("run_log.txt", "w") as f: f.write(log_entry)
