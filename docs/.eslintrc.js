module.exports = {
  plugins: ["@docusaurus"],
  ignorePatterns: ["src/pages/components-explorer/components/**/config.json"],
  overrides: [
    {
      files: ["*.ts", "*.tsx"],
      extends: [
        "airbnb-base",
        "airbnb-typescript/base",
        "plugin:@docusaurus/recommended",
        "plugin:@typescript-eslint/recommended",
        "plugin:import/errors",
        "plugin:import/warnings",
        "plugin:import/typescript",
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
        "import/no-unresolved": [
          2,
          { ignore: ["^@theme", "^@docusaurus", "^@site"] },
        ],
      },
    },
    {
      files: ["**/*.md?(x)"],
      extends: [
        "plugin:@docusaurus/recommended",
        "plugin:mdx/recommended",
        "prettier",
      ],
      parser: "eslint-mdx",
      parserOptions: {
        markdownExtensions: ["*.md, *.mdx"],
      },
      settings: {
        "mdx/code-blocks": true,
        "mdx/remark": true,
      },
    },
  ],
};
