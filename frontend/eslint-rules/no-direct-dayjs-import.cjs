/**
 * Custom ESLint rule to discourage direct dayjs imports
 * and encourage using timezone-aware helpers from lib/helpers/dates.ts
 */
module.exports = {
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Discourage direct dayjs default imports, use helpers from lib/helpers/dates.ts instead",
      category: "Best Practices",
      recommended: false,
    },
    messages: {
      noDayjsImport:
        "Avoid importing the default 'dayjs' export. Use the timezone-aware helper functions from 'lib/helpers/dates.ts' instead.",
    },
    schema: [],
  },

  create(context) {
    return {
      ImportDeclaration(node) {
        const importSource = node.source.value;

        // Only check imports from 'dayjs'
        if (importSource !== "dayjs") {
          return;
        }

        // Check if this import has a default import (import dayjs from "dayjs")
        const hasDefaultImport = node.specifiers.some(
          (specifier) => specifier.type === "ImportDefaultSpecifier",
        );

        // Check if this import has namespace import (import * as dayjs from "dayjs")
        const hasNamespaceImport = node.specifiers.some(
          (specifier) => specifier.type === "ImportNamespaceSpecifier",
        );

        // Report if there's a default or namespace import
        // Allow named imports like { Dayjs } or type imports
        if (hasDefaultImport || hasNamespaceImport) {
          context.report({
            node,
            messageId: "noDayjsImport",
          });
        }
      },
    };
  },
};
