import { useState } from "react";

import { useOSDTextHandlers } from "../camera/useOSDTextHandlers";
import { useVideoTransformHandlers } from "../camera/useVideoTransformHandlers";
import {
  parseOSDTextsFromComponentData,
  parseVideoTransformsFromComponentData,
} from "../camera/utils";
import { useZoneHandlers } from "../object_detector/useZoneHandlers";
import { Coordinate } from "./types";
import { useLabelHandlers } from "./useLabelHandlers";
import { useMaskHandlers } from "./useMaskHandlers";

export function useTuneHandlers() {
  const [selectedComponentData, setSelectedComponentData] = useState<any>(null);
  const [originalComponentData, setOriginalComponentData] = useState<any>(null);
  const [isConfigModified, setIsConfigModified] = useState(false);
  const [availableLabels, setAvailableLabels] = useState<string[]>([]);

  // Shared drawing state for both zone and mask (mutually exclusive)
  const [isDrawingMode, setIsDrawingMode] = useState(false);
  const [drawingType, setDrawingType] = useState<"zone" | "mask" | null>(null);
  const [drawingPoints, setDrawingPoints] = useState<Coordinate[]>([]);

  // Single shared selection state (only one zone OR mask can be selected)
  const [selectedItemType, setSelectedItemType] = useState<
    "zone" | "mask" | null
  >(null);
  const [selectedItemIndex, setSelectedItemIndex] = useState<number | null>(
    null,
  );

  // OSD text selection state
  const [selectedOSDTextIndex, setSelectedOSDTextIndex] = useState<
    number | null
  >(null);

  // Video transform selection state
  const [selectedVideoTransformIndex, setSelectedVideoTransformIndex] =
    useState<number | null>(null);

  // Unified selection handler
  const handleItemClick = (type: "zone" | "mask", index: number) => {
    // Toggle: if same item clicked, deselect
    if (selectedItemType === type && selectedItemIndex === index) {
      setSelectedItemType(null);
      setSelectedItemIndex(null);
    } else {
      // Select new item (automatically deselects other type)
      setSelectedItemType(type);
      setSelectedItemIndex(index);
    }
  };

  // OSD text click handler
  const handleOSDTextClick = (index: number) => {
    // Toggle: if same OSD text clicked, deselect
    if (selectedOSDTextIndex === index) {
      setSelectedOSDTextIndex(null);
    } else {
      setSelectedOSDTextIndex(index);
    }
  };

  // Video transform click handler
  const handleVideoTransformClick = (index: number) => {
    // Toggle: if same video transform clicked, deselect
    if (selectedVideoTransformIndex === index) {
      setSelectedVideoTransformIndex(null);
    } else {
      setSelectedVideoTransformIndex(index);
    }
  };

  // Camera domain handlers (OSD Text)
  const osdTextHandlers = useOSDTextHandlers(
    selectedComponentData,
    setSelectedComponentData,
    setIsConfigModified,
  );

  // Camera domain handlers (Video Transform)
  const videoTransformHandlers = useVideoTransformHandlers(
    selectedComponentData,
    setSelectedComponentData,
    setIsConfigModified,
  );

  // Motion detector domain handlers (Mask)
  const maskHandlers = useMaskHandlers(
    selectedComponentData,
    setSelectedComponentData,
    setIsConfigModified,
    isDrawingMode,
    setIsDrawingMode,
    drawingType,
    setDrawingType,
    drawingPoints,
    setDrawingPoints,
    selectedItemType === "mask" ? selectedItemIndex : null,
    (index: number) => handleItemClick("mask", index),
  );

  // Object detector domain handlers (Label)
  const objectDetectorLabelHandlers = useLabelHandlers(
    selectedComponentData,
    setSelectedComponentData,
    setIsConfigModified,
    availableLabels,
    { hasConfidence: true, hasTriggerRecording: true },
  );

  // Face recognition domain handlers (Label)
  const faceRecognitionLabelHandlers = useLabelHandlers(
    selectedComponentData,
    setSelectedComponentData,
    setIsConfigModified,
    availableLabels,
    { hasConfidence: false, hasTriggerRecording: false },
  );

  // License plate recognition domain handlers (Label)
  const licensePlateRecognitionLabelHandlers = useLabelHandlers(
    selectedComponentData,
    setSelectedComponentData,
    setIsConfigModified,
    availableLabels,
    { hasConfidence: false, hasTriggerRecording: false },
  );

  // Object detector domain handlers (Zone)
  const zoneHandlers = useZoneHandlers(
    selectedComponentData,
    setSelectedComponentData,
    setIsConfigModified,
    isDrawingMode,
    setIsDrawingMode,
    drawingType,
    setDrawingType,
    drawingPoints,
    setDrawingPoints,
    selectedItemType === "zone" ? selectedItemIndex : null,
    (index: number) => handleItemClick("zone", index),
  );

  const resetAllSelections = () => {
    // Reset shared selection state
    setSelectedItemType(null);
    setSelectedItemIndex(null);
    setSelectedOSDTextIndex(null);
    setSelectedVideoTransformIndex(null);
    // Reset shared drawing state
    setIsDrawingMode(false);
    setDrawingType(null);
    setDrawingPoints([]);
  };

  const handleComponentChange = (
    domainName: string,
    componentName: string,
    componentData: any,
    expandedComponent: string | false,
    setExpandedComponent: (value: string | false) => void,
  ) => {
    const componentKey = `${domainName}-${componentName}`;

    if (expandedComponent === componentKey) {
      setExpandedComponent(false);
      setSelectedComponentData(null);
      setOriginalComponentData(null);
      resetAllSelections();
    } else {
      setExpandedComponent(componentKey);

      // Determine component type
      let componentType = "not_tunable";
      if (domainName === "camera") {
        componentType = "camera";
      } else if (domainName === "motion_detector") {
        componentType = "motion_detector";
      } else if (domainName === "object_detector") {
        componentType = "object_detector";
      } else if (domainName === "face_recognition") {
        componentType = "face_recognition";
      } else if (domainName === "license_plate_recognition") {
        componentType = "license_plate_recognition";
      } else if (domainName === "onvif") {
        // For ONVIF domain, use component name as type (device, imaging, media, ptz, client)
        componentType = componentName;
      }

      // Parse OSD texts and video transforms if camera component
      let osdTexts: any[] = [];
      let videoTransforms: any[] = [];
      if (componentType === "camera") {
        osdTexts = parseOSDTextsFromComponentData(componentData);
        videoTransforms = parseVideoTransformsFromComponentData(componentData);
      }

      const enrichedData = {
        ...componentData,
        componentType,
        componentName,
        osd_texts: osdTexts,
        video_transforms: videoTransforms,
      };

      setSelectedComponentData(enrichedData);
      setOriginalComponentData(JSON.parse(JSON.stringify(enrichedData)));

      // Set available labels from API if present
      if (componentData.available_labels) {
        setAvailableLabels(componentData.available_labels);
      } else {
        setAvailableLabels([]);
      }

      resetAllSelections();
    }
    setIsConfigModified(false);
  };

  const handleRevertConfig = () => {
    if (originalComponentData) {
      setSelectedComponentData(
        JSON.parse(JSON.stringify(originalComponentData)),
      );
      setIsConfigModified(false);
      resetAllSelections();
    }
  };

  const handleImageClick = (
    event: React.MouseEvent<HTMLDivElement>,
    calculateCoords: (
      event: React.MouseEvent<HTMLDivElement>,
    ) => Coordinate | null,
  ) => {
    const coordinates = calculateCoords(event);

    // Check if we're in drawing mode for masks
    if (isDrawingMode && drawingType === "mask") {
      maskHandlers.handleImageClick(coordinates);
      return;
    }

    // Check if we're in drawing mode for zones
    if (isDrawingMode && drawingType === "zone") {
      zoneHandlers.handleImageClick(coordinates);
    }
  };

  return {
    // Shared state
    selectedComponentData,
    originalComponentData,
    isConfigModified,
    availableLabels,
    setSelectedComponentData,
    setOriginalComponentData,
    setIsConfigModified,
    setAvailableLabels,

    // Shared handlers
    handleComponentChange,
    handleRevertConfig,
    resetAllSelections,
    handleImageClick,

    // Camera domain (OSD Text)
    ...osdTextHandlers,
    selectedOSDTextIndex,
    handleOSDTextClick,

    // Camera domain (Video Transform)
    ...videoTransformHandlers,
    selectedVideoTransformIndex,
    handleVideoTransformClick,

    // Motion detector domain (Mask)
    selectedMaskIndex: maskHandlers.selectedMaskIndex,
    maskDrawingType: drawingType,
    maskDrawingPoints: drawingPoints,
    maskPolygonName: maskHandlers.polygonName,
    setMaskPolygonName: maskHandlers.setPolygonName,
    handleMaskClick: maskHandlers.handleMaskClick,
    handleAddMask: maskHandlers.handleAddMask,
    handleCancelMaskDrawing: maskHandlers.handleCancelDrawing,
    handleCompleteMaskDrawing: maskHandlers.handleCompleteDrawing,
    handleDeleteMask: maskHandlers.handleDeleteMask,
    handleMaskPointDrag: maskHandlers.handlePointDrag,
    handleMaskPolygonDrag: maskHandlers.handlePolygonDrag,

    // Object detector domain (Label)
    ...objectDetectorLabelHandlers,

    // Face recognition domain (Label) - prefixed to avoid conflicts, simplified (no confidence/trigger_recording)
    showFaceRecognitionLabelDialog:
      faceRecognitionLabelHandlers.showLabelDialog,
    editingFaceRecognitionLabelIndex:
      faceRecognitionLabelHandlers.editingLabelIndex,
    editingFaceRecognitionLabel: faceRecognitionLabelHandlers.editingLabel,
    showAddFaceRecognitionLabelDialog:
      faceRecognitionLabelHandlers.showAddLabelDialog,
    newFaceRecognitionLabel: faceRecognitionLabelHandlers.newLabel,
    setEditingFaceRecognitionLabel:
      faceRecognitionLabelHandlers.setEditingLabel,
    setNewFaceRecognitionLabel: faceRecognitionLabelHandlers.setNewLabel,
    handleFaceRecognitionLabelClick:
      faceRecognitionLabelHandlers.handleLabelClick,
    handleAddFaceRecognitionLabel: faceRecognitionLabelHandlers.handleAddLabel,
    handleConfirmFaceRecognitionLabel:
      faceRecognitionLabelHandlers.handleConfirmLabel,
    handleConfirmAddFaceRecognitionLabel:
      faceRecognitionLabelHandlers.handleConfirmAddLabel,
    handleDeleteFaceRecognitionLabel:
      faceRecognitionLabelHandlers.handleDeleteLabel,
    handleCancelFaceRecognitionLabel:
      faceRecognitionLabelHandlers.handleCancelLabel,
    handleCancelAddFaceRecognitionLabel:
      faceRecognitionLabelHandlers.handleCancelAddLabel,

    // License plate recognition domain (Label) - prefixed to avoid conflicts, simplified (no confidence/trigger_recording)
    showLicensePlateRecognitionLabelDialog:
      licensePlateRecognitionLabelHandlers.showLabelDialog,
    editingLicensePlateRecognitionLabelIndex:
      licensePlateRecognitionLabelHandlers.editingLabelIndex,
    editingLicensePlateRecognitionLabel:
      licensePlateRecognitionLabelHandlers.editingLabel,
    showAddLicensePlateRecognitionLabelDialog:
      licensePlateRecognitionLabelHandlers.showAddLabelDialog,
    newLicensePlateRecognitionLabel:
      licensePlateRecognitionLabelHandlers.newLabel,
    setEditingLicensePlateRecognitionLabel:
      licensePlateRecognitionLabelHandlers.setEditingLabel,
    setNewLicensePlateRecognitionLabel:
      licensePlateRecognitionLabelHandlers.setNewLabel,
    handleLicensePlateRecognitionLabelClick:
      licensePlateRecognitionLabelHandlers.handleLabelClick,
    handleAddLicensePlateRecognitionLabel:
      licensePlateRecognitionLabelHandlers.handleAddLabel,
    handleConfirmLicensePlateRecognitionLabel:
      licensePlateRecognitionLabelHandlers.handleConfirmLabel,
    handleConfirmAddLicensePlateRecognitionLabel:
      licensePlateRecognitionLabelHandlers.handleConfirmAddLabel,
    handleDeleteLicensePlateRecognitionLabel:
      licensePlateRecognitionLabelHandlers.handleDeleteLabel,
    handleCancelLicensePlateRecognitionLabel:
      licensePlateRecognitionLabelHandlers.handleCancelLabel,
    handleCancelAddLicensePlateRecognitionLabel:
      licensePlateRecognitionLabelHandlers.handleCancelAddLabel,

    // Object detector domain (Zone)
    selectedZoneIndex: zoneHandlers.selectedZoneIndex,
    zoneDrawingType: drawingType,
    zoneDrawingPoints: drawingPoints,
    zoneShowNameDialog: zoneHandlers.showNameDialog,
    zonePolygonName: zoneHandlers.polygonName,
    setZonePolygonName: zoneHandlers.setPolygonName,
    showZoneLabelsDialog: zoneHandlers.showZoneLabelsDialog,
    showEditZoneNameDialog: zoneHandlers.showEditNameDialog,
    editingZoneIndex: zoneHandlers.editingZoneIndex,
    editingZoneLabels: zoneHandlers.editingZoneLabels,
    editingZoneName: zoneHandlers.editingZoneName,
    setEditingZoneLabels: zoneHandlers.setEditingZoneLabels,
    setEditingZoneName: zoneHandlers.setEditingZoneName,
    handleZoneClick: zoneHandlers.handleZoneClick,
    handleAddZone: zoneHandlers.handleAddZone,
    handleCancelZoneDrawing: zoneHandlers.handleCancelDrawing,
    handleCompleteZoneDrawing: zoneHandlers.handleCompleteDrawing,
    handleConfirmZoneName: zoneHandlers.handleConfirmName,
    handleCancelZoneName: zoneHandlers.handleCancelName,
    handleDeleteZone: zoneHandlers.handleDeleteZone,
    handleEditZoneName: zoneHandlers.handleEditZoneName,
    handleEditZoneLabels: zoneHandlers.handleEditZoneLabels,
    handleConfirmEditZoneName: zoneHandlers.handleConfirmEditName,
    handleCancelEditZoneName: zoneHandlers.handleCancelEditName,
    handleConfirmZoneLabels: zoneHandlers.handleConfirmZoneLabels,
    handleCancelZoneLabels: zoneHandlers.handleCancelZoneLabels,
    handleZonePointDrag: zoneHandlers.handlePointDrag,
    handleZonePolygonDrag: zoneHandlers.handlePolygonDrag,

    // Shared drawing mode state (zone and mask are mutually exclusive)
    isDrawingMode,
    drawingType,
    drawingPoints,
  };
}
