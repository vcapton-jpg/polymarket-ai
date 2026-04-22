/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base API prefix, e.g. `http://localhost:8001/api` or leave unset to use `/api` (Vite proxy). */
  readonly VITE_API_URL?: string
  /** "1" = force the bundled MOCK_* datasets instead of hitting the API. Dev only. */
  readonly VITE_USE_MOCKS?: string
  /** Google OAuth client id for the "Continue with Google" button. */
  readonly VITE_GOOGLE_CLIENT_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module "*.css" {
  const content: { [className: string]: string }
  export default content
}