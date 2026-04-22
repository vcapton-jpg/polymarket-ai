/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base API prefix, e.g. `http://localhost:8001/api` or leave unset to use `/api` (Vite proxy). */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module "*.css" {
  const content: { [className: string]: string }
  export default content
}