/* eslint-disable no-nested-ternary */
// Have to disable no-explicit-any, since i have no idea how to type the complex JSON in the config.json files

/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react";

import CodeBlock from "@theme/CodeBlock";
import Tippy from "@tippyjs/react";
import clsx from "clsx";
import yaml from "js-yaml";
import "tippy.js/dist/tippy.css";

import styles from "./styles.module.css";

// Return list of valid values recursively
function getValidValues(options) {
  let recursiveOptions = [];

  options.forEach((option) => {
    if (option.options) {
      recursiveOptions = recursiveOptions.concat(
        getValidValues(option.options)
      );
    } else if (option.value) {
      recursiveOptions.push(option);
    } else {
      recursiveOptions.push(option);
    }
  });
  return recursiveOptions;
}

// Return div that contains valid values for the config option
function buildValidValues(item: any) {
  if (item.options) {
    return (
      <div className={styles.configVariablesValues}>
        Valid values:
        <ul className={styles.configVariablesValidValuesValue}>
          {getValidValues(item.options).map((option, index) => (
            <li key={`${option.value}${index}`}>
              <code>
                {option.value === undefined ? `<${option.type}>` : option.value}
              </code>
              {option.description ? `: ${option.description}` : null}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return null;
}

// Return div with lowest and/or highest value
function buildMinMax(item: any) {
  if (item.valueMin !== undefined || item.valueMax !== undefined) {
    return (
      <div className={styles.configVariablesMinMax}>
        {item.valueMin !== undefined ? (
          <div className={styles.configVariablesMin}>
            Lowest value: <code>{item.valueMin}</code>
          </div>
        ) : null}

        {item.valueMax !== undefined ? (
          <div className={styles.configVariablesMax}>
            Highest value: <code>{item.valueMax}</code>
          </div>
        ) : null}
      </div>
    );
  }
  if (item.lengthMin !== undefined || item.lengthMax !== undefined) {
    return (
      <div className={styles.configVariablesMinMax}>
        {item.lengthMin !== undefined ? (
          <div className={styles.configVariablesMin}>
            Minimum items: <code>{item.lengthMin}</code>
          </div>
        ) : null}

        {item.lengthMax !== undefined ? (
          <div className={styles.configVariablesMax}>
            Maximum items: <code>{item.lengthMax}</code>
          </div>
        ) : null}
      </div>
    );
  }
  return null;
}

// Return div with description
function buildDescription(item: any) {
  let { description } = item;
  if (item.deprecated) {
    description = `<b>DEPRECATED</b>. ${item.name.value}<br><br>${description}`;
  }
  return (
    <div className={styles.configVariablesDescription}>
      {description ? (
        <div
          dangerouslySetInnerHTML={{
            __html: description,
          }}
        />
      ) : (
        "Description missing!"
      )}
    </div>
  );
}

function getName(item: any) {
  if (typeof item.name === "string") {
    return item.name;
  }
  if (item.name.name) {
    return item.name.name;
  }
  return `<${item.name.type}>`;
}

function getDefault(item: any) {
  function getCodeBlock() {
    return (
      <span className={styles.configVariablesDefault}>
        , default:
        <Tippy
          interactive={true}
          content={
            <span>
              <CodeBlock language="yaml">
                {styles.configVariablesDefault}
                {yaml.dump(item.default, {
                  noCompatMode: true,
                  lineWidth: -1,
                })}
              </CodeBlock>
            </span>
          }
        >
          <span style={{ borderBottom: "#8792a2 dotted 0.5px" }}>
            {" hover to show)"}
          </span>
        </Tippy>
      </span>
    );
  }

  // Handle object defaults
  if (
    item.optional &&
    item.default !== null &&
    typeof item.default === "object" &&
    !Array.isArray(item.default) &&
    Object.keys(item.default).length > 0
  ) {
    // Show object defaults in a CodeBlock tooltip
    return getCodeBlock();
  }

  // Handle array defaults
  if (
    item.optional &&
    item.default !== null &&
    // Only display default values for arrays if the length is greater than zero
    Array.isArray(item.default) &&
    item.default.length > 0
  ) {
    // Show array defaults in a CodeBlock tooltip
    return getCodeBlock();
  }

  // Handle other defaults
  if (
    item.optional &&
    item.default !== null &&
    !Array.isArray(item.default) &&
    !(typeof item.default === "object")
  ) {
    return (
      <span className={styles.configVariablesDefault}>
        , default: <code>{item.default.toString()}</code>)
      </span>
    );
  }

  if (item.optional) {
    return ")";
  }
  return null;
}

// Return div with header containing item name/type/required/default value
function buildHeader(item: any) {
  const optional = item.optional || item.inclusive;
  return (
    <div className="config-variables-header">
      {item.name ? (
        <span className={styles.configVariablesName}>{getName(item)}</span>
      ) : null}
      {/* Zero width space to prevent selecting type when double clicking the name */}
      &#8203;
      <span className={styles.configVariablesType}>
        {item.format ? item.format : item.type}
      </span>
      <span className={styles.configVariablesRequired}>
        {optional ? " (" : null}
        <span
          className={clsx(styles.configVariablesRequired, {
            [styles.true]: !optional,
          })}
        >
          {optional
            ? "optional"
            : item.deprecated
            ? " deprecated"
            : " required"}
        </span>
        {getDefault(item)}
      </span>
    </div>
  );
}

// Return div that represents a single config item
function buildItem(item: ComponentConfigurationType, children: any, index) {
  const [isCollapsed, setIsCollapsed] = React.useState(
    !!(item.type === "map" && item.optional)
  );

  return (
    <div
      className={styles.configVariablesItem}
      key={`${index}${item.type}${item.name}`}
    >
      <div style={{ display: "flex", alignItems: "center" }}>
        {buildHeader(item)}
        {children ? (
          <button
            type="button"
            className={`collapse-button clean-btn menu__caret ${
              isCollapsed ? "collapsed menu__list-item--collapsed" : ""
            }`}
            onClick={() => setIsCollapsed(!isCollapsed)}
          ></button>
        ) : null}
      </div>
      {buildDescription(item)}
      <div
        className={`collapse-content ${isCollapsed ? "collapsed" : "expanded"}`}
        aria-expanded={isCollapsed}
      >
        {buildMinMax(item)}
        {buildValidValues(item)}

        {children ? (
          <div className={styles.configVariablesChildren}>{children}</div>
        ) : null}
      </div>
    </div>
  );
}

function configOption(_config: ComponentConfigurationType, index) {
  if (_config.type === "list") {
    if (_config.values && Array.isArray(_config.values[0])) {
      return buildItem(
        _config,
        _config.values[0].map((children) => configOption(children, index)),
        index
      );
    }
  }

  if (_config.type === "map") {
    return buildItem(
      _config,
      _config.value.map((children) => configOption(children, index)),
      index
    );
  }
  return buildItem(_config, null, index);
}

type ComponentConfigurationType = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
};

function ComponentConfiguration({
  config,
}: {
  config: ComponentConfigurationType;
}) {
  return (
    <span>
      <div className={clsx(styles.configVariables)}>
        {config.map((_config, index) => configOption(_config, index))}
      </div>
    </span>
  );
}

export default React.memo(ComponentConfiguration);
