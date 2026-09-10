import { Box, Card, CardContent, Typography } from "@mui/material";

interface EmptyStateCardProps {
  message: string;
  hasSetupErrors: boolean;
}

export function EmptyStateCard({
  message,
  hasSetupErrors,
}: EmptyStateCardProps) {
  return (
    <Card
      variant="outlined"
      sx={{
        height: {
          md: hasSetupErrors ? "70vh" : "73vh",
          xl: hasSetupErrors ? "72vh" : "75vh",
          xxl: hasSetupErrors ? "77vh" : "80vh",
        },
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
