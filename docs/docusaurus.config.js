// @ts-check
// Note: type annotations allow type checking and IDEs autocompletion

const lightCodeTheme = require("prism-react-renderer/themes/github");
const darkCodeTheme = require("prism-react-renderer/themes/dracula");

const PROJECT = "Viseron";
const URL = "https://viseron.netlify.app";

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: PROJECT,
  tagline: "A modular, self-hosted, local only NVR.",
  url: URL,
  baseUrl: "/",
  onBrokenLinks: "throw",
  onBrokenMarkdownLinks: "warn",
  favicon: "img/favicon.ico",
  organizationName: "roflcoopter",
  projectName: PROJECT.toLowerCase(),

  presets: [
    [
      "classic",
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: require.resolve("./sidebars.js"),
          editUrl: "https://github.com/roflcooter/viseron/edit/master/",
        },
        theme: {
          customCss: require.resolve("./src/css/custom.css"),
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      navbar: {
        title: PROJECT,
        logo: {
          alt: `${PROJECT} Logo`,
          src: "img/viseron-logo.svg",
        },
        items: [
          {
            type: "doc",
            docId: "documentation",
            position: "left",
            label: "Documentation",
          },
          {
            type: "doc",
            docId: "contributing",
            position: "left",
            label: "Contributing",
          },
          {
            title: "Components",
            to: "components-explorer",
            label: "Components",
            position: "left",
          },
          {
            href: "https://github.com/roflcoopter/viseron",
            label: "GitHub",
            position: "right",
          },
        ],
      },
      footer: {
        logo: {
          alt: "Viseron Logo",
          src: "img/viseron-logo.svg",
          href: URL,
          width: 130,
          height: 130,
        },
        style: "dark",
        links: [
          {
            title: "Docs",
            items: [
              {
                label: "Documentation",
                to: "/docs/documentation",
              },
              {
                label: "Contributing",
                to: "/docs/contributing",
              },
            ],
          },
          {
            title: "Community",
            items: [
              {
                label: "GitHub",
                href: "https://github.com/roflcooter/viseron",
              },
            ],
          },
          {
            title: "Support Viseron",
            items: [
              {
                label: "GitHub Sponsors",
                href: "https://github.com/sponsors/roflcoopter",
              },
              {
                label: "Buymeacoffe",
                href: "https://www.buymeacoffee.com/roflcoopter",
              },
            ],
          },
          {
            title: "Thanks",
            items: [
              {
                label: "unDraw for providing free images",
                href: "https://undraw.co/",
              },
              {
                html: `
                    <a href="https://www.netlify.com" target="_blank" rel="noreferrer noopener" aria-label="Deploys by Netlify">
                      <img src="https://www.netlify.com/img/global/badges/netlify-color-accent.svg" alt="Deploys by Netlify" width="114" height="51" />
                    </a>
                  `,
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} ${PROJECT}, Inc. Built with Docusaurus.`,
      },
      prism: {
        theme: lightCodeTheme,
        darkTheme: darkCodeTheme,
      },
    }),
  themes: [
    [
      require.resolve("@easyops-cn/docusaurus-search-local"),
      {
        hashed: true,
        indexDocs: true,
        indexBlog: false,
        highlightSearchTermsOnTargetPage: true,
      },
    ],
  ],
  plugins: ["@docusaurus/plugin-ideal-image"],
};

module.exports = config;
