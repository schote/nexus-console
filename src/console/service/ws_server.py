import websocket

def on_message(ws, message):
    print(message)

ws = websocket.WebSocket("ws://localhost:8765", on_message=on_message)
ws.run_forever()