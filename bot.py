Import os
import time
import json
import requests
from datetime import datetime, timezone
from google import genai
from google.genai import types

TELEGRAM_TOKEN = os.environ.get(“TELEGRAM_TOKEN”)
CHAT_ID = os.environ.get(“CHAT_ID”)
GEMINI_API_KEY = os.environ.get(“GEMINI_API_KEY”)

print(f”TELEGRAM_TOKEN 存在: {bool(TELEGRAM_TOKEN)}”)
print(f”CHAT_ID 存在: {bool(CHAT_ID)}”)
print(f”GEMINI_API_KEY 存在: {bool(GEMINI_API_KEY)}”)

STATE_FILE = “state.json”
CHECK_INTERVAL = 30
MAX_SILENT_HOURS = 12

SYSTEM_PROMPT = “”“你是阿筠的私人助手，名字叫小克。
阿筠正在备考德语B1，目标是去德国做MTA（医学检验技师）。
你的性格：俏皮、温柔、偶尔撒娇，像一个很懂她的老朋友。
你说话简洁，不说废话，不过分正经。
用中文回复，偶尔可以夹一点德语。”””

client = genai.Client(api_key=GEMINI_API_KEY)

def load_state():
if os.path.exists(STATE_FILE):
with open(STATE_FILE, “r”) as f:
return json.load(f)
return {“last_study_time”: None, “last_remind_time”: None, “conversation”: []}

def save_state(state):
with open(STATE_FILE, “w”) as f:
json.dump(state, f, ensure_ascii=False)

def send_telegram(text):
url = f”https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage”
r = requests.post(url, json={“chat_id”: CHAT_ID, “text”: text})
print(f”发送消息结果: {r.status_code} {r.text[:100]}”)

def get_updates(offset=None):
url = f”https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates”
params = {“timeout”: 5}
if offset:
params[“offset”] = offset
r = requests.get(url, params=params)
return r.json()

def chat(conversation, user_msg):
conversation.append({“role”: “user”, “content”: user_msg})
if len(conversation) > 20:
conversation = conversation[-20:]
history = []
for turn in conversation[:-1]:
role = “user” if turn[“role”] == “user” else “model”
history.append(types.Content(role=role, parts=[types.Part(text=turn[“content”])]))
chat_session = client.chats.create(
model=“gemini-2.0-flash”,
config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
history=history
)
response = chat_session.send_message(user_msg)
reply = response.text.strip()
conversation.append({“role”: “model”, “content”: reply})
return reply, conversation

def generate_proactive_message(hours_silent):
prompt = f”阿筠已经 {hours_silent:.0f} 小时没有学德语了。用俏皮温柔的语气催她一下，不超过80字，直接输出内容。”
response = client.models.generate_content(model=“gemini-2.0-flash”, contents=prompt)
return response.text.strip()

def main():
print(“小克启动了！”)
state = load_state()
last_update_id = None
last_daily_date = None

```
# 跳过所有历史消息
print("正在跳过历史消息...")
r = get_updates()
if r.get("result"):
    for update in r["result"]:
        last_update_id = update["update_id"] + 1
print(f"offset 设置为: {last_update_id}")

while True:
    now = datetime.now(timezone.utc)
    print(f"轮询中... offset={last_update_id}")

    r = get_updates(last_update_id)
    if not r.get("ok"):
        print(f"getUpdates 失败: {r}")
    elif r.get("result"):
        for update in r["result"]:
            last_update_id = update["update_id"] + 1
            msg = update.get("message", {}).get("text", "").strip()
            if not msg:
                continue
            print(f"收到消息: {msg}")
            if msg == "/reset":
                state["conversation"] = []
                save_state(state)
                send_telegram("好，咱们重新开始聊～")
            else:
                if msg in ["学完了", "学了", "done", "完成"]:
                    state["last_study_time"] = now.isoformat()
                    save_state(state)
                try:
                    reply, state["conversation"] = chat(state.get("conversation", []), msg)
                    save_state(state)
                    send_telegram(reply)
                except Exception as e:
                    print(f"Gemini 出错: {e}")
                    send_telegram("哎呀我出了点小问题，稍后再试试～")

    today_str = now.strftime("%Y-%m-%d")
    if now.hour == 1 and last_daily_date != today_str:
        try:
            prompt = "给阿筠写一条早上的德语学习提醒，温暖俏皮，不超过80字。"
            response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            send_telegram(response.text.strip())
            last_daily_date = today_str
        except Exception as e:
            print(f"日常提醒出错: {e}")

    if state.get("last_study_time"):
        try:
            last = datetime.fromisoformat(state["last_study_time"])
            hours_silent = (now - last).total_seconds() / 3600
            if hours_silent >= MAX_SILENT_HOURS:
                last_remind = state.get("last_remind_time")
                if not last_remind or (now - datetime.fromisoformat(last_remind)).total_seconds() > 10800:
                    msg = generate_proactive_message(hours_silent)
                    send_telegram(msg)
                    state["last_remind_time"] = now.isoformat()
                    save_state(state)
        except Exception as e:
            print(f"提醒出错: {e}")

    time.sleep(CHECK_INTERVAL)
```

if **name** == “**main**”:
main()
