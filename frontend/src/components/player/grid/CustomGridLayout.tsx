import Box from "@mui/material/Box";
import { useMemo, useRef, useImperativeHandle, forwardRef, useCallback } from "react";

import { useGridLayoutStore } from "stores/GridLayoutStore";
import { useCameraStore } from "components/camera/useCameraStore";
import { useFullscreen } from "context/FullscreenContext";
import type { GridLayoutType } from "types/GridLayoutTypes";
import * as types from "lib/types";

interface CustomGridLayoutProps {
  cameras: types.CamerasOrFailedCameras;
  containerRef: React.RefObject<HTMLDivElement | null>;
  renderPlayer: (
    camera: types.Camera | types.FailedCamera,
    playerRef: React.RefObject<any>,
  ) => React.ReactElement;
}

export interface CustomGridLayoutRef {
  setSize: () => void;
}

const CustomGridLayout = forwardRef<CustomGridLayoutRef, CustomGridLayoutProps>(
  ({ cameras, containerRef: _containerRef, renderPlayer }, ref) => {
    const { currentLayout, layoutConfig } = useGridLayoutStore();
    const { selectionOrder } = useCameraStore();
    const { isFullscreen } = useFullscreen();
    const playerRefs = useRef<Record<string, React.RefObject<any>>>({});

    // Initialize refs for all cameras
    Object.keys(cameras).forEach(cameraId => {
      if (!playerRefs.current[cameraId]) {
        playerRefs.current[cameraId] = { current: null };
      }
    });

    useImperativeHandle(ref, () => ({
      setSize: () => {
        // Custom grid layouts handle sizing internally
      },
    }));

    const getGridStyle = (layoutType: GridLayoutType) => {
      const baseStyle = {
        width: '100%',
        height: '100%',
        display: 'grid',
        gap: 0,
        padding: 0,
        boxSizing: 'border-box' as const,
        overflow: 'hidden',
        maxHeight: '100%',
        maxWidth: '100%',
      };

      switch (layoutType) {
        case '3plus1':
          return {
            ...baseStyle,
            gridTemplateColumns: '1fr 2fr',
            gridTemplateRows: '1fr 1fr 1fr',
            padding: isFullscreen ? 0 : '0 10.3vw 0 10.3vw',
          };
        case 'lshape':
          return {
            ...baseStyle,
            gridTemplateColumns: '1fr 1fr 1fr',
            gridTemplateRows: '1fr 1fr 1fr',
            padding: isFullscreen ? 0 : '0 10.3vw',
          };
        case 'square_center':
          return {
            ...baseStyle,
            gridTemplateColumns: '1fr 1fr 1fr',
            gridTemplateRows: '1fr 1fr 1fr',
            padding: isFullscreen ? 0 : '0 10.3vw 0 10.3vw',
          };
        case '2plus1':
          return {
            ...baseStyle,
            gridTemplateColumns: '1fr 1fr',
            gridTemplateRows: '1fr 1fr',
            padding: isFullscreen ? 0 : '0 10.3vw 0 10.3vw',
          };
        default:
          return baseStyle;
      }
    };

  const getCameraPositions = useCallback(() => {
    // Get cameras in selection order
    const orderedCameras = selectionOrder
      .map((cameraId: string) => cameras[cameraId])
      .filter((camera): camera is types.Camera | types.FailedCamera => Boolean(camera));
    
    // If we have a main slot configured, use it; otherwise use the first camera
    const mainCameraId = layoutConfig.mainSlot || (orderedCameras[0]?.identifier);
    const mainCamera = orderedCameras.find((cam: types.Camera | types.FailedCamera) => cam.identifier === mainCameraId);
    
    // Side cameras are all cameras except the main camera, in selection order
    const sideCameras = orderedCameras.filter((cam: types.Camera | types.FailedCamera) => cam.identifier !== mainCameraId);

    switch (currentLayout) {
      case '3plus1':
        return {
          main: mainCamera ? {
            camera: mainCamera,
            style: { gridColumn: '2', gridRow: '1 / 4' }
          } : null,
          sides: sideCameras.slice(0, 3).map((camera: types.Camera | types.FailedCamera, index: number) => ({
            camera,
            style: { gridColumn: '1', gridRow: `${index + 1}` }
          }))
        };

      case 'lshape':
        return {
          main: mainCamera ? {
            camera: mainCamera,
            style: { gridColumn: '1 / 3', gridRow: '1 / 3' }
          } : null,
          sides: [
            ...sideCameras.slice(0, 2).map((camera: types.Camera | types.FailedCamera, index: number) => ({
              camera,
              style: { gridColumn: '3', gridRow: `${index + 1}` }
            })),
            ...sideCameras.slice(2, 5).map((camera: types.Camera | types.FailedCamera, index: number) => ({
              camera,
              style: { gridColumn: `${index + 1}`, gridRow: '3' }
            }))
          ]
        };

      case 'square_center': {
        const positions = [
          { gridColumn: '1', gridRow: '1' },
          { gridColumn: '2', gridRow: '1' },
          { gridColumn: '3', gridRow: '1' },
          { gridColumn: '1', gridRow: '2' },
          { gridColumn: '3', gridRow: '2' },
          { gridColumn: '1', gridRow: '3' },
          { gridColumn: '2', gridRow: '3' },
          { gridColumn: '3', gridRow: '3' },
        ];
        return {
          main: mainCamera ? {
            camera: mainCamera,
            style: { gridColumn: '2', gridRow: '2' }
          } : null,
          sides: sideCameras.slice(0, 8).map((camera: types.Camera | types.FailedCamera, index: number) => ({
            camera,
            style: positions[index] || { gridColumn: '1', gridRow: '1' }
          }))
        };
      }

      case '2plus1': {
        // For 2+1 layout, use first 3 cameras in selection order
        // Top row: 2 cameras, Bottom row: 1 camera
        return {
          main: null, // No specific main camera in this layout
          sides: [
            // Top row - first 2 cameras
            ...orderedCameras.slice(0, 2).map((camera: types.Camera | types.FailedCamera, index: number) => ({
              camera,
              style: { 
                gridColumn: `${index + 1}`, 
                gridRow: '1' 
              }
            })),
            // Bottom row - third camera (spans full width)
            ...orderedCameras.slice(2, 3).map((camera: types.Camera | types.FailedCamera) => ({
              camera,
              style: { 
                gridColumn: '1 / 3', 
                gridRow: '2' 
              }
            }))
          ]
        };
      }

      default:
        return { main: null, sides: [] };
    }
  }, [cameras, currentLayout, layoutConfig.mainSlot, selectionOrder]);    const { main, sides } = useMemo(() => getCameraPositions(), [getCameraPositions]);

    if (currentLayout === 'auto') {
      return null; // Use default PlayerGrid
    }

    return (
      <Box sx={getGridStyle(currentLayout)}>
        {/* Main camera */}
        {main && (
          <Box
            key={main.camera.identifier}
            sx={{
              ...main.style,
              position: 'relative',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: 0,
              minWidth: 0,
              maxHeight: '100%',
              maxWidth: '100%',
              '& > *': {
                width: '100%',
                height: '100%',
                minHeight: 0,
                minWidth: 0,
                maxHeight: '100%',
                maxWidth: '100%',
                objectFit: 'contain',
              }
            }}
          >
            {renderPlayer(main.camera, playerRefs.current[main.camera.identifier])}
          </Box>
        )}

        {/* Side cameras */}
        {sides.map(({ camera, style }) => (
          <Box
            key={camera.identifier}
            sx={{
              ...style,
              position: 'relative',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: 0,
              minWidth: 0,
              maxHeight: '100%',
              maxWidth: '100%',
              '& > *': {
                width: '100%',
                height: '100%',
                minHeight: 0,
                minWidth: 0,
                maxHeight: '100%',
                maxWidth: '100%',
                objectFit: 'contain',
              }
            }}
          >
            {renderPlayer(camera, playerRefs.current[camera.identifier])}
          </Box>
        ))}
      </Box>
    );
  }
);

CustomGridLayout.displayName = 'CustomGridLayout';

export default CustomGridLayout;