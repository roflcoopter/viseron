import { useCallback, useEffect, useRef, useState } from "react";

interface Position {
  x: number;
  y: number;
}

interface UseDraggableOptions {
  initialPosition?: Position;
  boundaryPadding?: number;
}

export function useDraggable(options: UseDraggableOptions = {}) {
  const { initialPosition, boundaryPadding = 10 } = options;

  const [position, setPosition] = useState<Position>(
    initialPosition || { x: 0, y: 0 },
  );
  const [isDragging, setIsDragging] = useState(false);
  const [isPositionReady, setIsPositionReady] = useState(!!initialPosition);

  const dragRef = useRef<HTMLDivElement>(null);
  const dragStartRef = useRef<Position>({ x: 0, y: 0 });
  const positionRef = useRef<Position>(position);

  // Keep positionRef in sync
  useEffect(() => {
    positionRef.current = position;
  }, [position]);

  // Calculate center position
  const getCenterPosition = useCallback(() => {
    if (!dragRef.current) return { x: 0, y: 0 };

    const rect = dragRef.current.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    return {
      x: (viewportWidth - rect.width) / 2,
      y: (viewportHeight - rect.height) / 2,
    };
  }, []);

  // Initialize position to center when element mounts
  const initializePosition = useCallback(() => {
    if (!dragRef.current) return;

    const newPosition = getCenterPosition();
    setPosition(newPosition);
    positionRef.current = newPosition;
    setIsPositionReady(true);
  }, [getCenterPosition]);

  // Reset position to center
  const resetPosition = useCallback(() => {
    setIsPositionReady(false);
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    // Only start drag if clicking on the header area
    if ((e.target as HTMLElement).closest("[data-drag-handle]")) {
      e.preventDefault();
      setIsDragging(true);
      dragStartRef.current = {
        x: e.clientX - positionRef.current.x,
        y: e.clientY - positionRef.current.y,
      };
    }
  }, []);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if ((e.target as HTMLElement).closest("[data-drag-handle]")) {
      const touch = e.touches[0];
      setIsDragging(true);
      dragStartRef.current = {
        x: touch.clientX - positionRef.current.x,
        y: touch.clientY - positionRef.current.y,
      };
    }
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging || !dragRef.current) return;

      const rect = dragRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      let newX = e.clientX - dragStartRef.current.x;
      let newY = e.clientY - dragStartRef.current.y;

      // Constrain to viewport
      newX = Math.max(
        boundaryPadding,
        Math.min(newX, viewportWidth - rect.width - boundaryPadding),
      );
      newY = Math.max(
        boundaryPadding,
        Math.min(newY, viewportHeight - rect.height - boundaryPadding),
      );

      const newPosition = { x: newX, y: newY };
      setPosition(newPosition);
      positionRef.current = newPosition;
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (!isDragging || !dragRef.current) return;

      const touch = e.touches[0];
      const rect = dragRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      let newX = touch.clientX - dragStartRef.current.x;
      let newY = touch.clientY - dragStartRef.current.y;

      // Constrain to viewport
      newX = Math.max(
        boundaryPadding,
        Math.min(newX, viewportWidth - rect.width - boundaryPadding),
      );
      newY = Math.max(
        boundaryPadding,
        Math.min(newY, viewportHeight - rect.height - boundaryPadding),
      );

      const newPosition = { x: newX, y: newY };
      setPosition(newPosition);
      positionRef.current = newPosition;
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    const handleTouchEnd = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.addEventListener("touchmove", handleTouchMove);
      document.addEventListener("touchend", handleTouchEnd);
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.removeEventListener("touchmove", handleTouchMove);
      document.removeEventListener("touchend", handleTouchEnd);
    };
  }, [isDragging, boundaryPadding]);

  return {
    position,
    isDragging,
    isPositionReady,
    dragRef,
    handleMouseDown,
    handleTouchStart,
    initializePosition,
    resetPosition,
  };
}
