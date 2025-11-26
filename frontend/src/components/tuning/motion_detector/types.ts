// Motion detector domain specific types
import { Mask } from "../shared/types";

export interface MotionDetectorComponentData {
  componentType: string;
  mask?: Mask[];
}
