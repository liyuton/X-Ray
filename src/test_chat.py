import requests
from elasticsearch import Elasticsearch
from readgml import readgml
import os
import json
import math

# 调用API补全对话
def completion(user_prompt):
    dialogue = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_prompt},
    ]
    sjtu_temp = 'sk-o2ndZu1j0iWAg7LnJtsUzB957Zklec6mXnFDnDpA3gpOiSrt'

    response = requests.post(
        url='https://openai.acemap.cn/v1/chat/completions',
        headers={'Authorization': f'Bearer {sjtu_temp}'},
        json={'model': 'gpt-5-mini', 'messages': dialogue},
        # json={'model': 'deepseek-reasoner', 'messages': dialogue},
        verify=False,
        timeout=600
    )
    return response.json()['choices'][0]['message']['content']

res = completion("hello")
print(res)