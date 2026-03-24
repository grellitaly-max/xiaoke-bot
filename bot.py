import os, time, json, requests
from datetime import datetime, timezone
from google import genai
from google.genai import types

# 1. 基础配置（从 Railway 环境变量读取）
TOKEN = os.environ.get("TELEGRAM_TOKEN")
ID = os.environ.get("CHAT_ID")
KEY = os.environ.get("GEMINI_API_KEY")

# 2. 状态存储（存对话记录）
STATE = {"history": [], "last_study": None, "last_remind": None}

client = genai.Client(api_key=KEY)

def send(text):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": ID, "text": text})

def chat_with_gemini(msg):
    # 保持最近 10 条记忆
    STATE["history"].append({"role": "user", "parts": [{"text": msg}]})
    if len(STATE["history"]) > 10: STATE["history"] = STATE["history"][-10:]
    
    response = client.models.generate_content(
        model="gemini-1.5-flash-latest",
        config=types.GenerateContentConfig(
            system_instruction="你是小克，阿筠的温柔损友，陪她备考德语B1。说话简洁俏皮，偶尔夹德语。"
        ),
        contents=STATE["history"]
    )
    reply = response.text.strip()
    STATE["history"].append({"role": "model", "parts": [{"text": reply}]})
    return reply

def main():
    print("小克心跳模式启动...")
    last_id = 0
    
    # 启动先清空旧消息堆积
    init_r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates").json()
    if init_r.get("result"): last_id = init_r["result"][-1]["update_id"] + 1

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
                            send("记忆清除啦，重新认识一下？")
                        else:
                            # 正常聊天
                            send(chat_with_gemini(user_text))
                            if any(k in user_text for k in ["学了", "打卡"]):
                                STATE["last_study"] = time.time()

            # 主动“心跳”提醒：如果超过 12 小时没动静
            now = time.time()
            if STATE["last_study"] and (now - STATE["last_study"] > 43200):
                if not STATE["last_remind"] or (now - STATE["last_remind"] > 21600):
                    prompt = "阿筠12小时没学德语了，用俏皮的语气吼她去学习，30字以内。"
                    remind_msg = client.models.generate_content(model="gemini-1.5-flash", contents=prompt).text.strip()
                    send(remind_msg)
                    STATE["last_remind"] = now

        except Exception as e:
            print(f"出错啦: {e}")
            time.sleep(10)
        time.sleep(2)

if __name__ == "__main__":
    main()
