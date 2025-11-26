import { useState } from "react";

import {
  VideoTransform,
  VideoTransformTarget,
  VideoTransformType,
} from "./types";

export function useVideoTransformHandlers(
  selectedComponentData: any,
  setSelectedComponentData: (data: any) => void,
  setIsConfigModified: (modified: boolean) => void,
) {
  const [showVideoTransformDialog, setShowVideoTransformDialog] =
    useState(false);
  const [editingVideoTransformIndex, setEditingVideoTransformIndex] = useState<
    number | null
  >(null);
  const [videoTransformTarget, setVideoTransformTarget] =
    useState<VideoTransformTarget>("camera");
  const [videoTransformType, setVideoTransformType] =
    useState<VideoTransformType>("hflip");

  const handleAddVideoTransform = (type: VideoTransformTarget) => {
    setVideoTransformTarget(type);
    setVideoTransformType("hflip");
    setEditingVideoTransformIndex(null);
    setShowVideoTransformDialog(true);
  };

  const handleEditVideoTransform = (index: number) => {
    const transform = selectedComponentData?.video_transforms?.[index];
    if (!transform) return;

    setVideoTransformTarget(transform.type);
    setVideoTransformType(transform.transform);
    setEditingVideoTransformIndex(index);
    setShowVideoTransformDialog(true);
  };

  const handleVideoTransformClick = (index: number) => {
    // For now, clicking opens edit dialog
    handleEditVideoTransform(index);
  };

  const handleConfirmVideoTransform = () => {
    const newTransform: VideoTransform = {
      id: `transform-${Date.now()}-${Math.random()}`,
      type: videoTransformTarget,
      transform: videoTransformType,
    };

    let updatedTransforms: VideoTransform[];

    if (editingVideoTransformIndex !== null) {
      // Edit existing transform
      updatedTransforms = [...(selectedComponentData.video_transforms || [])];
      updatedTransforms[editingVideoTransformIndex] = newTransform;
    } else {
      // Add new transform
      updatedTransforms = [
        ...(selectedComponentData.video_transforms || []),
        newTransform,
      ];
    }

    setSelectedComponentData({
      ...selectedComponentData,
      video_transforms: updatedTransforms,
    });
    setIsConfigModified(true);
    setShowVideoTransformDialog(false);
  };

  const handleDeleteVideoTransform = (index: number) => {
    if (!selectedComponentData?.video_transforms) return;

    const updatedTransforms = selectedComponentData.video_transforms.filter(
      (_: any, i: number) => i !== index,
    );

    setSelectedComponentData({
      ...selectedComponentData,
      video_transforms: updatedTransforms,
    });
    setIsConfigModified(true);
  };

  return {
    // States
    showVideoTransformDialog,
    editingVideoTransformIndex,
    videoTransformTarget,
    videoTransformType,
    // Setters
    setShowVideoTransformDialog,
    setVideoTransformTarget,
    setVideoTransformType,
    // Handlers
    handleAddVideoTransform,
    handleVideoTransformClick,
    handleEditVideoTransform,
    handleConfirmVideoTransform,
    handleDeleteVideoTransform,
  };
}
