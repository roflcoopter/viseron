# pylint: disable=line-too-long

"""gen_docs constants."""

META_CONTENTS = """import {{ Component }} from "@site/src/types";

const ComponentMetadata: Component = {{
  title: "<ENTER VALUE>",
  name: "{component}",
  description: "<ENTER VALUE>",
  image: "<ENTER VALUE>",
  tags: {tags},
}};

export default ComponentMetadata;

"""

DOCS_IMPORTS = """import ComponentConfiguration from "@site/src/pages/components-explorer/_components/ComponentConfiguration";
import ComponentHeader from "@site/src/pages/components-explorer/_components/ComponentHeader";
import ComponentMetadata from "./_meta";
import config from "./config.json";
"""

DOCS_CONTENTS = """
<ComponentHeader meta={ComponentMetadata} />

-- Provide short summary here --

## Configuration

<details>
  <summary>Configuration example</summary>

```yaml
Config example here
```

</details>

<ComponentConfiguration meta={ComponentMetadata} config={config} />

"""


DOCS_OBJECT_DETECTOR_IMPORTS = """import ObjectDetector from "@site/src/pages/components-explorer/_domains/object_detector/index.mdx";
import ObjectDetectorLabels from "@site/src/pages/components-explorer/_domains/object_detector/labels.mdx";
import ObjectDetectorMask from "@site/src/pages/components-explorer/_domains/object_detector/mask.mdx";
import ObjectDetectorZones from "@site/src/pages/components-explorer/_domains/object_detector/zones.mdx";
"""

DOCS_OBJECT_DETECTOR_CONTENTS = """## Object detector

<ObjectDetector />

### Labels

<ObjectDetectorLabels label_path="/detectors/models/darknet/coco.names" />

### Zones

<ObjectDetectorZones />

### Mask

<ObjectDetectorMask />

"""


DOCS_FACE_RECOGNITION_IMPORTS = """import FaceRecognition from "@site/src/pages/components-explorer/_domains/face_recognition/index.mdx";
import FaceRecognitionLabels from "@site/src/pages/components-explorer/_domains/face_recognition/labels.mdx";
import FaceRecognitionTrain from "@site/src/pages/components-explorer/_domains/face_recognition/train.mdx";
"""

DOCS_FACE_RECOGNITION_CONTENTS = """## Face recognition

<FaceRecognition />

### Labels

<FaceRecognitionLabels />

### Train

<FaceRecognitionTrain />

"""


DOCS_MOTION_DETECTOR_IMPORTS = """import MotionDetector from "@site/src/pages/components-explorer/_domains/motion_detector/index.mdx";
import MotionDetectorMask from "@site/src/pages/components-explorer/_domains/motion_detector/mask.mdx";
"""

DOCS_MOTION_DETECTOR_CONTENTS = """## Motion detector

<MotionDetector />

### Mask

<MotionDetectorMask />

"""

DOCS_IMAGE_CLASSIFICATION_IMPORTS = """import ImageClassification from "@site/src/pages/components-explorer/_domains/image_classification/index.mdx";
import ImageClassificationLabels from "@site/src/pages/components-explorer/_domains/image_classification/labels.mdx"
"""

DOCS_IMAGE_CLASSIFICATION_CONTENTS = """## Image classification

<ImageClassification />

### Labels

<ImageClassificationLabels />

"""

DOCS_CAMERA_IMPORTS = """import Camera from "@site/src/pages/components-explorer/_domains/camera/index.mdx"
import CameraMjpegStreams from "@site/src/pages/components-explorer/_domains/camera/mjpeg_streams.mdx";
"""

DOCS_CAMERA_CONTENTS = """## Camera

<Camera />

### MJEPG Streams

<CameraMjpegStreams />

"""

DOMAIN_IMPORTS = {
    "camera": DOCS_CAMERA_IMPORTS,
    "face_recognition": DOCS_FACE_RECOGNITION_IMPORTS,
    "image_classification": DOCS_IMAGE_CLASSIFICATION_IMPORTS,
    "motion_detector": DOCS_MOTION_DETECTOR_IMPORTS,
    "object_detector": DOCS_OBJECT_DETECTOR_IMPORTS,
}

DOMAIN_CONTENT = {
    "camera": DOCS_CAMERA_CONTENTS,
    "face_recognition": DOCS_FACE_RECOGNITION_CONTENTS,
    "image_classification": DOCS_IMAGE_CLASSIFICATION_CONTENTS,
    "motion_detector": DOCS_MOTION_DETECTOR_CONTENTS,
    "object_detector": DOCS_OBJECT_DETECTOR_CONTENTS,
}
