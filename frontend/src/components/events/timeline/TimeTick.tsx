import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { memo } from "react";

import { getTimeFromDate, timestampToDate } from "lib/helpers";

import { TICK_HEIGHT } from "./TimelineTable";

type TimeTickProps = {
  time: number;
};
export const TimeTick = memo(({ time }: TimeTickProps) => {
  if (time % 300 === 0) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "start",
          alignItems: "center",
          height: TICK_HEIGHT,
          minWidth: "58px",
        }}
      >
        <Box
          sx={(theme) => ({
            height: "1px",
            width: "8px",
            marginRight: "5px",
            backgroundColor: theme.palette.divider,
          })}
        />
        <Typography
          variant="body2"
          color="textSecondary"
          lineHeight={0}
          fontSize={9}
        >
          {getTimeFromDate(timestampToDate(time), false)}
        </Typography>
      </Box>
    );
  }
  return (
    <Box sx={{ display: "flex", height: TICK_HEIGHT, minWidth: "58px" }}>
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
});
