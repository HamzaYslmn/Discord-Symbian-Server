import asyncio
import json
import ssl
import websockets
from fastapi import FastAPI, HTTPException
import uvicorn

NEW_LINE = '\n'

# FastAPI Application
app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Welcome to the FastAPI server running on port 8080"}

@app.get("/status")
async def get_status():
    return {"status": "Server is running"}

@app.get("/wsinfo")
async def get_ws_info():
    return {"message": "WebSocket connections should be made on the appropriate protocol"}

# TCP/WebSocket Server
async def handle_connection(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"Client connected from {addr}")
    
    supported_events = []
    websocket = None

    async def send_message(data):
        print(f"Sending to client {addr}: {data}")
        writer.write(data.encode() + NEW_LINE.encode())
        await writer.drain()

    async def send_object(obj):
        await send_message(json.dumps(obj))

    async def handle_proxy_message(payload):
        nonlocal supported_events, websocket
        if payload['t'] == "GATEWAY_CONNECT":
            supported_events = payload['d'].get('supported_events', [])
            websocket = await connect_gateway(payload['d']['url'])
        elif payload['t'] == "GATEWAY_DISCONNECT":
            await handle_close()
        elif payload['t'] == "GATEWAY_UPDATE_SUPPORTED_EVENTS":
            supported_events = payload['d']['supported_events']

    async def connect_gateway(gateway_url):
        try:
            websocket = await websockets.connect(
                gateway_url, ssl=ssl.SSLContext()
            )
            asyncio.create_task(handle_websocket(websocket))
            return websocket
        except Exception as e:
            print(f"WebSocket connection error: {e}")
            await handle_close()

    async def handle_websocket(websocket):
        nonlocal supported_events
        try:
            async for message in websocket:
                json_data = json.loads(message)
                t = json_data.get("t")
                if not t or not supported_events or t in supported_events:
                    await send_message(message)
        except websockets.ConnectionClosed as e:
            print(f"WebSocket closed: {e.code} - {e.reason}")
            await handle_close()

    async def handle_message(message):
        print(f"Received from client {addr}: {message}")
        try:
            if message.split(' ')[0] in ["GET", "POST", "HEAD", "PUT", "DELETE", "OPTIONS", "PATCH"]:
                print(f"Ignoring HTTP request: {message.splitlines()[0]}")
                await send_object({
                    'op': -1,
                    't': 'GATEWAY_DISCONNECT',
                    'd': {'message': 'HTTP request detected. Please use WebSockets for this connection.'}
                })
                await handle_close()
                return
            
            parsed = json.loads(message)
            if "op" in parsed and parsed["op"] == -1:
                await handle_proxy_message(parsed)
            elif websocket:
                await websocket.send(message)
        except json.JSONDecodeError as e:
            print(f"Error parsing message: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    async def handle_close():
        if websocket:
            await websocket.close()
        await send_object({
            'op': -1,
            't': 'GATEWAY_DISCONNECT',
            'd': {'message': 'Connection closed'}
        })
        writer.close()
        await writer.wait_closed()
        print(f"Connection closed for client {addr}")

    await send_object({
        'op': -1,
        't': 'GATEWAY_HELLO'
    })

    buffer = b''
    try:
        data = await reader.read(1024)
        if data:
            buffer += data
            while NEW_LINE.encode() in buffer:
                message, buffer = buffer.split(NEW_LINE.encode(), 1)
                await handle_message(message.decode())
    except Exception as e:
        print(f"Error receiving message from {addr}: {e}")
    finally:
        await handle_close()

async def start_tcp_server(host, port):
    server = await asyncio.start_server(handle_connection, host, port)
    addr = server.sockets[0].getsockname()
    print(f'TCP server is listening on {addr}')

    async with server:
        await server.serve_forever()

async def start_fastapi_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8080)
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    # Run FastAPI server and TCP server separately
    await asyncio.gather(
        start_fastapi_server(),
        start_tcp_server('0.0.0.0', 8081)
    )

if __name__ == "__main__":
    asyncio.run(main())
