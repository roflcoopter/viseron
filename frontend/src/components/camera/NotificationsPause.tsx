import { Notification, NotificationOff } from "@carbon/icons-react";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import ListSubheader from "@mui/material/ListSubheader";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Tooltip from "@mui/material/Tooltip";
import { useState } from "react";

import { useCameraNotifications } from "lib/api/camera";
import { useCamerasNotifications } from "lib/api/cameras";
import {
  getDayjs,
  getDayjsFromDateTimeString,
  getDisplayDateStringFromDayjs,
  getTimeStringFromDayjs,
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
  onPause: (duration?: number) => void;
  onResume?: () => void;
  header: string;
};

function NotificationsPauseMenu({
  anchorEl,
  onClose,
  onPause,
  onResume,
  header,
}: NotificationsPauseMenuProps) {
  return (
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
            onPause(seconds);
            onClose();
          }}
        >
          {label}
        </MenuItem>
      ))}
    </Menu>
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
        onPause={(duration) =>
          notifications.mutate({ camera, action: "pause", duration })
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
        onPause={(duration) =>
          notifications.mutate({ action: "pause", duration })
        }
        onResume={() => notifications.mutate({ action: "resume" })}
      />
    </>
  );
}
