// Object detector domain specific types
import { Coordinate, Mask } from "../shared/types";

export interface Label {
  label: string;
  confidence: number;
  trigger_event_recording?: boolean;
}

export interface ZoneLabel {
  label: string;
  confidence: number;
  trigger_event_recording: boolean;
}

export interface Zone {
  name: string;
  coordinates: Coordinate[];
  labels?: ZoneLabel[];
}

export interface ObjectDetectorComponentData {
  componentType: string;
  labels?: Label[];
  zones?: Zone[];
  mask?: Mask[];
  available_labels?: string[];
}
