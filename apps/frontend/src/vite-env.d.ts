/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BACKEND_URL?: string
  readonly VITE_API_MOCKING?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
