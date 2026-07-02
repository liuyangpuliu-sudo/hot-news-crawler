import requests
import random
import time

# 1. 建立 User-Agent 池，每次请求随机抽取，降低被识别为机器人的概率
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
]

def get_headers():
    """动态生成请求头"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://www.zhihu.com/'  # 知乎接口通常需要 Referer
    }

def fetch_with_retry(url, max_retries=3):
    """带有重试机制的请求方法，应对云端网络波动"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=get_headers(), timeout=15)
            response.raise_for_status()  # 如果状态码不是 200，抛出异常
            return response.json()
        except Exception as e:
            print(f"⚠️ 请求失败 (第 {attempt + 1} 次): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # 失败后等待 2 秒再重试
    return None

def fetch_weibo_hot():
    """抓取微博热搜"""
    url = "https://weibo.com/ajax/side/hotSearch"
    data = fetch_with_retry(url)
    
    print("\n🔥 ===== 微博热搜 TOP 10 =====")
    if not data or 'data' not in data:
        print("❌ 未获取到微博数据，可能接口已变更或触发反爬。")
        return
        
    for idx, item in enumerate(data['data'].get('realtime', [])[:10], 1):
        word = item.get('word', '无标题')
        num = item.get('num', 'N/A')
        print(f"{idx}. {word} (热度: {num})")

def fetch_zhihu_hot():
    """抓取知乎热榜"""
    url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"
    data = fetch_with_retry(url)
    
    print("\n💡 ===== 知乎热榜 TOP 10 =====")
    if not data or 'data' not in data:
        print("❌ 未获取到知乎数据，可能接口已变更或触发反爬。")
        return
        
    for idx, item in enumerate(data['data'][:10], 1):
        title = item.get('target', {}).get('title', '无标题')
        heat = item.get('detail_text', 'N/A')
        print(f"{idx}. {title} ({heat})")

if __name__ == "__main__":
    print("🚀 开始执行热点资讯抓取任务...")
    fetch_weibo_hot()
    time.sleep(1)  # 两个请求之间稍微停顿，模拟人类行为
    fetch_zhihu_hot()
    print("\n✅ 抓取任务执行完毕。")