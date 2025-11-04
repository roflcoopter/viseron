import { useCallback, useRef, useState, useEffect } from "react";

interface ZoomPanState {
  scale: number;
  translateX: number;
  translateY: number;
}

interface UseZoomPanOptions {
  minScale?: number;
  maxScale?: number;
  zoomSpeed?: number;
}

export const useZoomPan = (
  containerRef: React.RefObject<HTMLElement | HTMLDivElement | null>,
  options: UseZoomPanOptions = {}
) => {
  const {
    minScale = 1.0, // Changed from 0.5 to 1.0 to prevent zooming smaller than original
    maxScale = 5, // Can be adjusted as needed
    zoomSpeed = 0.1,
  } = options;

  const [transform, setTransform] = useState<ZoomPanState>({
    scale: 1,
    translateX: 0,
    translateY: 0,
  });

  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [dragStartTransform, setDragStartTransform] = useState({ x: 0, y: 0 });

  const transformRef = useRef(transform);
  transformRef.current = transform;

  const handleWheel = useCallback(
    (event: Event) => {
      const wheelEvent = event as WheelEvent;
      wheelEvent.preventDefault();
      
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const mouseX = wheelEvent.clientX - rect.left;
      const mouseY = wheelEvent.clientY - rect.top;

      // Calculate zoom center relative to current transform
      const currentTransform = transformRef.current;
      const zoomCenterX = (mouseX - currentTransform.translateX) / currentTransform.scale;
      const zoomCenterY = (mouseY - currentTransform.translateY) / currentTransform.scale;

      // Calculate new scale
      const delta = wheelEvent.deltaY > 0 ? -zoomSpeed : zoomSpeed;
      const newScale = Math.max(minScale, Math.min(maxScale, currentTransform.scale + delta));

      // If scale is back to minimum (1.0), reset position to center
      if (newScale === minScale) {
        setTransform({
          scale: newScale,
          translateX: 0,
          translateY: 0,
        });
      } else {
        // Calculate new translation to keep zoom center at mouse position
        let newTranslateX = mouseX - zoomCenterX * newScale;
        let newTranslateY = mouseY - zoomCenterY * newScale;

        // Apply boundary constraints
        const containerWidth = rect.width;
        const containerHeight = rect.height;
        const contentWidth = containerWidth * newScale;
        const contentHeight = containerHeight * newScale;

        // Calculate bounds
        const minTranslateX = Math.min(0, containerWidth - contentWidth);
        const maxTranslateX = Math.max(0, containerWidth - contentWidth);
        const minTranslateY = Math.min(0, containerHeight - contentHeight);
        const maxTranslateY = Math.max(0, containerHeight - contentHeight);

        // Clamp translate values
        newTranslateX = Math.max(minTranslateX, Math.min(maxTranslateX, newTranslateX));
        newTranslateY = Math.max(minTranslateY, Math.min(maxTranslateY, newTranslateY));

        setTransform({
          scale: newScale,
          translateX: newTranslateX,
          translateY: newTranslateY,
        });
      }
    },
    [containerRef, minScale, maxScale, zoomSpeed]
  );

  const handleMouseDown = useCallback((event: React.MouseEvent) => {
    if (event.button !== 0) return; // Only left mouse button
    
    // Only allow dragging if zoomed in
    if (transformRef.current.scale <= 1.0) {
      return;
    }
    
    setIsDragging(true);
    setDragStart({ x: event.clientX, y: event.clientY });
    setDragStartTransform({ 
      x: transformRef.current.translateX, 
      y: transformRef.current.translateY 
    });
    
    // Prevent text selection and other default behaviors
    event.preventDefault();
    event.stopPropagation();
  }, []);

  const handleMouseMove = useCallback((event: MouseEvent) => {
    if (!isDragging) return;
    
    const container = containerRef.current;
    if (!container) return;
    
    const deltaX = event.clientX - dragStart.x;
    const deltaY = event.clientY - dragStart.y;

    // Calculate new translate values
    const newTranslateX = dragStartTransform.x + deltaX;
    const newTranslateY = dragStartTransform.y + deltaY;

    // Get container dimensions
    const containerRect = container.getBoundingClientRect();
    const containerWidth = containerRect.width;
    const containerHeight = containerRect.height;

    // Calculate content dimensions when scaled
    const contentWidth = containerWidth * transformRef.current.scale;
    const contentHeight = containerHeight * transformRef.current.scale;

    // Calculate bounds to keep content within container
    const minTranslateX = Math.min(0, containerWidth - contentWidth);
    const maxTranslateX = Math.max(0, containerWidth - contentWidth);
    const minTranslateY = Math.min(0, containerHeight - contentHeight);
    const maxTranslateY = Math.max(0, containerHeight - contentHeight);

    // Clamp translate values to stay within bounds
    const clampedTranslateX = Math.max(minTranslateX, Math.min(maxTranslateX, newTranslateX));
    const clampedTranslateY = Math.max(minTranslateY, Math.min(maxTranslateY, newTranslateY));

    setTransform(prev => ({
      ...prev,
      translateX: clampedTranslateX,
      translateY: clampedTranslateY,
    }));
  }, [isDragging, dragStart, dragStartTransform, containerRef]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const resetTransform = useCallback(() => {
    setTransform({
      scale: 1,
      translateX: 0,
      translateY: 0,
    });
  }, []);

  // Add event listeners
  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return undefined;
    }

    container.addEventListener('wheel', handleWheel, { passive: false });
    
    return () => {
      container.removeEventListener('wheel', handleWheel);
    };
  }, [containerRef, handleWheel]);

  useEffect(() => {
    if (!isDragging) {
      return undefined;
    }

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  const transformStyle = {
    transform: `translate(${transform.translateX}px, ${transform.translateY}px) scale(${transform.scale})`,
    transformOrigin: '0 0',
    cursor: isDragging ? 'grabbing' : (transform.scale > 1.0 ? 'grab' : 'default'),
    transition: isDragging ? 'none' : 'transform 0.1s ease-out',
  };

  return {
    transform,
    transformStyle,
    isDragging,
    handleMouseDown,
    resetTransform,
    isZoomed: transform.scale !== 1.0 || transform.translateX !== 0 || transform.translateY !== 0,
    cursor: isDragging 
      ? 'grabbing' 
      : (transform.scale > 1.0 ? 'grab' : 'default'),
    // Export transform values for overlay
    scale: transform.scale,
    translateX: transform.translateX,
    translateY: transform.translateY,
  };
};