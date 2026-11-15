# Registro de skills del agente (plan §18.2)

Skills **preinstaladas por el usuario** antes de la sesión 1 (ver `skills-lock.json` y `.agents/skills/`).
No fueron instaladas por el agente; su auditoría formal (scripts, permisos, licencia) está **pendiente**.

| Skill | Origen | Uso previsto | Auditoría |
|---|---|---|---|
| frontend-design | anthropics/skills | F1 UI editorial | ✅ 2026-11-14: solo instrucciones (SKILL.md + LICENSE), sin scripts. **Usada** como guía de dirección visual |
| vercel-react-best-practices | vercel-labs/agent-skills | F1/F4 Next.js | pendiente |
| python-best-practices | alleneubank/claude-code | backend | pendiente |
| python-performance-optimization | wshobson/agents | backend | pendiente |
| scientific-visualization | K-Dense-AI/scientific-agent-skills | gráficos científicos | pendiente (incluye scripts) |
| scientific-toolkit-skill | zLanqing/codex-claude-academic-skills | estadística | pendiente |
| analytics-data-analysis | Mindrally/skills | análisis | pendiente |
| vercel-react-native-skills | vercel-labs/agent-skills | no aplica al MVP web | descartar |
| ui-ux-pro-max | sin entrada en lock | checklist UX/a11y | ✅ 2026-11-14: scripts Python solo leen CSV locales (sin red, subprocess ni eval); `--persist` escribe MASTER.md. **Usada** solo como checklist, sin persistir |
| obsidian-markdown | sin entrada en lock | notas del vault | ✅ 2026-11-15: solo instrucciones (SKILL.md + referencias), sin scripts. **Usada** para las notas del vault (propiedades, wikilinks, callouts, tareas) |
| obsidian-archive | sin entrada en lock | notas de avance en el vault | ✅ 2026-11-15: solo instrucciones. **Usada** (tags `proyecto/gaia`, `estado/…`, `ia/contexto`, `ultimo-avance`); su servidor MCP `obsidian-vault` no está conectado → se escribe con herramientas de archivo |
| cybersecurity-analyst, find-skills, myskillcommitter | sin entrada en lock | varios | pendiente |
| sql-code-review | aportada por el usuario (raíz del repo, ignorada en local vía `.git/info/exclude`) | revisión SQL cuando se añada PostgreSQL/PostGIS | solo instrucciones (SKILL.md, 301 líneas), sin scripts; usar al diseñar la capa de BD |

Ninguna skill es dependencia runtime del producto.
