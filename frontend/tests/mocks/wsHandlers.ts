import { WebSocketData, WebSocketHandlerConnection, ws } from "msw";
import { DEFAULT_YAML_CONFIG, MOCK_ENTITIES } from "tests/utils/const";

// Catch all ws connections
const socket = ws.link(/ws(s)?:\/\/[^/]+\/?.*/);

// Controls what the mocked `get_setup_status` command responds with. Defaults
// to no errors.
// Tests can override by setting `setupStatusMock.components`
export const setupStatusMock: { components: unknown[] } = {
  components: [],
};

export const resetSetupStatusMock = () => {
  setupStatusMock.components = [];
};

const RENDER_STEPS = 10;
const RENDER_STEP_INTERVAL = 300;
const renderTimers = new Map<string, ReturnType<typeof setInterval>>();

// Streams the status of a timelapse render the way the server does
const simulateRender = (
  client: WebSocketHandlerConnection["client"],
  commandId: number,
) => {
  const key = `${client.id}-${commandId}`;
  const status = (result: object) =>
    client.send(
      JSON.stringify({
        command_id: commandId,
        type: "subscription_result",
        success: true,
        result,
      }),
    );
  let step = 0;
  renderTimers.set(
    key,
    setInterval(() => {
      step++;
      if (step <= RENDER_STEPS) {
        status({
          status: "rendering",
          frame: step * 100,
          total_frames: RENDER_STEPS * 100,
          progress: (step / RENDER_STEPS) * 100,
        });
        return;
      }
      if (step === RENDER_STEPS + 1) {
        status({ status: "encoding" });
        return;
      }
      clearInterval(renderTimers.get(key));
      renderTimers.delete(key);
      status({
        status: "done",
        filename: "demo_timelapse.mp4",
        token: "demo-token",
      });
      client.send(
        JSON.stringify({ command_id: commandId, type: "cancel_subscription" }),
      );
    }, RENDER_STEP_INTERVAL),
  );
};

const cancelRender = (
  client: WebSocketHandlerConnection["client"],
  commandId: number,
) => {
  const key = `${client.id}-${commandId}`;
  clearInterval(renderTimers.get(key));
  renderTimers.delete(key);
};

const messageHandler = (
  client: WebSocketHandlerConnection["client"],
  event: MessageEvent<WebSocketData>,
) => {
  console.debug("Intercepted message from the client", event.data);
  let payload: any = {};
  try {
    const msg = typeof event.data === "string" ? JSON.parse(event.data) : {};
    const type = (msg as any)?.type || (msg as any)?.command;
    switch (type) {
      case "ping":
        payload = { command_id: msg.command_id, type: "pong" };
        break;
      case "auth":
        payload = {
          type: "auth_ok",
          message: "Authenticated.",
          system_information: {
            version: "demo",
            git_commit: "abcdefg",
            safe_mode: false,
          },
        };
        break;
      case "unsubscribe_event":
        cancelRender(client, msg.subscription);
        payload = {
          command_id: msg.command_id,
          type: "result",
          success: true,
          result: null,
        };
        break;
      case "subscribe_event":
      case "subscribe_states":
      case "subscribe_timespans":
      case "unsubscribe_states":
      case "unsubscribe_timespans":
      case "save_config":
      case "reload_config":
      case "restart_viseron":
        payload = {
          command_id: msg.command_id,
          type: "result",
          success: true,
          result: null,
        };
        break;
      case "get_cameras":
        payload = {
          command_id: msg.command_id,
          type: "result",
          success: true,
          result: { cameras: {} },
        };
        break;
      case "get_entities":
        payload = {
          command_id: msg.command_id,
          type: "result",
          success: true,
          result: MOCK_ENTITIES,
        };
        break;
      case "get_setup_status":
        console.debug("Mock get_setup_status");
        payload = {
          command_id: msg.command_id,
          type: "result",
          success: true,
          result: {
            components: setupStatusMock.components,
          },
        };
        break;
      case "get_config":
        payload = {
          command_id: msg.command_id,
          type: "result",
          success: true,
          result: { config: DEFAULT_YAML_CONFIG },
        };
        break;
      case "render_template":
        payload = {
          command_id: msg.command_id,
          type: "result",
          success: true,
          result: { rendered: msg.template },
        };
        break;
      case "export_recording":
      case "export_snapshot":
      case "export_timespan":
        payload = {
          command_id: msg.command_id,
          type: "result",
          success: true,
          result: { filename: "demo_export.mp4", token: "demo-token" },
        };
        break;
      case "render_timelapse":
        payload = {
          command_id: msg.command_id,
          type: "result",
          success: true,
          result: null,
        };
        simulateRender(client, msg.command_id);
        break;
      // A missing envelope leaves the client's promise pending forever, so
      // unmocked commands still get a valid result.
      default:
        console.warn("wsHandlers.ts: Unknown WS message type:", type);
        payload = {
          command_id: msg.command_id,
          type: "result",
          success: true,
          result: null,
        };
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
