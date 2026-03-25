import { useState } from "react";

import { Coordinate, Mask } from "./types";
import { dragPolygon, updatePolygonPoint } from "./utils";

export function useMaskHandlers(
  selectedComponentData: any,
  setSelectedComponentData: (data: any) => void,
  setIsConfigModified: (modified: boolean) => void,
  isDrawingMode: boolean,
  setIsDrawingMode: (value: boolean) => void,
  drawingType: "zone" | "mask" | null,
  setDrawingType: (value: "zone" | "mask" | null) => void,
  drawingPoints: Coordinate[],
  setDrawingPoints: (points: Coordinate[]) => void,
  selectedMaskIndex: number | null,
  handleMaskClick: (index: number) => void,
) {
  const [polygonName, setPolygonName] = useState("");

  const handleAddMask = () => {
    setIsDrawingMode(true);
    setDrawingType("mask");
    setDrawingPoints([]);
  };

  const handleCancelDrawing = () => {
    setIsDrawingMode(false);
    setDrawingType(null);
    setDrawingPoints([]);
  };

  const handleImageClick = (coordinates: Coordinate | null) => {
    if (!isDrawingMode || !coordinates) return;

    setDrawingPoints([...drawingPoints, coordinates]);
  };

  const handleCompleteDrawing = () => {
    if (drawingPoints.length < 3) return;

    // Mask doesn't need name dialog - save directly without name
    const newMask: Mask = {
      coordinates: drawingPoints,
    };

    const updatedData = { ...selectedComponentData };
    updatedData.mask = [...(selectedComponentData.mask || []), newMask];

    setSelectedComponentData(updatedData);
    setIsConfigModified(true);
    setIsDrawingMode(false);
    setDrawingType(null);
    setDrawingPoints([]);
  };

  const handleDeleteMask = (index: number) => {
    if (!selectedComponentData?.mask) return;

    const updatedMasks = selectedComponentData.mask.filter(
      (_: any, i: number) => i !== index,
    );

    setSelectedComponentData({
      ...selectedComponentData,
      mask: updatedMasks,
    });
    setIsConfigModified(true);

    // Deselection is handled automatically by parent if needed
  };

  const handlePointDrag = (
    itemIndex: number,
    pointIndex: number,
    newX: number,
    newY: number,
  ) => {
    if (!selectedComponentData?.mask) return;

    const updatedMasks = updatePolygonPoint(
      selectedComponentData.mask,
      itemIndex,
      pointIndex,
      newX,
      newY,
    );

    setSelectedComponentData({
      ...selectedComponentData,
      mask: updatedMasks,
    });
    setIsConfigModified(true);
  };

  const handlePolygonDrag = (
    itemIndex: number,
    deltaX: number,
    deltaY: number,
    imageWidth: number,
    imageHeight: number,
  ) => {
    if (!selectedComponentData?.mask) return;

    const updatedMasks = dragPolygon(
      selectedComponentData.mask,
      itemIndex,
      deltaX,
      deltaY,
      imageWidth,
      imageHeight,
    );

    setSelectedComponentData({
      ...selectedComponentData,
      mask: updatedMasks,
    });
    setIsConfigModified(true);
  };

  return {
    // States
    selectedMaskIndex,
    polygonName,
    // Setters
    setPolygonName,
    // Handlers
    handleMaskClick,
    handleAddMask,
    handleCancelDrawing,
    handleImageClick,
    handleCompleteDrawing,
    handleDeleteMask,
    handlePointDrag,
    handlePolygonDrag,
  };
}
