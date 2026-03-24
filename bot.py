import os, time, json, requests
from datetime import datetime, timezone
from google import genai
from google.genai import types

# 1. 基础配置
TOKEN = os.environ.get("TELEGRAM_TOKEN")
ID = os.environ.get("CHAT_ID")
KEY = os.environ.get("GEMINI_API_KEY")

# 2. 状态存储
STATE = {"history": [], "last_study": None, "last_remind": None}

client = genai.Client(api_key=KEY)

def send(text):
    if not text: return
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": ID, "text": text}, timeout=10)
    except: pass

def chat_with_gemini(msg):
    # 保持记忆
    STATE["history"].append({"role": "user", "parts": [{"text": msg}]})
    if len(STATE["history"]) > 8: STATE["history"] = STATE["history"][-8:]
    
    # 核心修复：直接使用最底层 ID
    model_id = "gemini-1.5-flash"
    
    response = client.models.generate_content(
        model=model_id, 
        config=types.GenerateContentConfig(
            system_instruction="你是小克，阿筠的私人助手，温柔、俏皮，陪她备考德语B1。简洁，中文为主，夹一点德语。"
        ),
        contents=STATE["history"]
    )
    reply = response.text.strip()
    STATE["history"].append({"role": "model", "parts": [{"text": reply}]})
    return reply

def main():
    print("小克启动测试中...")
    # 先发送一条简单的测试，确认 Telegram 通道没问题
    send("阿筠！小克现在正在尝试连接大脑，请等我回你第二句话！")
    
    last_id = 0
    while True:
        try:
            # 轮询消息
            r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id, "timeout": 20}).json()
            if r.get("result"):
                for up in r["result"]:
                    last_id = up["update_id"] + 1
                    user_text = up.get("message", {}).get("text", "")
                    if user_text:
                        if "/reset" in user_text:
                            STATE["history"] = []
                            send("记忆清除啦！")
                        else:
                            reply = chat_with_gemini(user_text)
                            send(reply)
                            if any(k in user_text for k in ["学了", "打卡", "done"]):
                                STATE["last_study"] = time.time()

            # 简单的催学逻辑
            now = time.time()
            if STATE["last_study"] and (now - STATE["last_study"] > 43200):
                if not STATE["last_remind"] or (now - STATE["last_remind"] > 21600):
                    res = client.models.generate_content(model="gemini-1.5-flash", contents="写一句俏皮的催促阿筠学德语的话，20字内")
                    send(res.text.strip())
                    STATE["last_remind"] = now

        except Exception as e:
            err_msg = str(e)
            print(f"详细错误日志: {err_msg}")
            # 如果还是找不到模型，尝试自动纠错
            if "NOT_FOUND" in err_msg:
                send("哎呀，Google的脑回路好像变了，我正在自动调整...")
                time.sleep(10)
            time.sleep(5)

if __name__ == "__main__":
    main()
