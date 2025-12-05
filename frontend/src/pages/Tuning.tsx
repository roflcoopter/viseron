import { Box, Grid, Typography } from "@mui/material";
import { useCallback, useState } from "react";
import { useParams } from "react-router-dom";
import ServerDown from "svg/undraw/server_down.svg?react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import { TuneComponentList } from "components/tuning/TuneComponentList";
import { TuneConfigPanel } from "components/tuning/TuneConfigPanel";
import { TuneSnapshot } from "components/tuning/TuneSnapshot";
import {
  parseOSDTextsFromComponentData,
  parseVideoTransformsFromComponentData,
} from "components/tuning/camera";
import { TuneOSDTextDialog } from "components/tuning/camera/OSDTextDialog";
import { VideoTransformDialog } from "components/tuning/camera/VideoTransformDialog";
import { updateMiscellaneousField } from "components/tuning/config/miscellaneousConfig";
import { getAvailableLabelsForAdd } from "components/tuning/object_detector";
import { ZoneLabelsDialog } from "components/tuning/object_detector/ZoneLabelsDialog";
import {
  LabelDialog,
  calculateImageCoordinates,
  useTuneHandlers,
} from "components/tuning/shared";
import { NameInputDialog } from "components/tuning/shared/NameInputDialog";
import { normalizeComponentData } from "components/tuning/utils";
import { useTitle } from "hooks/UseTitle";
import { useToast } from "hooks/UseToast";
import { useCameras } from "lib/api/cameras";
import { BASE_PATH } from "lib/api/client";
import { useTuneConfig, useUpdateTuneConfig } from "lib/api/tune";

function Tunes() {
  const { camera_identifier } = useParams<{ camera_identifier: string }>();
  const cameras = useCameras({});
  const toast = useToast();

  const [selectedTab, setSelectedTab] = useState(0);
  const [expandedComponent, setExpandedComponent] = useState<string | false>(
    false,
  );

  // Use custom hook for all tune handlers
  const tuneHandlers = useTuneHandlers();

  // Get camera from cameras data
  const camera = cameras.data?.[camera_identifier || ""];

  useTitle(camera ? `Camera Tuning | ${camera.name}` : "Camera Tuning");

  const generateSnapshotURL = useCallback(
    (width = null) =>
      `${BASE_PATH}/api/v1/camera/${camera_identifier}/snapshot?rand=${(
        Math.random() + 1
      )
        .toString(36)
        .substring(7)}${width ? `&width=${Math.trunc(width)}` : ""}`,
    [camera_identifier],
  );

  const [snapshotURL, setSnapshotURL] = useState({
    url: generateSnapshotURL(),
    disableSpinner: false,
    disableTransition: false,
    loading: true,
  });

  const updateSnapshot = useCallback(() => {
    setSnapshotURL((prevSnapshotURL) => {
      if (prevSnapshotURL.loading) {
        // Don't load new image if we are still loading
        return prevSnapshotURL;
      }
      return {
        ...prevSnapshotURL,
        url: generateSnapshotURL(),
        loading: true,
      };
    });
  }, [generateSnapshotURL]);

  // Fetch tune config using the API hook
  const tuneConfig = useTuneConfig({
    camera_identifier: camera_identifier || "",
  });

  // Mutation for updating tune config
  const updateTuneConfig = useUpdateTuneConfig(camera_identifier || "", {
    onSuccess: async () => {
      // Refetch tune config to get latest data from backend
      const refetchedData = await tuneConfig.refetch();

      // Update selectedComponentData with fresh data from backend
      if (refetchedData.data && expandedComponent) {
        const [domainName, componentName] = expandedComponent.split("-");
        const freshComponentData =
          refetchedData.data[domainName]?.[componentName];

        if (freshComponentData) {
          const { available_labels, ...dataWithoutAvailableLabels } =
            freshComponentData;

          // Update with fresh data from backend
          // If available_labels key doesn't exist or is null/undefined, set to empty array for text input mode
          tuneHandlers.setAvailableLabels?.(
            available_labels && Array.isArray(available_labels)
              ? available_labels
              : [],
          );

          // Parse OSD texts and video transforms if this is a camera component
          const componentDataWithParsed =
            domainName === "camera"
              ? {
                  ...dataWithoutAvailableLabels,
                  osd_texts: parseOSDTextsFromComponentData(
                    dataWithoutAvailableLabels,
                  ),
                  video_transforms: parseVideoTransformsFromComponentData(
                    dataWithoutAvailableLabels,
                  ),
                }
              : dataWithoutAvailableLabels;

          tuneHandlers.setSelectedComponentData({
            ...componentDataWithParsed,
            componentType: domainName,
            componentName,
          });

          // Update original data as well after successful save
          tuneHandlers.setOriginalComponentData({
            ...componentDataWithParsed,
            componentType: domainName,
            componentName,
          });
        }
      }

      tuneHandlers.setIsConfigModified(false);
      toast.success("Configuration saved successfully");
    },
    onError: (error) => {
      toast.error(error.message || "Failed to save configuration");
    },
  });

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setSelectedTab(newValue);
    // Reset selections when changing tabs
    setExpandedComponent(false);
    tuneHandlers.setSelectedComponentData(null);
    tuneHandlers.setOriginalComponentData(null);
    tuneHandlers.resetAllSelections();
    tuneHandlers.setIsConfigModified(false);
  };

  const getAvailableLabelsForAddWrapper = () => {
    const existingLabels =
      tuneHandlers.selectedComponentData?.labels?.map((l: any) =>
        typeof l === "string" ? l : l.label,
      ) || [];

    // Use available_labels from API (returns empty array if none, triggering text input mode)
    return getAvailableLabelsForAdd(
      existingLabels,
      tuneHandlers.availableLabels,
    );
  };

  const getAvailableLabelsForEditWrapper = (currentLabel: string) => {
    const existingLabels =
      tuneHandlers.selectedComponentData?.labels?.map((l: any) =>
        typeof l === "string" ? l : l.label,
      ) || [];

    // Filter out other labels, but keep the current label being edited
    const otherLabels = existingLabels.filter(
      (label: string) => label !== currentLabel,
    );

    // Use available_labels from API (returns empty array if none, triggering text input mode)
    return getAvailableLabelsForAdd(otherLabels, tuneHandlers.availableLabels);
  };

  const handleAddLabelWrapper = () => {
    const available = getAvailableLabelsForAddWrapper();

    // If no available labels (text input mode), set empty string as initial value
    const initialLabel = available.length > 0 ? available[0] : "";

    if (
      tuneHandlers.selectedComponentData?.componentType === "face_recognition"
    ) {
      tuneHandlers.handleAddFaceRecognitionLabel(initialLabel);
    } else if (
      tuneHandlers.selectedComponentData?.componentType ===
      "license_plate_recognition"
    ) {
      tuneHandlers.handleAddLicensePlateRecognitionLabel(initialLabel);
    } else {
      tuneHandlers.handleAddLabel(initialLabel);
    }
  };

  const handleMiscellaneousFieldChange = (key: string, value: any) => {
    if (!tuneHandlers.selectedComponentData) return;

    const updatedData = updateMiscellaneousField(
      tuneHandlers.selectedComponentData,
      key,
      value,
    );

    tuneHandlers.setSelectedComponentData(updatedData);
    tuneHandlers.setIsConfigModified(true);
  };

  const getDomainTabs = () => {
    if (!tuneConfig.data) return [];
    return Object.keys(tuneConfig.data).map((domainName) => ({
      label: domainName.replace(/_/g, " "),
      value: domainName,
    }));
  };

  const getCurrentDomainData = () => {
    if (!tuneConfig.data) return null;
    const domains = Object.keys(tuneConfig.data);
    const currentDomain = domains[selectedTab];
    return tuneConfig.data[currentDomain];
  };

  const getCurrentDomainName = () => {
    if (!tuneConfig.data) return "";
    const domains = Object.keys(tuneConfig.data);
    return domains[selectedTab];
  };

  const handleSaveConfig = async () => {
    if (!tuneHandlers.selectedComponentData || !camera_identifier) return;
    if (!expandedComponent || typeof expandedComponent !== "string") return;

    const component = expandedComponent.split("-")[1];
    if (!component) return;

    updateTuneConfig.mutate({
      domain: getCurrentDomainName(),
      component,
      data: normalizeComponentData(tuneHandlers.selectedComponentData),
    });
  };

  if (cameras.isPending || tuneConfig.isPending) {
    return <Loading text="Loading Camera Tuning" />;
  }

  if (tuneConfig.isError) {
    return (
      <ErrorMessage
        text="Error loading configuration"
        subtext={tuneConfig.error?.message}
        image={
          <ServerDown width={150} height={150} role="img" aria-label="Void" />
        }
      />
    );
  }

  if (!camera) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        height="100vh"
      >
        <Typography>Camera not found: {camera_identifier}</Typography>
      </Box>
    );
  }

  return (
    <>
      {/* Zone Name Input Dialog */}
      <NameInputDialog
        open={tuneHandlers.zoneShowNameDialog}
        polygonType="zone"
        polygonName={tuneHandlers.zonePolygonName}
        onPolygonNameChange={tuneHandlers.setZonePolygonName}
        onConfirm={tuneHandlers.handleConfirmZoneName}
        onCancel={tuneHandlers.handleCancelZoneName}
      />

      {/* Edit Zone Name Dialog */}
      <NameInputDialog
        open={tuneHandlers.showEditZoneNameDialog}
        polygonType="zone"
        polygonName={tuneHandlers.editingZoneName}
        onPolygonNameChange={tuneHandlers.setEditingZoneName}
        onConfirm={tuneHandlers.handleConfirmEditZoneName}
        onCancel={tuneHandlers.handleCancelEditZoneName}
      />

      {/* Label Edit Dialog */}
      <LabelDialog
        open={tuneHandlers.showLabelDialog}
        isEdit
        label={tuneHandlers.editingLabel}
        confidence={tuneHandlers.editingConfidence}
        triggerRecording={tuneHandlers.editingTriggerRecording}
        availableLabels={getAvailableLabelsForEditWrapper(
          tuneHandlers.editingLabel,
        )}
        onLabelChange={tuneHandlers.setEditingLabel}
        onConfidenceChange={tuneHandlers.setEditingConfidence}
        onTriggerRecordingChange={tuneHandlers.setEditingTriggerRecording}
        onConfirm={tuneHandlers.handleConfirmLabel}
        onCancel={tuneHandlers.handleCancelLabel}
      />

      {/* Add Label Dialog */}
      <LabelDialog
        open={tuneHandlers.showAddLabelDialog}
        isEdit={false}
        label={tuneHandlers.newLabel}
        confidence={tuneHandlers.newConfidence}
        triggerRecording={tuneHandlers.newTriggerRecording}
        availableLabels={getAvailableLabelsForAddWrapper()}
        onLabelChange={tuneHandlers.setNewLabel}
        onConfidenceChange={tuneHandlers.setNewConfidence}
        onTriggerRecordingChange={tuneHandlers.setNewTriggerRecording}
        onConfirm={tuneHandlers.handleConfirmAddLabel}
        onCancel={tuneHandlers.handleCancelAddLabel}
      />

      {/* Face Recognition Label Edit Dialog */}
      <LabelDialog
        open={tuneHandlers.showFaceRecognitionLabelDialog}
        isEdit
        label={tuneHandlers.editingFaceRecognitionLabel}
        availableLabels={getAvailableLabelsForEditWrapper(
          tuneHandlers.editingFaceRecognitionLabel,
        )}
        existingLabels={
          tuneHandlers.selectedComponentData?.labels?.map((l: any) =>
            typeof l === "string" ? l : l.label,
          ) || []
        }
        originalLabel={tuneHandlers.editingFaceRecognitionLabel}
        onLabelChange={tuneHandlers.setEditingFaceRecognitionLabel}
        onConfirm={tuneHandlers.handleConfirmFaceRecognitionLabel}
        onCancel={tuneHandlers.handleCancelFaceRecognitionLabel}
        showConfidence={false}
        showTriggerRecording={false}
        useTextInput
        inputType="face"
      />

      {/* Face Recognition Add Label Dialog */}
      <LabelDialog
        open={tuneHandlers.showAddFaceRecognitionLabelDialog}
        isEdit={false}
        label={tuneHandlers.newFaceRecognitionLabel}
        availableLabels={getAvailableLabelsForAddWrapper()}
        existingLabels={
          tuneHandlers.selectedComponentData?.labels?.map((l: any) =>
            typeof l === "string" ? l : l.label,
          ) || []
        }
        onLabelChange={tuneHandlers.setNewFaceRecognitionLabel}
        onConfirm={tuneHandlers.handleConfirmAddFaceRecognitionLabel}
        onCancel={tuneHandlers.handleCancelAddFaceRecognitionLabel}
        showConfidence={false}
        showTriggerRecording={false}
        useTextInput
        inputType="face"
      />

      {/* License Plate Recognition Label Edit Dialog */}
      <LabelDialog
        open={tuneHandlers.showLicensePlateRecognitionLabelDialog}
        isEdit
        label={tuneHandlers.editingLicensePlateRecognitionLabel}
        availableLabels={getAvailableLabelsForEditWrapper(
          tuneHandlers.editingLicensePlateRecognitionLabel,
        )}
        existingLabels={
          tuneHandlers.selectedComponentData?.labels?.map((l: any) =>
            typeof l === "string" ? l : l.label,
          ) || []
        }
        originalLabel={tuneHandlers.editingLicensePlateRecognitionLabel}
        onLabelChange={tuneHandlers.setEditingLicensePlateRecognitionLabel}
        onConfirm={tuneHandlers.handleConfirmLicensePlateRecognitionLabel}
        onCancel={tuneHandlers.handleCancelLicensePlateRecognitionLabel}
        showConfidence={false}
        showTriggerRecording={false}
        useTextInput
        inputType="plate"
      />

      {/* License Plate Recognition Add Label Dialog */}
      <LabelDialog
        open={tuneHandlers.showAddLicensePlateRecognitionLabelDialog}
        isEdit={false}
        label={tuneHandlers.newLicensePlateRecognitionLabel}
        availableLabels={getAvailableLabelsForAddWrapper()}
        existingLabels={
          tuneHandlers.selectedComponentData?.labels?.map((l: any) =>
            typeof l === "string" ? l : l.label,
          ) || []
        }
        onLabelChange={tuneHandlers.setNewLicensePlateRecognitionLabel}
        onConfirm={tuneHandlers.handleConfirmAddLicensePlateRecognitionLabel}
        onCancel={tuneHandlers.handleCancelAddLicensePlateRecognitionLabel}
        showConfidence={false}
        showTriggerRecording={false}
        useTextInput
        inputType="plate"
      />

      {/* Zone Labels Dialog */}
      <ZoneLabelsDialog
        open={tuneHandlers.showZoneLabelsDialog}
        zoneLabels={tuneHandlers.editingZoneLabels}
        availableLabels={tuneHandlers.availableLabels}
        onZoneLabelsChange={tuneHandlers.setEditingZoneLabels}
        onConfirm={tuneHandlers.handleConfirmZoneLabels}
        onCancel={tuneHandlers.handleCancelZoneLabels}
      />

      {/* OSD Text Dialog */}
      <TuneOSDTextDialog
        open={tuneHandlers.showOSDTextDialog}
        isEdit={tuneHandlers.editingOSDTextIndex !== null}
        osdType={tuneHandlers.osdTextType}
        textType={tuneHandlers.osdTextContent}
        customText={tuneHandlers.osdCustomText}
        position={tuneHandlers.osdPosition}
        paddingX={tuneHandlers.osdPaddingX}
        paddingY={tuneHandlers.osdPaddingY}
        fontSize={tuneHandlers.osdFontSize}
        fontColorHex={tuneHandlers.osdFontColorHex}
        boxColorHex={tuneHandlers.osdBoxColorHex}
        boxOpacity={tuneHandlers.osdBoxOpacity}
        onOSDTypeChange={tuneHandlers.setOSDTextType}
        onTextTypeChange={tuneHandlers.setOSDTextContent}
        onCustomTextChange={tuneHandlers.setOSDCustomText}
        onPositionChange={tuneHandlers.setOSDPosition}
        onPaddingXChange={tuneHandlers.setOSDPaddingX}
        onPaddingYChange={tuneHandlers.setOSDPaddingY}
        onFontSizeChange={tuneHandlers.setOSDFontSize}
        onFontColorChange={tuneHandlers.setOSDFontColorHex}
        onBoxColorChange={tuneHandlers.setOSDBoxColorHex}
        onBoxOpacityChange={tuneHandlers.setOSDBoxOpacity}
        onConfirm={tuneHandlers.handleConfirmOSDText}
        onCancel={() => tuneHandlers.setShowOSDTextDialog(false)}
      />

      {/* Video Transform Dialog */}
      <VideoTransformDialog
        open={tuneHandlers.showVideoTransformDialog}
        isEdit={tuneHandlers.editingVideoTransformIndex !== null}
        transformTarget={tuneHandlers.videoTransformTarget}
        transformType={tuneHandlers.videoTransformType}
        onTransformTargetChange={tuneHandlers.setVideoTransformTarget}
        onTransformTypeChange={tuneHandlers.setVideoTransformType}
        onConfirm={tuneHandlers.handleConfirmVideoTransform}
        onCancel={() => tuneHandlers.setShowVideoTransformDialog(false)}
      />

      <Box
        sx={{
          height: { md: "75vh" },
          display: "flex",
          flexDirection: "column",
          paddingY: 0.5,
          paddingX: { xs: 1, md: 2 },
        }}
      >
        <Grid container spacing={1} sx={{ flexGrow: 1, overflow: "hidden" }}>
          {/* Center Snapshot - First on mobile, middle on desktop */}
          <Grid size={{ xs: 12, md: 6.5 }} sx={{ order: { xs: 0, md: 1 } }}>
            <TuneSnapshot
              camera={camera}
              snapshotURL={snapshotURL}
              isDrawingMode={tuneHandlers.isDrawingMode}
              selectedComponentData={tuneHandlers.selectedComponentData}
              selectedZoneIndex={tuneHandlers.selectedZoneIndex}
              selectedMaskIndex={tuneHandlers.selectedMaskIndex}
              selectedOSDTextIndex={tuneHandlers.selectedOSDTextIndex}
              selectedVideoTransformIndex={
                tuneHandlers.selectedVideoTransformIndex
              }
              drawingType={tuneHandlers.drawingType}
              drawingPoints={tuneHandlers.drawingPoints}
              onSnapshotLoad={() => {
                setSnapshotURL((prevSnapshotURL) => ({
                  ...prevSnapshotURL,
                  disableSpinner: true,
                  disableTransition: true,
                  loading: false,
                }));
              }}
              onSnapshotError={() => {
                setSnapshotURL((prevSnapshotURL) => ({
                  ...prevSnapshotURL,
                  disableSpinner: false,
                  disableTransition: false,
                  loading: false,
                }));
              }}
              onImageClick={(e) =>
                tuneHandlers.handleImageClick(e, (event) =>
                  calculateImageCoordinates(event, camera),
                )
              }
              onUpdateSnapshot={updateSnapshot}
              onPointDrag={(type, itemIndex, pointIndex, newX, newY) => {
                if (type === "zone") {
                  tuneHandlers.handleZonePointDrag(
                    itemIndex,
                    pointIndex,
                    newX,
                    newY,
                  );
                } else {
                  tuneHandlers.handleMaskPointDrag(
                    itemIndex,
                    pointIndex,
                    newX,
                    newY,
                  );
                }
              }}
              onPolygonDrag={(
                type,
                itemIndex,
                deltaX,
                deltaY,
                imageWidth,
                imageHeight,
              ) => {
                if (type === "zone") {
                  tuneHandlers.handleZonePolygonDrag(
                    itemIndex,
                    deltaX,
                    deltaY,
                    imageWidth,
                    imageHeight,
                  );
                } else {
                  tuneHandlers.handleMaskPolygonDrag(
                    itemIndex,
                    deltaX,
                    deltaY,
                    imageWidth,
                    imageHeight,
                  );
                }
              }}
            />
          </Grid>

          {/* Left Card - Second on mobile, first on desktop */}
          <Grid size={{ xs: 12, md: 2.5 }} sx={{ order: { xs: 1, md: 0 } }}>
            <TuneConfigPanel
              selectedComponentData={tuneHandlers.selectedComponentData}
              isDrawingMode={tuneHandlers.isDrawingMode}
              drawingType={tuneHandlers.drawingType}
              drawingPoints={tuneHandlers.drawingPoints}
              selectedZoneIndex={tuneHandlers.selectedZoneIndex}
              selectedMaskIndex={tuneHandlers.selectedMaskIndex}
              selectedOSDTextIndex={tuneHandlers.selectedOSDTextIndex}
              selectedVideoTransformIndex={
                tuneHandlers.selectedVideoTransformIndex
              }
              isConfigModified={tuneHandlers.isConfigModified}
              isSaving={updateTuneConfig.isPending}
              onLabelClick={(index) => {
                if (
                  tuneHandlers.selectedComponentData?.componentType ===
                  "face_recognition"
                ) {
                  tuneHandlers.handleFaceRecognitionLabelClick(index);
                } else if (
                  tuneHandlers.selectedComponentData?.componentType ===
                  "license_plate_recognition"
                ) {
                  tuneHandlers.handleLicensePlateRecognitionLabelClick(index);
                } else {
                  tuneHandlers.handleLabelClick(index);
                }
              }}
              onAddLabel={handleAddLabelWrapper}
              onZoneClick={tuneHandlers.handleZoneClick}
              onAddZone={tuneHandlers.handleAddZone}
              onMaskClick={tuneHandlers.handleMaskClick}
              onAddMask={tuneHandlers.handleAddMask}
              onCompleteDrawing={() => {
                if (tuneHandlers.zoneDrawingType === "zone") {
                  tuneHandlers.handleCompleteZoneDrawing();
                } else if (tuneHandlers.maskDrawingType === "mask") {
                  tuneHandlers.handleCompleteMaskDrawing();
                }
              }}
              onCancelDrawing={() => {
                if (tuneHandlers.zoneDrawingType === "zone") {
                  tuneHandlers.handleCancelZoneDrawing();
                } else if (tuneHandlers.maskDrawingType === "mask") {
                  tuneHandlers.handleCancelMaskDrawing();
                }
              }}
              onSaveConfig={handleSaveConfig}
              onRevertConfig={tuneHandlers.handleRevertConfig}
              onDeleteLabel={(index) => {
                if (
                  tuneHandlers.selectedComponentData?.componentType ===
                  "face_recognition"
                ) {
                  tuneHandlers.handleDeleteFaceRecognitionLabel(index);
                } else if (
                  tuneHandlers.selectedComponentData?.componentType ===
                  "license_plate_recognition"
                ) {
                  tuneHandlers.handleDeleteLicensePlateRecognitionLabel(index);
                } else {
                  tuneHandlers.handleDeleteLabel(index);
                }
              }}
              onDeleteZone={tuneHandlers.handleDeleteZone}
              onDeleteMask={tuneHandlers.handleDeleteMask}
              onEditZoneName={tuneHandlers.handleEditZoneName}
              onEditZoneLabels={tuneHandlers.handleEditZoneLabels}
              onAddOSDText={tuneHandlers.handleAddOSDText}
              onOSDTextClick={tuneHandlers.handleOSDTextClick}
              onEditOSDText={tuneHandlers.handleEditOSDText}
              onDeleteOSDText={tuneHandlers.handleDeleteOSDText}
              onAddVideoTransform={tuneHandlers.handleAddVideoTransform}
              onVideoTransformClick={tuneHandlers.handleVideoTransformClick}
              onEditVideoTransform={tuneHandlers.handleEditVideoTransform}
              onDeleteVideoTransform={tuneHandlers.handleDeleteVideoTransform}
              onMiscellaneousFieldChange={handleMiscellaneousFieldChange}
              currentDomainName={getCurrentDomainName()}
            />
          </Grid>

          {/* Right Card with Tabs - Third on mobile, last on desktop */}
          <Grid size={{ xs: 12, md: 3 }} sx={{ order: { xs: 2, md: 2 } }}>
            <TuneComponentList
              selectedTab={selectedTab}
              expandedComponent={expandedComponent}
              domainTabs={getDomainTabs()}
              currentDomainData={getCurrentDomainData()}
              currentDomainName={getCurrentDomainName()}
              onTabChange={handleTabChange}
              onComponentChange={(domain, component, data) =>
                tuneHandlers.handleComponentChange(
                  domain,
                  component,
                  data,
                  expandedComponent,
                  setExpandedComponent,
                )
              }
            />
          </Grid>
        </Grid>
      </Box>
    </>
  );
}

export default Tunes;
