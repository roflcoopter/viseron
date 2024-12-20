import { AxiosError } from "axios";
import { Dayjs } from "dayjs";

export type SystemInformation = {
  version: string;
  git_commit: string;
  safe_mode: boolean;
};

type WebSocketAuthOkResponse = {
  type: "auth_ok";
  message: string;
  system_information: SystemInformation;
};

type WebSocketAuthRequiredResponse = {
  type: "auth_required";
  message: string;
};

type WebSocketAuthNotRequiredResponse = {
  type: "auth_not_required";
  message: string;
  system_information: SystemInformation;
};

type WebSocketAuthInvalidResponse = {
  type: "auth_failed";
  message: string;
};

export type WebSocketAuthResponse =
  | WebSocketAuthOkResponse
  | WebSocketAuthRequiredResponse
  | WebSocketAuthNotRequiredResponse
  | WebSocketAuthInvalidResponse;

type WebSocketPongResponse = {
  command_id: number;
  type: "pong";
};

export type WebSocketSubscriptionResultResponse = {
  command_id: number;
  type: "subscription_result";
  result: Event | HlsAvailableTimespans;
};

export type WebSocketSubscriptionCancelResponse = {
  command_id: number;
  type: "cancel_subscription";
};

export type WebSocketResultResponse = {
  command_id: number;
  type: "result";
  success: true;
  result: any;
};

export type WebSocketResultErrorResponse = {
  command_id: number;
  type: "result";
  success: false;
  error: {
    code: string;
    message: string;
  };
};

export type WebSocketResponse =
  | WebSocketPongResponse
  | WebSocketSubscriptionResultResponse
  | WebSocketSubscriptionCancelResponse
  | WebSocketResultResponse
  | WebSocketResultErrorResponse;

export type APISuccessResponse = {
  success: true;
};

export type APIErrorResponse = AxiosError<{
  status: number;
  error: string;
}>;

export type AuthEnabledResponse = {
  enabled: boolean;
  onboarding_complete: boolean;
};

export type AuthTokenResponse = {
  header: string;
  payload: string;
  expiration: number;
  expires_at: string;
  expires_at_timestamp: number;
  session_expires_at: string;
  session_expires_at_timestamp: number;
};

export type StoredTokens = {
  header: string;
  payload: string;
  expiration: number;
  expires_at: Dayjs;
  expires_at_timestamp: number;
  session_expires_at: Dayjs;
  session_expires_at_timestamp: number;
};

export type AuthUserResponse = {
  name: string;
  username: string;
  group: string;
};

export type AuthLoginResponse = AuthTokenResponse;
export type OnboardingResponse = AuthTokenResponse;

export interface Recording {
  id: number;
  camera_identifier: string;
  start_time: string;
  start_timestamp: number;
  end_time: string;
  end_timestamp: number;
  trigger_type: string;
  trigger_id: number;
  thumbnail_path: string;
  hls_url: string;
}

export interface RecordingsAll {
  [identifier: string]: {
    [date: string]: {
      [id: string]: Recording;
    };
  };
}

export interface RecordingsCamera {
  [date: string]: {
    [id: string]: Recording;
  };
}

export interface Camera {
  identifier: string;
  name: string;
  width: number;
  height: number;
  access_token: string;
  still_image_refresh_interval: number;
  failed: false;
  is_on: boolean;
  connected: boolean;
}

export interface Cameras {
  [identifier: string]: Camera;
}

export interface FailedCamera {
  identifier: string;
  name: string;
  width: number;
  height: number;
  error: string;
  retrying: boolean;
  failed: true;
}

export interface FailedCameras {
  [identifier: string]: FailedCamera;
}

export interface CamerasOrFailedCameras {
  [identifier: string]: Camera | FailedCamera;
}

export interface DetectedObject {
  label: string;
  confidence: number;
  rel_width: number;
  rel_height: number;
  rel_x1: number;
  rel_y1: number;
  rel_x2: number;
  rel_y2: number;
}

export type EventBase = {
  timestamp: number;
};

export type Event = EventBase & {
  name: string;
  data: { [key: string]: any };
};

export type EventCameraRegistered = Event & {
  name: "camera_registered";
  data: Camera;
};

export type EventRecorder = Event & {
  data: {
    camera: Camera;
    recording: Recording & {
      start_time: string;
      start_timestamp: number;
      end_time: string;
      end_timestamp: number;
      objects: [DetectedObject];
    };
  };
};

export type EventRecorderStart = EventRecorder & {
  name: "recorder_start";
};
export type EventRecorderStop = EventRecorder & {
  name: "recorder_stop";
};
export interface EntityAttributes {
  name: string;
  domain: string;
  [key: string]: any;
}

type CameraBaseEvent = {
  camera_identifier: string;
  id: number;
  created_at: string;
  created_at_timestamp: number;
};

type CameraBaseTimedEvent = CameraBaseEvent & {
  start_time: string;
  start_timestamp: number;
  end_time: string | null;
  end_timestamp: number | null;
  duration: number | null;
};
export type CameraMotionEvent = CameraBaseTimedEvent & {
  type: "motion";
  snapshot_path: string;
};
export type CameraRecordingEvent = CameraBaseTimedEvent & {
  type: "recording";
  trigger_type: "motion" | "object" | null;
  hls_url: string;
  thumbnail_path: string;
};
export type CameraTimedEvents = CameraMotionEvent | CameraRecordingEvent;

type CameraBaseSnapshotEvent = CameraBaseEvent & {
  time: string;
  timestamp: number;
  snapshot_path: string;
};
export type CameraObjectEvent = CameraBaseSnapshotEvent & {
  type: "object";
  time: string;
  timestamp: number;
  label: string;
  confidence: number;
};
export type CameraFaceRecognitionEvent = CameraBaseSnapshotEvent & {
  type: "face_recognition";
  data: {
    name: string;
    confidence: number;
    [key: string]: any;
  };
};
export type CameraLicensePlateRecognitionEvent = CameraBaseSnapshotEvent & {
  type: "license_plate_recognition";
  data: {
    camera_identifier: string;
    known: boolean;
    plate: string;
    confidence: number;
  };
};

export type CameraEvent =
  | CameraMotionEvent
  | CameraObjectEvent
  | CameraRecordingEvent
  | CameraFaceRecognitionEvent
  | CameraLicensePlateRecognitionEvent;

export type CameraEvents = {
  events: CameraEvent[];
};

export type CameraSnapshotEvent =
  | CameraObjectEvent
  | CameraFaceRecognitionEvent
  | CameraLicensePlateRecognitionEvent;
export type CameraSnapshotEvents = Array<CameraSnapshotEvent>;

export type CameraObjectEvents = Array<CameraObjectEvent>;

export type EventsAmount = {
  events_amount: {
    [date: string]: {
      motion?: number;
      object?: number;
      recording?: number;
      face_recognition?: number;
      license_plate_recognition?: number;
    };
  };
};

export interface Entity {
  entity_id: string;
  state: string;
  attributes: EntityAttributes;
}

export interface Entities {
  [index: string]: Entity;
}

export interface State {
  entity_id: string;
  state: string;
  attributes: EntityAttributes;
  timestamp: number;
}

export type StateChangedEvent = EventBase & {
  name: "state_changed";
  data: {
    entity_id: string;
    current_state: State;
    previous_state: State;
  };
};

export type HlsAvailableTimespan = {
  start: number;
  end: number;
  duration: number;
};

export type HlsAvailableTimespans = {
  timespans: HlsAvailableTimespan[];
};

export type DownloadFileResponse = {
  filename: string;
  token: string;
};
