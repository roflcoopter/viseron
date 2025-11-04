import { createContext, useContext, useRef, useState, useMemo, useCallback, useEffect } from "react";

interface FullscreenContextType {
  isFullscreen: boolean;
  toggleFullscreen: (element?: HTMLElement) => Promise<void>;
  fullscreenElementRef: React.RefObject<HTMLElement | null>;
}

const FullscreenContext = createContext<FullscreenContextType | undefined>(
  undefined,
);

export function useFullscreen() {
  const context = useContext(FullscreenContext);
  if (context === undefined) {
    throw new Error("useFullscreen must be used within a FullscreenProvider");
  }
  return context;
}

interface FullscreenProviderProps {
  children: React.ReactNode;
}

export function FullscreenProvider({ children }: FullscreenProviderProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const fullscreenElementRef = useRef<HTMLElement | null>(null);

  // Listen for browser fullscreen changes
  useEffect(() => {
    const handleFullscreenChange = () => {
      // If browser exits fullscreen but our state says we're fullscreen, clean up
      if (!document.fullscreenElement && isFullscreen && fullscreenElementRef.current) {
        const currentElement = fullscreenElementRef.current;
        
        // Reset styles
        currentElement.style.position = "";
        currentElement.style.top = "";
        currentElement.style.left = "";
        currentElement.style.width = "";
        currentElement.style.height = "";
        currentElement.style.zIndex = "";
        currentElement.style.backgroundColor = "";
        
        // Restore body overflow
        document.body.style.overflow = "";
        
        fullscreenElementRef.current = null;
        setIsFullscreen(false);
      }
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, [isFullscreen]);

  const toggleFullscreen = useCallback(async (targetElement?: HTMLElement) => {
    if (!isFullscreen && targetElement) {
      try {
        // Store reference to the element
        fullscreenElementRef.current = targetElement;
        
        // Apply fullscreen styles to the element
        targetElement.style.position = "fixed";
        targetElement.style.top = "0";
        targetElement.style.left = "0";
        targetElement.style.width = "100vw";
        targetElement.style.height = "100vh";
        targetElement.style.zIndex = "9000";
        targetElement.style.backgroundColor = "black";
        
        // Hide body overflow
        document.body.style.overflow = "hidden";
        
        // Enter browser fullscreen
        await document.documentElement.requestFullscreen();
        
        setIsFullscreen(true);
      } catch (err) {
        console.error("Error attempting to enable fullscreen:", err);
        // If browser fullscreen fails, clean up element styles
        if (fullscreenElementRef.current) {
          const currentElement = fullscreenElementRef.current;
          currentElement.style.position = "";
          currentElement.style.top = "";
          currentElement.style.left = "";
          currentElement.style.width = "";
          currentElement.style.height = "";
          currentElement.style.zIndex = "";
          currentElement.style.backgroundColor = "";
          document.body.style.overflow = "";
          fullscreenElementRef.current = null;
        }
      }
    } else if (isFullscreen) {
      try {
        // Exit browser fullscreen first
        if (document.fullscreenElement) {
          await document.exitFullscreen();
        }
        
        // Clean up element styles
        if (fullscreenElementRef.current) {
          const currentElement = fullscreenElementRef.current;
          currentElement.style.position = "";
          currentElement.style.top = "";
          currentElement.style.left = "";
          currentElement.style.width = "";
          currentElement.style.height = "";
          currentElement.style.zIndex = "";
          currentElement.style.backgroundColor = "";
          
          fullscreenElementRef.current = null;
        }
        
        // Restore body overflow
        document.body.style.overflow = "";
        
        setIsFullscreen(false);
      } catch (err) {
        console.error("Error attempting to exit fullscreen:", err);
      }
    }
  }, [isFullscreen]);

  const contextValue = useMemo(
    () => ({ isFullscreen, toggleFullscreen, fullscreenElementRef }),
    [isFullscreen, toggleFullscreen]
  );

  return (
    <FullscreenContext.Provider value={contextValue}>
      {children}
    </FullscreenContext.Provider>
  );
}