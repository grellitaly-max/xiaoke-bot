import os, time, json, requests

# 1. 基础配置 - 增加默认值检查
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
ID = os.environ.get("CHAT_ID", "").strip()
KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def send(text):
    if not text: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        res = requests.post(url, json={"chat_id": ID, "text": text}, timeout=10)
        print(f"发送测试: {res.status_code} - {res.text}") # 这一行会在日志显示为什么发不出去
    except Exception as e:
        print(f"发送请求彻底失败: {e}")

def chat_with_gemini(msg):
    # 直接用最原始的 Web 请求，不依赖任何库
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={KEY}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": msg}]}],
        "system_instruction": {"parts": [{"text": "你是小克，阿筠的损友，陪她学德语B1。语气俏皮，简洁。"}]}
    }
    try:
        r = requests.post(url, json=payload, timeout=20).json()
        return r['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"Gemini 报错: {e} | 返回内容: {r if 'r' in locals() else '无'}")
        return "（脑回路断了）"

def main():
    print(f"检查环境变量: TOKEN={bool(TOKEN)}, ID={bool(ID)}, KEY={bool(KEY)}")
    print("正在尝试发送首条消息...")
    
    # 强制尝试发送
    send("阿筠！我是保命版小克。如果你看到这条，说明我们连上了！")
    
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
            r = requests.get(url, params={"offset": last_id, "timeout": 20}).json()
            if r.get("result"):
                for up in r["result"]:
                    last_id = up["update_id"] + 1
                    user_text = up.get("message", {}).get("text", "")
                    if user_text:
                        reply = chat_with_gemini(user_text)
                        send(reply)
        except Exception as e:
            print(f"轮询错误: {e}")
            time.sleep(10)
        time.sleep(2)

if __name__ == "__main__":
    main()
