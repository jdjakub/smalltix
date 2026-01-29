#!/usr/bin/env python3
import asyncio
import websockets

clients = set()

async def handler(websocket):
    clients.add(websocket)
    print('Client connected')
    try:
        async for message in websocket:
            for client in clients:
                if client != websocket:
                    await client.send(message)
    except websockets.exceptions.ConnectionClosed:
        pass  # Client disconnected abruptly, that's fine
    finally:
        clients.remove(websocket)
        print('Client disconnected')

async def main():
    async with websockets.serve(handler, "localhost", 4000):
        print("Server running on ws://localhost:4000")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())