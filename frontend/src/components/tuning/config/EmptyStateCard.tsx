import { Box, Card, CardContent, Typography } from "@mui/material";

interface EmptyStateCardProps {
  message: string;
}

export function EmptyStateCard({ message }: EmptyStateCardProps) {
  return (
    <Card
      variant="outlined"
      sx={{
        height: { md: "72.5vh" },
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <CardContent sx={{ overflow: "auto" }}>
        <Box
          display="flex"
          flexDirection="column"
          justifyContent="center"
          alignItems="center"
          height={{ xs: "20vh", md: "60vh" }}
        >
          <Typography color="text.secondary" align="center">
            {message}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
}
