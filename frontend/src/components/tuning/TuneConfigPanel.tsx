import { Box, Card, CardContent, CardHeader } from "@mui/material";
import { MouseEvent, useState } from "react";

import { OSDText, VideoTransform } from "./camera/types";
import {
  ConfigPanelContextMenu,
  ConfigPanelHeader,
  DrawingModeInstructions,
  EmptyStateCard,
  LabelsSection,
  MasksSection,
  MiscellaneousSection,
  OSDTextsSection,
  SaveConfigButton,
  VideoTransformsSection,
  ZonesSection,
} from "./config";
import { getMiscellaneousFields } from "./config/miscellaneousConfig";
import { Label, Zone } from "./object_detector/types";
import { Mask } from "./shared/types";

interface ComponentData {
  componentType: string;
  labels?: Label[];
  zones?: Zone[];
  mask?: Mask[];
  osd_texts?: OSDText[];
  video_transforms?: VideoTransform[];
}

interface TuneConfigPanelProps {
  selectedComponentData: ComponentData | null;
  isDrawingMode: boolean;
  drawingType: "zone" | "mask" | null;
  drawingPoints: Array<{ x: number; y: number }>;
  isConfigModified: boolean;
  isSaving: boolean;
  onLabelClick: (index: number) => void;
  onAddLabel: () => void;
  onZoneClick: (index: number) => void;
  onAddZone: () => void;
  onMaskClick: (index: number) => void;
  onAddMask: () => void;
  onCompleteDrawing: () => void;
  onCancelDrawing: () => void;
  onSaveConfig: () => void;
  onRevertConfig: () => void;
  onDeleteLabel: (index: number) => void;
  onDeleteZone: (index: number) => void;
  onDeleteMask: (index: number) => void;
  onEditZoneName: (index: number) => void;
  onEditZoneLabels: (index: number) => void;
  onAddOSDText: (type: "camera" | "recorder") => void;
  onOSDTextClick: (index: number) => void;
  onEditOSDText: (index: number) => void;
  onDeleteOSDText: (index: number) => void;
  onAddVideoTransform: (type: "camera" | "recorder") => void;
  onVideoTransformClick: (index: number) => void;
  onEditVideoTransform: (index: number) => void;
  onDeleteVideoTransform: (index: number) => void;
  onMiscellaneousFieldChange: (key: string, value: any) => void;
  selectedZoneIndex: number | null;
  selectedMaskIndex: number | null;
  selectedOSDTextIndex: number | null;
  selectedVideoTransformIndex: number | null;
  currentDomainName: string;
}

export function TuneConfigPanel({
  selectedComponentData,
  isDrawingMode,
  drawingType,
  drawingPoints,
  isConfigModified,
  isSaving,
  onLabelClick,
  onAddLabel,
  onZoneClick,
  onAddZone,
  onMaskClick,
  onAddMask,
  onCompleteDrawing,
  onCancelDrawing,
  onSaveConfig,
  onRevertConfig,
  onDeleteLabel,
  onDeleteZone,
  onDeleteMask,
  onEditZoneName,
  onEditZoneLabels,
  onAddOSDText,
  onOSDTextClick,
  onEditOSDText,
  onDeleteOSDText,
  onAddVideoTransform,
  onVideoTransformClick,
  onEditVideoTransform,
  onDeleteVideoTransform,
  onMiscellaneousFieldChange,
  selectedZoneIndex,
  selectedMaskIndex,
  selectedOSDTextIndex,
  selectedVideoTransformIndex,
  currentDomainName,
}: TuneConfigPanelProps) {
  const [contextMenu, setContextMenu] = useState<{
    mouseX: number;
    mouseY: number;
    type: "label" | "zone" | "mask" | "osd" | "video_transform";
    index: number;
  } | null>(null);

  const handleContextMenu = (
    event: MouseEvent<HTMLButtonElement> | MouseEvent<HTMLDivElement>,
    type: "label" | "zone" | "mask" | "osd" | "video_transform",
    index: number,
  ) => {
    event.preventDefault();
    setContextMenu(
      contextMenu === null
        ? {
            mouseX: event.clientX + 2,
            mouseY: event.clientY - 6,
            type,
            index,
          }
        : null,
    );
  };

  const handleCloseContextMenu = () => {
    setContextMenu(null);
  };

  const handleDelete = () => {
    if (contextMenu) {
      switch (contextMenu.type) {
        case "label":
          onDeleteLabel(contextMenu.index);
          break;
        case "zone":
          onDeleteZone(contextMenu.index);
          break;
        case "mask":
          onDeleteMask(contextMenu.index);
          break;
        case "osd":
          onDeleteOSDText(contextMenu.index);
          break;
        case "video_transform":
          onDeleteVideoTransform(contextMenu.index);
          break;
        default:
          break;
      }
    }
    handleCloseContextMenu();
  };

  if (!selectedComponentData) {
    return <EmptyStateCard message="Please select component first" />;
  }

  if (selectedComponentData.componentType === "not_tunable") {
    return <EmptyStateCard message="This component can't be tuned" />;
  }

  return (
    <Card
      variant="outlined"
      sx={{
        height: { md: "72.5vh" },
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <CardHeader
        title={
          <ConfigPanelHeader
            isConfigModified={isConfigModified}
            isDrawingMode={isDrawingMode}
            isSaving={isSaving}
            onRevertConfig={onRevertConfig}
          />
        }
        sx={{
          paddingY: 1.5,
          borderBottom: 1,
          borderColor: "divider",
        }}
      />
      <CardContent sx={{ overflow: "auto", paddingY: 1.5, flex: 1 }}>
        <Box>
          {/* Drawing Mode Instructions */}
          {isDrawingMode && (
            <DrawingModeInstructions
              drawingType={drawingType}
              drawingPointsCount={drawingPoints.length}
              onCompleteDrawing={onCompleteDrawing}
              onCancelDrawing={onCancelDrawing}
            />
          )}

          {/* Labels section - for object_detector, face_recognition, and license_plate_recognition */}
          {(selectedComponentData.componentType === "object_detector" ||
            selectedComponentData.componentType === "face_recognition" ||
            selectedComponentData.componentType ===
              "license_plate_recognition") && (
            <LabelsSection
              labels={selectedComponentData.labels || []}
              isDrawingMode={isDrawingMode}
              isSaving={isSaving}
              componentType={selectedComponentData.componentType}
              onLabelClick={onLabelClick}
              onAddLabel={onAddLabel}
              onContextMenu={handleContextMenu}
            />
          )}

          {/* Zones section - only for object_detector */}
          {selectedComponentData.componentType === "object_detector" && (
            <ZonesSection
              zones={selectedComponentData.zones || []}
              selectedZoneIndex={selectedZoneIndex}
              isDrawingMode={isDrawingMode}
              isSaving={isSaving}
              onZoneClick={onZoneClick}
              onAddZone={onAddZone}
              onContextMenu={handleContextMenu}
            />
          )}

          {/* Masks section - for object_detector, motion_detector, face_recognition, and license_plate_recognition */}
          {(selectedComponentData.componentType === "object_detector" ||
            selectedComponentData.componentType === "motion_detector" ||
            selectedComponentData.componentType === "face_recognition" ||
            selectedComponentData.componentType ===
              "license_plate_recognition") && (
            <MasksSection
              masks={selectedComponentData.mask || []}
              selectedMaskIndex={selectedMaskIndex}
              isDrawingMode={isDrawingMode}
              isSaving={isSaving}
              onMaskClick={onMaskClick}
              onAddMask={onAddMask}
              onContextMenu={handleContextMenu}
            />
          )}

          {/* OSD Texts section - only for camera components */}
          {selectedComponentData.componentType === "camera" && (
            <OSDTextsSection
              osdTexts={selectedComponentData.osd_texts || []}
              isDrawingMode={isDrawingMode}
              isSaving={isSaving}
              selectedOSDTextIndex={selectedOSDTextIndex}
              onAddOSDText={onAddOSDText}
              onOSDTextClick={onOSDTextClick}
              onContextMenu={handleContextMenu}
            />
          )}

          {/* Video Transforms section - only for camera components */}
          {selectedComponentData.componentType === "camera" && (
            <VideoTransformsSection
              videoTransforms={selectedComponentData.video_transforms || []}
              selectedVideoTransformIndex={selectedVideoTransformIndex}
              isDrawingMode={isDrawingMode}
              isSaving={isSaving}
              onAddVideoTransform={onAddVideoTransform}
              onVideoTransformClick={onVideoTransformClick}
              onContextMenu={handleContextMenu}
            />
          )}

          {/* Miscellaneous section - domain-agnostic configurable fields */}
          <MiscellaneousSection
            fields={getMiscellaneousFields(
              currentDomainName,
              selectedComponentData,
            )}
            isDrawingMode={isDrawingMode}
            isSaving={isSaving}
            onFieldChange={onMiscellaneousFieldChange}
          />

          {/* Save Config Button */}
          <SaveConfigButton
            isConfigModified={isConfigModified}
            isSaving={isSaving}
            isDrawingMode={isDrawingMode}
            onSaveConfig={onSaveConfig}
          />
        </Box>
      </CardContent>

      {/* Context Menu */}
      <ConfigPanelContextMenu
        contextMenu={contextMenu}
        onClose={handleCloseContextMenu}
        onEditZoneName={onEditZoneName}
        onEditZoneLabels={onEditZoneLabels}
        onEditOSDText={onEditOSDText}
        onEditVideoTransform={onEditVideoTransform}
        onDelete={handleDelete}
      />
    </Card>
  );
}
