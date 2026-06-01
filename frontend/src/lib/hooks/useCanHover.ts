import useMediaQuery from "@mui/material/useMediaQuery";

// Returns true when the primary pointing device can hover.
// Returns false on touch-primary devices.
// Uses the CSS interaction media features `hover` and `pointer` so that
// hybrid devices (e.g. touchscreen laptops, iPad with trackpad) are
// correctly treated as hover-capable when driven by a precise pointer.
// Reactive, if the user plugs in or unplugs a mouse the value updates.
export function useCanHover(): boolean {
  return useMediaQuery("(any-hover: hover) and (any-pointer: fine)");
}
