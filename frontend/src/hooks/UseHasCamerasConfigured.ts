import { useContext, useMemo } from "react";

import { ViseronContext } from "context/ViseronContext";

// Returns true if any camera is configured.
// Returns true when not yet connected to avoid flashing "not configured"
// on pages that are waiting for cameras to register.
export function useHasCamerasConfigured(): boolean {
  const { connected, setupStatus } = useContext(ViseronContext);

  return useMemo(() => {
    if (!connected) {
      return true;
    }
    // Only consider "not configured" when we have received setup status and
    // no component has a camera domain at all.
    if (setupStatus.components.length === 0) {
      return true;
    }
    return setupStatus.components.some((component) =>
      component.domains.some((d) => d.domain === "camera"),
    );
  }, [connected, setupStatus]);
}
