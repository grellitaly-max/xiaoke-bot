import os
import time
import json
import requests
import google.generativeai as genai
from datetime import datetime, timezone

# 配置
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
CHECK_INTERVAL = 3600  # 每小时检查一次
MAX_SILENT_HOURS = 12  # 超过12小时没学就催

# 状态文件
STATE_FILE = "state.json"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_study_time": None, "last_message_time": None}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text})

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if offset:
        params["offset"] = offset
    r = requests.get(url, params=params)
    return r.json()

def generate_message(hours_silent):
    prompt = f"""你是阿筠的德语学习提醒助手，名字叫小克。
阿筠已经 {hours_silent:.0f} 小时没有学德语了。
请用中文写一条催她学习的消息，语气可以俏皮、温柔、或者稍微有点撒娇，不要太严肃。
不超过100字。直接输出消息内容，不要加任何前缀。"""
    response = model.generate_content(prompt)
    return response.text.strip()

def generate_daily_message():
    prompt = """你是阿筠的德语学习提醒助手，名字叫小克。
请用中文写一条早上的德语学习提醒，语气温暖有趣，可以加一句简单的德语鼓励。
不超过100字。直接输出消息内容，不要加任何前缀。"""
    response = model.generate_content(prompt)
    return response.text.strip()

def main():
    print("小克启动了！")
    state = load_state()
    last_update_id = None
    last_daily_date = None

    while True:
        now = datetime.now(timezone.utc)

        # 检查用户回复
        updates = get_updates(last_update_id)
        if updates.get("result"):
            for update in updates["result"]:
                last_update_id = update["update_id"] + 1
                msg = update.get("message", {}).get("text", "").strip()
                if msg in ["学完了", "学了", "done", "完成"]:
                    state["last_study_time"] = now.isoformat()
                    save_state(state)
                    send_telegram("好棒！记录下来了～继续加油 💪")

        # 每天早上9点（UTC+8就是1:00 UTC）发日常提醒
        today_str = now.strftime("%Y-%m-%d")
        if now.hour == 1 and last_daily_date != today_str:
            msg = generate_daily_message()
            send_telegram(msg)
            last_daily_date = today_str

        # 检查是否超过12小时没学
        if state["last_study_time"]:
            last = datetime.fromisoformat(state["last_study_time"])
            hours_silent = (now - last).total_seconds() / 3600
            if hours_silent >= MAX_SILENT_HOURS:
                last_msg = state.get("last_message_time")
                if not last_msg or (now - datetime.fromisoformat(last_msg)).total_seconds() > 3600 * 3:
                    msg = generate_message(hours_silent)
                    send_telegram(msg)
                    state["last_message_time"] = now.isoformat()
                    save_state(state)

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
