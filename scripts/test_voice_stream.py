"""Testing script for the websocket voice stream endpoint."""


import argparse
import asyncio
import base64
import json
from pathlib import Path

import websockets

audio_chunk_count = 0

def chunk_bytes(data: bytes, chunk_size: int = 3200):
    """
    3200 bytes ~= 100ms of PCM 16kHz mono 16-bit audio.
    """
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


async def receiver(ws, interrupt_after_assistant_text: float | None = None):
    interrupted = False
    audio_chunk_count = 0

    while True:
        try:
            raw = await ws.recv()
        except websockets.ConnectionClosed:
            print("[receiver] connection closed")
            break

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            print("[receiver] non-json message:", raw)
            continue

        msg_type = msg.get("type")

        if (
            msg_type == "assistant_text"
            and interrupt_after_assistant_text is not None
            and not interrupted
        ):
            interrupted = True

            async def delayed_interrupt():
                await asyncio.sleep(interrupt_after_assistant_text)
                print(f"[send] interrupt {interrupt_after_assistant_text}s after assistant_text")
                await ws.send(json.dumps({"type": "interrupt"}))

            asyncio.create_task(delayed_interrupt())

        if msg_type == "assistant_audio_chunk":
            audio_chunk_count += 1

            if audio_chunk_count % 10 == 0:
                print(
                    f"[recv] assistant_audio_chunk count={audio_chunk_count} "
                    f"turn_id={msg.get('turn_id')}"
                )

            continue

        print("[recv]", json.dumps(msg, ensure_ascii=False, indent=2))
async def send_audio(ws, audio_path: Path, chunk_size: int, delay: float):
    data = audio_path.read_bytes()

    print(f"[send] audio file: {audio_path}")
    print(f"[send] bytes: {len(data)}")
    print(f"[send] chunk_size: {chunk_size}")
    print(f"[send] delay: {delay}s")

    for chunk in chunk_bytes(data, chunk_size=chunk_size):
        await ws.send(
            json.dumps(
                {
                    "type": "audio_chunk",
                    "audio_base64": base64.b64encode(chunk).decode("utf-8"),
                }
            )
        )
        await asyncio.sleep(delay)

    print("[send] commit")
    await ws.send(json.dumps({"type": "commit"}))


async def interrupt_after(ws, seconds: float):
    await asyncio.sleep(seconds)
    print(f"[send] interrupt after {seconds}s")
    await ws.send(json.dumps({"type": "interrupt"}))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://localhost:8000/chat/voice-stream")
    parser.add_argument("--voice-id", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--language-code", default="spa")
    parser.add_argument("--chunk-size", type=int, default=3200)
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--interrupt-after", type=float, default=None)
    parser.add_argument("--listen-seconds", type=float, default=30)

    args = parser.parse_args()

    audio_path = Path(args.audio)

    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    url = (
        f"{args.url}"
        f"?voice_id={args.voice_id}"
        f"&namespace={args.namespace}"
        f"&language_code={args.language_code}"
    )

    print("[connect]", url)

    async with websockets.connect(url, max_size=20 * 1024 * 1024) as ws:
        receiver_task = asyncio.create_task(
            receiver(
                ws,
                interrupt_after_assistant_text=args.interrupt_after,
            )
        )

        await send_audio(
            ws=ws,
            audio_path=audio_path,
            chunk_size=args.chunk_size,
            delay=args.delay,
        )

        # interrupt_task = None
        # if args.interrupt_after is not None:
        #     interrupt_task = asyncio.create_task(
        #         interrupt_after(ws, args.interrupt_after)
        #     )

        await asyncio.sleep(args.listen_seconds)

        print("[send] close")
        await ws.send(json.dumps({"type": "close"}))

        # if interrupt_task:
        #     interrupt_task.cancel()

        receiver_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())