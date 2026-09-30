import { Notification, NotificationOff } from "@carbon/icons-react";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import IconButton from "@mui/material/IconButton";
import ListSubheader from "@mui/material/ListSubheader";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Tooltip from "@mui/material/Tooltip";
import { DateTimePicker } from "@mui/x-date-pickers/DateTimePicker";
import { Dayjs } from "dayjs";
import { useState } from "react";

import { useCameraNotifications } from "lib/api/camera";
import { useCamerasNotifications } from "lib/api/cameras";
import {
  getDayjs,
  getDayjsFromDateTimeString,
  getDisplayDateStringFromDayjs,
  getDisplayDateTimeFormat,
  getTimeStringFromDayjs,
  is12HourFormat,
} from "lib/helpers/dates";
import * as types from "lib/types";

export const PAUSE_DURATIONS: { label: string; seconds?: number }[] = [
  { label: "Pause for 15 minutes", seconds: 15 * 60 },
  { label: "Pause for 1 hour", seconds: 60 * 60 },
  { label: "Pause for 4 hours", seconds: 4 * 60 * 60 },
  { label: "Pause for 8 hours", seconds: 8 * 60 * 60 },
  { label: "Pause until resumed" },
];

export function pausedUntilText(camera: types.Camera) {
  if (!camera.notifications_paused) {
    return "Pause notifications";
  }
  if (!camera.notifications_paused_until) {
    return "Notifications paused until resumed";
  }
  const until = getDayjsFromDateTimeString(camera.notifications_paused_until);
  const time = getTimeStringFromDayjs(until, false);
  return until.isSame(getDayjs(), "day")
    ? `Notifications paused until ${time}`
    : `Notifications paused until ${getDisplayDateStringFromDayjs(until)} ${time}`;
}

type NotificationsPauseMenuProps = {
  anchorEl: HTMLElement | null;
  onClose: () => void;
  onPause: (pause: { duration?: number; until?: string }) => void;
  onResume?: () => void;
  header: string;
};

type PauseUntilDialogProps = {
  open: boolean;
  onClose: () => void;
  onPause: (until: string) => void;
};

function PauseUntilDialog({ open, onClose, onPause }: PauseUntilDialogProps) {
  const [until, setUntil] = useState<Dayjs | null>(null);
  const valid = until !== null && until.isValid() && until.isAfter(getDayjs());

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Pause notifications until</DialogTitle>
      <DialogContent>
        <DateTimePicker
          label="Resume at"
          value={until}
          onChange={setUntil}
          onAccept={setUntil}
          disablePast
          closeOnSelect={false}
          ampm={is12HourFormat()}
          format={getDisplayDateTimeFormat()}
          sx={{ mt: 1 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          disabled={!valid}
          onClick={() => {
            onPause(until!.toISOString());
            onClose();
          }}
        >
          Pause
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function NotificationsPauseMenu({
  anchorEl,
  onClose,
  onPause,
  onResume,
  header,
}: NotificationsPauseMenuProps) {
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <>
      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={onClose}>
        <ListSubheader>{header}</ListSubheader>
        {onResume && (
          <MenuItem
            onClick={() => {
              onResume();
              onClose();
            }}
          >
            Resume notifications
          </MenuItem>
        )}
        {PAUSE_DURATIONS.map(({ label, seconds }) => (
          <MenuItem
            key={label}
            onClick={() => {
              onPause({ duration: seconds });
              onClose();
            }}
          >
            {label}
          </MenuItem>
        ))}
        <MenuItem
          onClick={() => {
            setDialogOpen(true);
            onClose();
          }}
        >
          Pause until...
        </MenuItem>
      </Menu>
      <PauseUntilDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onPause={(until) => onPause({ until })}
      />
    </>
  );
}

const iconStyle = {
  width: "clamp(16px, 3vw, 20px)",
  height: "clamp(16px, 3vw, 20px)",
};

export function CameraNotificationsButton({
  camera,
}: {
  camera: types.Camera;
}) {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const notifications = useCameraNotifications();
  const text = pausedUntilText(camera);

  return (
    <>
      <Tooltip title={text}>
        <IconButton
          data-testid="camera-notifications-button"
          aria-label={text}
          color={camera.notifications_paused ? "warning" : "default"}
          disabled={notifications.isPending}
          onClick={(event) => setAnchorEl(event.currentTarget)}
        >
          {camera.notifications_paused ? (
            <NotificationOff style={iconStyle} />
          ) : (
            <Notification style={iconStyle} />
          )}
        </IconButton>
      </Tooltip>
      <NotificationsPauseMenu
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        header={text}
        onPause={(pause) =>
          notifications.mutate({ camera, action: "pause", ...pause })
        }
        onResume={
          camera.notifications_paused
            ? () => notifications.mutate({ camera, action: "resume" })
            : undefined
        }
      />
    </>
  );
}

export function AllCamerasNotificationsButton() {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const notifications = useCamerasNotifications();

  return (
    <>
      <Button
        data-testid="all-cameras-notifications-button"
        size="small"
        startIcon={<NotificationOff size={16} />}
        disabled={notifications.isPending}
        onClick={(event) => setAnchorEl(event.currentTarget)}
      >
        Pause notifications
      </Button>
      <NotificationsPauseMenu
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        header="All cameras"
        onPause={(pause) => notifications.mutate({ action: "pause", ...pause })}
        onResume={() => notifications.mutate({ action: "resume" })}
      />
    </>
  );
}
