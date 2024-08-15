import asyncio
import json
import ssl
import websockets
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse
from uvicorn import Config, Server

NEW_LINE = '\n'

# FastAPI Application
app = FastAPI()

@app.get("/")
@app.head("/")
async def read_root():
    return {"message": "Welcome to the FastAPI server running on port 8080"}

@app.get("/status")
@app.head("/status")
async def get_status():
    return {"status": "Server is running"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await handle_websocket_message(websocket, data)
    except websockets.exceptions.ConnectionClosed:
        print("WebSocket connection closed")

async def handle_websocket_message(websocket: WebSocket, message: str):
    try:
        data = json.loads(message)
        response = {"status": "received", "message": data}
        await websocket.send_json(response)
    except json.JSONDecodeError:
        await websocket.send_text("Invalid JSON")

class TCPConnection:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.addr = writer.get_extra_info('peername')
        self.supported_events = []
        self.gateway_websocket = None

    async def send_message(self, data):
        try:
            print(f"Sending to TCP client {self.addr}: {data}")
            self.writer.write(data.encode() + NEW_LINE.encode())
            await self.writer.drain()
        except ConnectionResetError:
            print(f"Connection reset while sending to {self.addr}")
        except Exception as e:
            print(f"Error sending message to {self.addr}: {e}")

    async def send_object(self, obj):
        await self.send_message(json.dumps(obj))

    async def handle_proxy_message(self, payload):
        if payload['t'] == "GATEWAY_CONNECT":
            self.supported_events = payload['d'].get('supported_events', [])
            await self.connect_gateway(payload['d']['url'])
        elif payload['t'] == "GATEWAY_DISCONNECT":
            await self.close()
        elif payload['t'] == "GATEWAY_UPDATE_SUPPORTED_EVENTS":
            self.supported_events = payload['d']['supported_events']

    async def connect_gateway(self, gateway_url):
        try:
            ssl_context = ssl.create_default_context()
            self.gateway_websocket = await websockets.connect(gateway_url, ssl=ssl_context)
            print(f"Successfully connected to gateway for {self.addr}")
            asyncio.create_task(self.handle_gateway_websocket())
        except Exception as e:
            print(f"Gateway WebSocket connection error for {self.addr}: {e}")
            await self.send_message(f"Error: Failed to connect to gateway - {str(e)}")
            self.gateway_websocket = None

    async def handle_gateway_websocket(self):
        try:
            async for message in self.gateway_websocket:
                json_data = json.loads(message)
                t = json_data.get("t")
                if not self.supported_events or not t or t in self.supported_events:
                    await self.send_message(message)
        except websockets.ConnectionClosed as e:
            print(f"Gateway WebSocket closed for {self.addr}: {e.code} - {e.reason}")
        except Exception as e:
            print(f"Error in gateway websocket handler for {self.addr}: {e}")
        finally:
            self.gateway_websocket = None
            await self.close()

    async def handle_message(self, message):
        print(f"Received message from TCP client {self.addr}: {message}")
        try:
            if message.split(' ')[0] in ["GET", "POST", "HEAD", "PUT", "DELETE", "OPTIONS", "PATCH"]:
                print(f"Ignoring HTTP request on TCP server: {message.splitlines()[0]}")
                await self.send_message("HTTP requests are not supported on this TCP server")
                return

            parsed = json.loads(message)
            if "op" in parsed and parsed["op"] == -1:
                await self.handle_proxy_message(parsed)
            elif self.gateway_websocket:
                if 'd' in parsed and isinstance(parsed['d'], dict) and 'token' in parsed['d']:
                    parsed['d']['token'] = '[REDACTED]'
                print(f"Forwarding message to gateway for {self.addr}: {json.dumps(parsed)}")
                await self.gateway_websocket.send(message)
            else:
                print(f"Gateway WebSocket is not connected for {self.addr}. Unable to forward message.")
                await self.send_message("Error: Gateway not connected")
        except json.JSONDecodeError as e:
            print(f"Error parsing TCP message from {self.addr}: {e}")
            await self.send_message("Invalid JSON")
        except Exception as e:
            print(f"Unexpected error in TCP message handling for {self.addr}: {e}")
            await self.send_message(f"Error: {str(e)}")

    async def close(self):
        if self.gateway_websocket:
            await self.gateway_websocket.close()
        try:
            await self.send_object({
                'op': -1,
                't': 'GATEWAY_DISCONNECT',
                'd': {'message': 'Connection closed'}
            })
        except Exception as e:
            print(f"Error sending disconnect message to {self.addr}: {e}")
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except Exception as e:
            print(f"Error waiting for writer to close: {e}")
        print(f"TCP connection closed for client {self.addr}")

    async def run(self):
        await self.send_object({
            'op': -1,
            't': 'GATEWAY_HELLO'
        })

        try:
            while True:
                data = await self.reader.readline()
                if not data:
                    break
                message = data.decode().strip()
                if message:
                    await self.handle_message(message)
        except ConnectionResetError:
            print(f"Connection reset by {self.addr}")
        except Exception as e:
            print(f"Error receiving message from TCP client {self.addr}: {e}")
        finally:
            await self.close()

async def handle_tcp_connection(reader, writer):
    connection = TCPConnection(reader, writer)
    await connection.run()

async def start_tcp_server(host, port):
    server = await asyncio.start_server(handle_tcp_connection, host, port)
    addr = server.sockets[0].getsockname()
    print(f'TCP server is listening on {addr}')

    async with server:
        await server.serve_forever()

async def start_fastapi_server():
    config = Config(app, host="0.0.0.0", port=8080)
    server = Server(config)
    await server.serve()

async def main():
    await asyncio.gather(
        start_fastapi_server(),
        start_tcp_server('0.0.0.0', 8081)
    )

if __name__ == "__main__":
    asyncio.run(main())