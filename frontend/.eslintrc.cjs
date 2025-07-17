const { defineConfig } = require("eslint-define-config");

module.exports = defineConfig({
  extends: [
    "airbnb-base",
    "airbnb-typescript/base",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
    "prettier",
  ],
  plugins: ["prettier"],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: 2020,
    ecmaFeatures: {
      modules: true,
    },
    sourceType: "module",
    project: "tsconfig.json",
    tsconfigRootDir: __dirname,
  },
  env: {
    browser: true,
  },
  ignorePatterns: [
    ".eslintrc.cjs",
    "vite.config.ts",
    "vitest.config.ts",
    "lint-staged.config.js",
    "video-rtc.js",
  ],
  rules: {
    "@typescript-eslint/no-non-null-assertion": "off",
    "@typescript-eslint/no-explicit-any": "off",
    "@typescript-eslint/no-unused-vars": [
      "error",
      {
        vars: "all",
        varsIgnorePattern: "^_",
        args: "after-used",
        argsIgnorePattern: "^_",
        ignoreRestSiblings: true,
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
  },
});
