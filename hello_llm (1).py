import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
my_api_key=os.getenv("OPENAI_API_KEY")

if not my_api_key:
    raise ValueError("API key kaha hai bhai")

client=OpenAI(api_key=my_api_key)

model="gpt-4o-mini"
role="user"
prompt="Do you know Padho with Pratyush"
# message me role and content
message={
    "role": role,
    "content": prompt
}

messages=[message]

response=client.chat.completions.create(model=model, messages=messages)
print(response)

print("#######################################")

answer=response.choices[0].message.content
print(answer)