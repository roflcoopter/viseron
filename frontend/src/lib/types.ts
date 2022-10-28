export type EventBase = {
  timestamp: number;
};

export type Event = EventBase & {
  name: string;
  data: { [key: string]: any };
};

export type StateChangedEvent = EventBase & {
  name: "state_changed";
  data: {
    entity_id: string;
    current_state: any | null;
    previous_state: any | null;
  };
};

export interface Recording {
  date: string
  filename: string
  path: string
  thumbnail_path: string
}

export interface Recordings {
  [index: string]: {
    [index: string]: Recording
  }
}

export interface Camera {
  identifier: string;
  name: string;
  width: number;
  height: number;
  recordings: Recordings;
}


export interface Cameras {
  [index: string]: Camera;
}

export type CameraRegisteredEvent = EventBase & {
  name: "camera_registered";
  data: Camera;
};


export type WebSocketEventResponse = {
  command_id: number;
  type: "event";
  event: Event;
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
  | WebSocketEventResponse
  | WebSocketResultResponse
  | WebSocketResultErrorResponse;
