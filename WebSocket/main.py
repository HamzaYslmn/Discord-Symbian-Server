import asyncio
import json
import websockets
import ssl
from fastapi import FastAPI
import uvicorn

app = FastAPI()

ACTIVE_CONNECTIONS = 0
CLIENTS = {}

class Client:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.addr = writer.get_extra_info('peername')
        self.websocket = None
        self.supported_events = set()
        self.is_closing = False
        self.client_id = id(self)
        CLIENTS[self.client_id] = self

    async def handle_connection(self): 
        await self.send_object({
            'op': -1,
            't': 'GATEWAY_HELLO'
        })
        await self.receive_messages()

    async def receive_messages(self):
        try:
            async for message in self.reader:
                if not message:
                    break
                await self.process_message(message.decode().strip())
        except Exception as e:
            print(f"Error receiving message from {self.addr}: {e}")
        finally:
            await self.close_connection()

    async def process_message(self, message):
        try:
            data = json.loads(message)
            if data.get("op") == -1:
                await self.process_internal_message(data)
            elif self.websocket:
                await self.websocket.send(message)
        except json.JSONDecodeError as e:
            print(f"Error parsing message from {self.addr}: {e}")

    async def process_internal_message(self, data):
        if data['t'] == "GATEWAY_CONNECT":
            self.supported_events = set(data['d'].get('supported_events', []))
            await self.connect_to_gateway(data['d']['url'])
        elif data['t'] == "GATEWAY_DISCONNECT":
            await self.close_connection()
        elif data['t'] == "GATEWAY_UPDATE_SUPPORTED_EVENTS":
            self.supported_events = set(data['d']['supported_events'])

    async def connect_to_gateway(self, url):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        try:
            self.websocket = await websockets.connect(url, ssl=ssl_context)
            asyncio.create_task(self.receive_ws_messages())
        except Exception as e:
            print(f"WebSocket connection error: {e}")
            await self.close_connection()

    async def receive_ws_messages(self):
        try:
            async for message in self.websocket:
                await self.process_ws_message(message)
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            await self.close_connection()

    async def process_ws_message(self, message):
        try:
            data = json.loads(message)
            if not data.get("t") or not self.supported_events or data["t"] in self.supported_events:
                await self.send_to_client(message)
        except json.JSONDecodeError as e:
            print(f"Error parsing WebSocket message: {e}")

    async def close_connection(self):
        if self.is_closing:
            return
        self.is_closing = True
        if self.websocket:
            await self.websocket.close()
        try:
            await self.send_object({
                'op': -1,
                't': 'GATEWAY_DISCONNECT',
                'd': {'message': 'Connection closed'}
            })
        except:
            pass
        self.writer.close()
        await self.writer.wait_closed()
        if self.client_id in CLIENTS:
            del CLIENTS[self.client_id]

    async def send_to_client(self, data):
        if self.is_closing:
            return
        try:
            self.writer.write(data.encode() + b'\n')
            await self.writer.drain()
        except Exception as e:
            print(f"Error sending data to client {self.addr}: {e}")
            await self.close_connection()

    async def send_object(self, obj):
        await self.send_to_client(json.dumps(obj))

async def handle_client(reader, writer):
    client = Client(reader, writer)
    await client.handle_connection()

async def main_ws():
    server = await asyncio.start_server(
        handle_client, '0.0.0.0', 8081)

    addr = server.sockets[0].getsockname()

    async with server:
        await server.serve_forever()

@app.get("/")
async def read_root():
    return {"status": "online"}

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main_ws())
    uvicorn.run(app, host="0.0.0.0", port=8082)