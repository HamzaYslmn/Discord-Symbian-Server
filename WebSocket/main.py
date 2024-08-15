import socket
import threading
import json
import websocket
import ssl

NEW_LINE = '\n'

class Client:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.websocket = None
        self.supported_events = []
        self.is_closing = False

    def create_message_receiver(self):
        buffer = b''
        while not self.is_closing:
            try:
                data = self.conn.recv(1024)
                if not data:
                    print(f"Client {self.addr} disconnected.")
                    break
                buffer += data
                while NEW_LINE.encode() in buffer:
                    message, buffer = buffer.split(NEW_LINE.encode(), 1)
                    self.handle_message(message.decode())
            except Exception as e:
                print(f"Error receiving message from {self.addr}: {e}")
                break
        self.handle_close()

    def handle_connection(self):
        print(f"Client connected from {self.addr}")
        self.send_object({
            'op': -1,
            't': 'GATEWAY_HELLO'
        })
        self.create_message_receiver()

    def handle_message(self, message):
        print(f"Received from client {self.addr}: {message}")
        try:
            parsed = json.loads(message)
            if "op" in parsed and parsed["op"] == -1:
                self.handle_proxy_message(parsed)
            elif self.websocket:
                self.websocket.send(message)
        except json.JSONDecodeError as e:
            print(f"Error parsing message: {e}")

    def handle_proxy_message(self, payload):
        if payload['t'] == "GATEWAY_CONNECT":
            self.supported_events = payload['d'].get('supported_events', [])
            self.connect_gateway(payload['d']['url'])
        elif payload['t'] == "GATEWAY_DISCONNECT":
            self.handle_close()
        elif payload['t'] == "GATEWAY_UPDATE_SUPPORTED_EVENTS":
            self.supported_events = payload['d']['supported_events']

    def connect_gateway(self, gateway_url):
        try:
            self.websocket = websocket.WebSocketApp(
                gateway_url,
                on_message=self.on_ws_message,
                on_error=self.on_ws_error,
                on_close=self.on_ws_close
            )
            wst = threading.Thread(target=self.websocket.run_forever, kwargs={'sslopt': {"cert_reqs": ssl.CERT_NONE}})
            wst.daemon = True
            wst.start()
        except Exception as e:
            print(f"WebSocket connection error: {e}")
            self.handle_close()

    def on_ws_message(self, ws, message):
        try:
            json_data = json.loads(message)
            t = json_data.get("t")
            if not t or not self.supported_events or t in self.supported_events:
                self.send_message(message)
        except json.JSONDecodeError as e:
            print(f"Error parsing WebSocket message: {e}")

    def on_ws_error(self, ws, error):
        print(f"WebSocket error: {error}")
        self.handle_close()

    def on_ws_close(self, ws, close_status_code, close_msg):
        print(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.handle_close()

    def handle_close(self):
        if self.is_closing:
            return
        self.is_closing = True
        if self.websocket:
            self.websocket.close()
        try:
            self.send_object({
                'op': -1,
                't': 'GATEWAY_DISCONNECT',
                'd': {'message': 'Connection closed'}
            })
        except:
            pass  # If we can't send the disconnect message, just continue closing
        self.conn.close()
        print(f"Connection closed for client {self.addr}")

    def send_message(self, data):
        if self.is_closing:
            return
        print(f"Sending to client {self.addr}: {data}")
        try:
            self.conn.sendall(data.encode() + NEW_LINE.encode())
        except Exception as e:
            print(f"Error sending data to client {self.addr}: {e}")
            self.handle_close()

    def send_object(self, obj):
        self.send_message(json.dumps(obj))

def start_server(host, port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"TCP server is listening on {host}:{port}")

    try:
        while True:
            conn, addr = server_socket.accept()
            client = Client(conn, addr)
            client_thread = threading.Thread(target=client.handle_connection)
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print("Server shutting down...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    HOST = '0.0.0.0'  # Listen on all available interfaces
    PORT = 8081
    start_server(HOST, PORT)