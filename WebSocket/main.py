import asyncio
import json
import ssl
import websockets

NEW_LINE = '\n'

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
        
    async def handle_close_http():
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            print(f"Error during close: {e}")
        print(f"HTTP connection closed for client {addr}")
    
    await send_object({
        'op': -1,
        't': 'GATEWAY_HELLO'
    })

    buffer = b''
    try:    
        while not reader.at_eof():
            data = await reader.read(1024)
            
            #   TODO: Handle HTTP requests
            #if "HTTP/" in data.decode():
            #    print(f"Received HTTP request from {addr}")
            #    response = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"status": "Online"}\r\n'
            #    writer.write(response)
            #    await writer.drain()
            #    
            #    await handle_close_http()
            #    return
            
            if not data:
                break
            buffer += data
            
            while NEW_LINE.encode() in buffer:
                message, buffer = buffer.split(NEW_LINE.encode(), 1)
                await handle_message(message.decode())
    except Exception as e:
        print(f"Error receiving message from {addr}: {e}")
    finally:
        await handle_close()

async def start_server(host, port):
    server = await asyncio.start_server(handle_connection, host, port)
    addr = server.sockets[0].getsockname()
    print(f'TCP server is listening on {addr}')

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    HOST = '0.0.0.0'
    PORT = 8081
    asyncio.run(start_server(HOST, PORT))
