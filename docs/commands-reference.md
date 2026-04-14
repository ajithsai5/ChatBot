# Commands Reference

Quick reference for all available BMad skills, WDS skills, Claude Code skills, and built-in CLI commands.

---

## BMad Skills (68)

### Agents

| Command | Description |
|---------|-------------|
| `/bmad-agent-analyst` | Strategic business analyst and requirements |
| `/bmad-agent-architect` | System architect and technical design leader |
| `/bmad-agent-builder` | Builds, edits or analyzes Agent Skills |
| `/bmad-agent-dev` | Senior software engineer for story execution |
| `/bmad-agent-pm` | Product manager for PRD creation and requirements |
| `/bmad-agent-tech-writer` | Technical documentation specialist |
| `/bmad-agent-ux-designer` | UX designer and UI specialist |

### Planning & Product

| Command | Description |
|---------|-------------|
| `/bmad-product-brief` | Create or update product briefs |
| `/bmad-create-prd` | Create a PRD from scratch |
| `/bmad-edit-prd` | Edit an existing PRD |
| `/bmad-validate-prd` | Validate a PRD against standards |
| `/bmad-create-architecture` | Create architecture solution design |
| `/bmad-create-epics-and-stories` | Break requirements into epics and user stories |
| `/bmad-create-story` | Create a dedicated story file with details |
| `/bmad-create-ux-design` | Plan UX patterns and design specifications |
| `/bmad-domain-research` | Conduct domain and industry research |
| `/bmad-market-research` | Market research on competition and trends |
| `/bmad-technical-research` | Technical research on technologies |
| `/bmad-prfaq` | Working Backwards PRFAQ challenge |
| `/bmad-brainstorming` | Facilitate interactive brainstorming sessions |

### Development & Execution

| Command | Description |
|---------|-------------|
| `/bmad-dev-story` | Execute story implementation following a workflow |
| `/bmad-quick-dev` | Implements any user intent, requirement, or story |
| `/bmad-code-review` | Review code changes adversarially |
| `/bmad-correct-course` | Manage significant changes during sprint |
| `/bmad-sprint-planning` | Generate sprint status tracking from epics |
| `/bmad-sprint-status` | Summarize sprint status and surface risks |
| `/bmad-retrospective` | Post-epic review to extract lessons |
| `/bmad-check-implementation-readiness` | Validate PRD, UX, Architecture and Epics |

### Testing

| Command | Description |
|---------|-------------|
| `/bmad-tea` | Master Test Architect and Quality Advisor |
| `/bmad-teach-me-testing` | Teach testing progressively |
| `/bmad-qa-generate-e2e-tests` | Generate end-to-end automated tests |
| `/bmad-testarch-atdd` | Generate red-phase acceptance test scaffolds |
| `/bmad-testarch-automate` | Expand test automation coverage |
| `/bmad-testarch-ci` | Scaffold CI/CD quality pipeline |
| `/bmad-testarch-framework` | Initialize test framework (Playwright, etc.) |
| `/bmad-testarch-nfr` | Assess NFRs (performance, security, etc.) |
| `/bmad-testarch-test-design` | Create system/epic-level test plans |
| `/bmad-testarch-test-review` | Review test quality using best practices |
| `/bmad-testarch-trace` | Generate traceability matrix and quality gates |

### Reviews & Editorial

| Command | Description |
|---------|-------------|
| `/bmad-review-adversarial-general` | Cynical review producing findings |
| `/bmad-review-edge-case-hunter` | Walk branching paths and boundary conditions |
| `/bmad-editorial-review-prose` | Clinical copy-editor for text |
| `/bmad-editorial-review-structure` | Structural editor for cuts and reorganization |

### Creative & Innovation (CIS)

| Command | Description |
|---------|-------------|
| `/bmad-cis-agent-brainstorming-coach` | Elite brainstorming specialist |
| `/bmad-cis-agent-creative-problem-solver` | Master problem solver |
| `/bmad-cis-agent-design-thinking-coach` | Design thinking maestro |
| `/bmad-cis-agent-innovation-strategist` | Disruptive innovation oracle |
| `/bmad-cis-agent-presentation-master` | Visual communication expert |
| `/bmad-cis-agent-storyteller` | Master storyteller for narratives |
| `/bmad-cis-design-thinking` | Human-centered design processes |
| `/bmad-cis-innovation-strategy` | Identify disruption opportunities |
| `/bmad-cis-problem-solving` | Systematic problem-solving methodologies |
| `/bmad-cis-storytelling` | Craft compelling narratives |

### Utilities

| Command | Description |
|---------|-------------|
| `/bmad-help` | Analyzes state and answers questions |
| `/bmad-bmb-setup` | Sets up BMad Builder module in a project |
| `/bmad-module-builder` | Plans, creates, and validates BMad modules |
| `/bmad-workflow-builder` | Builds, converts, and analyzes workflows |
| `/bmad-advanced-elicitation` | Push the LLM to reconsider and refine |
| `/bmad-checkpoint-preview` | LLM-assisted human-in-the-loop review |
| `/bmad-distillator` | Lossless LLM-optimized compression |
| `/bmad-document-project` | Document brownfield projects for AI context |
| `/bmad-generate-project-context` | Create project-context.md with AI rules |
| `/bmad-index-docs` | Generate or update an index.md |
| `/bmad-shard-doc` | Split large markdown docs into smaller files |
| `/bmad-party-mode` | Orchestrate group discussions between agents |

---

## WDS Skills (Web Design System - 12)

| Command | Description |
|---------|-------------|
| `/wds-0-alignment-signoff` | Create alignment around your idea |
| `/wds-0-project-setup` | Project onboarding and type determination |
| `/wds-1-project-brief` | Establish project context/foundation |
| `/wds-2-trigger-mapping` | Map business goals to user psychology |
| `/wds-3-scenarios` | Create UX scenario outlines |
| `/wds-4-ux-design` | Transform ideas into visual specifications |
| `/wds-5-agentic-development` | AI-assisted development and testing |
| `/wds-6-asset-generation` | Generate visual and text assets |
| `/wds-7-design-system` | Create, import, and maintain design systems |
| `/wds-8-product-evolution` | Brownfield improvements via full WDS pipeline |
| `/wds-agent-freya-ux` | Strategic UX designer |
| `/wds-agent-saga-analyst` | Strategic business analyst |

---

## Claude Code Skills

| Command | Description |
|---------|-------------|
| `/claude-api` | Build, debug, and optimize Claude API / Anthropic SDK apps |
| `/simplify` | Review changed code for reuse, quality, efficiency |
| `/loop` | Run a prompt or command on a recurring interval |
| `/schedule` | Create/manage scheduled remote agents (cron) |
| `/update-config` | Configure Claude Code settings, hooks, permissions |
| `/keybindings-help` | Customize keyboard shortcuts |

---

## Claude Code Built-in Commands

### Core

| Command | Description |
|---------|-------------|
| `/help` | Show help and available commands |
| `/exit` or `/quit` | Exit the CLI |
| `/clear` or `/reset` or `/new` | Clear conversation history and free context |
| `/compact [instructions]` | Compact conversation with optional focus |
| `/model [model]` | Select or change the AI model |
| `/fast [on|off]` | Toggle fast mode |
| `/effort [low|medium|high|max|auto]` | Set model effort level |
| `/init` | Initialize project with a CLAUDE.md |

### Session & Context

| Command | Description |
|---------|-------------|
| `/resume` or `/continue` | Resume a previous conversation |
| `/rename [name]` | Rename the current session |
| `/branch` or `/fork` | Branch the current conversation |
| `/rewind` or `/checkpoint` | Rewind conversation/code to a previous point |
| `/export [filename]` | Export conversation as plain text |
| `/copy [N]` | Copy last assistant response to clipboard |
| `/context` | Visualize current context usage as a grid |
| `/add-dir <path>` | Add a working directory for the session |
| `/btw <question>` | Quick side question without polluting context |

### Usage & Cost

| Command | Description |
|---------|-------------|
| `/cost` | Show token usage statistics |
| `/usage` | Show plan limits and rate limit status |
| `/stats` | Visualize daily usage, session history, model prefs |
| `/extra-usage` | Configure extra usage when rate limited |
| `/upgrade` | Open upgrade page |

### Account & Auth

| Command | Description |
|---------|-------------|
| `/login` | Sign in to Anthropic |
| `/logout` | Sign out |
| `/setup-bedrock` | Configure Amazon Bedrock |
| `/setup-vertex` | Configure Google Vertex AI |

### Settings & Config

| Command | Description |
|---------|-------------|
| `/config` or `/settings` | Open Settings interface |
| `/permissions` or `/allowed-tools` | Manage tool permissions |
| `/privacy-settings` | View/update privacy settings |
| `/hooks` | View hook configurations |
| `/sandbox` | Toggle sandbox mode |
| `/memory` | Edit CLAUDE.md memory files |
| `/keybindings` | Open keybindings config |
| `/statusline` | Configure status line |
| `/theme` | Change color theme |
| `/color [color]` | Set prompt bar color |
| `/terminal-setup` | Configure terminal keybindings |
| `/voice` | Toggle push-to-talk voice dictation |

### Tools & Integrations

| Command | Description |
|---------|-------------|
| `/mcp` | Manage MCP server connections |
| `/ide` | Manage IDE integrations |
| `/plugin` | Manage plugins |
| `/reload-plugins` | Reload active plugins |
| `/agents` | Manage agent configurations |
| `/skills` | List available skills |
| `/tasks` or `/bashes` | List and manage background tasks |
| `/chrome` | Configure Claude in Chrome |

### Git & Code

| Command | Description |
|---------|-------------|
| `/diff` | Interactive diff viewer for uncommitted changes |
| `/security-review` | Analyze pending changes for vulnerabilities |
| `/install-github-app` | Set up Claude GitHub Actions app |

### Remote & Web

| Command | Description |
|---------|-------------|
| `/desktop` or `/app` | Continue session in Desktop app |
| `/remote-control` or `/rc` | Make session available for remote control |
| `/remote-env` | Configure default remote environment |
| `/teleport` or `/tp` | Pull a web session into terminal |
| `/web-setup` | Connect GitHub to Claude Code on web |
| `/mobile` or `/ios` or `/android` | QR code for mobile app |

### Misc

| Command | Description |
|---------|-------------|
| `/doctor` | Diagnose installation and settings |
| `/feedback` or `/bug` | Submit feedback |
| `/release-notes` | View changelog |
| `/insights` | Analyze your Claude Code sessions |
| `/powerup` | Learn features through quick lessons |
| `/team-onboarding` | Generate team onboarding guide |
| `/plan [description]` | Enter plan mode |
| `/ultraplan <prompt>` | Draft, review, then execute a plan |
| `/passes` | Share a free week with friends |
| `/stickers` | Order Claude Code stickers |
