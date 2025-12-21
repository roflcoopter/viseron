import { useState } from "react";

import { OSDText } from "./types";

export function useOSDTextHandlers(
  selectedComponentData: any,
  setSelectedComponentData: (data: any) => void,
  setIsConfigModified: (modified: boolean) => void,
) {
  const [showOSDTextDialog, setShowOSDTextDialog] = useState(false);
  const [editingOSDTextIndex, setEditingOSDTextIndex] = useState<number | null>(
    null,
  );
  const [osdTextType, setOSDTextType] = useState<"camera" | "recorder">(
    "camera",
  );
  const [osdTextContent, setOSDTextContent] = useState<
    "timestamp" | "custom" | "text"
  >("timestamp");
  const [osdCustomText, setOSDCustomText] = useState("");
  const [osdPosition, setOSDPosition] = useState<
    "top-left" | "top-right" | "bottom-left" | "bottom-right"
  >("top-left");
  const [osdPaddingX, setOSDPaddingX] = useState(10);
  const [osdPaddingY, setOSDPaddingY] = useState(10);
  const [osdFontSize, setOSDFontSize] = useState(20);
  const [osdFontColorHex, setOSDFontColorHex] = useState("#ffffff");
  const [osdBoxColorHex, setOSDBoxColorHex] = useState("#000000");
  const [osdBoxOpacity, setOSDBoxOpacity] = useState(0);

  const handleAddOSDText = (type: "camera" | "recorder") => {
    setEditingOSDTextIndex(null);
    setOSDTextType(type);
    setOSDTextContent("timestamp");
    setOSDCustomText("");
    setOSDPosition("top-left");
    setOSDPaddingX(10);
    setOSDPaddingY(10);
    setOSDFontSize(20);
    setOSDFontColorHex("#ffffff");
    setOSDBoxColorHex("#000000");
    setOSDBoxOpacity(0);
    setShowOSDTextDialog(true);
  };

  // Helper to convert CSS color name or FFmpeg color to hex
  const parseColorToHex = (color: string): string => {
    // If it's already hex, return it
    if (color.startsWith("#")) return color;

    // If it's FFmpeg format (0xRRGGBB), convert to hex
    if (color.startsWith("0x")) {
      const hex = color.replace("0x", "").substring(0, 6);
      return `#${hex}`;
    }

    // Common color names to hex
    const colorMap: Record<string, string> = {
      white: "#ffffff",
      black: "#000000",
      red: "#ff0000",
      green: "#00ff00",
      blue: "#0000ff",
      yellow: "#ffff00",
      cyan: "#00ffff",
      magenta: "#ff00ff",
    };

    return colorMap[color.toLowerCase()] || "#ffffff";
  };

  // Helper to parse FFmpeg boxcolor format
  const parseBoxColor = (
    boxColor: string,
  ): { hex: string; opacity: number } => {
    const parts = boxColor.split("@");
    const hexPart = parts[0];
    const opacity = parts.length > 1 ? parseFloat(parts[1]) : 0;

    const hex = hexPart.startsWith("0x")
      ? `#${hexPart.substring(2, 8)}`
      : "#000000";

    return { hex, opacity };
  };

  const handleEditOSDText = (index: number) => {
    const osdText = selectedComponentData?.osd_texts?.[index];
    if (!osdText) return;

    setEditingOSDTextIndex(index);
    setOSDTextType(osdText.type);
    setOSDTextContent(osdText.textType);
    setOSDCustomText(osdText.customText || "");
    setOSDPosition(osdText.position);
    setOSDPaddingX(osdText.paddingX);
    setOSDPaddingY(osdText.paddingY);
    setOSDFontSize(osdText.fontSize);

    // Parse font color
    setOSDFontColorHex(parseColorToHex(osdText.fontColor || "white"));

    // Parse box color
    const { hex, opacity } = parseBoxColor(osdText.boxColor || "0x00000000@0");
    setOSDBoxColorHex(hex);
    setOSDBoxOpacity(opacity);

    setShowOSDTextDialog(true);
  };

  const handleDeleteOSDText = (index: number) => {
    if (!selectedComponentData?.osd_texts) return;

    const updatedOSDTexts = selectedComponentData.osd_texts.filter(
      (_: any, i: number) => i !== index,
    );

    const updatedData = { ...selectedComponentData };
    updatedData.osd_texts = updatedOSDTexts;

    setSelectedComponentData(updatedData);
    setIsConfigModified(true);
  };

  const handleConfirmOSDText = () => {
    // Convert hex to FFmpeg format
    const fontColor = osdFontColorHex; // Can use hex directly
    const boxColor = `0x${osdBoxColorHex.replace("#", "")}00@${osdBoxOpacity}`; // Add alpha channel (00) + opacity

    const newOSDText: OSDText = {
      id:
        editingOSDTextIndex !== null
          ? selectedComponentData.osd_texts[editingOSDTextIndex].id
          : `osd-${Date.now()}-${Math.random()}`,
      type: osdTextType,
      textType: osdTextContent,
      customText: osdCustomText,
      position: osdPosition,
      paddingX: osdPaddingX,
      paddingY: osdPaddingY,
      fontSize: osdFontSize,
      fontColor,
      boxColor,
    };

    const updatedData = { ...selectedComponentData };

    if (editingOSDTextIndex !== null) {
      // Edit existing OSD text
      updatedData.osd_texts = [...selectedComponentData.osd_texts];
      updatedData.osd_texts[editingOSDTextIndex] = newOSDText;
    } else {
      // Add new OSD text
      updatedData.osd_texts = [
        ...(selectedComponentData.osd_texts || []),
        newOSDText,
      ];
    }

    setSelectedComponentData(updatedData);
    setIsConfigModified(true);
    setShowOSDTextDialog(false);
  };

  return {
    // States
    showOSDTextDialog,
    editingOSDTextIndex,
    osdTextType,
    osdTextContent,
    osdCustomText,
    osdPosition,
    osdPaddingX,
    osdPaddingY,
    osdFontSize,
    osdFontColorHex,
    osdBoxColorHex,
    osdBoxOpacity,
    // Setters
    setShowOSDTextDialog,
    setOSDTextType,
    setOSDTextContent,
    setOSDCustomText,
    setOSDPosition,
    setOSDPaddingX,
    setOSDPaddingY,
    setOSDFontSize,
    setOSDFontColorHex,
    setOSDBoxColorHex,
    setOSDBoxOpacity,
    // Handlers
    handleAddOSDText,
    handleEditOSDText,
    handleDeleteOSDText,
    handleConfirmOSDText,
  };
}
