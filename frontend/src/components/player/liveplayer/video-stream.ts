import { VideoRTC } from "./video-rtc.js";

const STATUS_LOADING = "Loading";

/**
 * Based on the example from https://github.com/AlexxIT/go2rtc/tree/master/www
 */
class VideoStream extends VideoRTC {
  set status(value: string) {
    this.dispatchEvent(new CustomEvent("status", { detail: { value } }));
  }

  set localError(value: string) {
    if (this.state !== STATUS_LOADING) return;
    this.dispatchEvent(new CustomEvent("error", { detail: { value } }));
  }

  set controls(value: boolean) {
    if (this.video) {
      this.video.controls = value;
    }
  }

  oninit(): void {
    console.debug("stream.oninit");
    super.oninit();
    this.dispatchEvent(new CustomEvent("init"));
  }

  onconnect(): any {
    console.debug("stream.onconnect");
    const result = super.onconnect();
    if (result) this.status = STATUS_LOADING;
    this.dispatchEvent(new CustomEvent("connect"));
    return result;
  }

  ondisconnect(): void {
    console.debug("stream.ondisconnect");
    super.ondisconnect();
    this.dispatchEvent(new CustomEvent("disconnect"));
  }

  onopen(): any {
    console.debug("stream.onopen");
    const result = super.onopen();

    this.onmessage.stream = (msg: { type: string; value: string }) => {
      console.debug("stream.onmessge", msg);
      switch (msg.type) {
        case "error":
          this.localError = msg.value;
          break;
        case "mse":
        case "hls":
        case "mp4":
        case "mjpeg":
          this.status = msg.type.toUpperCase();
          break;
        default:
          break;
      }
    };

    this.dispatchEvent(new CustomEvent("open"));
    return result;
  }

  onclose(): any {
    console.debug("stream.onclose");
    const result = super.onclose();
    this.dispatchEvent(new CustomEvent("close"));
    return result;
  }

  onpcvideo(ev: Event): void {
    console.debug("stream.onpcvideo");
    super.onpcvideo(ev);

    if (this.pcState !== WebSocket.CLOSED) {
      this.status = "RTC";
    }
    this.dispatchEvent(new CustomEvent("pcvideo", { detail: { ev } }));
  }
}

if (!customElements.get("video-stream")) {
  customElements.define("video-stream", VideoStream);
}
