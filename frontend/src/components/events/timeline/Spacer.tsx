import Box from "@mui/material/Box";

type SpacerProps = {
  time: number;
  height: number;
};
export const Spacer = ({ time, height }: SpacerProps) => (
  <Box
    key={`spacer-${time}`}
    sx={{ width: "10px", height: `${height}px` }}
  ></Box>
);
