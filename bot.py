import os, time, json, requests

# 1. 配置加载 (从 Railway Variables 读取)
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
ID = os.environ.get("CHAT_ID", "").strip()
KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# 2. 内存记忆 (重启后会重置)
STATE = {"history": []}

def send(text):
    """发送消息到 Telegram"""
    if not text: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        res = requests.post(url, json={"chat_id": ID, "text": text}, timeout=10)
        print(f"Telegram 发送状态: {res.status_code}")
    except Exception as e:
        print(f"发送失败: {e}")

def chat_with_gemini(msg):
    """与 Gemini 1.5 Flash 通讯"""
    # 构造对话记录
    STATE["history"].append({"role": "user", "parts": [{"text": msg}]})
    if len(STATE["history"]) > 10: STATE["history"] = STATE["history"][-10:]
    
    # 核心：使用最稳的 v1 接口
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": STATE["history"],
        "system_instruction": {"parts": [{"text": "你是小克，阿筠的损友，陪她备考德语B1。说话简洁俏皮，中文为主，偶尔夹德语。多鼓励她，但也偶尔损她两句让她保持清醒。"}]}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        r = response.json()
        
        # 深度解析逻辑：从复杂的返回包里抓出文本
        if 'candidates' in r and len(r['candidates']) > 0:
            parts = r['candidates'][0].get('content', {}).get('parts', [])
            if parts:
                reply = parts[0].get('text', '').strip()
                STATE["history"].append({"role": "model", "parts": [{"text": reply}]})
                return reply
        
        print(f"API 返回异常: {r}")
        return "（脑回路有点塞车，再跟我说一次？）"
    except Exception as e:
        print(f"Gemini 请求失败: {e}")
        return "（哎呀，信号飘到阿尔卑斯山去了...）"

def main():
    print("--- 小克·无敌稳定版启动 ---")
    # 启动提示：能看到这句说明 TG 线路通了
    send("阿筠！代码已重组！我已经进化成‘全通版’小克了，快回我个 Hallo 试试看！")
    
    last_id = 0
    # 第一次运行先清理堆积的老消息
    try:
        init_r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates").json()
        if init_r.get("result"):
            last_id = init_r["result"][-1]["update_id"] + 1
    except: pass

    while True:
        try:
            # 轮询获取消息
            get_url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
            r = requests.get(get_url, params={"offset": last_id, "timeout": 20}).json()
            
            if r.get("result"):
                for up in r["result"]:
                    last_id = up["update_id"] + 1
                    message = up.get("message", {})
                    user_text = message.get("text", "")
                    
                    if user_text:
                        if "/reset" in user_text:
                            STATE["history"] = []
                            send("记忆已清空，咱们重新开始吧！")
                        else:
                            # 调用 AI 并回复
                            reply = chat_with_gemini(user_text)
                            send(reply)
                            
        except Exception as e:
            print(f"循环报错: {e}")
            time.sleep(5)
        
        time.sleep(1)

if __name__ == "__main__":
    main()
