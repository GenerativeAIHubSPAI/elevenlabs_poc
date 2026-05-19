from app.core.config import LLM_PROVIDER
from app.services.kb import kb_search


def _build_user_content(question: str, context_chunks: list[dict]) -> str:
    context_text = "\n\n".join(
        [f"[{i+1}] {c['title']}\n{c['text']}" for i, c in enumerate(context_chunks)]
    ).strip()

    base = f"Question:\n{question}"
    if context_text:
        base += (
            f"\n\nKnowledge base context:\n{context_text}\n\n"
            "Answer clearly. Use the context when possible. "
            "If the context does not fully support the answer, say so."
        )
    return base


async def llm_answer(system_prompt: str, question: str, context_chunks: list[dict]) -> str:
    user_content = _build_user_content(question, context_chunks)

    if LLM_PROVIDER == "bedrock":
        from app.clients import bedrock
        return await bedrock.call(system_prompt, user_content)

    from app.clients import openai
    return await openai.call(system_prompt, user_content)
