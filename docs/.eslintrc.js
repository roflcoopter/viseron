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
  rules: {
    "import/extensions": "off",
  },
};
