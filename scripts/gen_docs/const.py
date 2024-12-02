# pylint: disable=line-too-long

"""gen_docs constants."""

EXCLUDED_COMPONENTS = ["data_stream"]

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
import ComponentTroubleshooting from "@site/src/pages/components-explorer/components/troubleshooting.mdx";

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

DOCS_FOOTER = """<ComponentTroubleshooting meta={ComponentMetadata} />
"""

DOCS_OBJECT_DETECTOR_IMPORTS = """import ObjectDetector from "@site/src/pages/components-explorer/_domains/object_detector/index.mdx";
"""

DOCS_OBJECT_DETECTOR_CONTENTS = """<ObjectDetector labelPath={<CHANGEME>} />

"""


DOCS_FACE_RECOGNITION_IMPORTS = """import FaceRecognition from "@site/src/pages/components-explorer/_domains/face_recognition/index.mdx";
"""

DOCS_FACE_RECOGNITION_CONTENTS = """<FaceRecognition />

"""


DOCS_MOTION_DETECTOR_IMPORTS = """import MotionDetector from "@site/src/pages/components-explorer/_domains/motion_detector/index.mdx";
"""

DOCS_MOTION_DETECTOR_CONTENTS = """<MotionDetector meta={ComponentMetadata} />

"""

DOCS_IMAGE_CLASSIFICATION_IMPORTS = """import ImageClassification from "@site/src/pages/components-explorer/_domains/image_classification/index.mdx";
import ImageClassificationLabels from "@site/src/pages/components-explorer/_domains/image_classification/labels.mdx";
"""

DOCS_IMAGE_CLASSIFICATION_CONTENTS = """## Image classification

<ImageClassification />

### Labels

<ImageClassificationLabels />

"""

DOCS_CAMERA_IMPORTS = """import Camera from "@site/src/pages/components-explorer/_domains/camera/index.mdx";
"""

DOCS_CAMERA_CONTENTS = """<Camera />

"""

DOCS_LICENSE_PLATE_RECOGNITION_IMPORTS = """import LicensePlateRecognition from "@site/src/pages/components-explorer/_domains/license_plate_recognition/index.mdx";
"""

DOCS_LICENSE_PLATE_RECOGNITION_CONTENTS = """## License plate recognition

<LicensePlateRecognition />

"""


DOMAIN_IMPORTS = {
    "camera": DOCS_CAMERA_IMPORTS,
    "face_recognition": DOCS_FACE_RECOGNITION_IMPORTS,
    "image_classification": DOCS_IMAGE_CLASSIFICATION_IMPORTS,
    "license_plate_recognition": DOCS_LICENSE_PLATE_RECOGNITION_IMPORTS,
    "motion_detector": DOCS_MOTION_DETECTOR_IMPORTS,
    "object_detector": DOCS_OBJECT_DETECTOR_IMPORTS,
}

DOMAIN_CONTENT = {
    "camera": DOCS_CAMERA_CONTENTS,
    "face_recognition": DOCS_FACE_RECOGNITION_CONTENTS,
    "image_classification": DOCS_IMAGE_CLASSIFICATION_CONTENTS,
    "license_plate_recognition": DOCS_LICENSE_PLATE_RECOGNITION_CONTENTS,
    "motion_detector": DOCS_MOTION_DETECTOR_CONTENTS,
    "object_detector": DOCS_OBJECT_DETECTOR_CONTENTS,
}
