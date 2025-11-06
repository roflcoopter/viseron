import { Grid, Information } from "@carbon/icons-react";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { useState, useCallback, useMemo } from "react";

import { useGridLayoutStore } from "stores/GridLayoutStore";
import { GRID_LAYOUT_NAMES, type GridLayoutType } from "types/GridLayoutTypes";
import * as types from "lib/types";

interface GridLayoutSelectorDialogProps {
  open: boolean;
  onClose: () => void;
  cameras: types.Cameras;
}

function GridPreview({ layoutType }: { layoutType: GridLayoutType }) {
  const theme = useTheme();
  
  const getPreviewStyle = () => {
    const baseStyle = {
      width: '100%',
      maxWidth: 120,
      aspectRatio: '3/2',
      border: `2px solid ${theme.palette.divider}`,
      borderRadius: 1,
      display: 'grid',
      gap: '2px',
      padding: '4px',
      backgroundColor: theme.palette.background.paper,
    };

    switch (layoutType) {
      case 'auto':
        return {
          ...baseStyle,
          gridTemplateColumns: '1fr 1fr',
          gridTemplateRows: '1fr 1fr',
        };
      case '3plus1':
        return {
          ...baseStyle,
          gridTemplateColumns: '1fr 2fr',
          gridTemplateRows: '1fr 1fr 1fr',
        };
      case 'lshape':
        return {
          ...baseStyle,
          gridTemplateColumns: '1fr 1fr 1fr',
          gridTemplateRows: '1fr 1fr 1fr',
        };
      case 'square_center':
        return {
          ...baseStyle,
          gridTemplateColumns: '1fr 1fr 1fr',
          gridTemplateRows: '1fr 1fr 1fr',
        };
      case '2plus1':
        return {
          ...baseStyle,
          gridTemplateColumns: '1fr 1fr',
          gridTemplateRows: '1fr 1fr',
        };
      default:
        return baseStyle;
    }
  };

  const getCellStyle = (isMain: boolean = false) => ({
    backgroundColor: isMain 
      ? theme.palette.primary.main 
      : theme.palette.action.hover,
    borderRadius: '2px',
    minHeight: '8px',
  });

  const renderPreviewCells = () => {
    switch (layoutType) {
      case 'auto':
        return Array.from({ length: 4 }, (_, i) => (
          <Box key={i} sx={getCellStyle()} />
        ));
      case '3plus1':
        return (
          <>
            <Box sx={{ ...getCellStyle(), gridColumn: '1', gridRow: '1' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '1', gridRow: '2' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '1', gridRow: '3' }} />
            <Box sx={{ ...getCellStyle(true), gridColumn: '2', gridRow: '1 / 4' }} />
          </>
        );
      case 'lshape':
        return (
          <>
            <Box sx={{ ...getCellStyle(true), gridColumn: '1 / 3', gridRow: '1 / 3' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '3', gridRow: '1' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '3', gridRow: '2' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '1', gridRow: '3' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '2', gridRow: '3' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '3', gridRow: '3' }} />
          </>
        );
      case 'square_center':
        return (
          <>
            <Box sx={{ ...getCellStyle(), gridColumn: '1', gridRow: '1' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '2', gridRow: '1' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '3', gridRow: '1' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '1', gridRow: '2' }} />
            <Box sx={{ ...getCellStyle(true), gridColumn: '2', gridRow: '2' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '3', gridRow: '2' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '1', gridRow: '3' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '2', gridRow: '3' }} />
            <Box sx={{ ...getCellStyle(), gridColumn: '3', gridRow: '3' }} />
          </>
        );
      case '2plus1':
        return (
          <>
            {/* Top row - 2 cameras */}
            <Box sx={{ ...getCellStyle(true), gridColumn: '1', gridRow: '1' }} />
            <Box sx={{ ...getCellStyle(true), gridColumn: '2', gridRow: '1' }} />
            {/* Bottom row - 1 large camera */}
            <Box sx={{ ...getCellStyle(true), gridColumn: '1 / 3', gridRow: '2' }} />
          </>
        );
      default:
        return null;
    }
  };

  return (
    <Box sx={getPreviewStyle()}>
      {renderPreviewCells()}
    </Box>
  );
}

export function GridLayoutSelectorDialog({ 
  open, 
  onClose, 
  cameras 
}: GridLayoutSelectorDialogProps) {
  const theme = useTheme();
  const { 
    currentLayout, 
    layoutConfig, 
    setLayout, 
    setMainSlot, 
    setSideSlots 
  } = useGridLayoutStore();
  
  const [selectedLayout, setSelectedLayout] = useState<GridLayoutType>(currentLayout);
  const [selectedMainSlot, setSelectedMainSlot] = useState<string>(
    layoutConfig.mainSlot || ''
  );

  const cameraList = useMemo(() => Object.values(cameras), [cameras]);
  
  const cameraOptions = useMemo(() => 
    cameraList.map(camera => ({
      label: camera.name,
      value: camera.identifier
    })),
    [cameraList]
  );

  const handleLayoutChange = useCallback((layout: GridLayoutType) => {
    setSelectedLayout(layout);
  }, []);

  const handleMainSlotChange = useCallback((cameraId: string) => {
    setSelectedMainSlot(cameraId);
  }, []);

  const handleApply = useCallback(() => {
    setLayout(selectedLayout);
    if (selectedLayout !== 'auto' && selectedLayout !== '2plus1' && selectedMainSlot) {
      setMainSlot(selectedMainSlot);
      // Auto-assign remaining cameras to side slots
      const remainingCameras = cameraList
        .filter(cam => cam.identifier !== selectedMainSlot)
        .map(cam => cam.identifier);
      setSideSlots(remainingCameras);
    } else if (selectedLayout === '2plus1') {
      // For 2plus1 layout, just assign all cameras to side slots
      const allCameras = cameraList.map(cam => cam.identifier);
      setSideSlots(allCameras);
      setMainSlot(''); // Clear main slot for this layout
    }
    onClose();
  }, [selectedLayout, selectedMainSlot, cameraList, setLayout, setMainSlot, setSideSlots, onClose]);

  const needsMainSlot = selectedLayout !== 'auto' && selectedLayout !== '2plus1';

  return (
    <Dialog 
      fullWidth 
      maxWidth={false} 
      open={open} 
      onClose={onClose}
      disablePortal={false}
      container={() => document.body}
      style={{ zIndex: 9001 }}
      BackdropProps={{
        style: { zIndex: 9001 }
      }}
      PaperProps={{
        style: { zIndex: 9002, position: 'relative' },
        sx: { 
          borderRadius: 2,
          [theme.breakpoints.up('lg')]: {
            width: 'fit-content',
            maxWidth: '1000px',
            minWidth: '600px'
          }
        }
      }}
    >
      <DialogTitle>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Grid size={24} />
          <Typography variant="h6">Select Grid Layout</Typography>
        </Stack>
      </DialogTitle>
      
      <DialogContent>
        <Stack spacing={3}>

          {/* Layout Type Selection */}
          <Stack spacing={2}>
            <Typography variant="subtitle2">Layout Type</Typography>
            <Box
              sx={{
                display: 'grid',
                gap: 1.5,
                gridTemplateColumns: {
                  xs: 'repeat(2, 1fr)', // 2 columns on mobile
                  sm: 'repeat(2, 1fr)', // 2 columns on small tablets
                  md: 'repeat(3, 1fr)', // 3 columns on medium devices
                  lg: 'repeat(5, minmax(140px, 1fr))' // flexible on large devices
                },
                width: '100%',
                overflow: 'hidden'
              }}
            >
              {(Object.keys(GRID_LAYOUT_NAMES) as GridLayoutType[]).map((layout) => (
                <Stack 
                  key={layout}
                  alignItems="center" 
                  spacing={0.5}
                  sx={{
                    cursor: 'pointer',
                    padding: 0.8,
                    borderRadius: 1,
                    border: selectedLayout === layout 
                      ? `2px solid ${theme.palette.primary.main}`
                      : `1px solid ${theme.palette.divider}`,
                    '&:hover': {
                      backgroundColor: theme.palette.action.hover,
                    },
                    minWidth: 0, // Allow shrinking
                    overflow: 'hidden'
                  }}
                  onClick={() => handleLayoutChange(layout)}
                >
                  <GridPreview layoutType={layout} />
                  <Typography 
                    variant="caption"
                    sx={{ 
                      textAlign: 'center',
                      fontSize: { xs: '0.65rem', sm: '0.75rem' },
                      lineHeight: 1.2,
                      wordBreak: 'break-word'
                    }}
                  >
                    {GRID_LAYOUT_NAMES[layout]}
                  </Typography>
                </Stack>
              ))}
            </Box>
          </Stack>

          {/* Main Slot Selection */}
          {needsMainSlot && cameraList.length > 0 && (
            <Autocomplete
              options={cameraOptions}
              value={cameraOptions.find(option => option.value === selectedMainSlot) || null}
              onChange={(_, newValue) => {
                handleMainSlotChange(newValue?.value || '');
              }}
              getOptionLabel={(option) => option.label}
              isOptionEqualToValue={(option, value) => option.value === value.value}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Main Camera Slot"
                  placeholder="Search or select a camera..."
                />
              )}
              slotProps={{
                popper: {
                  style: {
                    zIndex: 9010
                  }
                },
                paper: {
                  style: {
                    zIndex: 9010
                  }
                }
              }}
            />
          )}

          {/* Layout Description */}
          <Box sx={{ 
            p: 2, 
            backgroundColor: theme.palette.action.selected,
            borderRadius: 1 
          }}>
            <Stack direction="row" alignItems="flex-start" spacing={1}>
              <Information size={16} style={{ marginTop: '2px', flexShrink: 0 }} />
              <Typography variant="body2">
                {selectedLayout === 'auto' && 
                  "Cameras will automatically arrange in an optimal grid based on available space and aspect ratios."
                }
                {selectedLayout === '3plus1' && 
                  "Three cameras in a vertical column with one large main camera taking up the remaining space."
                }
                {selectedLayout === 'lshape' && 
                  "Cameras arranged in an L-shape with one large main camera and smaller cameras along the edges."
                }
                {selectedLayout === 'square_center' && 
                  "Cameras arranged in a square pattern with one main camera in the center position."
                }
                {selectedLayout === '2plus1' && 
                  "Two cameras on the top row with one large camera spanning the full width below them."
                }
              </Typography>
            </Stack>
          </Box>
        </Stack>
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button 
          onClick={handleApply} 
          variant="contained"
          disabled={needsMainSlot && !selectedMainSlot}
        >
          Apply
        </Button>
      </DialogActions>
    </Dialog>
  );
}