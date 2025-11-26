import { OSDText, VideoTransform, VideoTransformTarget } from "./types";

/**
 * Convert VideoTransform to FFmpeg filter string
 */
export function videoTransformToFilter(transform: VideoTransform): string {
  switch (transform.transform) {
    case "hflip":
      return "hflip";
    case "vflip":
      return "vflip";
    case "rotate180":
      return "hflip,vflip";
    default:
      return "";
  }
}

/**
 * Parse video_filters to extract transforms
 */
export function parseVideoTransformsFromFilters(
  filters: string[],
  type: VideoTransformTarget,
): VideoTransform[] {
  const transforms: VideoTransform[] = [];

  filters.forEach((filter) => {
    // Check for hflip
    if (filter === "hflip") {
      transforms.push({
        id: `transform-${Date.now()}-${Math.random()}`,
        type,
        transform: "hflip",
      });
    }
    // Check for vflip
    else if (filter === "vflip") {
      transforms.push({
        id: `transform-${Date.now()}-${Math.random()}`,
        type,
        transform: "vflip",
      });
    }
    // Check for rotate180 (hflip,vflip combination)
    else if (filter === "hflip,vflip") {
      transforms.push({
        id: `transform-${Date.now()}-${Math.random()}`,
        type,
        transform: "rotate180",
      });
    }
  });

  return transforms;
}

/**
 * Parse video transforms from component data
 */
export function parseVideoTransformsFromComponentData(
  componentData: any,
): VideoTransform[] {
  const transforms: VideoTransform[] = [];

  // Parse camera video_filters
  if (
    componentData.video_filters &&
    Array.isArray(componentData.video_filters)
  ) {
    const cameraTransforms = parseVideoTransformsFromFilters(
      componentData.video_filters,
      "camera",
    );
    transforms.push(...cameraTransforms);
  }

  // Parse recorder video_filters
  if (
    componentData.recorder?.video_filters &&
    Array.isArray(componentData.recorder.video_filters)
  ) {
    const recorderTransforms = parseVideoTransformsFromFilters(
      componentData.recorder.video_filters,
      "recorder",
    );
    transforms.push(...recorderTransforms);
  }

  return transforms;
}

/**
 * Parse drawtext filter to OSDText object
 */
export function parseDrawtextFilter(
  filter: string,
  type: "camera" | "recorder",
): OSDText | null {
  if (!filter.startsWith("drawtext=")) return null;

  const params: Record<string, string> = {};
  const paramString = filter.substring(9); // Remove "drawtext="

  // Simple parser for key=value pairs
  const matches = paramString.matchAll(/(\w+)=([^:]+)/g);
  for (const match of matches) {
    params[match[1]] = match[2];
  }

  if (!params.text) return null;

  // Parse text content
  const text = params.text.replace(/'/g, "");
  const isTimestamp = text === "%{localtime}";
  const hasTimestamp = text.includes("%{localtime}");
  const customText = isTimestamp
    ? ""
    : hasTimestamp
      ? text
          .replace(/%{localtime}$/, "")
          .trim()
          .replace(/\|$/, "")
          .trim()
      : text;

  // Parse position from x and y coordinates
  const x = params.x || "10";
  const y = params.y || "10";
  let position: "top-left" | "top-right" | "bottom-left" | "bottom-right" =
    "top-left";

  if (x.includes("w-")) {
    position = y.includes("h-") ? "bottom-right" : "top-right";
  } else {
    position = y.includes("h-") ? "bottom-left" : "top-left";
  }

  // Extract padding from coordinates
  const paddingXMatch = x.match(/\d+/);
  const paddingYMatch = y.match(/\d+/);

  // Parse colors (default values if not present)
  const fontColor = params.fontcolor || "white";
  const boxColor = params.boxcolor || "0x00000000@1";

  return {
    id: `osd-${Date.now()}-${Math.random()}`,
    type,
    textType: isTimestamp ? "timestamp" : hasTimestamp ? "custom" : "text",
    customText,
    position,
    paddingX: paddingXMatch ? parseInt(paddingXMatch[0], 10) : 10,
    paddingY: paddingYMatch ? parseInt(paddingYMatch[0], 10) : 10,
    fontSize: params.fontsize ? parseInt(params.fontsize, 10) : 24,
    fontColor,
    boxColor,
  };
}

/**
 * Convert OSDText to drawtext filter string
 */
export function osdTextToDrawtextFilter(osd: OSDText): string {
  let x: string;
  let y: string;

  switch (osd.position) {
    case "top-left":
      x = `${osd.paddingX}`;
      y = `${osd.paddingY}`;
      break;
    case "top-right":
      x = `w-text_w-${osd.paddingX}`;
      y = `${osd.paddingY}`;
      break;
    case "bottom-left":
      x = `${osd.paddingX}`;
      y = `h-text_h-${osd.paddingY}`;
      break;
    case "bottom-right":
      x = `w-text_w-${osd.paddingX}`;
      y = `h-text_h-${osd.paddingY}`;
      break;
    default:
      x = `${osd.paddingX}`;
      y = `${osd.paddingY}`;
  }

  const text =
    osd.textType === "timestamp"
      ? "%{localtime}"
      : osd.textType === "custom"
        ? `${osd.customText} %{localtime}`
        : osd.customText || "";

  return `drawtext=text='${text}':x=${x}:y=${y}:fontcolor=${osd.fontColor}:box=1:boxcolor=${osd.boxColor}:fontsize=${osd.fontSize}`;
}

/**
 * Parse OSD texts from component data
 */
export function parseOSDTextsFromComponentData(componentData: any): OSDText[] {
  const osdTexts: OSDText[] = [];

  // Parse camera video_filters
  if (
    componentData.video_filters &&
    Array.isArray(componentData.video_filters)
  ) {
    componentData.video_filters.forEach((filter: string) => {
      const parsed = parseDrawtextFilter(filter, "camera");
      if (parsed) osdTexts.push(parsed);
    });
  }

  // Parse recorder video_filters
  if (
    componentData.recorder?.video_filters &&
    Array.isArray(componentData.recorder.video_filters)
  ) {
    componentData.recorder.video_filters.forEach((filter: string) => {
      const parsed = parseDrawtextFilter(filter, "recorder");
      if (parsed) osdTexts.push(parsed);
    });
  }

  return osdTexts;
}
