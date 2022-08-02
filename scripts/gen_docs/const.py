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

DOCS_OBJECT_DETECTOR_IMPORTS = """import ObjectDetectorLabels from "@site/src/pages/components-explorer/_domains/object_detector/labels.mdx";
import ObjectDetectorMask from "@site/src/pages/components-explorer/_domains/object_detector/mask.mdx";
import ObjectDetectorZones from "@site/src/pages/components-explorer/_domains/object_detector/zones.mdx";
"""

DOCS_OBJECT_DETECTOR_CONTENTS = """## Object detector

### Labels

<ObjectDetectorLabels label_path="/detectors/models/darknet/coco.names" />

### Zones

<ObjectDetectorZones />

### Mask

<ObjectDetectorMask />
"""
