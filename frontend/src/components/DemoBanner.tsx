import Chip from "@mui/material/Chip";

function DemoBanner() {
  if (import.meta.env.VITE_MOCK_API !== "true") {
    return null;
  }

  return (
    <Chip
      label="Demo | Data is mocked, nothing is saved"
      color="warning"
      size="small"
      sx={{
        position: "fixed",
        bottom: 16,
        left: "50%",
        transform: "translateX(-50%)",
        opacity: "50%",
        zIndex: (theme) => theme.zIndex.tooltip,
      }}
    />
  );
}

export default DemoBanner;
