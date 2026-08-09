import {
  MaxFileSizeExceededError,
  parseMultipartStream,
} from "@mjackson/multipart-parser";
import { useEffect, useRef, useState } from "react";

// Must match BOUNDARY in viseron/components/webserver/stream_handler.py
const BOUNDARY = "jpgboundary";

// Per-frame cap: protects against unbounded memory growth if a hostile/malformed
// stream never sends a boundary. 10 MB is well above any realistic camera frame.
const MAX_FRAME_SIZE_BYTES = 10 * 1024 * 1024;

// Hook that consumes an MJPEG stream via fetch/ReadableStream and parses
// frames using multipart-parser.
// This is needed for streaming thru HA Ingress, native browser streaming
// does not work for some reason.
// Parsed JPEG frames are rendered onto the provided <img> element via
// blob URLs.
// Another bonus of this approach is that streams stop instantly when closed,
// which fixes the common issue of streams continuing to consume bandwidth
// after navigating away.
export function useMjpegStreamMultipart(
  imgRef: React.RefObject<HTMLImageElement | null>,
  src: string,
): { error: string | null; isLoading: boolean } {
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const abortRef = useRef<AbortController | null>(null);
  const prevBlobUrl = useRef<string | null>(null);
  const prevSrcRef = useRef<string>(src);

  // Reset state synchronously during render when src changes
  if (prevSrcRef.current !== src) {
    prevSrcRef.current = src;
    if (error !== null) setError(null);
    if (!isLoading) setIsLoading(true);
  }

  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;

    let cancelled = false;

    // Display a single JPEG frame by creating a blob URL and revoking the previous one
    const displayFrame = (jpegData: Uint8Array) => {
      const blob = new Blob([new Uint8Array(jpegData)], { type: "image/jpeg" });
      const url = URL.createObjectURL(blob);
      if (imgRef.current) {
        imgRef.current.src = url;
      }
      if (prevBlobUrl.current) {
        URL.revokeObjectURL(prevBlobUrl.current);
      }
      prevBlobUrl.current = url;
    };

    const startStream = async () => {
      try {
        const response = await fetch(src, { signal: controller.signal });
        if (!response.ok || !response.body) {
          setError(`Stream returned status ${response.status}`);
          setIsLoading(false);
          return;
        }

        let firstFrame = true;
        for await (const part of parseMultipartStream(response.body, {
          boundary: BOUNDARY,
          maxFileSize: MAX_FRAME_SIZE_BYTES,
        })) {
          if (cancelled) break;
          displayFrame(part.bytes);
          if (firstFrame) {
            firstFrame = false;
            setIsLoading(false);
          }
        }
        if (!cancelled && firstFrame) {
          setError("MJPEG stream ended without sending any frames.");
          setIsLoading(false);
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        if (cancelled) return;
        if (err instanceof MaxFileSizeExceededError) {
          setError(
            `MJPEG stream frame exceeded the ${MAX_FRAME_SIZE_BYTES / (1024 * 1024)} MB size limit.`,
          );
        } else {
          setError("MJPEG stream connection failed.");
        }
        setIsLoading(false);
      }
    };

    startStream();

    return () => {
      cancelled = true;
      controller.abort();
      if (prevBlobUrl.current) {
        URL.revokeObjectURL(prevBlobUrl.current);
        prevBlobUrl.current = null;
      }
    };
  }, [imgRef, src]);

  return { error, isLoading };
}
