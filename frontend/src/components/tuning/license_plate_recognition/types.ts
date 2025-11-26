// License plate recognition domain specific types
import { Mask } from "../shared/types";

export interface LicensePlateRecognitionComponentData {
  componentType: string;
  labels?: string[];
  mask?: Mask[];
  available_labels?: string[];
}
