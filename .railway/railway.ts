// coopstorage's slice of the shared `resourceful-beauty` Railway project.
// As a named partial it owns only what it declares; locker, CoopPlatform and job-search own their own services.
// Secrets are `preserve()`: their values are set in Railway and never live in this file.
import { defineRailway, preserve, project, service } from "railway/iac";

export const partial = "coopstorage";

export default defineRailway(() => {
  const web = service("coopstorage-web", {
    // No source: CD (.github/workflows/cd.yml) deploys with `railway up` after each release.
    // `source: empty()` is equivalent but leaves a permanent plan diff, since Railway doesn't store it.
    build: { builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    healthcheck: "/health",
    // A correctness constraint, not cost: v1 storage and the SSE event bus are in-process.
    replicas: 1,
    env: {
      // Pinned so the generated domain's target port always matches what uvicorn binds.
      PORT: "8080",
      ALLOWED_EMAILS: "tyler.tj.burns@gmail.com",
      GOOGLE_CLIENT_ID: preserve(),
      GOOGLE_CLIENT_SECRET: preserve(),
      SESSION_SECRET: preserve(),
      // Set by CD on every deploy; /health reports it.
      COOPSTORAGE_BUILD_VERSION: preserve(),
    },
  });

  return project("resourceful-beauty", { resources: [web] });
});
