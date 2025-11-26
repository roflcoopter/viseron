import {
  osdTextToDrawtextFilter,
  videoTransformToFilter,
} from "./camera/utils";

// Default codec for recorder when adding video_filters
export const DEFAULT_RECORDER_CODEC = "h264" as const;

/**
 * Normalize component data before saving to backend
 * Handles zones, masks, video transforms, and OSD texts conversion
 */
export function normalizeComponentData(data: any): any {
  let normalized = { ...data };

  // Normalize labels for face_recognition and license_plate_recognition: labels first, then mask
  if (
    data.componentType === "face_recognition" ||
    data.componentType === "license_plate_recognition"
  ) {
    const { labels, mask, ...rest } = normalized;
    // Rebuild object with correct order to ensure JSON serialization order
    normalized = {
      ...(labels && Array.isArray(labels) && { labels }), // Include even if empty to allow deletion
      ...(mask && { mask }),
      ...rest,
    };
  }

  // Normalize zones: name first, then coordinates, then other keys
  // Note: coordinates are already integers from calculateImageCoordinates
  if (normalized.zones && Array.isArray(normalized.zones)) {
    normalized.zones = normalized.zones.map((zone: any) => {
      const { name, coordinates, ...rest } = zone;
      return {
        name,
        coordinates,
        ...rest,
      };
    });
  }

  // Process video transforms and OSD texts together for camera domain
  if (data.componentType === "camera") {
    // Separate camera and recorder transforms
    const cameraTransforms = (normalized.video_transforms || []).filter(
      (transform: any) => transform.type === "camera",
    );
    const recorderTransforms = (normalized.video_transforms || []).filter(
      (transform: any) => transform.type === "recorder",
    );

    // Separate camera and recorder OSD texts
    const cameraOSDs = (normalized.osd_texts || []).filter(
      (osd: any) => osd.type === "camera",
    );
    const recorderOSDs = (normalized.osd_texts || []).filter(
      (osd: any) => osd.type === "recorder",
    );

    // Build camera video_filters: transforms first, then drawtext
    const cameraTransformFilters = cameraTransforms.map((transform: any) =>
      videoTransformToFilter(transform),
    );
    const cameraDrawtextFilters = cameraOSDs.map((osd: any) =>
      osdTextToDrawtextFilter(osd),
    );

    if (cameraTransformFilters.length > 0 || cameraDrawtextFilters.length > 0) {
      normalized.video_filters = [
        ...cameraTransformFilters,
        ...cameraDrawtextFilters,
      ];
    } else {
      // Remove video_filters if no camera transforms or OSDs
      delete normalized.video_filters;
    }

    // Build recorder video_filters: transforms first, then drawtext
    const recorderTransformFilters = recorderTransforms.map((transform: any) =>
      videoTransformToFilter(transform),
    );
    const recorderDrawtextFilters = recorderOSDs.map((osd: any) =>
      osdTextToDrawtextFilter(osd),
    );

    if (
      recorderTransformFilters.length > 0 ||
      recorderDrawtextFilters.length > 0
    ) {
      if (!normalized.recorder) {
        normalized.recorder = {};
      }
      normalized.recorder.video_filters = [
        ...recorderTransformFilters,
        ...recorderDrawtextFilters,
      ];
      // Add default codec if not present when using video_filters
      if (!normalized.recorder.codec) {
        normalized.recorder.codec = DEFAULT_RECORDER_CODEC;
      }
    } else if (normalized.recorder?.video_filters) {
      // Remove recorder video_filters if no recorder transforms or OSDs
      delete normalized.recorder.video_filters;
    }
  }

  // Remove internal/UI-only fields that should not be sent to backend
  // These fields are added by frontend for UI purposes only
  delete normalized.componentType;
  delete normalized.componentName;
  delete normalized.available_labels;
  delete normalized.video_transforms;
  delete normalized.osd_texts;

  return normalized;
}
