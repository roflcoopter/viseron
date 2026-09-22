import { TrashCan } from "@carbon/icons-react";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Paper from "@mui/material/Paper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell, { tableCellClasses } from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { styled, useTheme } from "@mui/material/styles";
import { useState } from "react";

import ConfirmDeleteDialog from "components/dialog/ConfirmDeleteDialog";
import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import { useTitle } from "hooks/UseTitle";
import { useDeleteOrphanedCamera, useOrphanedCameras } from "lib/api/cameras";
import { formatBytes } from "lib/helpers";
import * as types from "lib/types";

const StyledTableCell = styled(TableCell)(() => ({
  [`&.${tableCellClasses.body}`]: {
    fontSize: 14,
    verticalAlign: "top",
    overflowWrap: "anywhere",
  },
}));

function StorageCleanup() {
  useTitle("Storage Cleanup");
  const theme = useTheme();
  const orphanedCameras = useOrphanedCameras();
  const deleteOrphanedCamera = useDeleteOrphanedCamera();
  const [cameraToDelete, setCameraToDelete] =
    useState<types.OrphanedCamera | null>(null);

  if (orphanedCameras.isLoading) {
    return <Loading text="Searching for orphaned cameras" />;
  }

  // The server refuses to guess while components are still setting up or broken
  if (orphanedCameras.error?.response?.status === 503) {
    return (
      <Container
        maxWidth={false}
        sx={{ paddingX: { xs: 1, md: 2 }, paddingY: 0.5 }}
      >
        <Alert severity="warning">
          {orphanedCameras.error.response.data.error}
        </Alert>
      </Container>
    );
  }

  if (orphanedCameras.isError || !orphanedCameras.data) {
    return (
      <ErrorMessage
        text="Error loading orphaned cameras"
        subtext={
          orphanedCameras.error?.response?.data.error ||
          orphanedCameras.error?.message
        }
      />
    );
  }

  const { cameras } = orphanedCameras.data;

  return (
    <Container
      maxWidth={false}
      sx={{ paddingX: { xs: 1, md: 2 }, paddingY: 0.5 }}
    >
      <Typography variant="body2" sx={{ marginBottom: 1 }}>
        Recordings, snapshots and database entries that belong to cameras which
        are no longer in your configuration. Deleting a camera here is
        permanent.
      </Typography>
      {cameras.length === 0 ? (
        <Alert severity="success">
          No orphaned cameras found. Every stored file belongs to a configured
          camera.
        </Alert>
      ) : (
        <TableContainer component={Paper}>
          <Table
            sx={() => ({
              [`& .${tableCellClasses.root}`]: {
                border: `1px solid ${theme.palette.background.default}`,
              },
            })}
          >
            <TableHead>
              <TableRow>
                <StyledTableCell>Camera</StyledTableCell>
                <StyledTableCell align="right">Files</StyledTableCell>
                <StyledTableCell align="right">Size</StyledTableCell>
                <StyledTableCell align="right">Database rows</StyledTableCell>
                <StyledTableCell align="right">Delete</StyledTableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {cameras.map((camera) => (
                <TableRow key={camera.camera_identifier} hover>
                  <StyledTableCell>
                    <Tooltip
                      title={
                        camera.directories.join(", ") || "No files on disk"
                      }
                    >
                      <span>{camera.camera_identifier}</span>
                    </Tooltip>
                  </StyledTableCell>
                  <StyledTableCell align="right">
                    {camera.file_count}
                  </StyledTableCell>
                  <StyledTableCell align="right">
                    {formatBytes(camera.size_bytes)}
                  </StyledTableCell>
                  <StyledTableCell align="right">
                    {camera.database_rows}
                  </StyledTableCell>
                  <StyledTableCell align="right">
                    <Button
                      color="error"
                      size="small"
                      startIcon={<TrashCan size={16} />}
                      onClick={() => setCameraToDelete(camera)}
                    >
                      Delete
                    </Button>
                  </StyledTableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      <ConfirmDeleteDialog
        open={!!cameraToDelete}
        onClose={() => setCameraToDelete(null)}
        isPending={deleteOrphanedCamera.isPending}
        title={`Delete ${cameraToDelete?.camera_identifier}?`}
        description={
          cameraToDelete
            ? `This permanently deletes ${cameraToDelete.file_count} files ` +
              `(${formatBytes(cameraToDelete.size_bytes)}) and ` +
              `${cameraToDelete.database_rows} database rows for ` +
              `${cameraToDelete.camera_identifier}.`
            : ""
        }
        onConfirm={() => {
          if (!cameraToDelete) {
            return;
          }
          deleteOrphanedCamera.mutate(
            { camera_identifier: cameraToDelete.camera_identifier },
            { onSuccess: () => setCameraToDelete(null) },
          );
        }}
      />
    </Container>
  );
}

export default StorageCleanup;
