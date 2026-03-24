import os
import time
import json
import requests
from datetime import datetime, timezone
from google import genai
from google.genai import types

# --- 配置区 ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Railway 环境下建议放在 /tmp 目录下以确保写入权限
STATE_FILE = "/tmp/state.json"
CHECK_INTERVAL = 40  # 稍微拉长轮询间隔，减少 API 消耗
MAX_SILENT_HOURS = 12
MODEL_NAME = "gemini-1.5-flash" # 使用 1.5 版本更稳定且配额更多

SYSTEM_PROMPT = """你是阿筠的私人助手，名字叫小克。
阿筠正在备考德语B1，目标是去德国做MTA（医学检验技师）。
你的性格：俏皮、温柔、偶尔撒娇，像一个很懂她的老朋友。
你说话简洁，不说废话，不过分正经。
用中文回复，偶尔可以夹一点德语。"""

client = genai.Client(api_key=GEMINI_API_KEY)

# --- 工具函数 ---
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"last_study_time": None, "last_remind_time": None, "conversation": []}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception as e:
        print(f"保存状态失败: {e}")

def send_telegram(text):
    if not text: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)
        print(f"发送消息结果: {r.status_code}")
    except Exception as e:
        print(f"发送 Telegram 失败: {e}")

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(url, params=params, timeout=15)
        return r.json()
    except:
        return {}

def chat(conversation, user_msg):
    # 保持最近10轮对话，减少 token 消耗和限额压力
    conversation.append({"role": "user", "content": user_msg})
    if len(conversation) > 10:
        conversation = conversation[-10:]
    
    history = []
    for turn in conversation[:-1]:
        role = "user" if turn["role"] == "user" else "model"
        history.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))
    
    chat_session = client.chats.create(
        model=MODEL_NAME,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        history=history
    )
    
    response = chat_session.send_message(user_msg)
    reply = response.text.strip()
    conversation.append({"role": "model", "content": reply})
    return reply, conversation

def generate_proactive_message(hours_silent):
    prompt = f"阿筠已经 {hours_silent:.0f} 小时没有打卡德语了。用俏皮温柔的语气催她一下，不超过60字，直接输出内容。"
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return response.text.strip()

# --- 主程序 ---
def main():
    print("小克正式上线啦！")
    state = load_state()
    last_update_id = None
    last_daily_date = None

    # 跳过历史消息
    r = get_updates()
    if r.get("result"):
        for update in r["result"]:
            last_update_id = update["update_id"] + 1

    while True:
        now = datetime.now(timezone.utc)
        
        # 1. 处理用户消息
        r = get_updates(last_update_id)
        if r.get("result"):
            for update in r["result"]:
                last_update_id = update["update_id"] + 1
                msg_obj = update.get("message", {})
                msg = msg_obj.get("text", "").strip()
                
                if not msg: continue
                
                if msg == "/reset":
                    state["conversation"] = []
                    save_state(state)
                    send_telegram("好哒，咱们重新开始聊～ Alles auf Anfang!")
                    continue

                # 记录学习时间
                if any(k in msg for k in ["学完了", "学了", "done", "打卡"]):
                    state["last_study_time"] = now.isoformat()
                    save_state(state)

                try:
                    reply, state["conversation"] = chat(state.get("conversation", []), msg)
                    save_state(state)
                    send_telegram(reply)
                except Exception as e:
                    print(f"Gemini API 错误: {e}")
                    if "429" in str(e):
                        send_telegram("唔... 我话太多被系统禁言了，等一分钟再找我哦～")
                    else:
                        send_telegram("哎呀，脑子抽筋了，稍后再试试吧～")

        # 2. 每日早晨 8:00 提醒 (UTC+8 对应 UTC 0:00)
        # 注意：Railway 服务器通常是 UTC 时间
        if now.hour == 0 and last_daily_date != now.strftime("%Y-%m-%d"):
            try:
                prompt = "给阿筠写一条早上的德语学习提醒，不超过50字。Guten Morgen!"
                res = client.models.generate_content(model=MODEL_NAME, contents=prompt)
                send_telegram(res.text.strip())
                last_daily_date = now.strftime("%Y-%m-%d")
            except: pass

        # 3. 长期不学的主动催促
        if state.get("last_study_time"):
            try:
                last = datetime.fromisoformat(state["last_study_time"])
                hours_silent = (now - last).total_seconds() / 3600
                if hours_silent >= MAX_SILENT_HOURS:
                    last_remind = state.get("last_remind_time")
                    # 每 6 小时最多催一次，避免刷屏
                    if not last_remind or (now - datetime.fromisoformat(last_remind)).total_seconds() > 21600:
                        msg = generate_proactive_message(hours_silent)
                        send_telegram(msg)
                        state["last_remind_time"] = now.isoformat()
                        save_state(state)
            except Exception as e:
                print(f"提醒逻辑出错: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
