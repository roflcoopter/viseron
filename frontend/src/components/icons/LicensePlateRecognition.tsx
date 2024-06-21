import DirectionsCarIcon from "@mui/icons-material/DirectionsCar";
import SearchIcon from "@mui/icons-material/Search";
import Box from "@mui/material/Box";

const LicensePlateRecgnition = () => (
  <Box sx={{ position: "relative" }}>
    <DirectionsCarIcon
      sx={(theme) => ({
        color:
          theme.palette.mode === "dark"
            ? theme.palette.primary[600]
            : theme.palette.primary[300],
      })}
    />
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
      sx={(theme) => ({
        position: "absolute",
        right: "-6.5px",
        bottom: "-1px",
        color:
          theme.palette.mode === "dark"
            ? theme.palette.primary[600]
            : theme.palette.primary[300],
      })}
    />
  </Box>
);

export default LicensePlateRecgnition;
