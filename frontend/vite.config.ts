import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { CodeInspectorPlugin } from "@rdservices/aime-code-inspector";

export default defineConfig({
  plugins: [
    react(),
    // IMPORTANT: DO NOT REMOVE THIS!
    CodeInspectorPlugin({
      bundler: "vite",
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
