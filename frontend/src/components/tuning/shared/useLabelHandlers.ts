import { useState } from "react";

interface UseLabelHandlersOptions {
  hasConfidence?: boolean;
  hasTriggerRecording?: boolean;
}

export function useLabelHandlers(
  selectedComponentData: any,
  setSelectedComponentData: (data: any) => void,
  setIsConfigModified: (modified: boolean) => void,
  _availableLabels: string[],
  options: UseLabelHandlersOptions = {},
) {
  const { hasConfidence = true } = options;

  const [showLabelDialog, setShowLabelDialog] = useState(false);
  const [editingLabelIndex, setEditingLabelIndex] = useState<number | null>(
    null,
  );
  const [editingLabel, setEditingLabel] = useState("");
  const [editingConfidence, setEditingConfidence] = useState<number>(0.8);
  const [editingTriggerRecording, setEditingTriggerRecording] = useState(true);
  const [showAddLabelDialog, setShowAddLabelDialog] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newConfidence, setNewConfidence] = useState<number>(0.8);
  const [newTriggerRecording, setNewTriggerRecording] = useState(true);

  const handleLabelClick = (index: number) => {
    const label = selectedComponentData?.labels?.[index];
    if (!label) return;

    setEditingLabelIndex(index);

    if (hasConfidence) {
      // object_detector: label is {label, confidence, trigger_event_recording}
      setEditingLabel(label.label);
      setEditingConfidence(label.confidence);
      setEditingTriggerRecording(label.trigger_event_recording ?? true);
    } else {
      // face_recognition/license_plate_recognition: label is just a string
      setEditingLabel(label);
    }

    setShowLabelDialog(true);
  };

  const handleAddLabel = (firstAvailableLabel: string) => {
    // For text input types (face_recognition, license_plate_recognition),
    // start with empty string. For select types (object_detector), use first available.
    setNewLabel(hasConfidence ? firstAvailableLabel : "");
    if (hasConfidence) {
      setNewConfidence(0.8);
      setNewTriggerRecording(true);
    }
    setShowAddLabelDialog(true);
  };

  const handleConfirmLabel = () => {
    if (editingLabelIndex === null) return;

    const updatedLabels = [...(selectedComponentData.labels || [])];

    if (hasConfidence) {
      // object_detector: store as object
      updatedLabels[editingLabelIndex] = {
        label: editingLabel,
        confidence: editingConfidence,
        trigger_event_recording: editingTriggerRecording,
      };
    } else {
      // face_recognition/license_plate_recognition: store as string
      updatedLabels[editingLabelIndex] = editingLabel;
    }

    setSelectedComponentData({
      ...selectedComponentData,
      labels: updatedLabels,
    });
    setIsConfigModified(true);
    setShowLabelDialog(false);
  };

  const handleConfirmAddLabel = () => {
    let newLabelItem: any;

    if (hasConfidence) {
      // object_detector: store as object
      newLabelItem = {
        label: newLabel,
        confidence: newConfidence,
        trigger_event_recording: newTriggerRecording,
      };
    } else {
      // face_recognition/license_plate_recognition: store as string
      newLabelItem = newLabel;
    }

    setSelectedComponentData({
      ...selectedComponentData,
      labels: [...(selectedComponentData.labels || []), newLabelItem],
    });
    setIsConfigModified(true);
    setShowAddLabelDialog(false);
  };

  const handleDeleteLabel = (index: number) => {
    if (!selectedComponentData?.labels) return;

    const updatedLabels = selectedComponentData.labels.filter(
      (_: any, i: number) => i !== index,
    );

    setSelectedComponentData({
      ...selectedComponentData,
      labels: updatedLabels,
    });
    setIsConfigModified(true);
  };

  const handleCancelLabel = () => {
    setShowLabelDialog(false);
  };

  const handleCancelAddLabel = () => {
    setShowAddLabelDialog(false);
  };

  return {
    // States
    showLabelDialog,
    editingLabelIndex,
    editingLabel,
    editingConfidence,
    editingTriggerRecording,
    showAddLabelDialog,
    newLabel,
    newConfidence,
    newTriggerRecording,
    // Setters
    setEditingLabel,
    setEditingConfidence,
    setEditingTriggerRecording,
    setNewLabel,
    setNewConfidence,
    setNewTriggerRecording,
    // Handlers
    handleLabelClick,
    handleAddLabel,
    handleConfirmLabel,
    handleConfirmAddLabel,
    handleDeleteLabel,
    handleCancelLabel,
    handleCancelAddLabel,
  };
}
