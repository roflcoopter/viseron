// Device Types

// Media Types

// Imaging Types

// PTZ Types
export type PtzConfigResponse = {
  user_config: {
    home_position: boolean;
    reverse_pan: boolean;
    reverse_tilt: boolean;
    presets?: PtzPresetUserConfig[];
  };
};

export type PtzPosition = {
  PanTilt?: {
    x: number;
    y: number;
  };
  Zoom?: {
    x: number;
  };
};

export type PtzStatusResponse = {
  status: {
    Position?: PtzPosition;
    MoveStatus?: {
      PanTilt?: string;
      Zoom?: string;
    };
    UtcTime?: string;
  };
};

export type PtzPresetUserConfig = {
  name: string;
  pan: number;
  tilt: number;
  zoom?: number;
  on_startup?: boolean;
};

export type PtzPreset = {
  Name?: string;
  type: "onvif";
  token: string;
  PTZPosition?: PtzPosition;
};

export type PtzPresetsResponse = {
  presets: PtzPreset[];
};

export type PtzNodesResponse = {
  nodes: any[];
};

export type PtzConfigurationsResponse = {
  configurations: any[];
};

export type PtzContinuousMoveParams = {
  x_velocity?: number;
  y_velocity?: number;
  zoom_velocity?: number;
};

export type PtzRelativeMoveParams = {
  x_translation?: number;
  y_translation?: number;
  zoom_translation?: number;
  x_speed?: number;
  y_speed?: number;
  zoom_speed?: number;
};

export type PtzAbsoluteMoveParams = {
  x_position?: number;
  y_position?: number;
  zoom_position?: number;
  x_speed?: number;
  y_speed?: number;
  zoom_speed?: number;
  is_adjusted?: boolean;
};
