import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import DeleteIcon from "@mui/icons-material/Delete";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import SaveIcon from "@mui/icons-material/Save";
import UndoIcon from "@mui/icons-material/Undo";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useCallback, useContext, useRef, useState } from "react";

import { ViseronContext } from "context/ViseronContext";
import { useToast } from "hooks/UseToast";
import * as commands from "lib/commands";

import {
  createDefaultPolygon,
  detectComponents,
  updateConfigWithPolygons,
} from "./configParser";
import { CATEGORY_LABELS, CATEGORY_STROKE_COLORS, PolygonCategory } from "./types";
import { usePolygonEditorStore } from "./usePolygonEditorStore";

interface PolygonEditorToolbarProps {
  cameraWidth: number;
  cameraHeight: number;
}

export function PolygonEditorToolbar({
  cameraWidth,
  cameraHeight,
}: PolygonEditorToolbarProps) {
  const viseron = useContext(ViseronContext);
  const toast = useToast();
  const [categoryFilter, setCategoryFilter] = useState<PolygonCategory | null>(
    null,
  );
  const [saved, setSaved] = useState(false);

  // Draggable window state
  const paperRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ x: number; y: number }>({
    x: 8,
    y: 8,
  });
  const dragState = useRef<{
    dragging: boolean;
    startX: number;
    startY: number;
    origX: number;
    origY: number;
  }>({ dragging: false, startX: 0, startY: 0, origX: 0, origY: 0 });

  const dragHandleRef = useRef<HTMLDivElement>(null);

  const handleDragStart = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragState.current = {
        dragging: true,
        startX: e.clientX,
        startY: e.clientY,
        origX: position.x,
        origY: position.y,
      };
      // Capture pointer so we keep tracking even outside the element/window
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [position],
  );

  const handleDragMove = useCallback((e: React.PointerEvent) => {
    if (!dragState.current.dragging) return;
    e.preventDefault();
    e.stopPropagation();
    const dx = e.clientX - dragState.current.startX;
    const dy = e.clientY - dragState.current.startY;
    setPosition({
      x: dragState.current.origX + dx,
      y: dragState.current.origY + dy,
    });
  }, []);

  const handleDragEnd = useCallback((e: React.PointerEvent) => {
    dragState.current.dragging = false;
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
  }, []);

  const {
    polygons,
    selectedPolygonId,
    isDirty,
    isSaving,
    rawYamlConfig,
    cameraIdentifier,
    selectPolygon,
    addPolygon,
    deletePolygon,
    updatePolygonName,
    revert,
    stopEditing,
    setSaving,
    setRawYamlConfig,
  } = usePolygonEditorStore();

  const selectedPolygon = polygons.find((p) => p.id === selectedPolygonId);

  const filteredPolygons = categoryFilter
    ? polygons.filter((p) => p.category === categoryFilter)
    : polygons;

  const handleAddPolygon = useCallback(() => {
    if (!rawYamlConfig || !cameraIdentifier) return;

    const category = categoryFilter || "motion_mask";
    const { motionComponent, objectComponent } = detectComponents(
      rawYamlConfig,
      cameraIdentifier,
    );

    let componentKey: string;
    if (category === "motion_mask") {
      componentKey = motionComponent || "mog2";
    } else {
      componentKey = objectComponent || "codeprojectai";
    }

    const polygon = createDefaultPolygon(
      category,
      componentKey,
      cameraWidth,
      cameraHeight,
    );
    addPolygon(polygon);
  }, [
    categoryFilter,
    rawYamlConfig,
    cameraIdentifier,
    cameraWidth,
    cameraHeight,
    addPolygon,
  ]);

  const handleSave = useCallback(async () => {
    if (!viseron.connection || !rawYamlConfig || !cameraIdentifier) return;

    setSaving(true);
    try {
      const updatedYaml = updateConfigWithPolygons(
        rawYamlConfig,
        cameraIdentifier,
        polygons,
      );
      await commands.saveConfig(viseron.connection, updatedYaml);
      setRawYamlConfig(updatedYaml);
      setSaved(true);
      toast.success("Configuration saved. Restart to apply changes.");
    } catch (error) {
      toast.error(`Failed to save: ${error}`);
    } finally {
      setSaving(false);
    }
  }, [
    viseron.connection,
    rawYamlConfig,
    cameraIdentifier,
    polygons,
    setSaving,
    setRawYamlConfig,
    toast,
  ]);

  const handleRestart = useCallback(async () => {
    if (!viseron.connection) return;
    try {
      await commands.restartViseron(viseron.connection);
      toast.info("Viseron is restarting...");
      stopEditing();
    } catch (error) {
      toast.error(`Failed to restart: ${error}`);
    }
  }, [viseron.connection, toast, stopEditing]);

  const handleClose = useCallback(() => {
    if (isDirty) {
      if (!window.confirm("Discard unsaved changes?")) return;
    }
    stopEditing();
  }, [isDirty, stopEditing]);

  return (
    <Paper
      ref={paperRef}
      elevation={6}
      sx={{
        position: "absolute",
        top: position.y,
        left: position.x,
        zIndex: 5,
        p: 1,
        display: "flex",
        flexDirection: "column",
        gap: 1,
        backgroundColor: "rgba(30, 30, 30, 0.92)",
        backdropFilter: "blur(8px)",
        maxHeight: "40%",
        maxWidth: "calc(100% - 16px)",
        minWidth: 280,
        overflow: "auto",
      }}
    >
      {/* Header — drag handle */}
      <Box
        ref={dragHandleRef}
        onPointerDown={handleDragStart}
        onPointerMove={handleDragMove}
        onPointerUp={handleDragEnd}
        display="flex"
        alignItems="center"
        justifyContent="space-between"
        gap={1}
        sx={{ cursor: "grab", userSelect: "none", touchAction: "none", "&:active": { cursor: "grabbing" } }}
      >
        <Typography variant="subtitle2" color="white" fontWeight="bold">
          Mask / Zone Editor
        </Typography>
        <Box display="flex" gap={0.5}>
          {isDirty && (
            <Tooltip title="Revert changes">
              <IconButton size="small" onClick={revert} sx={{ color: "white" }}>
                <UndoIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          <Tooltip title="Close editor">
            <IconButton
              size="small"
              onClick={handleClose}
              sx={{ color: "white" }}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Category filter */}
      <ToggleButtonGroup
        value={categoryFilter}
        exclusive
        onChange={(_, val) => setCategoryFilter(val)}
        size="small"
        fullWidth
      >
        <ToggleButton value="motion_mask">Motion Mask</ToggleButton>
        <ToggleButton value="object_mask">Object Mask</ToggleButton>
        <ToggleButton value="zone">Zone</ToggleButton>
      </ToggleButtonGroup>

      {/* Polygon list */}
      <Box display="flex" flexWrap="wrap" gap={0.5}>
        {filteredPolygons.map((p) => (
          <Chip
            key={p.id}
            label={
              p.category === "zone" && p.name
                ? p.name
                : `${CATEGORY_LABELS[p.category]} ${filteredPolygons.indexOf(p) + 1}`
            }
            size="small"
            onClick={() => selectPolygon(p.id)}
            onDelete={
              selectedPolygonId === p.id
                ? () => deletePolygon(p.id)
                : undefined
            }
            deleteIcon={<DeleteIcon />}
            variant={selectedPolygonId === p.id ? "filled" : "outlined"}
            sx={{
              borderColor: CATEGORY_STROKE_COLORS[p.category],
              color: "white",
              "& .MuiChip-deleteIcon": { color: "rgba(255,80,80,0.8)" },
              ...(selectedPolygonId === p.id
                ? {
                    backgroundColor: CATEGORY_STROKE_COLORS[p.category],
                  }
                : {}),
            }}
          />
        ))}
        <Tooltip title="Add polygon">
          <IconButton
            size="small"
            onClick={handleAddPolygon}
            sx={{ color: "white" }}
          >
            <AddIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Zone name editor */}
      {selectedPolygon?.category === "zone" && (
        <TextField
          size="small"
          label="Zone name"
          value={selectedPolygon.name || ""}
          onChange={(e) =>
            updatePolygonName(selectedPolygon.id, e.target.value)
          }
          sx={{
            "& .MuiInputBase-root": { color: "white", fontSize: "0.8rem" },
            "& .MuiInputLabel-root": { color: "rgba(255,255,255,0.6)" },
          }}
        />
      )}

      {/* Hints */}
      <Typography
        variant="caption"
        color="rgba(255,255,255,0.5)"
        sx={{ fontSize: "0.65rem" }}
      >
        Click polygon to select. Drag vertices to move. Click edge midpoint to
        add vertex. Right-click vertex to delete.
      </Typography>

      {/* Action buttons */}
      <Box display="flex" gap={1} justifyContent="flex-end">
        {saved && (
          <Button
            size="small"
            variant="outlined"
            color="warning"
            startIcon={<RestartAltIcon />}
            onClick={handleRestart}
          >
            Restart
          </Button>
        )}
        <Button
          size="small"
          variant="contained"
          color="primary"
          startIcon={
            isSaving ? <CircularProgress size={16} /> : <SaveIcon />
          }
          onClick={handleSave}
          disabled={!isDirty || isSaving}
        >
          Save
        </Button>
      </Box>
    </Paper>
  );
}
