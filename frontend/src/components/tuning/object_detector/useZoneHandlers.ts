import { useState } from "react";

import { Coordinate } from "../shared/types";
import { dragPolygon, updatePolygonPoint } from "../shared/utils";
import { Zone, ZoneLabel } from "./types";

export function useZoneHandlers(
  selectedComponentData: any,
  setSelectedComponentData: (data: any) => void,
  setIsConfigModified: (modified: boolean) => void,
  isDrawingMode: boolean,
  setIsDrawingMode: (value: boolean) => void,
  drawingType: "zone" | "mask" | null,
  setDrawingType: (value: "zone" | "mask" | null) => void,
  drawingPoints: Coordinate[],
  setDrawingPoints: (points: Coordinate[]) => void,
  selectedZoneIndex: number | null,
  handleZoneClick: (index: number) => void,
) {
  const [showNameDialog, setShowNameDialog] = useState(false);
  const [polygonName, setPolygonName] = useState("");
  const [pendingPolygon, setPendingPolygon] = useState<{
    coordinates: Coordinate[];
    type: "zone";
  } | null>(null);
  const [showZoneLabelsDialog, setShowZoneLabelsDialog] = useState(false);
  const [editingZoneIndex, setEditingZoneIndex] = useState<number | null>(null);
  const [editingZoneLabels, setEditingZoneLabels] = useState<ZoneLabel[]>([]);
  const [showEditNameDialog, setShowEditNameDialog] = useState(false);
  const [editingZoneName, setEditingZoneName] = useState("");

  const handleAddZone = () => {
    setIsDrawingMode(true);
    setDrawingType("zone");
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

    setPendingPolygon({
      coordinates: drawingPoints,
      type: "zone",
    });
    setPolygonName("");
    setShowNameDialog(true);
  };

  const handleConfirmName = () => {
    if (!pendingPolygon) return;

    const newZone: Zone = {
      name: polygonName || "Zone",
      coordinates: pendingPolygon.coordinates,
    };

    const updatedData = { ...selectedComponentData };
    updatedData.zones = [...(selectedComponentData.zones || []), newZone];

    setSelectedComponentData(updatedData);
    setIsConfigModified(true);
    setIsDrawingMode(false);
    setDrawingPoints([]);
    setPendingPolygon(null);
    setShowNameDialog(false);
  };

  const handleCancelName = () => {
    setPendingPolygon(null);
    setShowNameDialog(false);
  };

  const handleDeleteZone = (index: number) => {
    if (!selectedComponentData?.zones) return;

    const updatedZones = selectedComponentData.zones.filter(
      (_: any, i: number) => i !== index,
    );

    setSelectedComponentData({
      ...selectedComponentData,
      zones: updatedZones,
    });
    setIsConfigModified(true);

    // Deselection is handled automatically by parent if needed
  };

  const handleEditZoneLabels = (index: number) => {
    const zone = selectedComponentData?.zones?.[index];
    if (!zone) return;

    setEditingZoneIndex(index);
    setEditingZoneLabels(zone.labels || []);
    setShowZoneLabelsDialog(true);
  };

  const handleEditZoneName = (index: number) => {
    const zone = selectedComponentData?.zones?.[index];
    if (!zone) return;

    setEditingZoneIndex(index);
    setEditingZoneName(zone.name || "");
    setShowEditNameDialog(true);
  };

  const handleConfirmEditName = () => {
    if (editingZoneIndex === null) return;

    const updatedZones = [...(selectedComponentData.zones || [])];
    updatedZones[editingZoneIndex] = {
      ...updatedZones[editingZoneIndex],
      name: editingZoneName || "Zone",
    };

    setSelectedComponentData({
      ...selectedComponentData,
      zones: updatedZones,
    });
    setIsConfigModified(true);
    setShowEditNameDialog(false);
    setEditingZoneIndex(null);
  };

  const handleCancelEditName = () => {
    setShowEditNameDialog(false);
    setEditingZoneIndex(null);
  };

  const handleConfirmZoneLabels = () => {
    if (editingZoneIndex === null) return;

    const updatedZones = [...(selectedComponentData.zones || [])];
    updatedZones[editingZoneIndex] = {
      ...updatedZones[editingZoneIndex],
      labels: editingZoneLabels,
    };

    setSelectedComponentData({
      ...selectedComponentData,
      zones: updatedZones,
    });
    setIsConfigModified(true);
    setShowZoneLabelsDialog(false);
  };

  const handleCancelZoneLabels = () => {
    setShowZoneLabelsDialog(false);
  };

  const handlePointDrag = (
    itemIndex: number,
    pointIndex: number,
    newX: number,
    newY: number,
  ) => {
    if (!selectedComponentData?.zones) return;

    const updatedZones = updatePolygonPoint(
      selectedComponentData.zones,
      itemIndex,
      pointIndex,
      newX,
      newY,
    );

    setSelectedComponentData({
      ...selectedComponentData,
      zones: updatedZones,
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
    if (!selectedComponentData?.zones) return;

    const updatedZones = dragPolygon(
      selectedComponentData.zones,
      itemIndex,
      deltaX,
      deltaY,
      imageWidth,
      imageHeight,
    );

    setSelectedComponentData({
      ...selectedComponentData,
      zones: updatedZones,
    });
    setIsConfigModified(true);
  };

  return {
    // States
    selectedZoneIndex,
    showNameDialog,
    polygonName,
    showZoneLabelsDialog,
    editingZoneIndex,
    editingZoneLabels,
    showEditNameDialog,
    editingZoneName,
    // Setters
    setPolygonName,
    setEditingZoneLabels,
    setEditingZoneName,
    // Handlers
    handleZoneClick,
    handleAddZone,
    handleCancelDrawing,
    handleImageClick,
    handleCompleteDrawing,
    handleConfirmName,
    handleCancelName,
    handleDeleteZone,
    handleEditZoneName,
    handleEditZoneLabels,
    handleConfirmEditName,
    handleCancelEditName,
    handleConfirmZoneLabels,
    handleCancelZoneLabels,
    handlePointDrag,
    handlePolygonDrag,
  };
}
