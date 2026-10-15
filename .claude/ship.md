# Ship profile: supervaize_hello_world
- Branches: single branch `main`; changes land through a PR from a GitButler branch
- Command: bump `AGENT_VERSION` in `supervaizer_control.py` and `uv version X.Y` (same value), PR, merge, `but pull`, then `just deploy`
- Merge rule: single-branch (merge commits used so far, `gh pr merge --merge`)
- Release notes: none
- Deploys to: Vercel project `supervaize_hello_world`, triggered manually by `just deploy` (tags `vX.Y` on origin/main, pushes the tag, runs `vercel --prod`); no Git integration. `just vercel_redeploy` redeploys without a tag.
- Live check: `https://supervaizehelloworld.vercel.app/api/context` returns `agent_version` = new version; `/.well-known/health` status `operational`; `/.well-known/agents/v<version>/hello-world-ai-agent_agent.json` returns 200; home page shows "Agent version X.Y"
- Back-merge: none
## Known failures
| Symptom | Fix |
|---|---|
| `gh pr ...` says "Could not resolve to a PullRequest" | local remote is named `alain-sv`; pass `--repo supervaize/supervaize_hello_world` |
| `vercel whoami` hangs on a device-login prompt | auth expired; run `vercel login` in a visible terminal tab and approve the code |
| `just deploy`: "Working tree differs from origin/main" | merge the release PR and run `but pull` first |
| `just deploy`: "AGENT_VERSION ... is not X.Y" | set `AGENT_VERSION` in `supervaizer_control.py` to the pyproject version |
| 500 FUNCTION_INVOCATION_FAILED after deploy | `vercel logs <deployment-url>` while hitting a route; usually an import error in `main.py` |
| `curl` refused in Bash by the context-mode hook | verify with ctx_execute (python urllib) |
