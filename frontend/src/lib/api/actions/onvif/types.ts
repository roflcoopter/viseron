// Service Types ----------------------------------------------------------------------

export type ServiceCapabilitiesResponse = {
  capabilities: any;
};

// Device Types -----------------------------------------------------------------------

export type DeviceInformationResponse = {
  information: any;
};

export type DeviceScope = {
  ScopeDef: string;
  ScopeItem: string;
};

export type DeviceScopesResponse = {
  scopes: DeviceScope[];
};

export type DeviceServicesResponse = {
  services: any;
};

export type DeviceUser = {
  Username: string;
  Password?: string | null;
  UserLevel: string;
};

export type DeviceUsersResponse = {
  users: DeviceUser[];
};

export type DeviceSystemDateAndTimeResponse = {
  system_date: any;
};

export type DeviceSystemDateAndTimeParams = {
  datetime_type?: string;
  daylight_savings?: boolean;
  timezone?: string;
  utc_datetime?: {
    Time: {
      Hour: number;
      Minute: number;
      Second: number;
    };
    Date: {
      Year: number;
      Month: number;
      Day: number;
    };
  };
};

export type DeviceHostnameResponse = {
  hostname: any;
};

export type DeviceNetworkDefaultGatewayResponse = {
  network_default_gateway: any;
};

export type DeviceNetworkDefaultGatewayParams = {
  ipv4_address?: string;
  ipv6_address?: string;
};

export type DeviceNetworkInterfacesResponse = {
  network_interfaces: any[];
};

export type DeviceNetworkInterfaceSetParams = {
  interface_token: string;
  network_interface: any;
};

export type DeviceNetworkInterfacesParams = {
  network_interfaces: DeviceNetworkInterfaceSetParams;
};

export type DeviceNetworkProtocolsResponse = {
  network_protocols: any[];
};

export type DeviceNetworkProtocolsParams = {
  network_protocols: any[];
};

export type DeviceNTPResponse = {
  ntp: any;
};

export type DeviceNTPParams = {
  from_dhcp?: boolean;
  ntp_manual?: any[];
};

export type DeviceDNSResponse = {
  dns: any;
};

export type DeviceDNSParams = {
  from_dhcp?: boolean;
  search_domain?: any[];
  dns_manual?: any[];
};

// Media Types ------------------------------------------------------------------------

export type MediaProfilesResponse = {
  profiles: any[];
};

// Imaging Types ----------------------------------------------------------------------

export type ImagingSettingsResponse = {
  settings: any;
};

export type ImagingOptionsResponse = {
  options: any;
};

export type ImagingPresetsResponse = {
  presets: any[];
};

export type ImagingMoveOptionsResponse = {
  move_options: any;
};

export type ImagingMoveParams = {
  Absolute?: {
    Position: number;
    Speed?: number;
  };
  Relative?: {
    Distance: number;
    Speed?: number;
  };
  Continuous?: {
    Speed: number;
  };
};

// PTZ Types --------------------------------------------------------------------------

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
