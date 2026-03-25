import {
  Camera,
  ComponentData,
  Coordinate,
  DragHandlers,
  DrawingOverlay,
  MasksOverlay,
  OSDTextsOverlay,
  ZonesOverlay,
} from "./overlay";

interface OverlayProps {
  camera: Camera;
  selectedComponentData: ComponentData | null;
  selectedZoneIndex: number | null;
  selectedMaskIndex: number | null;
  selectedOSDTextIndex: number | null;
  selectedVideoTransformIndex: number | null;
  isDrawingMode: boolean;
  drawingType: "zone" | "mask" | null;
  drawingPoints: Coordinate[];
  onPointDrag?: (
    type: "zone" | "mask",
    itemIndex: number,
    pointIndex: number,
    newX: number,
    newY: number,
  ) => void;
  onPolygonDrag?: (
    type: "zone" | "mask",
    itemIndex: number,
    deltaX: number,
    deltaY: number,
    imageWidth: number,
    imageHeight: number,
  ) => void;
}

export function renderOverlay({
  camera,
  selectedComponentData,
  selectedZoneIndex,
  selectedMaskIndex,
  selectedOSDTextIndex,
  isDrawingMode,
  drawingType,
  drawingPoints,
  onPointDrag,
  onPolygonDrag,
}: OverlayProps) {
  if (!camera) return null;

  const zones = selectedComponentData?.zones || [];
  const masks = selectedComponentData?.mask || [];
  const osdTexts = selectedComponentData?.osd_texts || [];

  // Only show selected OSD text
  const selectedOSDTexts =
    selectedOSDTextIndex !== null && osdTexts[selectedOSDTextIndex]
      ? [osdTexts[selectedOSDTextIndex]]
      : [];

  const hasOverlays =
    zones.length > 0 ||
    masks.length > 0 ||
    selectedOSDTexts.length > 0 ||
    isDrawingMode;
  if (!hasOverlays) return null;

  const imageWidth = camera.still_image.width;
  const imageHeight = camera.still_image.height;

  const dragHandlers: DragHandlers = {
    onPointDrag,
    onPolygonDrag,
  };

  return (
    <svg
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
      viewBox={`0 0 ${imageWidth} ${imageHeight}`}
      preserveAspectRatio="xMidYMid meet"
    >
      {/* Draw all zones */}
      <ZonesOverlay
        zones={zones}
        selectedZoneIndex={selectedZoneIndex}
        imageWidth={imageWidth}
        imageHeight={imageHeight}
        dragHandlers={dragHandlers}
      />

      {/* Draw all masks */}
      <MasksOverlay
        masks={masks}
        selectedMaskIndex={selectedMaskIndex}
        imageWidth={imageWidth}
        imageHeight={imageHeight}
        dragHandlers={dragHandlers}
      />

      {/* Draw current drawing polygon */}
      {isDrawingMode && (
        <DrawingOverlay
          drawingType={drawingType}
          drawingPoints={drawingPoints}
        />
      )}

      {/* Render OSD Texts - only selected OSD text */}
      {selectedOSDTexts.length > 0 && (
        <OSDTextsOverlay
          osdTexts={selectedOSDTexts}
          imageWidth={imageWidth}
          imageHeight={imageHeight}
        />
      )}
    </svg>
  );
}
