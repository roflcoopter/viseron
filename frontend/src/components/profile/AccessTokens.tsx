import { Add, Copy, TrashCan } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import Paper from "@mui/material/Paper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { DateTimePicker } from "@mui/x-date-pickers/DateTimePicker";
import { UseMutationResult } from "@tanstack/react-query";
import { Dayjs } from "dayjs";
import { Dispatch, SetStateAction, useEffect, useRef, useState } from "react";

import { useToast } from "hooks/UseToast";
import {
  ProfileDeleteAccessTokenVariables,
  useProfileAccessTokens,
  useProfileCreateAccessToken,
  useProfileDeleteAccessToken,
} from "lib/api/profile";
import {
  getDayjsFromUnixTimestamp,
  getDisplayDateTimeFormat,
  is12HourFormat,
} from "lib/helpers/dates";
import * as types from "lib/types";

function formatTimestamp(ts: number | null): string {
  if (ts === null) return "Never";
  return getDayjsFromUnixTimestamp(ts).format(getDisplayDateTimeFormat());
}

function isExpired(token: types.AccessToken): boolean {
  return token.expires_at !== null && Date.now() / 1000 > token.expires_at;
}

function useCopyToken(token: string) {
  const [copied, setCopied] = useState(false);
  const copiedResetTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toast = useToast();

  useEffect(
    () => () => {
      if (copiedResetTimeout.current) {
        clearTimeout(copiedResetTimeout.current);
      }
    },
    [],
  );

  const handleCopy = () => {
    if (!navigator.clipboard) {
      toast.error("Clipboard is not available in this browser context");
      return;
    }

    navigator.clipboard
      .writeText(token)
      .then(() => {
        setCopied(true);
        if (copiedResetTimeout.current) {
          clearTimeout(copiedResetTimeout.current);
        }
        copiedResetTimeout.current = setTimeout(() => {
          setCopied(false);
          copiedResetTimeout.current = null;
        }, 2000);
      })
      .catch(() => {
        toast.error("Failed to copy token to clipboard");
      });
  };

  return { copied, handleCopy };
}

function TokenRevealDialog({
  token,
  onClose,
}: {
  token: string;
  onClose: () => void;
}) {
  const { copied, handleCopy } = useCopyToken(token);

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Your new access token</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ marginBottom: 2 }}>
          Copy this token now. <strong>It will not be shown again.</strong>
        </DialogContentText>
        <TextField
          fullWidth
          value={token}
          InputProps={{
            readOnly: true,
            endAdornment: (
              <InputAdornment position="end">
                <Tooltip title={copied ? "Copied!" : "Copy"}>
                  <IconButton onClick={handleCopy} edge="end">
                    <Copy />
                  </IconButton>
                </Tooltip>
              </InputAdornment>
            ),
          }}
          sx={{ fontFamily: "monospace" }}
        />
      </DialogContent>
      <DialogActions>
        <Button variant="contained" onClick={onClose}>
          Done
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function CreateTokenDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (token: string) => void;
}) {
  const createToken = useProfileCreateAccessToken();
  const [name, setName] = useState("");
  const [expiry, setExpiry] = useState<Dayjs | null>(null);

  const handleCreate = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    const expires_at = expiry ? expiry.unix() : null;
    createToken.mutate(
      { name: trimmed, expires_at },
      {
        onSuccess: (data) => {
          onCreated(data.token);
          setName("");
          setExpiry(null);
        },
      },
    );
  };

  const handleClose = () => {
    setName("");
    setExpiry(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Create access token</DialogTitle>
      <DialogContent
        sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}
      >
        <TextField
          autoFocus
          label="Token name"
          size="small"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleCreate();
          }}
          fullWidth
          sx={{ mt: 1 }}
        />
        <DateTimePicker
          label="Expiry date (optional)"
          views={["year", "month", "day", "hours", "minutes", "seconds"]}
          value={expiry}
          onAccept={(value) => setExpiry(value)}
          onChange={(value) => setExpiry(value)}
          closeOnSelect={false}
          ampm={is12HourFormat()}
          format={getDisplayDateTimeFormat()}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleCreate}
          disabled={!name.trim()}
          loading={createToken.isPending}
          loadingPosition="start"
          startIcon={<Add />}
        >
          Create token
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function DeleteTokenConfirmationDialog({
  deleteConfirmToken,
  setDeleteConfirmToken,
  deleteToken,
}: {
  deleteConfirmToken: types.AccessToken | null;
  setDeleteConfirmToken: Dispatch<SetStateAction<types.AccessToken | null>>;
  deleteToken: UseMutationResult<
    types.APISuccessResponse,
    types.APIErrorResponse,
    ProfileDeleteAccessTokenVariables,
    unknown
  >;
}) {
  return (
    <Dialog
      open={deleteConfirmToken !== null}
      onClose={() => setDeleteConfirmToken(null)}
      maxWidth="xs"
      fullWidth
    >
      <DialogTitle>Revoke access token</DialogTitle>
      <DialogContent>
        <DialogContentText>
          Are you sure you want to revoke the token{" "}
          <strong>{deleteConfirmToken?.name}</strong>? This action cannot be
          undone.
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setDeleteConfirmToken(null)}>Cancel</Button>
        <Button
          variant="contained"
          color="error"
          loading={deleteToken.isPending}
          onClick={() => {
            if (deleteConfirmToken) {
              deleteToken.mutate(
                { tokenId: deleteConfirmToken.id },
                { onSuccess: () => setDeleteConfirmToken(null) },
              );
            }
          }}
        >
          Revoke
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function TokenTable({
  tokens,
  setDeleteConfirmToken,
  deleteToken,
}: {
  tokens: types.AccessToken[];
  setDeleteConfirmToken: Dispatch<SetStateAction<types.AccessToken | null>>;
  deleteToken: UseMutationResult<
    types.APISuccessResponse,
    types.APIErrorResponse,
    ProfileDeleteAccessTokenVariables,
    unknown
  >;
}) {
  return (
    <TableContainer
      component={Paper}
      variant="outlined"
      sx={{ marginBottom: 2 }}
    >
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>Created</TableCell>
            <TableCell>Expires</TableCell>
            <TableCell>Last used</TableCell>
            <TableCell padding="checkbox" />
          </TableRow>
        </TableHead>
        <TableBody>
          {tokens.map((token) => (
            <TableRow
              key={token.id}
              sx={isExpired(token) ? { opacity: 0.5 } : undefined}
            >
              <TableCell sx={{ whiteSpace: "nowrap" }}>
                {token.name}
                {isExpired(token) && (
                  <Chip
                    label="Expired"
                    size="small"
                    color="warning"
                    sx={{ ml: 1 }}
                  />
                )}
              </TableCell>
              <TableCell sx={{ whiteSpace: "nowrap" }}>
                {formatTimestamp(token.created_at)}
              </TableCell>
              <TableCell sx={{ whiteSpace: "nowrap" }}>
                {token.expires_at ? formatTimestamp(token.expires_at) : "Never"}
              </TableCell>
              <TableCell sx={{ whiteSpace: "nowrap" }}>
                {token.last_used_at
                  ? `${formatTimestamp(token.last_used_at)} (${token.last_used_by ?? "unknown"})`
                  : "Never"}
              </TableCell>
              <TableCell padding="checkbox">
                <Tooltip title="Revoke token">
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => setDeleteConfirmToken(token)}
                    disabled={deleteToken.isPending}
                  >
                    <TrashCan />
                  </IconButton>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export function AccessTokens() {
  const tokensQuery = useProfileAccessTokens();
  const deleteToken = useProfileDeleteAccessToken();
  const tokens = tokensQuery.data?.access_tokens ?? [];

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [revealedToken, setRevealedToken] = useState<string | null>(null);
  const [deleteConfirmToken, setDeleteConfirmToken] =
    useState<types.AccessToken | null>(null);

  return (
    <Box sx={{ marginBottom: 3 }}>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ marginBottom: 2 }}
      >
        Tokens can be used to access the API and MJPEG streams. Pass the token
        as <strong>Authorization: Bearer &lt;token&gt;</strong> header in your
        requests.
      </Typography>

      <Button
        variant="contained"
        startIcon={<Add />}
        onClick={() => setCreateDialogOpen(true)}
        sx={{ marginBottom: 2 }}
      >
        Create token
      </Button>

      {/* Token list */}
      {tokensQuery.isLoading ? (
        <CircularProgress size={24} />
      ) : tokensQuery.isError ? (
        <Typography variant="body2" color="error" sx={{ marginBottom: 2 }}>
          Error loading access tokens.
          {tokensQuery.error?.message && ` ${tokensQuery.error.message}`}
        </Typography>
      ) : tokens.length === 0 ? (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ marginBottom: 2 }}
        >
          No tokens yet.
        </Typography>
      ) : (
        <TokenTable
          tokens={tokens}
          setDeleteConfirmToken={setDeleteConfirmToken}
          deleteToken={deleteToken}
        />
      )}

      <CreateTokenDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onCreated={(token) => {
          setCreateDialogOpen(false);
          setRevealedToken(token);
        }}
      />

      {revealedToken && (
        <TokenRevealDialog
          token={revealedToken}
          onClose={() => setRevealedToken(null)}
        />
      )}
      <DeleteTokenConfirmationDialog
        deleteConfirmToken={deleteConfirmToken}
        setDeleteConfirmToken={setDeleteConfirmToken}
        deleteToken={deleteToken}
      />
    </Box>
  );
}
