import { OSDTextData } from "./types";

interface OSDTextsOverlayProps {
  osdTexts: OSDTextData[];
  imageWidth: number;
  imageHeight: number;
}

/**
 * Measure text width accurately using canvas
 */
function measureTextWidth(text: string, fontSize: number): number {
  // Create temporary canvas for measurement
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (!context) return text.length * fontSize * 0.5; // fallback

  context.font = `200 ${fontSize}px 'DejaVu Sans', monospace`;
  const metrics = context.measureText(text);
  return metrics.width;
}

/**
 * Convert FFmpeg box color format to CSS rgba
 * Example: "0x000000FF@0.5" -> "rgba(0, 0, 0, 0.5)"
 */
function ffmpegBoxColorToRgba(boxColor: string): string {
  // Default transparent black
  if (!boxColor) {
    return "rgba(0, 0, 0, 0)";
  }

  try {
    const parts = boxColor.split("@");
    const hexColor = parts[0].replace("0x", "");
    const opacity = parts.length > 1 ? parseFloat(parts[1]) : 1;

    // If opacity is 0, return transparent
    if (opacity === 0) {
      return "rgba(0, 0, 0, 0)";
    }

    // Parse RRGGBB only (ignore AA if present)
    // FFmpeg format: 0xRRGGBBAA@opacity
    // The AA part is not used, opacity after @ is what matters
    const r = parseInt(hexColor.substring(0, 2), 16);
    const g = parseInt(hexColor.substring(2, 4), 16);
    const b = parseInt(hexColor.substring(4, 6), 16);

    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  } catch {
    return "rgba(0, 0, 0, 0)";
  }
}

export function OSDTextsOverlay({
  osdTexts,
  imageWidth,
  imageHeight,
}: OSDTextsOverlayProps) {
  if (osdTexts.length === 0) return null;

  return (
    <>
      {osdTexts.map((osdText) => {
        // Calculate position based on position setting
        let x = osdText.paddingX;
        let y = osdText.paddingY;
        let anchor: "start" | "end" = "start";
        let baseline: "hanging" | "auto" = "hanging";

        if (osdText.position === "top-right") {
          x = imageWidth - osdText.paddingX;
          y = osdText.paddingY;
          anchor = "end";
          baseline = "hanging";
        } else if (osdText.position === "bottom-left") {
          x = osdText.paddingX;
          y = imageHeight - osdText.paddingY;
          anchor = "start";
          baseline = "auto";
        } else if (osdText.position === "bottom-right") {
          x = imageWidth - osdText.paddingX;
          y = imageHeight - osdText.paddingY;
          anchor = "end";
          baseline = "auto";
        } else {
          // top-left
          x = osdText.paddingX;
          y = osdText.paddingY;
          anchor = "start";
          baseline = "hanging";
        }

        // Generate preview text
        const formatTimestamp = () => {
          const now = new Date();
          const year = now.getFullYear();
          const month = String(now.getMonth() + 1).padStart(2, "0");
          const day = String(now.getDate()).padStart(2, "0");
          const hours = String(now.getHours()).padStart(2, "0");
          const minutes = String(now.getMinutes()).padStart(2, "0");
          const seconds = String(now.getSeconds()).padStart(2, "0");
          return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
        };

        const previewText =
          osdText.textType === "timestamp"
            ? formatTimestamp()
            : osdText.textType === "custom"
              ? `${osdText.customText} ${formatTimestamp()}`
              : osdText.customText || "";

        // Convert colors
        const fillColor = osdText.fontColor || "white";
        const backgroundColor = ffmpegBoxColorToRgba(
          osdText.boxColor || "0x00000000@0",
        );
        const hasBackground = backgroundColor !== "rgba(0, 0, 0, 0)";

        // Measure text width accurately
        const textWidth = measureTextWidth(previewText, osdText.fontSize);
        const boxPaddingX = 4;
        const boxWidth = textWidth + boxPaddingX * 2;
        const boxHeight = osdText.fontSize;

        return (
          <g key={osdText.id}>
            {hasBackground && (
              <rect
                x={anchor === "end" ? x - boxWidth : x - boxPaddingX}
                y={baseline === "hanging" ? y : y - boxHeight}
                width={boxWidth}
                height={boxHeight}
                fill={backgroundColor}
              />
            )}
            <text
              x={x}
              y={y}
              fill={fillColor}
              fontSize={osdText.fontSize}
              fontFamily="'DejaVu Sans'"
              fontWeight="200"
              textAnchor={anchor}
              dominantBaseline={baseline}
            >
              {previewText}
            </text>
          </g>
        );
      })}
    </>
  );
}
