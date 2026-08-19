const { defineConfig, globalIgnores } = require("eslint/config");
const { configs } = require("eslint-config-airbnb-extended/legacy");
const eslintConfigPrettier = require("eslint-config-prettier/flat");

const docusaurus = require("@docusaurus/eslint-plugin");
const mdx = require("eslint-plugin-mdx");
const react = require("eslint-plugin-react");
const tsParser = require("@typescript-eslint/parser");
const tsEslintPlugin = require("@typescript-eslint/eslint-plugin");

module.exports = defineConfig([
  globalIgnores([
    "**/eslint.config.cjs",
    "**/.docusaurus/**",
    "**/build/**",
    "src/pages/components-explorer/components/**/config.json",
  ]),

  {
    files: ["**/*.{ts,tsx}"],

    extends: [
      ...configs.base.legacy,
      ...configs.base.recommended,
      ...configs.base.typescript,
      ...tsEslintPlugin.configs["flat/recommended"],
    ],

    plugins: {
      "@docusaurus": docusaurus,
    },

    languageOptions: {
      parser: tsParser,
      ecmaVersion: 2020,
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: { modules: true },
        tsconfigRootDir: __dirname,
      },
    },

    rules: {
      ...docusaurus.configs.recommended.rules,

      "import/extensions": "off",
      "import/no-unresolved": [
        2,
        { ignore: ["^@theme", "^@docusaurus", "^@site"] },
      ],
    },
  },

  {
    ...mdx.flat,
    files: ["**/*.{md,mdx}"],
    plugins: {
      ...mdx.flat.plugins,
      "@docusaurus": docusaurus,
      react,
    },
    rules: {
      ...mdx.flat.rules,
      ...docusaurus.configs.recommended.rules,
    },
  },
  {
    ...mdx.flatCodeBlocks,
    rules: {
      ...mdx.flatCodeBlocks.rules,
    },
  },

  eslintConfigPrettier,
]);
