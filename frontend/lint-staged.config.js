module.exports = {
  "src/**/*.{js,jsx,ts,tsx,json,css,scss,md}": [
    "eslint --fix",
    "prettier --write",
  ],
  "src/**/*.{ts,tsx}": () => "tsc -p tsconfig.json --noEmit",
};
