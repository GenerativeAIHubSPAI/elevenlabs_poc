import os

import boto3
from fastapi import HTTPException

from app.core.config import AWS_BEARER_TOKEN_BEDROCK, AWS_REGION, BEDROCK_MODEL_ID


def _get_client():
    if AWS_BEARER_TOKEN_BEDROCK:
        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = AWS_BEARER_TOKEN_BEDROCK
    return boto3.client(service_name="bedrock-runtime", region_name=AWS_REGION)


async def call(system_prompt: str, user_content: str) -> str:
    client = _get_client()

    messages = [
        {
            "role": "user",
            "content": [{"text": user_content}],
        }
    ]

    try:
        response = client.converse(
            modelId=BEDROCK_MODEL_ID,
            messages=messages,
            system=[{"text": system_prompt}],
            inferenceConfig={"maxTokens": 10},
        )
        return response["output"]["message"]["content"][0]["text"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bedrock error: {e}")
