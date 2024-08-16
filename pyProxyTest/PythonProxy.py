import socket

def start_server(host='0.0.0.0', port=8080):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(1)
    print(f"Listening on {host}:{port}...")

    while True:
        client_socket, client_address = server_socket.accept()
        print(f"Connection from {client_address}")

        try:
            request = client_socket.recv(1024).decode('utf-8')
            print(f"Received request: {request}")

            # Simple response
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html; charset=UTF-8\r\n\r\n"
                "<html><body><h1>Hello, World!</h1></body></html>"
            )
            client_socket.sendall(response.encode('utf-8'))

        finally:
            client_socket.close()

if __name__ == "__main__":
    start_server()
