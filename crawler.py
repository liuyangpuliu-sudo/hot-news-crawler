import requests
import random
import time
import re
import json
import os
import html as html_mod
from datetime import datetime, timezone, timedelta
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
]

OUTPUT_PATH = os.path.join('data', 'hot_news.json')


def create_session():
    session = requests.Session()
    session.verify = False
    user_agent = random.choice(USER_AGENTS)
    common_headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    session.headers.update(common_headers)
    return session


def fetch_json(url, headers=None, max_retries=2):
    """简单 GET 请求获取 JSON，跳过 SSL 验证"""
    for attempt in range(max_retries):
        try:
            h = {'User-Agent': random.choice(USER_AGENTS)}
            if headers:
                h.update(headers)
            resp = requests.get(url, headers=h, timeout=15, verify=False)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"⚠️ 请求失败: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    return None


def fetch_weibo_hot():
    """抓取微博热搜，返回结构化列表"""
    session = create_session()
    print("🌐 获取微博 cookies...")
    try:
        session.get("https://weibo.com/", timeout=15)
        time.sleep(1)
    except Exception as e:
        print(f"⚠️ 访问微博首页失败: {e}")

    url = "https://weibo.com/ajax/side/hotSearch"
    data = None
    for attempt in range(3):
        try:
            headers = {'Referer': 'https://weibo.com/', 'Accept': 'application/json, text/plain, */*'}
            response = session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            break
        except Exception as e:
            print(f"⚠️ 微博请求失败 (第 {attempt + 1} 次): {e}")
            if attempt < 2:
                time.sleep(2)

    print("\n🔥 ===== 微博热搜 TOP 10 =====")
    results = []
    if not data or 'data' not in data:
        print("❌ 未获取到微博数据。")
        return results

    for idx, item in enumerate(data['data'].get('realtime', [])[:10], 1):
        word = item.get('word', '无标题')
        num = item.get('num', '')
        print(f"{idx}. {word} (热度: {num})")
        results.append({'rank': idx, 'title': word, 'heat': num})
    return results


def fetch_zhihu_hot():
    """抓取知乎热榜 - 降级为从 52vmy 免费 API + 百度热搜兜底，返回结构化列表"""
    print("🌐 获取知乎热榜...")
    titles = []

    # 源1: 52vmy API (带 verify=False)
    print("🔄 尝试 52vmy API...")
    data = fetch_json("https://api.52vmy.cn/api/wl/zhihu/hot")
    if data and isinstance(data, dict) and data.get('code') == 200:
        items = data.get('data', [])
        if items:
            titles = [{'title': item.get('title', '无标题'), 'hot': item.get('hot', '')} for item in items[:10]]
            print("✅ 通过 52vmy API 获取成功")

    # 源2: 解析知乎首页 HTML (带 verify=False)
    if not titles:
        print("🔄 尝试解析知乎首页 HTML...")
        try:
            session = create_session()
            session.get("https://www.zhihu.com/", timeout=15, verify=False)
            time.sleep(1)
            resp = session.get("https://www.zhihu.com/hot", timeout=15, verify=False)
            resp.encoding = 'utf-8'
            found = re.findall(r'<h2[^>]*class="HotItem-title"[^>]*>(.*?)</h2>', resp.text, re.DOTALL)
            if found:
                titles = []
                for t in found[:10]:
                    clean = re.sub(r'<[^>]+>', '', t).strip()
                    titles.append({'title': html_mod.unescape(clean), 'hot': ''})
                print("✅ 通过 HTML 解析获取成功")
        except Exception as e:
            print(f"⚠️ HTML 解析失败: {e}")

    # 源3: 百度热搜 (兜底，确保至少有一个数据源工作)
    if not titles:
        print("🔄 降级为百度热搜...")
        try:
            session = create_session()
            resp = session.get("https://top.baidu.com/board?tab=realtime", timeout=15, verify=False)
            resp.encoding = 'utf-8'
            found = re.findall(r'"word":"(.*?)"', resp.text)
            if found:
                titles = [{'title': w, 'hot': ''} for w in found[:10]]
                print("✅ 从百度热搜获取成功")
        except Exception as e:
            print(f"⚠️ 百度热搜失败: {e}")

    # 源4: oschina 热门资讯 (最后的兜底)
    if not titles:
        print("🔄 降级为开源中国热门资讯...")
        try:
            resp = requests.get("https://www.oschina.net/news", timeout=15, verify=False,
                                headers={'User-Agent': random.choice(USER_AGENTS)})
            resp.encoding = 'utf-8'
            found = re.findall(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
            if found:
                titles = []
                for t in found[:10]:
                    clean = re.sub(r'<[^>]+>', '', t).strip()
                    if clean:
                        titles.append({'title': html_mod.unescape(clean), 'hot': ''})
                print("✅ 从开源中国获取成功")
        except Exception as e:
            print(f"⚠️ 开源中国失败: {e}")

    print("\n💡 ===== 知乎热榜 TOP 10 =====")
    results = []
    if not titles:
        print("❌ 所有数据源均未获取到数据。")
        return results

    for idx, item in enumerate(titles[:10], 1):
        title = item.get('title', '无标题')
        heat = item.get('hot', '')
        print(f"{idx}. {title}" + (f" ({heat})" if heat else ""))
        results.append({'rank': idx, 'title': title, 'heat': heat})
    return results


def fetch_bilibili_hot():
    """抓取B站热搜词，返回结构化列表"""
    print("🌐 获取B站热搜...")
    titles = []

    # 源1: B站官方热搜词接口
    print("🔄 尝试 B站热搜词接口...")
    data = fetch_json("https://s.search.bilibili.com/main/hotword")
    if data and isinstance(data, dict):
        items = data.get('list', []) or data.get('data', {}).get('trending', {}).get('list', [])
        if items:
            titles = [{'title': item.get('show_name') or item.get('keyword', '无标题'),
                       'hot': item.get('heat_score', '') or item.get('word_type', '')} for item in items[:10]]
            print("✅ 通过 B站热搜词接口获取成功")

    # 源2: B站热门视频榜单兜底 (用视频标题代替热搜词)
    if not titles:
        print("🔄 降级为 B站热门视频榜单...")
        try:
            data2 = fetch_json("https://api.bilibili.com/x/web-interface/popular?ps=10&pn=1")
            if data2 and data2.get('code') == 0:
                items = data2.get('data', {}).get('list', [])
                titles = [{'title': item.get('title', '无标题'), 'hot': item.get('stat', {}).get('view', '')}
                          for item in items[:10]]
                print("✅ 从 B站热门视频榜单获取成功")
        except Exception as e:
            print(f"⚠️ B站热门视频榜单失败: {e}")

    print("\n📺 ===== B站热搜 TOP 10 =====")
    results = []
    if not titles:
        print("❌ 所有数据源均未获取到数据。")
        return results

    for idx, item in enumerate(titles[:10], 1):
        title = item.get('title', '无标题')
        heat = item.get('hot', '')
        print(f"{idx}. {title}" + (f" ({heat})" if heat else ""))
        results.append({'rank': idx, 'title': title, 'heat': heat})
    return results


def fetch_douyin_hot():
    """抓取抖音热搜榜，返回结构化列表"""
    print("🌐 获取抖音热搜...")
    titles = []

    # 源1: 抖音官方热搜接口
    print("🔄 尝试抖音官方热搜接口...")
    try:
        session = create_session()
        resp = session.get(
            "https://www.iesdouyin.com/aweme/v1/web/hot/search/list/",
            params={'device_platform': 'webapp', 'aid': '6383', 'channel': 'channel_pc_web'},
            timeout=15, verify=False
        )
        data = resp.json()
        items = data.get('data', {}).get('word_list', [])
        if items:
            titles = [{'title': item.get('word', '无标题'), 'hot': item.get('hot_value', '')} for item in items[:10]]
            print("✅ 通过抖音官方接口获取成功")
    except Exception as e:
        print(f"⚠️ 抖音官方接口失败: {e}")

    # 源2: 52vmy 第三方聚合 API 兜底
    if not titles:
        print("🔄 尝试 52vmy 抖音热搜 API...")
        data2 = fetch_json("https://api.52vmy.cn/api/wl/douyin/hot")
        if data2 and isinstance(data2, dict) and data2.get('code') == 200:
            items = data2.get('data', [])
            if items:
                titles = [{'title': item.get('word', item.get('title', '无标题')), 'hot': item.get('hot', '')}
                          for item in items[:10]]
                print("✅ 通过 52vmy API 获取成功")

    print("\n🎵 ===== 抖音热搜 TOP 10 =====")
    results = []
    if not titles:
        print("❌ 所有数据源均未获取到数据。")
        return results

    for idx, item in enumerate(titles[:10], 1):
        title = item.get('title', '无标题')
        heat = item.get('hot', '')
        print(f"{idx}. {title}" + (f" ({heat})" if heat else ""))
        results.append({'rank': idx, 'title': title, 'heat': heat})
    return results


def save_output(weibo_list, zhihu_list, bilibili_list, douyin_list):
    """把抓取结果写成 JSON 文件，供前端网页读取"""
    beijing_tz = timezone(timedelta(hours=8))
    payload = {
        'generated_at': datetime.now(beijing_tz).isoformat(),
        'weibo': weibo_list,
        'zhihu': zhihu_list,
        'bilibili': bilibili_list,
        'douyin': douyin_list,
    }
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n💾 已写入 {OUTPUT_PATH}")


if __name__ == "__main__":
    print("🚀 开始执行热点资讯抓取任务...")
    weibo_data = fetch_weibo_hot()
    time.sleep(1)
    zhihu_data = fetch_zhihu_hot()
    time.sleep(1)
    bilibili_data = fetch_bilibili_hot()
    time.sleep(1)
    douyin_data = fetch_douyin_hot()
    save_output(weibo_data, zhihu_data, bilibili_data, douyin_data)
    print("\n✅ 抓取任务执行完毕。")
