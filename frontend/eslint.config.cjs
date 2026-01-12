const { defineConfig, globalIgnores } = require("eslint/config");
const { configs } = require("eslint-config-airbnb-extended/legacy");
const eslintConfigPrettier = require("eslint-config-prettier/flat");

const prettier = require("eslint-plugin-prettier");
const tsParser = require("@typescript-eslint/parser");
const tsEslintPlugin = require("@typescript-eslint/eslint-plugin");
const globals = require("globals");
const reactHooks = require("eslint-plugin-react-hooks");

// Custom rules
const noDayjsImport = require("./eslint-rules/no-direct-dayjs-import.cjs");

module.exports = defineConfig([
  ...configs.react.legacy,
  ...configs.react.base,
  ...configs.react.recommended,
  ...configs.react.hooks,
  ...configs.base.typescript,
  ...configs.react.typescript,

  {
    plugins: {
      prettier,
      "@typescript-eslint": tsEslintPlugin,
      "react-hooks": reactHooks,
      "viseron-custom": {
        rules: {
          "no-direct-dayjs-import": noDayjsImport,
        },
      },
    },

    languageOptions: {
      parser: tsParser,
      ecmaVersion: 2020,
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: { modules: true },
        project: "tsconfig.json",
        tsconfigRootDir: __dirname,
      },
      globals: {
        ...globals.browser,
      },
    },

    rules: {
      ...reactHooks.configs.recommended.rules,

      // Custom Viseron rules
      "viseron-custom/no-direct-dayjs-import": "error",

      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          vars: "all",
          varsIgnorePattern: "^_",
          args: "after-used",
          argsIgnorePattern: "^_",
          ignoreRestSiblings: true,
          caughtErrors: "none",
        },
      ],
      "@typescript-eslint/naming-convention": [
        "off",
        {
          selector: "default",
          format: ["camelCase", "snake_case"],
          leadingUnderscore: "allow",
          trailingUnderscore: "allow",
        },
        {
          selector: ["variable"],
          format: ["camelCase", "snake_case", "UPPER_CASE"],
          leadingUnderscore: "allow",
          trailingUnderscore: "allow",
        },
        {
          selector: "typeLike",
          format: ["PascalCase"],
        },
      ],
      "prefer-destructuring": "off",
      "no-underscore-dangle": "off",
      "no-param-reassign": "off",
      "no-restricted-syntax": ["error", "LabeledStatement", "WithStatement"],
      "import/no-cycle": "off", // Long term we should try to fix these
      "import/extensions": "off",
      "import/prefer-default-export": "off",
      "import/no-extraneous-dependencies": [
        "error",
        {
          devDependencies: [
            "**/*.test.ts",
            "**/*.test.tsx",
            "**/*.spec.ts",
            "**/*.spec.tsx",
            "**/tests/**/*.{tsx,ts}",
          ],
          optionalDependencies: false,
        },
      ],
      "no-console": "off",
      "no-plusplus": "off",
      "no-restricted-globals": "off",
      "no-restricted-imports": [
        "error",
        {
          patterns: ["@mui/*/*/*", "!@mui/material/test-utils/*"],
        },
      ],
      "no-nested-ternary": "off",
      "react/react-in-jsx-scope": "off",
      "react/require-default-props": "off",
      "react/jsx-props-no-spreading": [
        "error",
        {
          exceptions: ["TextField"],
        },
      ],
      "react-hooks/refs": "off", // This rule triggers a lot of errors and i dont fully understand it
      "jsx-a11y/media-has-caption": "off", // Not feasible to add captions for recordings
      "jsx-a11y/click-events-have-key-events": "off",
      "jsx-a11y/no-static-element-interactions": "off",
    },
  },

  eslintConfigPrettier,

  // Exception for dates.ts - it needs to import dayjs directly
  {
    files: ["src/lib/helpers/dates.ts"],
    rules: {
      "viseron-custom/no-direct-dayjs-import": "off",
    },
  },

  globalIgnores([
    "**/eslint.config.cjs",
    "**/vite.config.ts",
    "**/vitest.config.ts",
    "**/lint-staged.config.js",
    "**/video-rtc.js",
    "src/components/editor/yaml.worker.js",
  ]),
]);
