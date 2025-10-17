export class VideoRTC extends HTMLElement {
  state: string;

  pcState: number;

  video: HTMLVideoElement | null;

  src: string;

  private _controls: boolean;

  public get controls(): boolean {
    return this._controls;
  }

  public set controls(value: boolean) {
    this._controls = value;
  }

  onmessage: { stream?: (msg: { type: string; value: string }) => void };

  oninit(): void;

  onconnect(): any;

  ondisconnect(): void;

  onopen(): any;

  onclose(): any;

  onpcvideo(ev: Event): void;
}
