/**
 * SIDEBARS.TS UPDATES for supervaize-doc
 *
 * Two sections need updating in sidebars.ts:
 * 1. skillsCookbookSidebar — add the skill architecture page
 * 2. integrationsSidebar — add the Claude Code integration page
 */

// ============================================================
// UPDATE 1: skillsCookbookSidebar
// ============================================================

// Before (current):
//
//   skillsCookbookSidebar: [
//     {
//       type: "doc",
//       id: "skills-cookbook/intro",
//     },
//   ],

// After (updated):
//
//   skillsCookbookSidebar: [
//     {
//       type: "doc",
//       id: "skills-cookbook/intro",
//     },
//     {
//       type: "category",
//       label: "Claude Code Skills",
//       collapsed: false,
//       items: [
//         {
//           type: "doc",
//           id: "skills-cookbook/claude-code-skill",
//           label: "Supervaizer Integration Skill",
//         },
//       ],
//     },
//   ],

// ============================================================
// UPDATE 2: integrationsSidebar
// ============================================================

// Before (current):
//
//   integrationsSidebar: [
//     {
//       type: "doc",
//       id: "integrations/intro",
//     },
//     {
//       type: "doc",
//       id: "integrations/n8n-integration",
//     },
//   ],

// After (updated):
//
//   integrationsSidebar: [
//     {
//       type: "doc",
//       id: "integrations/intro",
//     },
//     {
//       type: "doc",
//       id: "integrations/n8n-integration",
//     },
//     {
//       type: "doc",
//       id: "integrations/claude-code-integration",
//       label: "Claude Code Integration",
//     },
//   ],

/**
 * FILE PLACEMENT:
 *
 * Copy these files from this repo to supervaize-doc:
 *
 *   docs/claude-code-skill.mdx
 *     → supervaize-doc/docs/skills-cookbook/claude-code-skill.mdx
 *
 *   docs/claude-code-integration.mdx
 *     → supervaize-doc/docs/integrations/claude-code-integration.mdx
 *
 * Then apply both sidebar updates above to:
 *   supervaize-doc/sidebars.ts
 */
