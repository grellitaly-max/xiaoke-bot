import os
import time
import json
import requests
from google import genai

# 配置
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
CHECK_INTERVAL = 3600  # 每小时检查一次
MAX_SILENT_HOURS = 12  # 超过12小时没学就催

# 状态文件
STATE_FILE = "state.json"

client = genai.Client(api_key=GEMINI_API_KEY)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_study_time": None, "last_message_time": None}

def save_state(state):
    with open(STATE_FILE​​​​​​​​​​​​​​​​
