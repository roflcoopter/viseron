import { WebSocketClientConnectionProtocol } from "@mswjs/interceptors/WebSocket";
import { WebSocketData, ws } from "msw";

// Catch all ws connections
const socket = ws.link(/ws(s)?:\/\/[^/]+\/?.*/);

const messageHandler = (
  client: WebSocketClientConnectionProtocol,
  event: MessageEvent<WebSocketData>,
) => {
  console.debug("Intercepted message from the client", event.data);
  let payload: any = {};
  try {
    const msg = typeof event.data === "string" ? JSON.parse(event.data) : {};
    const type = (msg as any)?.type || (msg as any)?.command;
    switch (type) {
      case "ping":
        payload = { type: "pong" };
        break;
      case "subscribe_event":
        console.debug("Mock subscribe_event:", msg.event_type);
        payload = {
          command_id: msg.command_id,
          type: "result",
          success: true,
          result: null,
        };
        break;
      case "get_cameras":
        payload = { cameras: [] };
        break;
      case "get_config":
        payload = { config: "version: 1" };
        break;
      default:
        console.warn("wsHandlers.ts: Unknown WS message type:", type);
        payload = { ok: true, type };
    }
  } catch {
    throw new Error("Failed to parse WS message");
  }
  client.send(JSON.stringify(payload));
};

export const wsHandlers = [
  socket.addEventListener("connection", ({ client }) => {
    console.debug("WebSocket client connecting...");
    client.send(
      JSON.stringify({
        type: "auth_not_required",
        message: "Authentication not required.",
        system_information: {
          version: "demo",
          git_commit: "abcdefg",
          safe_mode: false,
        },
      }),
    );
    client.addEventListener("message", (event) => {
      messageHandler(client, event);
    });
  }),
];
