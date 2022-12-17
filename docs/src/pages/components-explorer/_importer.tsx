// Dynamically import component meta files
import { camelCase } from "lodash-es";

import { Component } from "@site/src/types";

const requireModule = require.context("./components", true, /meta.tsx$/);

interface Components {
  [key: string]: Component;
}

const componentList: Components = {};

requireModule
  .keys()
  .sort()
  .forEach((fileName) => {
    if (fileName === "./index.tsx") return;
    const moduleName = camelCase(fileName.replace(/(\.\/|\._meta.tsx)/g, ""));
    componentList[moduleName] = {
      ...requireModule(fileName).default,
    };
  });

export default componentList;
