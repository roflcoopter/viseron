import { 
  CarFront,
  Search
} from  "@carbon/icons-react";
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
      <CarFront color={color} size={20}/>
      <Box
        sx={{
          position: "absolute",
          right: "-6.5px",
          bottom: "-1px",
        }}
      >
        <Search color={color} size={16}/>
      </Box>
    </Box>
  );
}

export default LicensePlateRecognition;
