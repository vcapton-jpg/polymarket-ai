/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_GOOGLE_CLIENT_ID?: string
}

declare module "*.css" {
  const content: { [className: string]: string }
  export default content
}