// Face recognition domain specific types
import { Mask } from "../shared/types";

export interface FaceRecognitionComponentData {
  componentType: string;
  labels?: string[];
  mask?: Mask[];
  available_labels?: string[];
}
