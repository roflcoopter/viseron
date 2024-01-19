import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";

import { getTimeFromDate, timestampToDate } from "lib/helpers";

import { TICK_HEIGHT } from "./TimelineTable";

type TimeTickProps = {
  time: number;
};
export const TimeTick = ({ time }: TimeTickProps) => {
  if (time % 300 === 0) {
    return (
      <Box sx={{ display: "flex", height: TICK_HEIGHT, marginRight: "8px" }}>
        <Box
          sx={(theme) => ({
            height: "1px",
            width: "8px",
            margin: "auto",
            marginRight: "5px",
            backgroundColor: theme.palette.divider,
          })}
        />
        <Typography
          variant="body2"
          color="textSecondary"
          lineHeight={0}
          fontSize={9}
          noWrap
          sx={{ margin: "auto", overflow: "visible" }}
        >
          {getTimeFromDate(timestampToDate(time), false)}
        </Typography>
      </Box>
    );
  }
  return (
    <Box sx={{ display: "flex", height: TICK_HEIGHT }}>
      <Box
        sx={(theme) => ({
          height: "1px",
          width: "4px",
          margin: "auto",
          marginLeft: "0px",
          backgroundColor: theme.palette.divider,
        })}
      />
    </Box>
  );
};
