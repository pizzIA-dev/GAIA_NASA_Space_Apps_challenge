---
name: obsidian-archive
description: Resume el estado actual de la conversación o el desarrollo y guarda una nota de contexto estructurada directamente en el vault de Obsidian conectado por MCP. Úsalo cuando el usuario pida documentar el progreso, archivar la sesión o crear una nota de lo avanzado hasta el momento.
---

A partir de ahora, cuando se invoque esta habilidad, debes consolidar el conocimiento del chat siguiendo estos pasos:

1. **Recopilar información:** Extrae las decisiones de arquitectura tomadas, los problemas resueltos (como el estado del embed de Twitch) y las tareas pendientes.
2. **Estructurar la nota:** Crea un archivo Markdown limpio. En la parte superior, incluye propiedades YAML básicas (Properties):
   ---
   tags: [proyecto/proyecto1, estado/desarrollo, ia/contexto]
   ultimo-avance: {{current_date}}
   ---
3. **Escribir el contenido:** Usa títulos claros, bloques de código para fragmentos lógicos importantes y una lista de siguientes pasos.
4. **Genera conexiones si son necesarias** Usa las conexiones para enlazar con otras notas del vault si necessario, con el fin de para una mejor organización y recuperación de información.
4. **Guardar en Obsidian:** Utiliza la herramienta del servidor MCP `obsidian-vault` para escribir el archivo directamente en la carpeta de destino utilizando un nombre descriptivo (ej: `Avance-Embed-Twitch.md`). Informa al usuario cuando la nota se haya creado con éxito.
