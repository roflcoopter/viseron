import DirectionsCarIcon from "@mui/icons-material/DirectionsCar";
import SearchIcon from "@mui/icons-material/Search";
import Box from "@mui/material/Box";

type LicensePlateRecognitionProps = {
  color?:
    | "disabled"
    | "action"
    | "inherit"
    | "primary"
    | "secondary"
    | "error"
    | "info"
    | "success"
    | "warning"
    | undefined;
};

function LicensePlateRecognition({
  color = undefined,
}: LicensePlateRecognitionProps) {
  return (
    <Box sx={{ position: "relative" }}>
      <DirectionsCarIcon color={color} />
      <SearchIcon
        sx={(theme) => ({
          position: "absolute",
          right: "-6.5px",
          bottom: "-1px",
          strokeWidth: 2,
          stroke: theme.palette.background.paper,
        })}
      />
      <SearchIcon
        color={color}
        sx={{
          position: "absolute",
          right: "-6.5px",
          bottom: "-1px",
        }}
      />
    </Box>
  );
}

export default LicensePlateRecognition;
