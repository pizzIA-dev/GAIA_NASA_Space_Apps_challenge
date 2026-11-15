// Sin "use client": lo usa el layout del servidor.
export const THEME_KEY = "ets-theme";

/** Script en <head> para aplicar el tema guardado antes del primer pintado (evita parpadeo). */
export const THEME_BOOT = `try{var t=localStorage.getItem("${THEME_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;
