import asyncio
import websockets
import json


async def test_ws():
    uri = "ws://localhost:8000/ws/voice"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Waiting for welcome message...")

            # Wait for startup message
            msg = await websocket.recv()
            print("Received:", msg)

            # Send command
            cmd = {"type": "command", "text": "Hi"}
            print(f"Sending: {cmd}")
            await websocket.send(json.dumps(cmd))

            # Read responses
            while True:
                try:
                    response = await websocket.recv()
                    # Check if response is bytes (audio) or string (json)
                    if isinstance(response, bytes):
                        print(f"Received audio chunk: {len(response)} bytes")
                    else:
                        print("Received text:", response)
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed cleanly.")
                    break
    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    asyncio.run(test_ws())
