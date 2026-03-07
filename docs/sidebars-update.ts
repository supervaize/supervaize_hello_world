/**
 * SIDEBARS.TS UPDATE for supervaize-doc
 *
 * Replace the existing skillsCookbookSidebar section in sidebars.ts with this:
 */

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

/**
 * FILE PLACEMENT:
 *
 * Copy docs/claude-code-skill.mdx to:
 *   supervaize-doc/docs/skills-cookbook/claude-code-skill.mdx
 *
 * Then apply the sidebar update above to:
 *   supervaize-doc/sidebars.ts
 */
