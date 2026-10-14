import configparser
from pathlib import Path
from openai import OpenAI

config = configparser.ConfigParser()
config.read(Path(__file__).with_name("config.ini"), encoding="utf-8")
llm = config["llm"]

client = OpenAI(base_url=llm["base_url"], api_key=llm["api_key"])

messages = []

print("输入提示词开始对话，按 Ctrl+C 退出。")
while True:
    try:
        prompt = input("\n你: ")
    except EOFError:
        break

    messages.append({"role": "user", "content":prompt})

    stream = client.chat.completions.create(
        model=llm["model"],
        messages=messages,
        stream=True,
    )
    print("AI: ", end="", flush=True)
    full_reply = ""
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            print(delta.content, end="", flush=True)
            full_reply += delta.content
    print()
    messages.append({"role": "assistant", "content": full_reply})