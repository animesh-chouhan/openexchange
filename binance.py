import websocket, json
import logging

logger = logging.getLogger(__name__)


def on_message(ws, msg):
    data = json.loads(msg)
    logger.debug("received binance message keys: %s", list(data.keys()))
    event_type = data["e"]
    event_time = data["E"]
    symbol = data["s"]


base_url = "wss://stream.binance.com:9443/ws"

ws = websocket.WebSocketApp(f"{base_url}/btcusdt@depth", on_message=on_message)
ws.run_forever()
