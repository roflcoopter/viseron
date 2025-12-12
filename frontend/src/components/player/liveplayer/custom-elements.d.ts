import type { VideoRTC } from "./video-rtc.js";

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "video-stream": React.DetailedHTMLProps<
        React.VideoHTMLAttributes<VideoRTC>,
        VideoRTC
      >;
    }
  }
}
export {};
