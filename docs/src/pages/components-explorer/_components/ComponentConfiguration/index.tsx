// Have to disable no-explicit-any, since i have no idea how to type the complex JSON in the config.json files

/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react";

import clsx from "clsx";

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
  return null;
}

// Return div with description
function buildDescription(item: any) {
  return (
    <div className={styles.configVariablesDescription}>
      {item.description ? (
        <div
          dangerouslySetInnerHTML={{
            __html: item.description,
          }}
        />
      ) : (
        "Description missing!"
      )}
    </div>
  );
}

// Return div with header containing item name/type/required/default value
function buildHeader(item: any) {
  return (
    <div className="config-variables-header">
      {item.name ? (
        <span className={styles.configVariablesName}>{item.name}</span>
      ) : null}
      <span className={styles.configVariablesType}>{item.type}</span>

      <span className={styles.configVariablesRequired}>
        {item.optional ? " (" : null}
        <span
          className={clsx(styles.configVariablesRequired, {
            [styles.true]: !item.optional,
          })}
        >
          {item.optional ? "optional" : " required"}
        </span>
        {item.optional &&
        item.default !== null &&
        !(Array.isArray(item.default) && item.default.length === 0) ? (
          <span className={styles.configVariablesDefault}>
            , default: <code>{item.default.toString()}</code>
          </span>
        ) : null}
        {item.optional ? ")" : null}
      </span>
    </div>
  );
}

// Return div that represents a single config item
function buildItem(item: ComponentConfigurationType, children: any, index) {
  const [isCollapsed, setIsCollapsed] = React.useState(false);

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
      <div
        className={`collapse-content ${isCollapsed ? "collapsed" : "expanded"}`}
        aria-expanded={isCollapsed}
      >
        {buildDescription(item)}
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
  if (_config.type === "map" && _config.key) {
    // Recursively build up all child nodes
    return buildItem(
      _config,
      buildItem(
        {
          ..._config,
          type: _config.key.type,
          name: _config.key.name,
          description: _config.key.description,
        },
        _config.value.map((children) => configOption(children, index)),
        index
      ),
      index
    );
  }

  if (_config.type === "list") {
    if (Array.isArray(_config.values[0])) {
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
      <div className="config-variables">
        {config.map((_config, index) => configOption(_config, index))}
      </div>
    </span>
  );
}

export default React.memo(ComponentConfiguration);
