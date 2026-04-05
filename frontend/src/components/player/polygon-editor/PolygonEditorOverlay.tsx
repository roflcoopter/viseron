import { PolygonCanvas } from "./PolygonCanvas";
import { PolygonEditorToolbar } from "./PolygonEditorToolbar";
import { CoordinateTransform } from "./types";
import { usePolygonEditorStore } from "./usePolygonEditorStore";

interface PolygonEditorOverlayProps {
  containerRef: React.RefObject<HTMLElement | null>;
  transform: CoordinateTransform;
  cameraWidth: number;
  cameraHeight: number;
}

export function PolygonEditorOverlay({
  containerRef,
  transform,
  cameraWidth,
  cameraHeight,
}: PolygonEditorOverlayProps) {
  const { isEditing, polygons } = usePolygonEditorStore();

  if (!isEditing) return null;

  return (
    <>
      <PolygonCanvas
        containerRef={containerRef}
        transform={transform}
        polygons={polygons}
        isEditing={isEditing}
        cameraWidth={cameraWidth}
        cameraHeight={cameraHeight}
      />
      <PolygonEditorToolbar
        cameraWidth={cameraWidth}
        cameraHeight={cameraHeight}
      />
    </>
  );
}
