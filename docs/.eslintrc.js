module.exports = {
  plugins: ["@docusaurus"],
  extends: [
    "airbnb-base",
    "airbnb-typescript/base",
    "plugin:@docusaurus/recommended",
    "plugin:@typescript-eslint/recommended",
    "prettier",
  ],
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
  ignorePatterns: ["src/pages/components-explorer/components/**/config.json"],
  rules: {
    "import/extensions": "off",
  },
};
