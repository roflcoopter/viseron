import type { Config } from "@docusaurus/types";
import type * as Preset from "@docusaurus/preset-classic";
import { themes } from "prism-react-renderer";

const lightCodeTheme = themes.github;
const darkCodeTheme = themes.dracula;

const PROJECT = "Viseron";
const SITE_URL = "https://viseron.netlify.app";

const config: Config = {
  title: PROJECT,
  tagline: "Self-hosted, local only NVR and AI Computer Vision software.",
  url: SITE_URL,
  baseUrl: "/",
  onBrokenLinks: "throw",
  onBrokenMarkdownLinks: "warn",
  favicon: "img/favicon.ico",
  organizationName: "roflcoopter",
  projectName: PROJECT.toLowerCase(),

  presets: [
    [
      "classic",
      {
        docs: {
          sidebarPath: require.resolve("./sidebars.js"),
          editUrl: "https://github.com/roflcoopter/viseron/edit/master/",
        },
        theme: {
          customCss: require.resolve("./src/css/custom.css"),
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
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
          title: "Components",
          to: "components-explorer",
          label: "Components",
          position: "left",
        },
        
        {
          type: "doc",
          docId: "contributing",
          position: "left",
          label: "Contributing",
        },
        {
          type: "doc",
          docId: "developers",
          position: "left",
          label: "Developers",
        },
        {
          href: "https://hub.docker.com/r/roflcoopter/viseron/tags",
          label: "Docker Hub",
          position: "right",
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
        href: SITE_URL,
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
              href: "https://github.com/roflcoopter/viseron",
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
  } satisfies Preset.ThemeConfig,
  themes: [
    [
      require.resolve("@easyops-cn/docusaurus-search-local"),
      {
        hashed: true,
        indexDocs: true,
        indexPages: true,
        indexBlog: false,
        highlightSearchTermsOnTargetPage: true,
      },
    ],
  ],
  plugins: ["@docusaurus/plugin-ideal-image"],
  clientModules: [require.resolve("./src/lib/injectVersion.ts")],
};

export default config;
