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
          md: hasSetupErrors ? "70vh" : "72.5vh",
          xl: hasSetupErrors ? "78vh" : "80vh",
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
