export default {
  "{src,tests}/**/*.{js,jsx,ts,tsx,json,css,scss,md}": [
    "eslint --fix",
    "prettier --write",
  ],
  "{src,tests}/**/*.{ts,tsx}": () => "tsc -p tsconfig.json --noEmit",
};
